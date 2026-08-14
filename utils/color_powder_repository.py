"""Turso-first persistence for color powders and their Sheet outbox events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso
from .sheet_export import color_powder_sheet_payload


class ColorPowderError(RuntimeError):
    """Base error safe for the color-powder UI to present."""


class ColorPowderAlreadyExists(ColorPowderError):
    pass


class ColorPowderNotFound(ColorPowderError):
    pass


@dataclass(frozen=True)
class ColorPowderInput:
    colorpowder_id: str
    international_code: str = ""
    name: str = ""
    category: str = ""
    package: str = ""
    notes: str = ""

    def normalized(self) -> "ColorPowderInput":
        return ColorPowderInput(**{
            field: str(getattr(self, field) or "").strip()
            for field in self.__dataclass_fields__
        })


def _mapping(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _mappings(cursor) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [{key: row[key] for key in row.keys()} for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def list_color_powders(config: DatabaseConfig) -> list[dict[str, Any]]:
    """Return canonical color powders from the configured source of truth."""
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            """SELECT colorpowder_id, international_code, name, category, package,
                      notes, version, updated_at, last_synced_at
               FROM color_powders ORDER BY colorpowder_id"""
        ))


def create_color_powder(config: DatabaseConfig, data: ColorPowderInput) -> dict[str, Any]:
    """Create a powder and queue its Sheet insert in one database transaction."""
    data = data.normalized()
    if not data.colorpowder_id:
        raise ColorPowderError("請輸入色粉編號")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        if _mapping(conn.execute(
            "SELECT colorpowder_id FROM color_powders WHERE colorpowder_id=?",
            (data.colorpowder_id,),
        )):
            raise ColorPowderAlreadyExists(f"色粉編號 {data.colorpowder_id} 已存在")
        conn.execute(
            """INSERT INTO color_powders(
                   colorpowder_id, international_code, name, category, package, notes,
                   source, version, created_at, updated_at, last_synced_at
               ) VALUES (?, ?, ?, ?, ?, ?, 'app', 1, ?, ?, NULL)""",
            (
                data.colorpowder_id, data.international_code, data.name, data.category,
                data.package, data.notes, now, now,
            ),
        )
        entity = _mapping(conn.execute(
            "SELECT * FROM color_powders WHERE colorpowder_id=?", (data.colorpowder_id,)
        ))
        enqueue_sheet_sync(
            conn, sheet_name="色粉管理", row_key=data.colorpowder_id,
            operation="insert", payload=color_powder_sheet_payload(entity), entity_version=1,
        )
        return entity


def update_color_powder(config: DatabaseConfig, data: ColorPowderInput) -> dict[str, Any]:
    """Update a powder and queue the new entity version in one transaction."""
    data = data.normalized()
    if not data.colorpowder_id:
        raise ColorPowderError("請輸入色粉編號")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute(
            "SELECT * FROM color_powders WHERE colorpowder_id=?", (data.colorpowder_id,)
        ))
        if existing is None:
            raise ColorPowderNotFound(f"找不到色粉編號 {data.colorpowder_id}")
        version = int(existing["version"]) + 1
        conn.execute(
            """UPDATE color_powders SET international_code=?, name=?, category=?, package=?,
                      notes=?, source='app', version=?, updated_at=?
               WHERE colorpowder_id=?""",
            (
                data.international_code, data.name, data.category, data.package,
                data.notes, version, now, data.colorpowder_id,
            ),
        )
        entity = _mapping(conn.execute(
            "SELECT * FROM color_powders WHERE colorpowder_id=?", (data.colorpowder_id,)
        ))
        enqueue_sheet_sync(
            conn, sheet_name="色粉管理", row_key=data.colorpowder_id,
            operation="update", payload=color_powder_sheet_payload(entity), entity_version=version,
        )
        return entity
