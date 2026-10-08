import pytest

from utils import shipment_page_data as data


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
