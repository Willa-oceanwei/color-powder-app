from pathlib import Path

from utils.persistent_auth import create_remember_token, validate_remember_token


def test_remember_token_is_valid_until_expiry():
    token = create_remember_token("correct horse", 3600, now=1_000)

    assert validate_remember_token(token, "correct horse", now=4_599)
    assert not validate_remember_token(token, "correct horse", now=4_600)


def test_remember_token_rejects_wrong_password_and_tampering():
    token = create_remember_token("original", 3600, now=1_000)

    assert not validate_remember_token(token, "changed", now=1_001)
    assert not validate_remember_token(f"x{token}", "original", now=1_001)


def test_remember_token_rejects_malformed_values():
    assert not validate_remember_token(None, "password", now=1_000)
    assert not validate_remember_token("not-a-token", "password", now=1_000)


def test_app_defaults_to_four_hours_and_provides_logout():
    app_source = (Path(__file__).parents[1] / "app.py").read_text()
    component_source = (
        Path(__file__).parents[1] / "components" / "persistent_auth" / "index.html"
    ).read_text()

    assert 'st.secrets.get("REMEMBER_LOGIN_HOURS", 4)' in app_source
    assert "st.session_state.authenticated = True\n            st.rerun()" in app_source
    assert '"↪ 登出"' in app_source
    assert "on_click=request_logout" in app_source
    assert 'st.session_state["_clear_remember_token"] = True' in app_source
    assert "window.localStorage.setItem(STORAGE_KEY, args.token)" in component_source
    assert "window.localStorage.removeItem(STORAGE_KEY)" in component_source
    assert "Do not\n            // send the token back" in component_source
    assert "if (args.authenticated)" in component_source
    assert 'dataType: "json"' in component_source
    assert "if (!hasResponded) sendValue(null)" in component_source


def test_app_logs_non_sensitive_startup_performance_stages():
    app_source = (Path(__file__).parents[1] / "app.py").read_text()

    for stage in (
        "browser_token_wait",
        "authentication_ready",
        "database_startup",
        "application_shell",
        "menu_selected",
        "page_render",
        "total_authenticated_run",
    ):
        assert f'"{stage}"' in app_source

    assert 'logging.getLogger("color_powder.performance")' in app_source
    assert 'PERFORMANCE_LOGGER.warning("[PERF]' in app_source
    assert 'PERFORMANCE_DIAGNOSTICS_VERSION = "2026-09-outsourcing-v3"' in app_source


def test_browser_token_check_does_not_flash_a_loading_message():
    app_source = (Path(__file__).parents[1] / "app.py").read_text()

    assert 'log_performance("browser_token_wait", APP_RUN_STARTED_AT)' in app_source
    assert "正在確認登入狀態" not in app_source
