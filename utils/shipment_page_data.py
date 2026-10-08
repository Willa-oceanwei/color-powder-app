"""Bounded session-local read cache for shipment page interactions."""

from copy import deepcopy
from time import monotonic


def cached_read(config, state, key, loader, *, ttl=30):
    cache = state.setdefault("shipment_page_cache", {})
    identity = (repr(config), key)
    now = monotonic()
    entry = cache.get(identity)
    if entry is not None and now - entry[0] < ttl:
        return deepcopy(entry[1])
    value = loader()
    cache.pop(identity, None)
    while len(cache) >= 32:
        cache.pop(next(iter(cache)))
    cache[identity] = (now, deepcopy(value))
    return value


def clear_reads(state):
    state.pop("shipment_page_cache", None)
    state.pop("shipment_read_cache", None)
