"""Recipe defaults and explicit shipment-to-product price synchronization."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .customer_repository import _mapping, _mappings
from .database import connect_from_config
from .product_repository import (
    ProductError, _document, blank_product, product_from_recipe, save_product,
)
from .shipment_repository import ShipmentError, recent_shipment_price, shipment_price_history
from .shipment_codes import display_code_options


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


def matching_products(choices, value, *, by_name=False, history=()):
    value = str(value or "").strip().upper()
    if not value:
        return []
    if not by_name:
        exact = [code for code in choices if code.upper() == value]
        if exact:
            return exact
        aliases = [code for code in choices if code.upper().startswith("C") and code[1:].upper() == value]
        if aliases:
            return aliases
        return [code for code in choices if value in code.upper()]
    names = {code: {str(product["name"]).upper()} for code, product in choices.items()}
    for row in history:
        code = next((c for c in choices if c.upper() == str(row["code"]).upper()), None)
        if code:
            names[code].add(str(row.get("name") or "").upper())
    exact = [code for code, values in names.items() if value in values]
    return exact or [code for code, values in names.items() if any(value in name for name in values)]


def item_price(config, document, code, unit, product, *, history=None, quotes=None):
    from .advance_price_repository import applicable_price, list_advance_prices
    if quotes is None:
        quotes = list_advance_prices(config, document["customer_id"]) if config is not None else []
    quote = applicable_price(quotes, document["customer_id"], code, unit, document["tax_mode"], document["shipment_date"])
    if quote:
        return quote["price"]
    previous = recent_shipment_price(config, document["customer_id"], code, unit,
                                     shipment_date=document["shipment_date"], tax_mode=document["tax_mode"],
                                     exclude_id=document.get("id", ""), history=history)
    if previous:
        return str(previous["price"])
    if product["sales_unit"].upper() == unit.upper() and product["tax_mode"] == document["tax_mode"]:
        return product["standard_price"]
    return "0"


def complete_items(config, document, items, previous, *, choices=None, history=None, quotes=None):
    from .advance_price_repository import list_advance_prices
    if quotes is None:
        quotes = list_advance_prices(config, document["customer_id"]) if config is not None else []
    if choices is None:
        choices = shipment_choices(config, document["customer_id"], all_recipes=True)
    if history is None:
        history = shipment_price_history(config, document["customer_id"], document["shipment_date"], document.get("id", ""))
    result = deepcopy(items)
    for index, item in enumerate(result):
        old = previous[index] if index < len(previous) else {}
        code = str(item.get("code") or "").strip()
        candidates = matching_products(choices, code) if code else matching_products(choices, item.get("name"), by_name=True, history=history)
        resolved = candidates[0] if len(candidates) == 1 else None
        match = choices.get(resolved)
        if match:
            code = resolved
            item["code"] = resolved
            if not str(items[index].get("code") or "").strip():
                item["name"] = (recent_item_defaults(history, code) or {}).get("name") or match["name"]
        code_changed = code != old.get("code")
        if item.get("display_code") and item["display_code"] not in display_code_options(code):
            item["display_code"] = ""
        unit_changed = str(item.get("unit") or "").strip().upper() != str(old.get("unit") or "").strip().upper()
        tax_changed = bool(quotes) and bool(item.get("tax_exempt")) != bool(old.get("tax_exempt"))
        if not match or not (code_changed or unit_changed or tax_changed):
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
            item["price"] = item_price(config, price_document, code, item["unit"], match, history=history, quotes=quotes)
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
