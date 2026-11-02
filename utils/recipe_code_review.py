"""Opt-in, per-recipe correction of historical leading-zero workarounds."""
import hashlib
import json
import re

from .database import connect_from_config, enqueue_sheet_sync, utc_now_iso
from .read_cache import cached_read
from .recipe_repository import RecipeError, _mapping, _mappings, _recipe_sheet_payload


def suggested_recipe_code(code):
    match = re.fullmatch(r"[A-Za-z]+(0[0-9]+)[A-Za-z]*", str(code or "").strip())
    return match.group(1) if match else None


@cached_read
def reviewed_recipe_codes(config):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute("SELECT v.source_code,v.source_created_at,v.choice,v.target_code FROM recipe_code_reviews v JOIN recipes r ON r.recipe_id=v.source_code AND r.created_at=v.source_created_at"))


def recipe_code_preview(config, source):
    with connect_from_config(config) as conn:
        return _preview(conn, source)


def _preview(conn, source):
    recipe = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (source,)))
    if not recipe:
        raise RecipeError("配方已變更或不存在，請重新搜尋")
    target = suggested_recipe_code(source)
    if not target:
        raise RecipeError("此編號不屬於前導零舊編號候選")
    components = _mappings(conn.execute(
        "SELECT * FROM recipe_components WHERE recipe_id=? ORDER BY position", (source,)))
    token = hashlib.sha256(json.dumps([recipe, components], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(source=source, target=target, token=token, recipe=recipe,
                target_exists=_mapping(conn.execute(
                    "SELECT recipe_id FROM recipes WHERE UPPER(recipe_id)=UPPER(?)", (target,))) is not None)


def confirm_recipe_code(config, source, token, *, rename):
    """Change identifiers only; component values and historical quantities stay intact."""
    with connect_from_config(config) as conn:
        # Acquire the write lock before checking the version and destination.
        conn.execute("UPDATE recipes SET version=version WHERE recipe_id=?", (source,))
        preview = _preview(conn, source)
        if preview["token"] != token:
            raise RecipeError("配方在確認前已變更，請重新查看後確認")
        target = preview["target"]
        if rename and preview["recipe"]["lifecycle_status"] != "active":
            raise RecipeError("停用配方請先恢復，再確認是否改名")
        if rename and preview["target_exists"]:
            raise RecipeError(f"配方編號 {target} 已存在，不能覆蓋或自動合併")
        reviewed = _mapping(conn.execute(
            "SELECT source_code FROM recipe_code_reviews WHERE source_code=? AND source_created_at=?",
            (source, preview["recipe"]["created_at"])))
        if reviewed:
            raise RecipeError("此配方已完成確認，請重新整理")
        now = utc_now_iso()
        if rename:
            conn.execute("UPDATE recipes SET recipe_id=?,version=version+1,updated_at=? WHERE recipe_id=?",
                         (target, now, source))
            dependents = _mappings(conn.execute("SELECT recipe_id FROM recipes WHERE original_recipe=?", (source,)))
            conn.execute("UPDATE recipes SET original_recipe=?,version=version+1,updated_at=? WHERE original_recipe=?",
                         (target, now, source))
            for code in [target] + [row["recipe_id"] for row in dependents]:
                recipe = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (code,)))
                components = _mappings(conn.execute(
                    "SELECT position,colorpowder_id,weight FROM recipe_components WHERE recipe_id=? ORDER BY position", (code,)))
                enqueue_sheet_sync(conn, sheet_name="配方管理", row_key=code,
                    operation="insert" if code == target else "update",
                    payload=_recipe_sheet_payload(recipe, components), entity_version=recipe["version"])
            enqueue_sheet_sync(conn, sheet_name="配方管理", row_key=source, operation="delete",
                               payload=None, entity_version=preview["recipe"]["version"]+1)
            archived_versions = {
                row["outsourcing_order_id"]: row["version"]
                for row in _mappings(conn.execute(
                    "SELECT outsourcing_order_id,version,payload_json FROM outsourcing_orders WHERE recipe_id=?",
                    (source,)))
                if json.loads(row["payload_json"]).get("配方編號") == source
            }
            # Foreign keys have cascaded. Keep the corresponding display/Sheet payload
            # consistent without invoking save routines that rebuild packages or recalculate.
            for table, id_column, sheet in [
                ("production_orders", "production_order_id", "生產單"),
                ("outsourcing_orders", "outsourcing_order_id", "代工管理"),
            ]:
                rows = _mappings(conn.execute(f"SELECT * FROM {table} WHERE recipe_id IN (?,?)", (source,target)))
                for row in rows:
                    payload = json.loads(row["payload_json"])
                    if payload.get("配方編號") != source:
                        continue
                    payload["配方編號"] = target
                    # Preserve the cancellation guard when only the linked code changed.
                    if table == "production_orders" and "_cancelled_outsourcing_orders" in payload:
                        archived = json.loads(payload["_cancelled_outsourcing_orders"])
                        payload["_cancelled_outsourcing_orders"] = json.dumps([
                            [order_id, v+1 if archived_versions.get(order_id) == v else v]
                            for order_id, v in archived
                        ], ensure_ascii=False)
                    version = row["version"] + 1
                    conn.execute(f"UPDATE {table} SET recipe_id=?,payload_json=?,version=?,updated_at=? WHERE {id_column}=?",
                        (target, json.dumps(payload, ensure_ascii=False), version, now, row[id_column]))
                    inactive = bool(row.get("cancelled_at")) if table == "production_orders" else row["lifecycle_status"] != "active"
                    enqueue_sheet_sync(conn, sheet_name=sheet, row_key=row[id_column],
                                       operation="delete" if inactive else "update",
                                       payload=None if inactive else payload, entity_version=version)
        conn.execute("""INSERT INTO recipe_code_reviews(source_code,source_created_at,target_code,choice,recipe_token,reviewed_at)
            VALUES (?,?,?,?,?,?) ON CONFLICT(source_code) DO UPDATE SET
            source_created_at=excluded.source_created_at,target_code=excluded.target_code,
            choice=excluded.choice,recipe_token=excluded.recipe_token,reviewed_at=excluded.reviewed_at""",
            (source, preview["recipe"]["created_at"], target, "rename" if rename else "keep", token, now))
    return target if rename else source
