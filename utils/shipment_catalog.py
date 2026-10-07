"""Recipe defaults and explicit shipment-to-product price synchronization."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .customer_repository import _mapping
from .product_repository import (
    ProductError, _document, blank_product, list_products, product_from_recipe, save_product, shipment_products,
)
from .shipment_repository import ShipmentError, list_shipment_recipes, recent_shipment_price


def shipment_choices(config, customer_id):
    products = {p["product_id"]: p for p in shipment_products(config, customer_id)}
    master_codes = {p["product_id"] for p in list_products(config, include_inactive=True)}
    choices = {r["recipe_id"]: product_from_recipe(r) for r in list_shipment_recipes(config, customer_id)
               if r["recipe_id"].upper() not in master_codes}
    choices.update(products)
    return choices


def item_price(config, document, code, unit, product):
    previous = recent_shipment_price(config, document["customer_id"], code, unit,
                                     shipment_date=document["shipment_date"], tax_mode=document["tax_mode"],
                                     exclude_id=document.get("id", ""))
    if previous:
        return str(previous["price"])
    if product["sales_unit"].upper() == unit.upper() and product["tax_mode"] == document["tax_mode"]:
        return product["standard_price"]
    return "0"


def complete_items(config, document, items, previous, *, choices=None):
    if choices is None:
        choices = shipment_choices(config, document["customer_id"])
    result = deepcopy(items)
    for index, item in enumerate(result):
        old = previous[index] if index < len(previous) else {}
        code = str(item.get("code") or "").strip()
        match = next((p for c, p in choices.items() if c.upper() == code.upper()), None)
        if not match or code == old.get("code"):
            continue
        for key, value in (("name", match["name"]), ("unit", match["sales_unit"]), ("notes", match["specification"])):
            if not item.get(key) or item.get(key) == old.get(key):
                item[key] = value
        same_price = item.get("price") == old.get("price")
        try:
            same_price = same_price or Decimal(str(item.get("price"))) == Decimal(str(old.get("price")))
        except InvalidOperation:
            pass
        if item.get("price", "") == "" or same_price:
            item["price"] = item_price(config, document, code, item["unit"], match)
    return result


def sync_shipment_products(config, conn, items, tax_mode):
    candidates = {}
    for item in items:
        code = item["code"].upper()
        value = (item["unit"].upper(), item["price"])
        if code in candidates and candidates[code] != value:
            raise ShipmentError("同貨品在本單有不同單位或單價，請改由貨品資料設定標準售價")
        candidates[code] = value
    for code, (unit, price) in candidates.items():
        entity = _mapping(conn.execute("SELECT * FROM products WHERE product_id=?", (code,)))
        item = next(i for i in items if i["code"].upper() == code)
        if entity:
            data = _document(entity)
            if data["lifecycle_status"] != "active":
                raise ShipmentError("已刪除貨品不可更新定價，請先恢復貨品")
            if data["sales_unit"].upper() != unit or data["tax_mode"] != tax_mode:
                raise ShipmentError("本單與貨品的單位或課稅方式不同，不可直接更新標準售價")
        else:
            recipe = _mapping(conn.execute("SELECT recipe_id,color,measurement_unit FROM recipes "
                                           "WHERE UPPER(recipe_id)=? AND lifecycle_status='active'", (code,)))
            data = product_from_recipe(recipe) if recipe else blank_product()
            data.update(product_id=code, name=item["name"], sales_unit=item["unit"],
                        base_unit=item["unit"], tax_mode=tax_mode)
        data["standard_price"] = price
        try:
            save_product(config, data, _connection=conn)
        except ProductError as exc:
            raise ShipmentError(str(exc)) from exc
