"""Product specifications and initial prices, separate from recipe composition."""

from copy import deepcopy
from contextlib import nullcontext
import json
from decimal import Decimal

from .customer_repository import _mapping, _mappings
from .database import connect_from_config, utc_now_iso
from .shipment_repository import TAX_MODES, decimal_value

TEXT_FIELDS = ("category", "specification", "base_unit", "inner_unit", "outer_unit", "notes", "tax_mode")
NUMBER_FIELDS = ("inner_quantity", "outer_quantity", "standard_cost", "opening_cost", "current_cost",
                 "standard_price", "price_a", "price_b", "price_c", "price_d", "price_e")


class ProductError(ValueError):
    pass


def blank_product():
    result = dict(product_id="", name="", recipe_id="", supplier_id="", sales_unit="KG",
                  category="", specification="", base_unit="KG", inner_unit="", outer_unit="",
                  notes="", tax_mode="外加")
    result.update({key: "0" for key in NUMBER_FIELDS})
    return result


def _document(entity):
    if entity is None:
        raise ProductError("找不到貨品")
    result = blank_product()
    result.update(json.loads(entity["payload_json"]))
    result.update({key: entity[key] or "" for key in
                   ("product_id", "name", "recipe_id", "supplier_id", "sales_unit", "lifecycle_status",
                    "deleted_at", "delete_reason", "version", "created_at", "updated_at")})
    return result


def get_product(config, product_id):
    with connect_from_config(config) as conn:
        return _document(_mapping(conn.execute("SELECT * FROM products WHERE product_id=?", (product_id,))))


def list_products(config, *, query="", include_inactive=False):
    clauses, args = [], []
    if not include_inactive:
        clauses.append("lifecycle_status='active'")
    if query.strip():
        clauses.append("(product_id LIKE ? OR name LIKE ? OR recipe_id LIKE ? OR json_extract(payload_json,'$.specification') LIKE ?)")
        args.extend([f"%{query.strip()}%"] * 4)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with connect_from_config(config) as conn:
        return [_document(row) for row in _mappings(conn.execute(
            f"SELECT * FROM products {where} ORDER BY product_id", tuple(args)))]


def product_references(config):
    with connect_from_config(config) as conn:
        recipes = _mappings(conn.execute("SELECT recipe_id,color,customer_id,measurement_unit,lifecycle_status FROM recipes ORDER BY recipe_id"))
        suppliers = _mappings(conn.execute("SELECT supplier_id,name,lifecycle_status FROM suppliers ORDER BY supplier_id"))
    return recipes, suppliers


def product_from_recipe(recipe):
    data = blank_product()
    unit = str(recipe.get("measurement_unit") or "").strip()
    data.update(product_id=recipe["recipe_id"], recipe_id=recipe["recipe_id"],
                name=recipe.get("color") or recipe["recipe_id"], specification=unit)
    if unit.upper() in ("KG", "G", "公斤", "公克", "包", "桶", "袋", "箱", "支", "瓶", "個"):
        data.update(base_unit=unit, sales_unit=unit)
    return data


