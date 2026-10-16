"""Short-lived Turso read snapshots, invalidated after committed writes.

No connections are shared between threads. Values are copied so UI dataframe
normalization cannot modify a later caller's results. Snapshots expire after
READ_TTL_SECONDS to pick up external workers; local writes invalidate at once.
"""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import wraps
from inspect import signature
from threading import RLock
from time import monotonic

READ_TTL_SECONDS = 15
MAX_ENTRIES = 128
_lock = RLock()
_entries = OrderedDict()
_generation = {}


def warm_reads(readers):
    """Load independent page dependencies together, using separate connections.

    Failures are not cached; the normal page loader remains responsible for its
    existing error UI and retry behavior.
    """
    if not readers:
        return
    with ThreadPoolExecutor(max_workers=min(6, len(readers))) as executor:
        futures = [executor.submit(reader) for reader in readers]
        for future in futures:
            try:
                future.result()
            except Exception:
                pass


def invalidate_read_cache(config):
    """Discard this database's snapshots, including any in-flight old reads."""
    with _lock:
        _generation[config] = _generation.get(config, 0) + 1
        for key in list(_entries):
            if key[0] == config:
                del _entries[key]


def cached_read(function):
    """Cache read-only repository functions; keep SQLite behavior unchanged."""
    parameters = signature(function)

    @wraps(function)
    def read(config, *args, **kwargs):
        if getattr(config, 'backend', None) != 'turso':
            return function(config, *args, **kwargs)
        bound = parameters.bind(config, *args, **kwargs)
        bound.apply_defaults()
        # These repository reads accept only scalar filter arguments.
        key = (config, function.__module__, function.__qualname__,
               tuple(bound.arguments.items()))
        with _lock:
            generation = _generation.get(config, 0)
            entry = _entries.get(key)
            if entry is not None and monotonic() - entry[0] < READ_TTL_SECONDS:
                _entries.move_to_end(key)
                return deepcopy(entry[1])
        value = function(config, *args, **kwargs)
        snapshot = deepcopy(value)
        with _lock:
            # A concurrent save must not let an older read refill the cache.
            if _generation.get(config, 0) == generation:
                _entries[key] = (monotonic(), snapshot)
                _entries.move_to_end(key)
                while len(_entries) > MAX_ENTRIES:
                    _entries.popitem(last=False)
        return value

    return read
