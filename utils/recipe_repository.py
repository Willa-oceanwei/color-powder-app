"""Turso-first recipe persistence with atomic component and outbox updates."""

from __future__ import annotations

from typing import Any

from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso

RECIPE_COMPONENT_POSITIONS = range(1, 9)


class RecipeError(RuntimeError):
    pass


class RecipeAlreadyExists(RecipeError):
    pass


class RecipeNotFound(RecipeError):
    pass


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


def list_recipes(config: DatabaseConfig) -> list[dict[str, str]]:
    with connect_from_config(config) as conn:
        recipes = _mappings(conn.execute("SELECT * FROM recipes ORDER BY recipe_id"))
        components = _mappings(conn.execute(
            "SELECT recipe_id, position, colorpowder_id, weight FROM recipe_components ORDER BY recipe_id, position"
        ))
    by_recipe: dict[str, list[dict[str, Any]]] = {}
    for component in components:
        by_recipe.setdefault(str(component["recipe_id"]), []).append(component)
    result = []
    for entity in recipes:
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
        }
        for component in by_recipe.get(str(entity["recipe_id"]), []):
            position = int(component["position"])
            row[f"色粉編號{position}"] = str(component["colorpowder_id"])
            row[f"色粉重量{position}"] = str(component["weight"])
        result.append(row)
    return result
