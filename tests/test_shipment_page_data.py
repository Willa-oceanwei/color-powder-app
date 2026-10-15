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
