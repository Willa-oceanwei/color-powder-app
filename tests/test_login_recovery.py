from pathlib import Path
import shutil
import subprocess

import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def login_app(token=None, fail_database=False):
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    source = source.split('# ======== \U0001f510 簡易登入驗證區 ========', 1)[1]
    source = source.split("# Backward-compatible name", 1)[0]
    source = source.replace('st.secrets["APP_PASSWORD"]', repr("test-password"))
    source = source.replace('st.secrets.get("REMEMBER_LOGIN_HOURS", 4)', '4')
    script = f'''import sys
sys.path.insert(0, {str(ROOT)!r})
import streamlit as st
import time
import logging
st.session_state["main_runs"] = st.session_state.get("main_runs", 0) + 1
from utils.persistent_auth import create_remember_token, validate_remember_token
from utils.database import DatabaseStartupError, SCHEMA_VERSION
APP_RUN_STARTED_AT = time.perf_counter()
PERFORMANCE_LOGGER = logging.getLogger("login-test")
def log_performance(*args, **kwargs): pass
def _persistent_auth_storage(**kwargs): return st.session_state.get("test_token")
def secret_presence_from_secrets(secrets): return {{}}
def database_config_from_secrets(secrets):
    from types import SimpleNamespace
    return SimpleNamespace(backend="turso")
def _initialize_database_once(*args):
    st.session_state["database_attempts"] = st.session_state.get("database_attempts", 0) + 1
    if st.session_state.get("fail_database"):
        raise DatabaseStartupError("private connection detail")
    return "turso", "healthy"
''' + source + '\nst.success("Ready")\n'
    app = AppTest.from_string(script)
    app.session_state["test_token"] = token
    app.session_state["fail_database"] = fail_database
    return app.run(timeout=20)


@pytest.mark.parametrize("token", [None, "__browser_token_loading__"])
def test_explicit_login_works_without_browser_storage(token):
    app = login_app(token)
    assert not app.exception
    assert "database_attempts" not in app.session_state
    app.text_input(key="login_password").set_value("wrong")
    next(button for button in app.button if button.label == "登入").click().run()
    assert not app.session_state["authenticated"] and app.error
    assert "database_attempts" not in app.session_state
    app.text_input(key="login_password").set_value("test-password")
    next(button for button in app.button if button.label == "登入").click().run()
    assert not app.exception and app.session_state["authenticated"]
    assert app.session_state["database_attempts"] == 1
    assert app.session_state["main_runs"] == 3
    assert app.success[0].value == "Ready"


def test_database_failure_preserves_authentication_and_can_retry():
    app = login_app(fail_database=True)
    app.text_input(key="login_password").set_value("test-password")
    next(button for button in app.button if button.label == "登入").click().run()
    assert not app.exception and app.session_state["authenticated"]
    assert app.session_state["database_attempts"] == 1
    assert "private connection detail" not in str(app.error)
    assert app.button(key="logout_database_startup")
    app.session_state["fail_database"] = False
    app.button(key="retry_database_startup").click().run()
    assert not app.exception and app.success[0].value == "Ready"
    assert app.session_state["database_attempts"] == 2


def test_browser_storage_reports_once_but_still_handles_logout():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to exercise the browser component")
    script = r'''
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const html = fs.readFileSync(process.argv[1], "utf8");
const messages = [], listeners = {}, timers = [], storage = new Map();
const window = {
  localStorage: {getItem: k => storage.get(k) ?? null, setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)},
  parent: {postMessage: message => messages.push(message)},
  addEventListener: (type, fn) => listeners[type] = fn,
  setTimeout: fn => timers.push(fn),
};
vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], {window, document: {}});
const render = args => listeners.message({data: {type: "streamlit:render", args}});
const values = () => messages.filter(m => m.type === "streamlit:setComponentValue").map(m => m.value);
render({}); render({}); render({}); timers[0]();
assert.deepEqual(values(), [null]);
render({token: "signed-token", authenticated: true});
assert.equal(storage.get("color_powder_remember"), "signed-token");
render({authenticated: true});
assert.deepEqual(values(), [null]);
render({clear: true});
assert.equal(storage.size, 0);
assert.deepEqual(values(), [null, "__browser_token_cleared__"]);
render({});
assert.equal(values().length, 2);
'''
    result = subprocess.run([node, "-e", script, str(ROOT / "components/persistent_auth/index.html")],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_customer_ranking_read_error_does_not_crash_page(monkeypatch):
    import utils.receivable_ui as ui

    def unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(ui, "build_statements", unavailable)
    app = AppTest.from_string(f'''import sys
sys.path.insert(0, {str(ROOT)!r})
from utils.receivable_ui import render_customer_ranking
render_customer_ranking(None)
''').run(timeout=20)
    app.session_state["ranking_statements"] = [{"stale": True}]
    next(button for button in app.button if button.label == "查詢").click().run()
    assert not app.exception and app.error
    assert "ranking_statements" not in app.session_state
