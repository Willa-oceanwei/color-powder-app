"""Turso-first recipe persistence with atomic component and outbox updates."""

from __future__ import annotations

from datetime import date
from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso
from .sheet_export import color_powder_sheet_payload

RECIPE_COMPONENT_POSITIONS = range(1, 9)


class RecipeError(RuntimeError):
    pass


class RecipeAlreadyExists(RecipeError):
    pass


class RecipeNotFound(RecipeError):
    pass


def normalize_color_powder_id(value: Any) -> str:
    """Apply the same whitespace/case normalization used by the recipe UI."""
    if value is None:
        return ""
    return str(value).strip().replace("\u3000", "").replace(" ", "").upper()


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


def _text(row: dict[str, Any], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def _number(value: Any, default: float = 0) -> float:
    try:
        return float(str(value).replace(",", "").strip() or default)
    except (TypeError, ValueError):
        return default


def _validated_payload(conn, row: dict[str, Any]) -> tuple[dict[str, str], list[tuple[int, str, float]]]:
    payload = {str(key): _text(row, str(key)) for key in row}
    recipe_id = payload.get("配方編號", "")
    if not recipe_id:
        raise RecipeError("請輸入配方編號")
    if payload.get("配方類別") == "附加配方" and not payload.get("原始配方"):
        raise RecipeError("附加配方必須填寫原始配方")
    components = []
    for position in RECIPE_COMPONENT_POSITIONS:
        powder_id = payload.get(f"色粉編號{position}", "")
        weight_text = payload.get(f"色粉重量{position}", "")
        if not powder_id:
            if _number(weight_text):
                raise RecipeError(f"色粉重量{position}有值但色粉編號{position}空白")
            continue
        if _mapping(conn.execute(
            "SELECT colorpowder_id FROM color_powders WHERE colorpowder_id=?", (powder_id,)
        )) is None:
            raise RecipeError(f"找不到色粉編號 {powder_id}")
        components.append((position, powder_id, _number(weight_text)))
    return payload, components


def _save_recipe(config: DatabaseConfig, row: dict[str, Any], *, create: bool) -> dict[str, str]:
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        payload, components = _validated_payload(conn, row)
        recipe_id = payload["配方編號"]
        existing = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)))
        if create and existing is not None:
            raise RecipeAlreadyExists(f"配方編號 {recipe_id} 已存在")
        if not create and existing is None:
            raise RecipeNotFound(f"找不到配方編號 {recipe_id}")
        version = 1 if existing is None else int(existing["version"]) + 1
        created_at = now if existing is None else existing["created_at"]
        conn.execute(
            """INSERT INTO recipes(
                   recipe_id, color, customer_id, customer_name, recipe_category, status,
                   original_recipe, powder_category, measurement_unit, pantone_code,
                   ratio1, ratio2, ratio3, net_weight, net_weight_unit, total_category,
                   sheet_created_at, notes, important_notice, oem_multiplier, source, version,
                   created_at, updated_at, last_synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       'app', ?, ?, ?, NULL)
               ON CONFLICT(recipe_id) DO UPDATE SET
                   color=excluded.color, customer_id=excluded.customer_id,
                   customer_name=excluded.customer_name, recipe_category=excluded.recipe_category,
                   status=excluded.status, original_recipe=excluded.original_recipe,
                   powder_category=excluded.powder_category, measurement_unit=excluded.measurement_unit,
                   pantone_code=excluded.pantone_code, ratio1=excluded.ratio1,
                   ratio2=excluded.ratio2, ratio3=excluded.ratio3, net_weight=excluded.net_weight,
                   net_weight_unit=excluded.net_weight_unit, total_category=excluded.total_category,
                   sheet_created_at=excluded.sheet_created_at, notes=excluded.notes,
                   important_notice=excluded.important_notice, oem_multiplier=excluded.oem_multiplier,
                   source='app', version=excluded.version, updated_at=excluded.updated_at""",
            (
                recipe_id, payload.get("顏色", ""), payload.get("客戶編號", ""),
                payload.get("客戶名稱", ""), payload.get("配方類別", ""), payload.get("狀態", ""),
                payload.get("原始配方", ""), payload.get("色粉類別", ""), payload.get("計量單位", ""),
                payload.get("Pantone色號", ""), payload.get("比例1", ""), payload.get("比例2", ""),
                payload.get("比例3", ""), _number(payload.get("淨重")), payload.get("淨重單位", ""),
                payload.get("合計類別", ""), payload.get("建檔時間", ""), payload.get("備註", ""),
                payload.get("重要提醒", ""), _number(payload.get("代工倍率"), 1) or 1,
                version, created_at, now,
            ),
        )
        conn.execute("DELETE FROM recipe_components WHERE recipe_id=?", (recipe_id,))
        for position, powder_id, weight in components:
            conn.execute(
                """INSERT INTO recipe_components(recipe_id, position, colorpowder_id, weight, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (recipe_id, position, powder_id, weight, now, now),
            )
        operation = "insert" if create else "update"
        enqueue_sheet_sync(
            conn, sheet_name="配方管理", row_key=recipe_id, operation=operation,
            payload=payload, entity_version=version,
        )
        return payload


def create_recipe(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    return _save_recipe(config, row, create=True)


def update_recipe(config: DatabaseConfig, row: dict[str, Any]) -> dict[str, str]:
    return _save_recipe(config, row, create=False)


def _recipe_sheet_payload(entity: dict[str, Any], components: list[dict[str, Any]]) -> dict[str, str]:
    row = {
        "配方編號": entity["recipe_id"], "顏色": entity.get("color") or "",
        "客戶編號": entity.get("customer_id") or "", "客戶名稱": entity.get("customer_name") or "",
        "配方類別": entity.get("recipe_category") or "", "狀態": entity.get("status") or "",
        "原始配方": entity.get("original_recipe") or "", "色粉類別": entity.get("powder_category") or "",
        "計量單位": entity.get("measurement_unit") or "", "Pantone色號": entity.get("pantone_code") or "",
        "代工倍率": str(entity.get("oem_multiplier") or 1), "比例1": entity.get("ratio1") or "",
        "比例2": entity.get("ratio2") or "", "比例3": entity.get("ratio3") or "",
        "淨重": str(entity.get("net_weight") or ""), "淨重單位": entity.get("net_weight_unit") or "",
        "合計類別": entity.get("total_category") or "", "重要提醒": entity.get("important_notice") or "",
        "備註": entity.get("notes") or "", "建檔時間": entity.get("sheet_created_at") or "",
        "生命週期": entity.get("lifecycle_status") or "active",
        "停用時間": entity.get("deleted_at") or "", "停用原因": entity.get("delete_reason") or "",
    }
    for component in components:
        position = int(component["position"])
        row[f"色粉編號{position}"] = str(component["colorpowder_id"])
        row[f"色粉重量{position}"] = str(component["weight"])
    return row


def list_recipes(config: DatabaseConfig, *, include_inactive: bool = False) -> list[dict[str, str]]:
    with connect_from_config(config) as conn:
        where = "" if include_inactive else "WHERE lifecycle_status='active'"
        recipes = _mappings(conn.execute(f"SELECT * FROM recipes {where} ORDER BY recipe_id"))
        components = _mappings(conn.execute(
            "SELECT recipe_id, position, colorpowder_id, weight FROM recipe_components ORDER BY recipe_id, position"
        ))
    by_recipe: dict[str, list[dict[str, Any]]] = {}
    for component in components:
        by_recipe.setdefault(str(component["recipe_id"]), []).append(component)
    return [
        _recipe_sheet_payload(entity, by_recipe.get(str(entity["recipe_id"]), []))
        for entity in recipes
    ]


def find_recipes_using_color_powder(
    config: DatabaseConfig, colorpowder_id: str
) -> list[dict[str, Any]]:
    """Return one preview row per recipe whose component ID exactly normalizes to the ID."""
    target = normalize_color_powder_id(colorpowder_id)
    if not target:
        raise RecipeError("請輸入舊色粉編號")
    with connect_from_config(config) as conn:
        rows = _mappings(conn.execute(
            """SELECT r.recipe_id, r.customer_name, r.color, c.position, c.colorpowder_id
               FROM recipes AS r JOIN recipe_components AS c ON c.recipe_id=r.recipe_id
               ORDER BY r.recipe_id, c.position"""
        ))
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if normalize_color_powder_id(row["colorpowder_id"]) != target:
            continue
        recipe_id = str(row["recipe_id"])
        item = grouped.setdefault(recipe_id, {
            "配方編號": recipe_id,
            "客戶": str(row.get("customer_name") or ""),
            "顏色": str(row.get("color") or ""),
            "使用位置": [],
        })
        item["使用位置"].append(f"色粉{int(row['position'])}")
    return [
        {**item, "使用位置": "、".join(item["使用位置"])}
        for item in grouped.values()
    ]


def replace_color_powder_in_recipes(
    config: DatabaseConfig, old_colorpowder_id: str, new_colorpowder_id: str,
    replacement_date: date,
) -> list[dict[str, str]]:
    """Atomically replace current recipe components, append notices, and queue Sheet updates."""
    old_normalized = normalize_color_powder_id(old_colorpowder_id)
    new_normalized = normalize_color_powder_id(new_colorpowder_id)
    if not old_normalized or not new_normalized:
        raise RecipeError("請輸入舊色粉編號與新色粉編號")
    if old_normalized == new_normalized:
        raise RecipeError("新舊色粉編號不可相同")
    if not isinstance(replacement_date, date):
        raise RecipeError("更換日期格式不正確")

    notice = (
        f"{replacement_date.year - 1911:03d}/{replacement_date.month:02d}/{replacement_date.day:02d}"
        f"原色粉編號{old_normalized}更換成{new_normalized}"
    )
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        powders = _mappings(conn.execute(
            "SELECT colorpowder_id, lifecycle_status FROM color_powders"
        ))
        old_matches = [p for p in powders if normalize_color_powder_id(p["colorpowder_id"]) == old_normalized]
        new_matches = [p for p in powders if normalize_color_powder_id(p["colorpowder_id"]) == new_normalized]
        if not old_matches:
            raise RecipeError(f"找不到舊色粉編號 {old_normalized}")
        if not new_matches:
            raise RecipeError(
                f"找不到新色粉編號 {new_normalized}，請先至「色粉資料管理」建立此色粉。"
            )
        if len(old_matches) != 1 or len(new_matches) != 1:
            raise RecipeError("色粉主檔有標準化後重複的編號，請先整理主檔")
        old_id = str(old_matches[0]["colorpowder_id"])
        new_id = str(new_matches[0]["colorpowder_id"])

        components = _mappings(conn.execute(
            """SELECT recipe_id, position, colorpowder_id FROM recipe_components
               ORDER BY recipe_id, position"""
        ))
        affected: dict[str, list[int]] = {}
        for component in components:
            if normalize_color_powder_id(component["colorpowder_id"]) == old_normalized:
                affected.setdefault(str(component["recipe_id"]), []).append(int(component["position"]))

        if not affected:
            return []

        if new_matches[0].get("lifecycle_status") != "active":
            conn.execute(
                """UPDATE color_powders SET lifecycle_status='active', deleted_at=NULL,
                          delete_reason=NULL, source='app', version=version+1, updated_at=?
                   WHERE colorpowder_id=?""",
                (now, new_id),
            )
            new_entity = _mapping(conn.execute(
                "SELECT * FROM color_powders WHERE colorpowder_id=?", (new_id,)
            ))
            enqueue_sheet_sync(
                conn, sheet_name="色粉管理", row_key=new_id, operation="update",
                payload=color_powder_sheet_payload(new_entity),
                entity_version=int(new_entity["version"]),
            )

        results: list[dict[str, str]] = []
        for recipe_id, positions in affected.items():
            recipe = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)))
            if recipe is None:
                raise RecipeError(f"找不到配方編號 {recipe_id}")
            existing_notice = str(recipe.get("important_notice") or "").strip()
            notice_lines = existing_notice.splitlines()
            updated_notice = existing_notice if notice in notice_lines else "\n".join(
                part for part in (existing_notice, notice) if part
            )
            conn.execute(
                """UPDATE recipe_components SET colorpowder_id=?, updated_at=?
                   WHERE recipe_id=? AND colorpowder_id=?""",
                (new_id, now, recipe_id, old_id),
            )
            conn.execute(
                """UPDATE recipes SET important_notice=?, source='app', version=version+1,
                          updated_at=? WHERE recipe_id=?""",
                (updated_notice, now, recipe_id),
            )
            updated_recipe = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)))
            updated_components = _mappings(conn.execute(
                """SELECT position, colorpowder_id, weight FROM recipe_components
                   WHERE recipe_id=? ORDER BY position""", (recipe_id,)
            ))
            enqueue_sheet_sync(
                conn, sheet_name="配方管理", row_key=recipe_id, operation="update",
                payload=_recipe_sheet_payload(updated_recipe, updated_components),
                entity_version=int(updated_recipe["version"]),
            )
            results.append({
                "配方編號": recipe_id,
                "客戶": str(recipe.get("customer_name") or ""),
                "顏色": str(recipe.get("color") or ""),
                "更換欄位": "、".join(f"色粉{position}" for position in positions),
                "重要提醒新增內容": notice,
            })

        if old_matches[0].get("lifecycle_status") == "active":
            conn.execute(
                """UPDATE color_powders SET lifecycle_status='inactive', deleted_at=?,
                          delete_reason=?, source='app', version=version+1, updated_at=?
                   WHERE colorpowder_id=?""",
                (now, f"色粉編號替代為 {new_id}", now, old_id),
            )
            old_entity = _mapping(conn.execute(
                "SELECT * FROM color_powders WHERE colorpowder_id=?", (old_id,)
            ))
            enqueue_sheet_sync(
                conn, sheet_name="色粉管理", row_key=old_id, operation="delete",
                payload=None, entity_version=int(old_entity["version"]),
            )
        return results


def set_recipe_active(config: DatabaseConfig, recipe_id: str, *, active: bool, reason: str = "") -> dict[str, Any]:
    """Soft-disable or restore a recipe; components and order snapshots remain readable."""
    recipe_id = str(recipe_id or "").strip()
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)))
        if existing is None:
            raise RecipeNotFound(f"找不到配方編號 {recipe_id}")
        conn.execute(
            """UPDATE recipes SET lifecycle_status=?, deleted_at=?, delete_reason=?,
                      version=version+1, updated_at=? WHERE recipe_id=?""",
            ("active" if active else "inactive", None if active else now,
             None if active else str(reason or "").strip(), now, recipe_id),
        )
        entity = _mapping(conn.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)))
        components = _mappings(conn.execute(
            """SELECT position, colorpowder_id, weight FROM recipe_components
               WHERE recipe_id=? ORDER BY position""",
            (recipe_id,),
        ))
        enqueue_sheet_sync(
            conn, sheet_name="配方管理", row_key=recipe_id,
            operation="update" if active else "delete",
            payload=_recipe_sheet_payload(entity, components) if active else None,
            entity_version=int(entity["version"]),
        )
        return entity
