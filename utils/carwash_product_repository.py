"""Name-only wash-facility grouping; movements and their formulas stay intact."""
import hashlib
import json
import uuid

from .database import connect_from_config, utc_now_iso
from .carwash_inventory_repository import CarwashInventoryError, _mapping, _mappings
from .read_cache import cached_read


def name_key(value):
    return str(value or "").strip().casefold()


@cached_read
def list_carwash_aliases(config):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute("SELECT * FROM carwash_product_aliases ORDER BY alias_key"))


def canonical_name(name, aliases):
    key = name_key(name)
    for item in aliases:
        if key in (item["alias_key"], item["canonical_key"]):
            return item["canonical_name"]
    return str(name or "").strip()


def _preview(conn, source, target):
    aliases = _mappings(conn.execute("SELECT * FROM carwash_product_aliases ORDER BY alias_key"))
    revision = _mapping(conn.execute("SELECT revision FROM carwash_product_catalog WHERE singleton=1"))["revision"]
    source, target = canonical_name(source, aliases), canonical_name(target, aliases)
    if not source or not target or name_key(source) == name_key(target):
        raise CarwashInventoryError("請選擇兩個不同的貨品編號")
    records = _mappings(conn.execute(
        "SELECT * FROM carwash_inventory_movements WHERE lifecycle_status='active' ORDER BY created_at,movement_id"))
    relevant = [row for row in records if name_key(canonical_name(row["product_id"], aliases))
                in {name_key(source), name_key(target)}]
    sides = {name_key(canonical_name(row["product_id"], aliases)) for row in relevant}
    if sides != {name_key(source), name_key(target)}:
        raise CarwashInventoryError("兩個編號都必須有有效庫存紀錄，請重新選擇")
    units = {str(row["unit"] or "").strip().upper() for row in relevant}
    if len(units) != 1 or "" in units:
        raise CarwashInventoryError("單位不同或缺漏，不能合併；不會自動換算單位")
    initial_sides = {name_key(canonical_name(row["product_id"], aliases)) for row in relevant
                     if row["movement_type"] == "初始庫存"}
    snapshot = {"revision": revision, "aliases": aliases, "records": relevant,
                "source": source, "target": target}
    token = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return dict(snapshot, token=token, needs_initial_confirmation=len(initial_sides) > 1,
                members=sorted({str(row["product_id"]).strip() for row in relevant}))


def preview_carwash_merge(config, source, target):
    with connect_from_config(config) as conn:
        return _preview(conn, source, target)


def merge_carwash_names(config, source, target, token, *, actor, confirm_initials=False):
    actor = str(actor or "").strip()
    if not actor:
        raise CarwashInventoryError("請填寫登記人")
    with connect_from_config(config) as conn:
        # Start the write transaction before reading any validation snapshot.
        # SQLite SELECTs alone do not prevent concurrent movement changes.
        conn.execute("UPDATE carwash_product_catalog SET revision=revision WHERE singleton=1")
        preview = _preview(conn, source, target)
        if preview["token"] != token:
            raise CarwashInventoryError("紀錄或合併對應已變更，請重新預覽後確認")
        if preview["needs_initial_confirmation"] and not confirm_initials:
            raise CarwashInventoryError("兩邊都有初始庫存，請先確認是不同批庫存；不會自動刪除或抵銷")
        locked = _mapping(conn.execute(
            "UPDATE carwash_product_catalog SET revision=revision+1 WHERE singleton=1 AND revision=? RETURNING revision",
            (preview["revision"],)))
        if not locked:
            raise CarwashInventoryError("合併對應已變更，請重新預覽")
        merge_id, now = str(uuid.uuid4()), utc_now_iso()
        conn.execute(
            "INSERT INTO carwash_product_merge_log VALUES (?,?,?,?,?,?,?)",
            (merge_id, preview["source"], preview["target"],
             json.dumps(preview["members"], ensure_ascii=False),
             json.dumps({key: preview[key] for key in ("revision", "aliases", "records")}, ensure_ascii=False),
             actor, now))
        target_key = name_key(preview["target"])
        names = {name_key(row["product_id"]): str(row["product_id"]).strip() for row in preview["records"]}
        for alias in preview["aliases"]:
            if alias["canonical_key"] in {name_key(preview["source"]), target_key}:
                names[alias["alias_key"]] = alias["alias_name"]
        names[name_key(preview["source"])] = preview["source"]
        for key, name in names.items():
            if key == target_key:
                continue
            conn.execute(
                """INSERT INTO carwash_product_aliases VALUES (?,?,?,?,?,?)
                   ON CONFLICT(alias_key) DO UPDATE SET canonical_key=excluded.canonical_key,
                   canonical_name=excluded.canonical_name,merge_id=excluded.merge_id,updated_at=excluded.updated_at""",
                (key, name, target_key, preview["target"], merge_id, now))
    return merge_id


@cached_read
def carwash_merge_history(config):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT merge_id,source_name,target_name,members_json,actor,created_at FROM carwash_product_merge_log ORDER BY created_at DESC,merge_id"))
