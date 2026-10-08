"""Recipe defaults and explicit shipment-to-product price synchronization."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .customer_repository import _mapping
from .product_repository import (
    ProductError, _document, blank_product, list_products, product_from_recipe, save_product, shipment_products,
)
from .shipment_repository import ShipmentError, list_shipment_recipes, recent_shipment_price


def shipment_choices(config, customer_id, *, all_recipes=False):
    products = {p["product_id"]: p for p in shipment_products(config, customer_id)}
    master_codes = {p["product_id"] for p in list_products(config, include_inactive=True)}
    choices = {r["recipe_id"]: product_from_recipe(r) for r in list_shipment_recipes(config, None if all_recipes else customer_id)
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
        choices = shipment_choices(config, document["customer_id"], all_recipes=True)
    result = deepcopy(items)
    for index, item in enumerate(result):
        old = previous[index] if index < len(previous) else {}
        code = str(item.get("code") or "").strip()
        match = next((p for c, p in choices.items() if c.upper() == code.upper()), None)
        code_changed = code != old.get("code")
        unit_changed = str(item.get("unit") or "").strip().upper() != str(old.get("unit") or "").strip().upper()
        if not match or not (code_changed or unit_changed):
            continue
        if code_changed:
            for key, value in (("name", match["name"]), ("unit", match["sales_unit"])):
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
    # Customer prices live in shipment history; never overwrite the shared base price.
    candidates = {item["code"].upper(): item for item in reversed(items)}
    for code, item in candidates.items():
        entity = _mapping(conn.execute("SELECT * FROM products WHERE product_id=?", (code,)))
        if entity:
            data = _document(entity)
            if data["lifecycle_status"] != "active":
                raise ShipmentError("已刪除貨品不可更新定價，請先恢復貨品")
            continue
        else:
            recipe = _mapping(conn.execute("SELECT recipe_id,color,measurement_unit FROM recipes "
                                           "WHERE UPPER(recipe_id)=? AND lifecycle_status='active'", (code,)))
            data = product_from_recipe(recipe) if recipe else blank_product()
            data.update(product_id=code, name=item["name"], sales_unit=item["unit"],
                        base_unit=item["unit"], tax_mode=tax_mode)
        try:
            save_product(config, data, _connection=conn)
        except ProductError as exc:
            raise ShipmentError(str(exc)) from exc
