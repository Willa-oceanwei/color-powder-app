from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Barrier, Event

import pytest

from utils import database, read_cache
from utils.customer_display import CustomerDisplay
from utils.customer_repository import CustomerInput, create_customer, list_customers, update_customer
from utils.database import DatabaseConfig, connect_from_config, initialize_database


@pytest.fixture
def remote(tmp_path, monkeypatch):
    path = tmp_path / 'remote.db'
    initialize_database(path)
    config = DatabaseConfig('turso', None, str(path), 'test-token')
    connections = []

    def connect(config):
        connections.append(config)
        conn = sqlite3.connect(config.turso_database_url)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(database, '_connect_turso', connect)
    read_cache.invalidate_read_cache(config)
    return config, connections


def test_repeated_navigation_reuses_reads_and_keeps_caller_mutations_private(remote):
    config, connections = remote
    create_customer(config, CustomerInput('C01', 'Full name', short_name='Short'))
    connections.clear()
    first = list_customers(config)
    first[0]['name'] = 'UI changed a copy'
    assert list_customers(config)[0]['name'] == 'Full name'
    assert list_customers(config, include_inactive=False)[0]['name'] == 'Full name'
    assert len(connections) == 1
    # Filter variants never share a snapshot accidentally.
    list_customers(config, include_inactive=True)
    assert len(connections) == 2


def test_committed_save_immediately_refreshes_lists_and_customer_labels(remote):
    config, connections = remote
    create_customer(config, CustomerInput('C01', 'Full name', short_name='Short'))
    assert list_customers(config)[0]['short_name'] == 'Short'
    assert CustomerDisplay(config).name('Full name') == 'Short'
    count = len(connections)
    assert CustomerDisplay(config).name('Full name') == 'Short'
    assert len(connections) == count
    update_customer(config, CustomerInput('C01', 'Full name', short_name='New short'))
    assert list_customers(config)[0]['short_name'] == 'New short'
    assert CustomerDisplay(config).name('Full name') == 'New short'


def test_external_changes_expire_and_explicit_reload_bypasses_ttl(remote, monkeypatch):
    config, connections = remote
    clock = [100.0]
    monkeypatch.setattr(read_cache, 'monotonic', lambda: clock[0])
    create_customer(config, CustomerInput('C01', 'Original'))
    assert list_customers(config)[0]['name'] == 'Original'
    # Simulates a different process updating Turso, outside this worker.
    with sqlite3.connect(config.turso_database_url) as conn:
        conn.execute("UPDATE customers SET name='External' WHERE customer_id='C01'")
    assert list_customers(config)[0]['name'] == 'Original'
    clock[0] += read_cache.READ_TTL_SECONDS
    assert list_customers(config)[0]['name'] == 'External'
    count = len(connections)
    read_cache.invalidate_read_cache(config)
    list_customers(config)
    assert len(connections) == count + 1


def test_rollback_keeps_the_committed_snapshot(remote):
    config, connections = remote
    create_customer(config, CustomerInput('C01', 'Original'))
    assert list_customers(config)[0]['name'] == 'Original'
    with pytest.raises(RuntimeError):
        with connect_from_config(config) as conn:
            conn.execute("UPDATE customers SET name='Uncommitted'")
            raise RuntimeError('cancel transaction')
    count = len(connections)
    assert list_customers(config)[0]['name'] == 'Original'
    assert len(connections) == count
    with sqlite3.connect(config.turso_database_url) as conn:
        assert conn.execute('SELECT name FROM customers').fetchone()[0] == 'Original'


def test_failed_reads_are_not_cached(remote):
    config, _ = remote
    attempts = []

    @read_cache.cached_read
    def failing(config):
        attempts.append(1)
        raise RuntimeError('temporary outage')

    for _ in range(2):
        with pytest.raises(RuntimeError):
            failing(config)
    assert len(attempts) == 2