def save_product(config, document, *, _connection=None):
    data = blank_product()
    data.update(deepcopy(document))
    for key in ("product_id", "name", "recipe_id", "supplier_id", "sales_unit") + TEXT_FIELDS:
        data[key] = str(data.get(key) or "").strip()
    data["product_id"] = data["product_id"].upper()
    for key, label in (("product_id", "貨品編號"), ("name", "貨品名稱"), ("sales_unit", "銷售單位"), ("base_unit", "基本單位")):
        if not data[key]:
            raise ProductError(f"請輸入{label}")
    if len(data["product_id"]) > 40 or len(data["name"]) > 120:
        raise ProductError("貨品編號最多 40 字、名稱最多 120 字")
    if data["tax_mode"] not in TAX_MODES:
        raise ProductError("請選擇定價課稅方式")
    try:
        for key in NUMBER_FIELDS:
            data[key] = str(decimal_value(data[key], "貨品金額或包裝數量"))
    except ValueError as exc:
        raise ProductError(str(exc)) from exc
    if (not data["inner_unit"] and Decimal(data["inner_quantity"]) != 0
            or not data["outer_unit"] and Decimal(data["outer_quantity"]) != 0):
        raise ProductError("包裝數量有值時，請填寫包裝單位")
    now = utc_now_iso()
    with (nullcontext(_connection) if _connection is not None else connect_from_config(config)) as conn:
        original_id = str(document.get("original_id") or data["product_id"])
        existing = _mapping(conn.execute("SELECT * FROM products WHERE product_id=?", (original_id,)))
        editing = bool(document.get("version"))
        if editing:
            if not existing or existing["version"] != document["version"]:
                raise ProductError("貨品已由其他人修改，請重新讀取")
            if data["product_id"] != original_id:
                raise ProductError("修改時不可變更貨品編號")
            if existing["lifecycle_status"] != "active":
                raise ProductError("已刪除貨品不可修改，請先恢復")
        elif existing:
            raise ProductError("貨品編號已存在，包含已刪除貨品")
        for field, table, column in (("recipe_id", "recipes", "recipe_id"), ("supplier_id", "suppliers", "supplier_id")):
            if data[field]:
                reference = _mapping(conn.execute(f"SELECT lifecycle_status FROM {table} WHERE {column}=?", (data[field],)))
                if not reference or reference["lifecycle_status"] != "active":
                    if not existing or existing[field] != data[field]:
                        raise ProductError("關聯配方或供應商不存在或已停用")
        payload = json.dumps({key: data[key] for key in TEXT_FIELDS + NUMBER_FIELDS}, ensure_ascii=False)
        values = (data["name"], data["recipe_id"] or None, data["supplier_id"] or None, data["sales_unit"], payload)
        if editing:
            cursor = conn.execute("UPDATE products SET name=?,recipe_id=?,supplier_id=?,sales_unit=?,payload_json=?,"
                                  "version=version+1,updated_at=? WHERE product_id=? AND version=?",
                                  values + (now, original_id, document["version"]))
            if cursor.rowcount == 0:
                raise ProductError("貨品已由其他人修改，請重新讀取")
        else:
            conn.execute("INSERT INTO products(product_id,name,recipe_id,supplier_id,sales_unit,payload_json,created_at,updated_at) "
                         "VALUES (?,?,?,?,?,?,?,?)", (data["product_id"],) + values + (now, now))
        return _document(_mapping(conn.execute("SELECT * FROM products WHERE product_id=?", (data["product_id"],))))


def set_product_active(config, product_id, version, *, active, reason=""):
    if not active and not reason.strip():
        raise ProductError("請填寫刪除原因")
    now = utc_now_iso()
    with connect_from_config(config) as conn:
        cursor = conn.execute("UPDATE products SET lifecycle_status=?,deleted_at=?,delete_reason=?,version=version+1,updated_at=? "
                              "WHERE product_id=? AND version=?",
                              ("active" if active else "inactive", None if active else now,
                               None if active else reason.strip(), now, product_id, version))
        if cursor.rowcount == 0:
            raise ProductError("貨品已由其他人修改，請重新讀取")
        return _document(_mapping(conn.execute("SELECT * FROM products WHERE product_id=?", (product_id,))))


def shipment_products(config, customer_id):
    if not customer_id:
        return []
    with connect_from_config(config) as conn:
        rows = _mappings(conn.execute(
            "SELECT p.* FROM products p LEFT JOIN recipes r ON r.recipe_id=p.recipe_id "
            "WHERE p.lifecycle_status='active' AND (p.recipe_id IS NULL OR "
            "(r.lifecycle_status='active' AND (COALESCE(r.customer_id,'')='' OR r.customer_id=?))) ORDER BY p.product_id",
            (customer_id,)))
    return [_document(row) for row in rows]
