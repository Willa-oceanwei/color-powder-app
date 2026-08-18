"""Turso-first supplier persistence with durable Google Sheet outbox events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso


class SupplierError(RuntimeError):
    pass


class SupplierAlreadyExists(SupplierError):
    pass


class SupplierNotFound(SupplierError):
    pass


@dataclass(frozen=True)
class SupplierInput:
    supplier_id: str
    name: str
    notes: str = ""

    def normalized(self) -> "SupplierInput":
        return SupplierInput(
            supplier_id=str(self.supplier_id or "").strip(),
            name=str(self.name or "").strip(),
            notes=str(self.notes or "").strip(),
        )


def _mapping(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(zip((column[0] for column in cursor.description), row))


def _mappings(cursor) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def supplier_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "供應商編號": str(entity.get("supplier_id") or ""),
        "供應商簡稱": str(entity.get("name") or ""),
        "備註": str(entity.get("notes") or ""),
        "生命週期": str(entity.get("lifecycle_status") or "active"),
        "停用時間": str(entity.get("deleted_at") or ""),
        "停用原因": str(entity.get("delete_reason") or ""),
    }


def list_suppliers(config: DatabaseConfig, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(
            f"""SELECT supplier_id, name, notes, lifecycle_status, deleted_at, delete_reason,
                       version, updated_at, last_synced_at
                FROM suppliers {where} ORDER BY supplier_id"""
        ))


def set_supplier_active(config: DatabaseConfig, supplier_id: str, *, active: bool, reason: str = "") -> dict[str, Any]:
    """Soft-disable or restore a supplier while preserving historical references."""
    supplier_id = str(supplier_id or "").strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)))
        if existing is None:
            raise SupplierNotFound(f"找不到供應商編號 {supplier_id}")
        conn.execute(
            """UPDATE suppliers SET lifecycle_status=?, deleted_at=?, delete_reason=?,
                      version=version+1, updated_at=? WHERE supplier_id=?""",
            ("active" if active else "inactive", None if active else now,
             None if active else str(reason or "").strip(), now, supplier_id),
        )
        entity = _mapping(conn.execute("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)))
        enqueue_sheet_sync(
            conn, sheet_name="供應商管理", row_key=supplier_id,
            operation="update" if active else "delete",
            payload=supplier_sheet_payload(entity) if active else None,
            entity_version=int(entity["version"]),
        )
        return entity


def _validate(data: SupplierInput) -> SupplierInput:
    data = data.normalized()
    if not data.supplier_id:
        raise SupplierError("請輸入供應商編號")
    if not data.name:
        raise SupplierError("請輸入供應商簡稱")
    return data


def _ensure_alias_available(conn, name: str, supplier_id: str) -> None:
    owner = _mapping(conn.execute(
        "SELECT supplier_id FROM supplier_aliases WHERE alias=?", (name,)
    ))
    if owner is not None and owner["supplier_id"] != supplier_id:
        raise SupplierError(f"供應商簡稱／別名 {name} 已由 {owner['supplier_id']} 使用")


def create_supplier(config: DatabaseConfig, data: SupplierInput) -> dict[str, Any]:
    data = _validate(data)
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        if _mapping(conn.execute("SELECT supplier_id FROM suppliers WHERE supplier_id=?", (data.supplier_id,))):
            raise SupplierAlreadyExists(f"供應商編號 {data.supplier_id} 已存在")
        _ensure_alias_available(conn, data.name, data.supplier_id)
        conn.execute(
            """INSERT INTO suppliers(
                   supplier_id, name, notes, source, version, created_at, updated_at, last_synced_at,
                   sheet_row_key)
               VALUES (?, ?, ?, 'app', 1, ?, ?, NULL, ?)""",
            (data.supplier_id, data.name, data.notes, now, now, data.supplier_id),
        )
        conn.execute(
            "INSERT INTO supplier_aliases(alias, supplier_id, created_at) VALUES (?, ?, ?)",
            (data.name, data.supplier_id, now),
        )
        entity = _mapping(conn.execute("SELECT * FROM suppliers WHERE supplier_id=?", (data.supplier_id,)))
        enqueue_sheet_sync(
            conn, sheet_name="供應商管理", row_key=data.supplier_id, operation="insert",
            payload=supplier_sheet_payload(entity), entity_version=1,
        )
        return entity


def update_supplier(config: DatabaseConfig, data: SupplierInput) -> dict[str, Any]:
    data = _validate(data)
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM suppliers WHERE supplier_id=?", (data.supplier_id,)))
        if existing is None:
            raise SupplierNotFound(f"找不到供應商編號 {data.supplier_id}")
        _ensure_alias_available(conn, data.name, data.supplier_id)
        version = int(existing["version"]) + 1
        conn.execute(
            """UPDATE suppliers SET name=?, notes=?, source='app', version=?, updated_at=?
               WHERE supplier_id=?""",
            (data.name, data.notes, version, now, data.supplier_id),
        )
        conn.execute(
            "INSERT OR IGNORE INTO supplier_aliases(alias, supplier_id, created_at) VALUES (?, ?, ?)",
            (data.name, data.supplier_id, now),
        )
        entity = _mapping(conn.execute("SELECT * FROM suppliers WHERE supplier_id=?", (data.supplier_id,)))
        enqueue_sheet_sync(
            conn, sheet_name="供應商管理", row_key=data.supplier_id, operation="update",
            payload=supplier_sheet_payload(entity), entity_version=version,
        )
        return entity
