"""Turso-first customer master data with aliases and Sheet outbox events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .read_cache import cached_read
from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso

CONTACT_FIELDS = {"address": "地址", "phone": "電話", "fax": "傳真", "contact": "聯絡人", "tax_id": "統一編號"}


class CustomerError(RuntimeError):
    pass


class CustomerAlreadyExists(CustomerError):
    pass


class CustomerNotFound(CustomerError):
    pass


@dataclass(frozen=True)
class CustomerInput:
    customer_id: str
    name: str
    notes: str = ""
    address: str | None = None
    phone: str | None = None
    fax: str | None = None
    contact: str | None = None
    tax_id: str | None = None
    short_name: str | None = None

    def normalized(self) -> "CustomerInput":
        return CustomerInput(str(self.customer_id or "").strip(), str(self.name or "").strip(),
                             str(self.notes or "").strip(),
                             short_name=None if self.short_name is None else str(self.short_name).strip(),
                             **{key: None if getattr(self, key) is None else str(getattr(self, key)).strip()
                                for key in CONTACT_FIELDS})


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


def customer_sheet_payload(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "客戶編號": str(entity.get("customer_id") or ""),
        "客戶名稱": str(entity.get("name") or ""),
        "客戶簡稱": str(entity.get("short_name") or ""),
        "備註": str(entity.get("notes") or ""),
        **{label: str(entity.get(key) or "") for key, label in CONTACT_FIELDS.items()},
        "生命週期": str(entity.get("lifecycle_status") or "active"),
        "停用時間": str(entity.get("deleted_at") or ""),
        "停用原因": str(entity.get("delete_reason") or ""),
    }


def get_customer(config: DatabaseConfig, customer_id: str) -> dict[str, Any]:
    with connect_from_config(config) as conn:
        customer = _mapping(conn.execute('SELECT * FROM customers WHERE customer_id=?', (customer_id,)))
    if not customer:
        raise CustomerNotFound(f'找不到客戶編號 {customer_id}')
    return customer


@cached_read
def list_customers(config: DatabaseConfig, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(
            f"""SELECT customer_id, name, short_name, notes, address, phone, fax, contact, tax_id, lifecycle_status, deleted_at, delete_reason,
                       version, updated_at, last_synced_at FROM customers {where} ORDER BY customer_id"""
        ))


def _validate(data: CustomerInput) -> CustomerInput:
    data = data.normalized()
    if not data.customer_id:
        raise CustomerError("請輸入客戶編號")
    if not data.name:
        raise CustomerError("請輸入客戶完整名稱")
    if len(data.short_name or "") > 120:
        raise CustomerError("客戶簡稱內容過長")
    for key, label in CONTACT_FIELDS.items():
        if len(getattr(data, key) or "") > (500 if key == "address" else 120):
            raise CustomerError(f"{label}內容過長")
    return data


def _ensure_alias(conn, name: str, customer_id: str) -> None:
    owner = _mapping(conn.execute("SELECT customer_id FROM customer_aliases WHERE alias=?", (name,)))
    if owner and owner["customer_id"] != customer_id:
        raise CustomerError(f"客戶簡稱／別名 {name} 已由 {owner['customer_id']} 使用")


def create_customer(config: DatabaseConfig, data: CustomerInput) -> dict[str, Any]:
    data, now = _validate(data), utc_now_iso()
    with connect_from_config(config) as conn:
        if _mapping(conn.execute("SELECT 1 FROM customers WHERE customer_id=?", (data.customer_id,))):
            raise CustomerAlreadyExists(f"客戶編號 {data.customer_id} 已存在")
        prior = _mapping(conn.execute(
            "SELECT COALESCE(MAX(entity_version),0) AS version FROM sync_outbox WHERE sheet_name='客戶名單' AND row_key=?",
            (data.customer_id,),
        ))
        version = int(prior["version"]) + 1
        _ensure_alias(conn, data.name, data.customer_id)
        if data.short_name:
            _ensure_alias(conn, data.short_name, data.customer_id)
        conn.execute("""INSERT INTO customers(customer_id,name,short_name,notes,address,phone,fax,contact,tax_id,source,version,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,'app',?,?,?)""",
                     (data.customer_id, data.name, data.short_name or "", data.notes, *(getattr(data, key) or "" for key in CONTACT_FIELDS), version, now, now))
        conn.execute("INSERT INTO customer_aliases(alias,customer_id,created_at) VALUES (?,?,?)",
                     (data.name, data.customer_id, now))
        if data.short_name:
            conn.execute("INSERT OR IGNORE INTO customer_aliases(alias,customer_id,created_at) VALUES (?,?,?)",
                         (data.short_name, data.customer_id, now))
        entity = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (data.customer_id,)))
        enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=data.customer_id, operation="insert",
                           payload=customer_sheet_payload(entity), entity_version=version)
        return entity


def _rename_customer_links(conn, old_id: str, new_id: str, now: str) -> None:
    """Move current customer references; retain historical monetary/snapshot data."""
    from .recipe_repository import _recipe_sheet_payload
    from .trial_repository import trial_sheet_payload

    # Create the new parent first. Some customer FKs deliberately do not cascade.
    existing = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (old_id,)))
    parent = dict(existing, customer_id=new_id, last_synced_at=None)
    columns = list(parent)
    conn.execute(
        "INSERT INTO customers(" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")",
        tuple(parent[column] for column in columns),
    )
    conn.execute("UPDATE customer_aliases SET customer_id=? WHERE customer_id=?", (new_id, old_id))
    for table in ("scheduled_quotes", "receipt_batches"):
        conn.execute(
            f"UPDATE {table} SET customer_id=?,version=version+1,updated_at=? WHERE customer_id=?",
            (new_id, now, old_id),
        )

    shipments = _mappings(conn.execute(
        """SELECT id,customer_id,payload_json FROM shipment_orders
           WHERE customer_id=? OR json_extract(payload_json,'$.recipient_id')=?""", (old_id, old_id)))
    for shipment in shipments:
        payload = json.loads(shipment["payload_json"])
        customer_id = new_id if shipment["customer_id"] == old_id else shipment["customer_id"]
        if shipment["customer_id"] == old_id:
            payload["customer_id"] = new_id
        if payload.get("recipient_id") == old_id:
            payload["recipient_id"] = new_id
        conn.execute(
            "UPDATE shipment_orders SET customer_id=?,payload_json=?,version=version+1,updated_at=? WHERE id=?",
            (customer_id, json.dumps(payload, ensure_ascii=False), now, shipment["id"]),
        )

    for table, id_column, sheet_name, formatter in (
        ("recipes", "recipe_id", "配方管理", _recipe_sheet_payload),
        ("trial_records", "trial_id", "試色登錄", trial_sheet_payload),
    ):
        entities = _mappings(conn.execute(f"SELECT * FROM {table} WHERE customer_id=?", (old_id,)))
        for entity in entities:
            identity = entity[id_column]
            conn.execute(
                f"UPDATE {table} SET customer_id=?,source='app',version=version+1,updated_at=? WHERE {id_column}=?",
                (new_id, now, identity),
            )
            entity.update(customer_id=new_id, version=int(entity["version"]) + 1, updated_at=now)
            if table == "recipes":
                components = _mappings(conn.execute(
                    "SELECT position,colorpowder_id,weight FROM recipe_components WHERE recipe_id=? ORDER BY position",
                    (identity,),
                ))
                payload = formatter(entity, components)
            else:
                payload = formatter(entity)
            active = entity["lifecycle_status"] == "active"
            enqueue_sheet_sync(
                conn, sheet_name=sheet_name, row_key=identity,
                operation="update" if active else "delete", payload=payload if active else None,
                entity_version=int(entity["version"]),
            )

    # Some imported production payloads include a customer code even though the
    # normalized order header links customers by name. Preserve saved recipe snapshots.
    orders = _mappings(conn.execute(
        """SELECT production_order_id,payload_json,version,cancelled_at FROM production_orders
           WHERE json_extract(payload_json,'$."客戶編號"')=?""", (old_id,)))
    for order in orders:
        payload = json.loads(order["payload_json"])
        payload["客戶編號"] = new_id
        version = int(order["version"]) + 1
        conn.execute(
            "UPDATE production_orders SET payload_json=?,source='app',version=?,updated_at=? WHERE production_order_id=?",
            (json.dumps(payload, ensure_ascii=False), version, now, order["production_order_id"]),
        )
        enqueue_sheet_sync(
            conn, sheet_name="生產單", row_key=order["production_order_id"],
            operation="delete" if order["cancelled_at"] else "update",
            payload=None if order["cancelled_at"] else payload, entity_version=version,
        )
    conn.execute("DELETE FROM customers WHERE customer_id=?", (old_id,))


def update_customer(
    config: DatabaseConfig, data: CustomerInput, *,
    original_customer_id: str | None = None, expected_version: int | None = None,
) -> dict[str, Any]:
    data, now = _validate(data), utc_now_iso()
    lookup_id = str(original_customer_id).strip() if original_customer_id is not None else data.customer_id
    if not lookup_id:
        raise CustomerError("缺少原客戶編號")
    renaming = lookup_id != data.customer_id
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (lookup_id,)))
        if not existing:
            raise CustomerNotFound(f"找不到客戶編號 {lookup_id}")
        if existing["lifecycle_status"] != "active":
            raise CustomerError("已停用客戶不可修改")
        if expected_version is not None and int(existing["version"]) != expected_version:
            raise CustomerError("客戶已被其他人修改，請取消編輯後重新讀取")
        if expected_version is not None:
            guarded = conn.execute(
                "UPDATE customers SET version=version WHERE customer_id=? AND version=?",
                (lookup_id, expected_version),
            )
            if guarded.rowcount != 1:
                raise CustomerError("客戶已被其他人修改，請取消編輯後重新讀取")
        if renaming:
            if expected_version is None:
                raise CustomerError("更改客戶編號前請重新讀取客戶資料")
            if _mapping(conn.execute("SELECT 1 FROM customers WHERE customer_id=?", (data.customer_id,))):
                raise CustomerAlreadyExists(f"客戶編號 {data.customer_id} 已存在")
            if _mapping(conn.execute(
                "SELECT 1 FROM sheet_rows WHERE sheet_name='客戶名單' AND row_key=?", (data.customer_id,))):
                raise CustomerError("新客戶編號仍有 Sheet 同步紀錄，請先完成同步後再試")
            if _mapping(conn.execute(
                """SELECT 1 FROM sync_outbox WHERE status='processing' AND (
                   (sheet_name='客戶名單' AND row_key=?) OR
                   (sheet_name='配方管理' AND row_key IN (SELECT recipe_id FROM recipes WHERE customer_id=?)) OR
                   (sheet_name='試色登錄' AND row_key IN (SELECT trial_id FROM trial_records WHERE customer_id=?)) OR
                   (sheet_name='生產單' AND row_key IN (
                       SELECT production_order_id FROM production_orders WHERE json_extract(payload_json,'$."客戶編號"')=?)))""",
                (lookup_id, lookup_id, lookup_id, lookup_id),
            )):
                raise CustomerError("相關資料正在同步，請稍後再更改客戶編號")
        _ensure_alias(conn, data.name, lookup_id)
        if data.short_name:
            _ensure_alias(conn, data.short_name, lookup_id)
        version = int(existing["version"]) + 1
        if renaming:
            prior = _mapping(conn.execute(
                "SELECT COALESCE(MAX(entity_version),0) AS version FROM sync_outbox WHERE sheet_name='客戶名單' AND row_key=?",
                (data.customer_id,),
            ))
            version = max(version, int(prior["version"]) + 1)
        if renaming:
            _rename_customer_links(conn, lookup_id, data.customer_id, now)
        contact_values = [existing[key] if getattr(data, key) is None else getattr(data, key) for key in CONTACT_FIELDS]
        conn.execute("UPDATE customers SET name=?,short_name=?,notes=?,address=?,phone=?,fax=?,contact=?,tax_id=?,source='app',version=?,updated_at=? WHERE customer_id=?",
                     (data.name, existing["short_name"] if data.short_name is None else data.short_name, data.notes, *contact_values, version, now, data.customer_id))
        conn.execute("INSERT OR IGNORE INTO customer_aliases(alias,customer_id,created_at) VALUES (?,?,?)",
                     (data.name, data.customer_id, now))
        if data.short_name:
            conn.execute("INSERT OR IGNORE INTO customer_aliases(alias,customer_id,created_at) VALUES (?,?,?)",
                         (data.short_name, data.customer_id, now))
        entity = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (data.customer_id,)))
        enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=data.customer_id,
                           operation="insert" if renaming else "update",
                           payload=customer_sheet_payload(entity), entity_version=version)
        if renaming:
            enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=lookup_id, operation="delete",
                               payload=None, entity_version=version)
        return entity


def set_customer_active(config: DatabaseConfig, customer_id: str, *, active: bool, reason: str = "") -> dict[str, Any]:
    customer_id, now = str(customer_id or "").strip(), utc_now_iso()
    if not active and not str(reason or "").strip():
        raise CustomerError("請輸入停用原因")
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,)))
        if not existing:
            raise CustomerNotFound(f"找不到客戶編號 {customer_id}")
        conn.execute("""UPDATE customers SET lifecycle_status=?,deleted_at=?,delete_reason=?,
                        version=version+1,updated_at=? WHERE customer_id=?""",
                     ("active" if active else "inactive", None if active else now,
                      None if active else str(reason).strip(), now, customer_id))
        entity = _mapping(conn.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,)))
        enqueue_sheet_sync(conn, sheet_name="客戶名單", row_key=customer_id,
                           operation="update" if active else "delete",
                           payload=customer_sheet_payload(entity) if active else None,
                           entity_version=int(entity["version"]))
        return entity



def customer_display_name(customer):
    """Internal label; full legal name remains in name for external documents."""
    return str(customer.get("short_name") or customer.get("name") or "")

