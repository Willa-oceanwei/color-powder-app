"""Turso-first trial-color records and analysis settings."""

from __future__ import annotations

import uuid
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso

DEFAULT_TRIAL_SETTINGS = {"收費門檻百分比": "20", "最小樣本數": "10", "未採購追蹤天數": "30"}


class TrialError(RuntimeError):
    """Raised when a trial-color operation is invalid or unsafe."""


def _mapping(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(zip((column[0] for column in cursor.description), row))


def _mappings(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def trial_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "配方編號": str(entity.get("formula_code") or ""),
        "主配方編號": str(entity.get("root_formula_code") or ""),
        "客戶編號": str(entity.get("customer_id") or ""),
        "客戶名稱": str(entity.get("customer_name") or ""),
        "試色日期": str(entity.get("trial_date") or ""),
        "日期精度": str(entity.get("date_precision") or ""),
        "歷史補登": str(entity.get("historical_backfill") or ""),
        "原料": str(entity.get("material") or ""),
        "已採購": str(entity.get("purchased") or "否"),
        "採購日期": str(entity.get("purchase_date") or ""),
        "建立時間": str(entity.get("sheet_created_at") or ""),
        "更新時間": str(entity.get("sheet_updated_at") or ""),
        "_sync_id": str(entity.get("trial_id") or ""),
    }


def list_trial_records(config: DatabaseConfig, *, include_inactive: bool = False):
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(f"SELECT * FROM trial_records {where} ORDER BY trial_date,trial_id"))


def create_trial_record(config: DatabaseConfig, row: dict[str, Any]):
    formula_code = str(row.get("配方編號") or "").strip().upper()
    customer_id = str(row.get("客戶編號") or "").strip()
    trial_date = str(row.get("試色日期") or "").strip()
    material = str(row.get("原料") or "").strip()
    if not formula_code or not customer_id or not trial_date or not material:
        raise TrialError("配方編號、客戶編號、試色日期與原料皆為必填")
    trial_id = str(row.get("_sync_id") or "").strip() or f"trial-{uuid.uuid4().hex}"
    purchased = str(row.get("已採購") or "否").strip()
    purchase_date = str(row.get("採購日期") or "").strip()
    if purchased not in {"是", "否"}:
        raise TrialError("已轉單只能是『是』或『否』")
    if purchased == "是" and not purchase_date:
        raise TrialError("已轉單記錄必須填寫轉單日期")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        if conn.execute("SELECT 1 FROM trial_records WHERE formula_code=?", (formula_code,)).fetchone():
            raise TrialError(f"配方編號 {formula_code} 已存在")
        conn.execute(
            """INSERT INTO trial_records(
                   trial_id,formula_code,root_formula_code,customer_id,customer_name,trial_date,
                   date_precision,historical_backfill,material,purchased,purchase_date,
                   sheet_created_at,sheet_updated_at,source,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'app',?,?)""",
            (trial_id, formula_code, str(row.get("主配方編號") or "").strip(), customer_id,
             str(row.get("客戶名稱") or "").strip(), trial_date,
             str(row.get("日期精度") or "精確").strip(), str(row.get("歷史補登") or "否").strip(),
             material, purchased, purchase_date or None,
             str(row.get("建立時間") or "").strip() or now,
             str(row.get("更新時間") or "").strip() or now, now, now),
        )
        entity = _mapping(conn.execute("SELECT * FROM trial_records WHERE trial_id=?", (trial_id,)))
        enqueue_sheet_sync(conn, sheet_name="試色登錄", row_key=trial_id, operation="insert",
                           payload=trial_sheet_payload(entity), entity_version=1)
        return entity


def mark_trial_purchased(config: DatabaseConfig, formula_code: str, purchase_date: str):
    formula_code = str(formula_code).strip().upper()
    if not formula_code or not str(purchase_date).strip():
        raise TrialError("請填寫配方編號與轉單日期")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute(
            "SELECT * FROM trial_records WHERE formula_code=? AND lifecycle_status='active'", (formula_code,)
        ))
        if not old:
            raise TrialError("找不到該配方編號")
        version = int(old["version"]) + 1
        conn.execute(
            """UPDATE trial_records SET purchased='是',purchase_date=?,sheet_updated_at=?,
               source='app',version=?,updated_at=? WHERE trial_id=?""",
            (str(purchase_date).strip(), now, version, now, old["trial_id"]),
        )
        entity = _mapping(conn.execute("SELECT * FROM trial_records WHERE trial_id=?", (old["trial_id"],)))
        enqueue_sheet_sync(conn, sheet_name="試色登錄", row_key=old["trial_id"], operation="update",
                           payload=trial_sheet_payload(entity), entity_version=version)
        return entity


def archive_trial_record(
    config: DatabaseConfig, trial_id: str, *, reason: str = "使用者封存"
):
    """Archive a trial while retaining its auditable Turso history."""
    trial_id = str(trial_id).strip()
    reason = str(reason).strip()
    if not reason:
        raise TrialError("封存原因不可空白")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute("SELECT * FROM trial_records WHERE trial_id=?", (trial_id,)))
        if not old or old["lifecycle_status"] != "active":
            raise TrialError("找不到有效的試色記錄")
        version = int(old["version"]) + 1
        conn.execute(
            """UPDATE trial_records SET lifecycle_status='inactive',deleted_at=?,delete_reason=?,
               version=?,updated_at=? WHERE trial_id=?""",
            (now, reason, version, now, trial_id),
        )
        enqueue_sheet_sync(
            conn, sheet_name="試色登錄", row_key=trial_id, operation="delete",
            payload=None, entity_version=version,
        )


def restore_trial_record(config: DatabaseConfig, trial_id: str):
    """Restore an archived trial and requeue its Sheet copy."""
    trial_id = str(trial_id).strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute("SELECT * FROM trial_records WHERE trial_id=?", (trial_id,)))
        if not old or old["lifecycle_status"] != "inactive":
            raise TrialError("找不到已封存的試色記錄")
        version = int(old["version"]) + 1
        conn.execute(
            """UPDATE trial_records SET lifecycle_status='active',deleted_at=NULL,delete_reason=NULL,
               version=?,updated_at=? WHERE trial_id=?""",
            (version, now, trial_id),
        )
        entity = _mapping(conn.execute("SELECT * FROM trial_records WHERE trial_id=?", (trial_id,)))
        enqueue_sheet_sync(
            conn, sheet_name="試色登錄", row_key=trial_id, operation="insert",
            payload=trial_sheet_payload(entity), entity_version=version,
        )
        return entity


def get_trial_settings(config: DatabaseConfig) -> dict[str, str]:
    with connect_from_config(config) as conn:
        stored = {row[0]: str(row[1]) for row in conn.execute(
            "SELECT setting_key,setting_value FROM trial_settings"
        ).fetchall()}
    return {**DEFAULT_TRIAL_SETTINGS, **stored}


def save_trial_settings(config: DatabaseConfig, settings: dict[str, Any]) -> None:
    unknown = set(settings) - set(DEFAULT_TRIAL_SETTINGS)
    if unknown:
        raise TrialError(f"不支援的試色參數：{', '.join(sorted(unknown))}")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        for key, value in settings.items():
            conn.execute(
                """INSERT INTO trial_settings(setting_key,setting_value,updated_at) VALUES (?,?,?)
                   ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,
                   updated_at=excluded.updated_at""",
                (key, str(value), now),
            )
