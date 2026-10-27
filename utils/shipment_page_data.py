"""Bounded session-local read cache for shipment page interactions."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import logging
from time import monotonic, perf_counter


LOGGER = logging.getLogger("color_powder.performance")


@contextmanager
def shipment_timing(stage, *, read_kind="", item_count=0):
    """Log operation timing and counts, never document contents or credentials."""
    started = perf_counter()
    outcome = "interrupted"
    try:
        yield
        outcome = "ok"
    except Exception:
        outcome = "error"
        raise
    finally:
        LOGGER.warning("[PERF] stage=%s elapsed_ms=%.1f read_kind=%s item_count=%d outcome=%s diag=shipment-save-v1",
                       stage, (perf_counter() - started) * 1000, read_kind, item_count, outcome)


def timed_read(key, loader):
    kind = key[0] if isinstance(key, tuple) and key else key
    kind = kind if kind in ("records", "number-navigation", "document", "customers", "history", "all_choices") else "other"
    with shipment_timing("shipment_read", read_kind=kind):
        return loader()


def cached_read(config, state, key, loader, *, ttl=30):
    cache = state.setdefault("shipment_page_cache", {})
    identity = (repr(config), key)
    now = monotonic()
    entry = cache.get(identity)
    if entry is not None and now - entry[0] < ttl:
        return deepcopy(entry[1])
    value = timed_read(key, loader)
    cache.pop(identity, None)
    while len(cache) >= 32:
        cache.pop(next(iter(cache)))
    cache[identity] = (now, deepcopy(value))
    return value


def clear_reads(state):
    state.pop("shipment_page_cache", None)
    state.pop("shipment_read_cache", None)


def preload_edit_reads(config, state, loaders):
    """Load a draft's independent dependencies without accessing UI state in workers.

    Customers and history are fresh for every editing snapshot. Other reads can
    reuse the existing bounded page cache. Failed loads remain retryable.
    """
    cache = state.setdefault("shipment_read_cache", {})
    pending = {}
    for key, loader in loaders.items():
        identity = (repr(config), key)
        if identity in cache:
            continue
        fresh = key == "customers" or isinstance(key, tuple) and key[0] == "history"
        if not fresh:
            entry = state.get("shipment_page_cache", {}).get(identity)
            if entry is not None and monotonic() - entry[0] < 60:
                cache[identity] = deepcopy(entry[1])
                continue
        pending[key] = loader
    if not pending:
        return
    # Each loader owns its connection. Only the main thread writes session state.
    with ThreadPoolExecutor(max_workers=min(3, len(pending))) as executor:
        futures = {key: executor.submit(timed_read, key, loader)
                   for key, loader in pending.items()}
        for key, future in futures.items():
            try:
                value = future.result()
            except Exception:
                # The normal page read retains its existing error/retry behavior.
                continue
            cache[(repr(config), key)] = value

