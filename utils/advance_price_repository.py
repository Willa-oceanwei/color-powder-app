"""Effective-dated customer prices; independent of accounting calculations."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from uuid import uuid4

from .customer_repository import _mapping, _mappings
from .database import connect_from_config, utc_now_iso
from .read_cache import cached_read, invalidate_read_cache


class AdvancePriceError(ValueError):
    pass


def business_today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def _quotes(conn, customer_id=""):
    condition = " WHERE q.customer_id=?" if customer_id else ""
    return _mappings(conn.execute(
        "SELECT q.*,COALESCE(NULLIF(c.short_name,''),c.name) AS customer_label,"
        "EXISTS(SELECT 1 FROM shipment_order_items i JOIN shipment_orders s ON s.id=i.shipment_id "
        "WHERE s.status='draft' AND json_extract(i.payload_json,'$.advance_price_id')=q.id) AS used,"
        "EXISTS(SELECT 1 FROM shipment_order_items i WHERE json_extract(i.payload_json,'$.advance_price_id')=q.id "
        "OR json_extract(i.payload_json,'$.advance_price_override_id')=q.id) AS referenced "
        "FROM advance_prices q LEFT JOIN customers c ON c.customer_id=q.customer_id" + condition +
        " ORDER BY q.effective_date DESC,q.created_at DESC,q.id", (customer_id,) if customer_id else ()))


@cached_read
def list_advance_prices(config, customer_id=""):
    with connect_from_config(config) as conn:
        return _quotes(conn, customer_id)


def scope(row):
    return (row.get("customer_id", ""), str(row.get("code", "")).strip().upper(),
            str(row.get("unit", "")).strip().upper(), row.get("tax_mode", "外加"))


def applicable_price(quotes, customer_id, code, unit, tax_mode, shipment_date):
    wanted = scope(dict(customer_id=customer_id, code=code, unit=unit, tax_mode=tax_mode))
    matches = [q for q in quotes if q["status"] == "active" and scope(q) == wanted
               and q["effective_date"] <= str(shipment_date or "")]
    return max(matches, key=lambda q: (q["effective_date"], q["created_at"], q["id"]), default=None)


def reminder_status(quote, quotes, today=None):
    today = str(today or business_today())
    if quote["status"] == "cancelled":
        return "已取消"
    if quote["effective_date"] > today:
        return "待生效"
    latest = applicable_price(quotes, *scope(quote), today)
    if latest and latest["id"] != quote["id"]:
        return "已被後續報價取代"
    return "已套用" if quote.get("used") else "已生效未出貨"


def save_advance_price(config, data):
    # Import locally so shipment persistence can use this module as a guard.
    from .shipment_repository import TAX_MODES, ShipmentError, decimal_value, _valid_date
    row = {k: str(data.get(k) if data.get(k) is not None else "").strip() for k in
           ("customer_id", "code", "name", "unit", "tax_mode", "price", "effective_date", "notes")}
    row["code"], row["unit"] = row["code"].upper(), row["unit"].upper()
    if not all(row[k] for k in ("customer_id", "code", "name", "unit")):
        raise AdvancePriceError("請選擇客戶、貨品並填寫銷售單位")
    if row["tax_mode"] not in TAX_MODES:
        raise AdvancePriceError("請選擇課稅方式")
    try:
        row["price"] = str(decimal_value(row["price"], "預告單價"))
        row["effective_date"] = _valid_date(row["effective_date"], "生效日期")
    except ShipmentError as exc:
        raise AdvancePriceError(str(exc)) from exc
    quote_id, now = data.get("id") or str(uuid4()), utc_now_iso()
    with connect_from_config(config) as conn:
        customer = _mapping(conn.execute("SELECT lifecycle_status FROM customers WHERE customer_id=?", (row["customer_id"],)))
        if not customer or customer["lifecycle_status"] != "active":
            raise AdvancePriceError("請選擇有效客戶")
        duplicate = _mapping(conn.execute(
            "SELECT id FROM advance_prices WHERE customer_id=? AND code=? AND unit=? AND tax_mode=? "
            "AND effective_date=? AND status='active' AND id!=?",
            (*scope(row), row["effective_date"], quote_id)))
        if duplicate:
            raise AdvancePriceError("同一客戶、貨品、單位及課稅方式在該日已有預告報價，請修改原紀錄")
        values = tuple(row.values())
        if data.get("id"):
            # Once referenced (even by a void shipment), preserve the quote snapshot.
            used = _mapping(conn.execute("SELECT shipment_id FROM shipment_order_items WHERE json_extract(payload_json,'$.advance_price_id')=? "
                                         "OR json_extract(payload_json,'$.advance_price_override_id')=? LIMIT 1", (quote_id, quote_id)))
            if used:
                raise AdvancePriceError("已使用的報價不可改寫，請新增下一次調價")
            saved = _mapping(conn.execute(
                "UPDATE advance_prices SET customer_id=?,code=?,name=?,unit=?,tax_mode=?,price=?,effective_date=?,notes=?,"
                "version=version+1,updated_at=? WHERE id=? AND version=? AND status='active' RETURNING *",
                (*values, now, quote_id, data.get("version"))))
            if not saved:
                raise AdvancePriceError("報價已被修改或取消，請重新讀取")
        else:
            saved = _mapping(conn.execute(
                "INSERT INTO advance_prices(id,customer_id,code,name,unit,tax_mode,price,effective_date,notes,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING *", (quote_id, *values, now, now)))
    invalidate_read_cache(config)
    return saved


def cancel_advance_price(config, quote_id, version, reason):
    if not str(reason).strip():
        raise AdvancePriceError("請填寫取消原因")
    with connect_from_config(config) as conn:
        changed = _mapping(conn.execute(
            "UPDATE advance_prices SET status='cancelled',cancel_reason=?,version=version+1,updated_at=? "
            "WHERE id=? AND version=? AND status='active' RETURNING id",
            (str(reason).strip(), utc_now_iso(), quote_id, version)))
        if not changed:
            raise AdvancePriceError("報價已被修改或取消，請重新讀取")
    invalidate_read_cache(config)


def same_price(left, right):
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError, TypeError):
        return False


def item_quote(quotes, document, item):
    mode = "免稅" if item.get("tax_exempt") else document["tax_mode"]
    return applicable_price(quotes, document["customer_id"], item.get("code"), item.get("unit"), mode, document["shipment_date"])


def unchanged_price_context(header, item, old_header, old_item):
    return (all(header.get(k) == old_header.get(k) for k in ("customer_id", "shipment_date", "tax_mode"))
            and all(item.get(k) == old_item.get(k) for k in ("code", "unit"))
            and bool(item.get("tax_exempt")) == bool(old_item.get("tax_exempt"))
            and same_price(item.get("price"), old_item.get("price")))


def guard_shipment_prices(conn, header, items, existing):
    """Validate against fresh prices in the shipment transaction; never reprice history."""
    quotes = _quotes(conn, header["customer_id"])
    old_header = json.loads(existing["payload_json"]) if existing else {}
    old_items = [json.loads(r["payload_json"]) for r in _mappings(conn.execute(
        "SELECT payload_json FROM shipment_order_items WHERE shipment_id=? ORDER BY line_number", (existing["id"],)))] if existing else []
    for index, item in enumerate(items):
        if index < len(old_items) and unchanged_price_context(header, item, old_header, old_items[index]):
            # Preserve the audit data as well when only quantity/notes are edited.
            for key in ("advance_price_id", "advance_price_version", "advance_price_override_reason", "advance_price_override_id", "advance_price_override_version"):
                if key in old_items[index]:
                    item[key] = old_items[index][key]
            continue
        for key in ("advance_price_id", "advance_price_version"):
            item.pop(key, None)
        quote = item_quote(quotes, header, item)
        if not quote:
            item.pop("advance_price_override_reason", None)
            continue
        if not same_price(item["price"], quote["price"]) and not str(item.get("advance_price_override_reason") or "").strip():
            from .shipment_repository import ShipmentError
            raise ShipmentError(f"第 {index + 1} 項已有 {quote['effective_date']} 生效報價 {quote['price']} / {quote['unit']}，請採用新價或填寫特殊議價原因")
        if same_price(item["price"], quote["price"]):
            item.pop("advance_price_override_reason", None)
            item.update(advance_price_id=quote["id"], advance_price_version=quote["version"])
        else:
            # Overrides do not clear the 'not yet used' reminder.
            item["advance_price_override_reason"] = str(item["advance_price_override_reason"]).strip()
            item.update(advance_price_override_id=quote["id"], advance_price_override_version=quote["version"])


def reprice_for_context(config, document, items, old_context, quotes, choices, history):
    """Reprice copied/new drafts and date/customer/tax changes, preserving manual edits otherwise."""
    from .shipment_catalog import item_price
    context = (document["customer_id"], document["shipment_date"], document["tax_mode"])
    if old_context == context or old_context is None and document.get("id"):
        return items
    old_quotes = list_advance_prices(config, old_context[0]) if old_context and old_context[0] and old_context[0] != context[0] else []
    result = deepcopy(items)
    for item in result:
        relevant = any(q["status"] == "active" and str(q["code"]).upper() == str(item.get("code", "")).upper()
                       and str(q["unit"]).upper() == str(item.get("unit", "")).upper()
                       for q in quotes + old_quotes)
        if not relevant:
            continue
        quote = item_quote(quotes, document, item)
        if quote:
            item["price"] = quote["price"]
        elif old_context is not None and item.get("code") in choices:
            price_doc = dict(document, tax_mode="免稅") if item.get("tax_exempt") else document
            item["price"] = item_price(config, price_doc, item["code"], item["unit"], choices[item["code"]], history=history, quotes=[])
        item.pop("advance_price_override_reason", None)
    return result
