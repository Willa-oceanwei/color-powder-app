"""Recipe defaults and explicit shipment-to-product price synchronization."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .customer_repository import _mapping, _mappings
from .database import connect_from_config
from .product_repository import (
    ProductError, _document, blank_product, product_from_recipe, save_product,
)
from .shipment_repository import ShipmentError, recent_shipment_price, shipment_price_history


def shipment_choices(config, customer_id, *, all_recipes=False):
    with connect_from_config(config) as conn:
        masters = _mappings(conn.execute("SELECT p.*,r.lifecycle_status AS recipe_status FROM products p LEFT JOIN recipes r ON r.recipe_id=p.recipe_id ORDER BY p.product_id"))
        recipes = _mappings(conn.execute("SELECT recipe_id,color,measurement_unit,customer_id FROM recipes WHERE lifecycle_status='active' ORDER BY recipe_id"))
        powders = _mappings(conn.execute("SELECT colorpowder_id,name,international_code,package FROM color_powders WHERE lifecycle_status='active' ORDER BY colorpowder_id"))
    products = {p["product_id"]: _document(p) for p in masters if customer_id and p["lifecycle_status"] == "active" and (not p["recipe_id"] or p["recipe_status"] == "active")}
    master_codes = {p["product_id"].upper() for p in masters}
    choices = {p["colorpowder_id"]: dict(blank_product(), product_id=p["colorpowder_id"], name=p["name"] or p["international_code"] or p["colorpowder_id"],
               sales_unit="KG", base_unit="KG", specification=p["package"] or "") for p in powders if p["colorpowder_id"].upper() not in master_codes}
    choices.update({r["recipe_id"]: dict(product_from_recipe(r), _recipe_customer=r["customer_id"] or "") for r in recipes
                    if r["recipe_id"].upper() not in master_codes and (all_recipes or customer_id and r["customer_id"] in (customer_id, "", None))})
    choices.update(products)
    return choices


def recent_item_defaults(history, code):
    return next((row for row in history if str(row["code"]).strip().upper() == code.strip().upper()), None)


def item_price(config, document, code, unit, product, *, history=None):
    previous = recent_shipment_price(config, document["customer_id"], code, unit,
                                     shipment_date=document["shipment_date"], tax_mode=document["tax_mode"],
                                     exclude_id=document.get("id", ""), history=history)
    if previous:
        return str(previous["price"])
    if product["sales_unit"].upper() == unit.upper() and product["tax_mode"] == document["tax_mode"]:
        return product["standard_price"]
    return "0"


def complete_items(config, document, items, previous, *, choices=None, history=None):
    if choices is None:
        choices = shipment_choices(config, document["customer_id"], all_recipes=True)
    if history is None:
        history = shipment_price_history(config, document["customer_id"], document["shipment_date"], document.get("id", ""))
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
            recent = recent_item_defaults(history, code) or {}
            for key, value in (("name", recent.get("name") or match["name"]), ("unit", recent.get("unit") or match["sales_unit"])):
                if not item.get(key) or item.get(key) == old.get(key):
                    item[key] = value
            if "tax_exempt" not in item or not item.get("tax_exempt"):
                item["tax_exempt"] = bool(recent.get("tax_exempt", False))
        same_price = item.get("price") == old.get("price")
        try:
            same_price = same_price or Decimal(str(item.get("price"))) == Decimal(str(old.get("price")))
        except InvalidOperation:
            pass
        if item.get("price", "") == "" or same_price:
            price_document = dict(document, tax_mode="免稅") if item.get("tax_exempt") else document
            item["price"] = item_price(config, price_document, code, item["unit"], match, history=history)
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
