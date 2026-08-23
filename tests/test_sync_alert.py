import scripts.manage_sync_alert as sync_alert


def test_failure_opens_one_deduplicated_issue(monkeypatch):
    calls = []

    def fake_request(path, *, token, method="GET", payload=None):
        calls.append((path, method, payload))
        if method == "GET":
            return []
        return {"number": 42}

    monkeypatch.setattr(sync_alert, "_request", fake_request)
    outcome = sync_alert.update_sync_alert(
        repo="owner/repo", workflow="safe sync", status="failure",
        run_url="https://example.test/run/1", token="secret",
    )

    assert outcome == "opened issue #42"
    assert calls[1][0] == "/repos/owner/repo/issues"
    assert calls[1][1] == "POST"
    assert calls[1][2]["title"] == "[Sync Alert] safe sync failed"
    assert "https://example.test/run/1" in calls[1][2]["body"]


def test_repeated_failure_comments_on_existing_issue(monkeypatch):
    calls = []

    def fake_request(path, *, token, method="GET", payload=None):
        calls.append((path, method, payload))
        if method == "GET":
            return [{"number": 7, "title": "[Sync Alert] inbound failed"}]
        return {}

    monkeypatch.setattr(sync_alert, "_request", fake_request)
    outcome = sync_alert.update_sync_alert(
        repo="owner/repo", workflow="inbound", status="failure",
        run_url="https://example.test/run/2", token="secret",
    )

    assert outcome == "updated issue #7"
    assert calls[1][0] == "/repos/owner/repo/issues/7/comments"
    assert calls[1][1] == "POST"


def test_success_resolves_existing_alert(monkeypatch):
    calls = []

    def fake_request(path, *, token, method="GET", payload=None):
        calls.append((path, method, payload))
        if method == "GET":
            return [{"number": 9, "title": "[Sync Alert] inbound failed"}]
        return {}

    monkeypatch.setattr(sync_alert, "_request", fake_request)
    outcome = sync_alert.update_sync_alert(
        repo="owner/repo", workflow="inbound", status="success",
        run_url="https://example.test/run/3", token="secret",
    )

    assert outcome == "resolved issue #9"
    assert calls[-1] == (
        "/repos/owner/repo/issues/9", "PATCH", {"state": "closed"}
    )