def test_concurrent_save_prevents_an_old_read_from_refilling_cache(remote):
    config, _ = remote
    entered, release = Event(), Event()
    calls = []

    @read_cache.cached_read
    def snapshot(config):
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
            return ['old']
        return ['new']

    with ThreadPoolExecutor(max_workers=1) as executor:
        old = executor.submit(snapshot, config)
        assert entered.wait(5)
        read_cache.invalidate_read_cache(config)
        release.set()
        assert old.result() == ['old']
    assert snapshot(config) == ['new']
    assert snapshot(config) == ['new']
    assert len(calls) == 2


def test_different_credentials_and_databases_do_not_share_entries(remote):
    config, _ = remote
    other = DatabaseConfig('turso', None, config.turso_database_url, 'other-token')
    calls = []

    @read_cache.cached_read
    def snapshot(config):
        calls.append(config)
        return [len(calls)]

    assert snapshot(config) == [1]
    assert snapshot(other) == [2]
    assert snapshot(config) == [1]


def test_sqlite_repository_behavior_remains_uncached(tmp_path):
    config = DatabaseConfig('sqlite', tmp_path / 'local.db')
    initialize_database(config.path)
    create_customer(config, CustomerInput('C01', 'Before'))
    assert list_customers(config)[0]['name'] == 'Before'
    with sqlite3.connect(config.path) as conn:
        conn.execute("UPDATE customers SET name='After'")
    assert list_customers(config)[0]['name'] == 'After'


def test_snapshot_count_is_bounded(remote, monkeypatch):
    config, _ = remote
    monkeypatch.setattr(read_cache, 'MAX_ENTRIES', 3)
    calls = []

    @read_cache.cached_read
    def snapshot(config, identifier):
        calls.append(identifier)
        return identifier

    for i in range(4):
        assert snapshot(config, i) == i
    assert len(read_cache._entries) <= 3
    snapshot(config, 0)
    assert calls == [0, 1, 2, 3, 0]


def test_first_page_dependencies_load_together_and_reuse_results(remote):
    config, _ = remote
    barrier = Barrier(2)
    calls = []

    @read_cache.cached_read
    def master(config, kind):
        calls.append(kind)
        barrier.wait(timeout=5)
        return [kind]

    read_cache.warm_reads([lambda: master(config, 'inventory'), lambda: master(config, 'customers')])
    assert sorted(calls) == ['customers', 'inventory']
    assert master(config, 'inventory') == ['inventory']
    assert master(config, 'customers') == ['customers']
    assert len(calls) == 2


def test_failed_warmup_leaves_normal_loader_free_to_retry(remote):
    config, _ = remote
    attempts = []

    @read_cache.cached_read
    def master(config):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError('temporary outage')
        return ['loaded']

    read_cache.warm_reads([lambda: master(config)])
    assert master(config) == ['loaded']
    assert master(config) == ['loaded']
    assert len(attempts) == 2


def test_sidebar_warmup_only_loads_selected_workspace_dependencies(remote, monkeypatch):
    from utils import navigation_data

    config, _ = remote
    reads = []
    state = {}

    class Display:
        def _load(self):
            reads.append('customer labels')

    for name in ['list_color_powders', 'list_inventory_movements',
                 'list_customer_inventory_records', 'list_recipes', 'list_production_orders']:
        monkeypatch.setattr(navigation_data, name,
                            lambda *args, _name=name, **kwargs: reads.append(_name))
    navigation_data.warm_navigation_reads(config, state, '庫存區', Display())
    assert sorted(reads) == sorted(['list_color_powders', 'list_inventory_movements',
                                   'list_customer_inventory_records', 'list_recipes',
                                   'list_production_orders', 'customer labels'])
    reads.clear()
    navigation_data.warm_navigation_reads(config, state, '庫存區', Display())
    navigation_data.warm_navigation_reads(config, state, '外部連結', Display())
    assert reads == []
    state['df_recipe'] = object()
    state['df_order'] = object()
    navigation_data.warm_navigation_reads(config, state, '庫存區', Display())
    assert 'list_recipes' not in reads and 'list_production_orders' not in reads
