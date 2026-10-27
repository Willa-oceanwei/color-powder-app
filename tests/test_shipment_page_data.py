import pytest
from threading import Barrier, get_ident

from utils import shipment_page_data as data


def test_edit_reads_overlap_and_only_main_thread_touches_state():
    main_thread = get_ident()
    class State(dict):
        def setdefault(self, *args):
            assert get_ident() == main_thread
            return super().setdefault(*args)
        def get(self, *args):
            assert get_ident() == main_thread
            return super().get(*args)
    state = State()
    barrier = Barrier(3)
    calls = []
    def load(key):
        assert get_ident() != main_thread
        calls.append(key)
        barrier.wait(timeout=3)
        return [key]
    keys = ["customers", ("history", "C01", "2026-10-27", "S01"), "all_choices"]
    loaders = {key: lambda key=key: load(key) for key in keys}
    data.preload_edit_reads("db", state, loaders)
    assert len(calls) == 3
    assert len(state["shipment_read_cache"]) == 3
    data.preload_edit_reads("db", state, loaders)
    assert len(calls) == 3


def test_edit_preload_refreshes_prices_and_customers_but_reuses_catalog():
    state = {}
    history = ("history", "C01", "2026-10-27", "S01")
    for key in ("customers", history, "all_choices"):
        data.cached_read("db", state, key, lambda: ["old"])
    loaders = {key: lambda: ["fresh"] for key in ("customers", history, "all_choices")}
    data.preload_edit_reads("db", state, loaders)
    cache = state["shipment_read_cache"]
    assert cache[(repr("db"), "customers")] == ["fresh"]
    assert cache[(repr("db"), history)] == ["fresh"]
    assert cache[(repr("db"), "all_choices")] == ["old"]
    data.clear_reads(state)
    data.preload_edit_reads("db", state, loaders)
    assert state["shipment_read_cache"][(repr("db"), "all_choices")] == ["fresh"]


def test_failed_edit_preloads_retry_and_other_databases_are_isolated():
    state = {}
    def fail():
        raise ValueError("offline")
    data.preload_edit_reads("db", state, {"customers": fail})
    assert (repr("db"), "customers") not in state["shipment_read_cache"]
    data.preload_edit_reads("db", state, {"customers": lambda: ["one"]})
    data.preload_edit_reads("other", state, {"customers": lambda: ["two"]})
    assert state["shipment_read_cache"][(repr("db"), "customers")] == ["one"]
    assert state["shipment_read_cache"][(repr("other"), "customers")] == ["two"]


def test_session_cache_expiry_isolation_and_mutation_safety(monkeypatch):
    clock = [0]
    monkeypatch.setattr(data, "monotonic", lambda: clock[0])
    calls = []
    def load():
        calls.append(1)
        return {"items": [{"code": "R1"}]}
    state = {}
    first = data.cached_read("db", state, "doc", load)
    first["items"][0]["code"] = "EDITED"
    second = data.cached_read("db", state, "doc", load)
    assert second["items"][0]["code"] == "R1"
    second["items"].clear()
    assert data.cached_read("db", state, "doc", load)["items"]
    assert len(calls) == 1
    clock[0] = 30
    data.cached_read("db", state, "doc", load)
    data.cached_read("other-db", state, "doc", load)
    data.cached_read("db", {}, "doc", load)
    assert len(calls) == 4
    data.clear_reads(state)
    data.cached_read("db", state, "doc", load)
    assert len(calls) == 5


def test_cache_is_bounded_and_failed_reads_are_not_saved():
    state = {}
    for key in range(40):
        data.cached_read("db", state, key, lambda: [])
    assert len(state["shipment_page_cache"]) == 32
    def fail():
        raise ValueError("offline")
    with pytest.raises(ValueError):
        data.cached_read("db", state, "failed", fail)
    assert (repr("db"), "failed") not in state["shipment_page_cache"]


def test_read_timings_exclude_document_data_and_log_failures(caplog):
    state = {}
    key = ("document", "private-document-id")
    data.cached_read("private-connection", state, key, lambda: {"notes": "private-notes"})
    data.cached_read("private-connection", state, key, lambda: pytest.fail("cache hit"))
    assert len(caplog.records) == 1
    assert "stage=shipment_read" in caplog.text and "read_kind=document" in caplog.text
    assert "outcome=ok" in caplog.text
    def fail():
        raise RuntimeError("private-error-details")
    with pytest.raises(RuntimeError):
        data.cached_read("private-connection", state, ("history", "private-customer"), fail)
    assert "outcome=error" in caplog.text and "read_kind=history" in caplog.text
    assert "private-" not in caplog.text

