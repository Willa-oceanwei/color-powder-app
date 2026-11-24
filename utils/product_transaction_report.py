"""Read-only shipment history, with optional letter-suffix code families."""

from datetime import date
from decimal import Decimal
import re

from .customer_repository import _mappings
from .database import connect_from_config
from .scheduled_quote_repository import list_scheduled_quotes, quote_today
from .shipment_repository import ShipmentError, is_blank_price


def _code_family(code):
    match = re.fullmatch(r"(.*\d)[A-Z]*", code)
    return match.group(1) if match else None


def product_transactions(config, code, start=None, end=None, *, include_prior=False, include_related=False):
    code = str(code or "").strip().upper()
    if not code:
        raise ShipmentError("請輸入貨品／配方編號")
    try:
        start = date.fromisoformat(str(start)).isoformat() if start else None
        end = date.fromisoformat(str(end)).isoformat() if end else None
    except ValueError as error:
        raise ShipmentError("請輸入有效的出貨日期") from error
    if start and end and start > end:
        raise ShipmentError("起始日期不可晚於結束日期")
    base = _code_family(code)
    search_family = include_related and base is not None
    code_expression = "UPPER(TRIM(json_extract(i.payload_json,'$.code')))"
    if search_family:
        prefix = base.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions = ["s.status='draft'", code_expression + " LIKE ? ESCAPE '\\'"]
        args = [prefix + "%"]
    else:
        conditions = ["s.status='draft'", code_expression + "=?"]
        args = [code]
    if start and not include_prior:
        conditions.append("s.shipment_date>=?")
        args.append(start)
    if end and not include_prior:
        conditions.append("s.shipment_date<=?")
        args.append(end)
    with connect_from_config(config) as conn:
        rows = _mappings(conn.execute(
            "SELECT s.id AS shipment_id,s.shipment_number,s.shipment_date,s.customer_id,s.customer_name,"
            "s.created_at,i.line_number,json_extract(i.payload_json,'$.code') AS code,"
            "json_extract(i.payload_json,'$.name') AS name,json_extract(i.payload_json,'$.quantity') AS quantity,"
            "json_extract(i.payload_json,'$.unit') AS unit,json_extract(i.payload_json,'$.price') AS price,"
            "json_extract(i.payload_json,'$.amount') AS amount,json_extract(i.payload_json,'$.order_number') AS order_number,"
            "json_extract(i.payload_json,'$.notes') AS notes,"
            "CASE WHEN json_extract(i.payload_json,'$.tax_exempt')=1 THEN '免稅' "
            "ELSE json_extract(s.payload_json,'$.tax_mode') END AS tax_mode "
            "FROM shipment_orders s JOIN shipment_order_items i ON i.shipment_id=s.id WHERE "
            + " AND ".join(conditions)
            + " ORDER BY s.shipment_date DESC,s.created_at DESC,s.shipment_number DESC,s.id,i.line_number", args))
    if search_family:
        # Suffix letters belong to the same family; P10 is not a variant of P1.
        family = re.compile(re.escape(base) + r"[A-Z]*")
        rows = [row for row in rows if family.fullmatch(str(row["code"]).strip().upper())]
    return rows


def _chronological_transactions(rows):
    return sorted(rows, key=lambda row: (
        row["shipment_date"], row["created_at"], row["shipment_number"],
        row["shipment_id"], row["line_number"],
    ))


def product_price_changes(rows):
    """Compare chronological sales within each customer/unit/tax group using exact decimals."""
    previous = {}
    changes = []
    for row in _chronological_transactions(rows):
        if is_blank_price(row["price"]):
            continue
        group = (str(row["code"]).strip().upper(), row["customer_id"],
                 str(row["unit"] or "").strip(), row["tax_mode"])
        price = Decimal(str(row["price"]))
        old_price = previous.get(group)
        if old_price is None or price != old_price:
            changes.append(dict(row,
                price_event="初始售價" if old_price is None else "調漲" if price > old_price else "調降",
                previous_price="—" if old_price is None else format(old_price.normalize(), "f"),
                price_change="—" if old_price is None else format(price - old_price, "+f"),
            ))
        previous[group] = price
    return list(reversed(changes))


def product_price_notices(config, code, rows):
    """Link dated quotes without treating ordinary sale-price changes as official adjustments."""
    code = code.strip().upper()
    base = _code_family(code)
    family = re.compile(re.escape(base or code) + (r"[A-Z]*" if base else ""))
    cutoff = quote_today().isoformat()
    daily_quotes = {}
    for quote in list_scheduled_quotes(config, product_code_prefix=base or code):
        if quote["effective_date"] <= cutoff and family.fullmatch(quote["product_code"]):
            identity = (quote["product_code"], quote["customer_id"], quote["unit"], quote["tax_mode"])
            # Quotes arrive newest first; the last recorded price for a day wins.
            daily_quotes.setdefault((identity, quote["effective_date"]), quote)

    first_sales = {}
    for row in _chronological_transactions(rows):
        if not is_blank_price(row["price"]):
            identity = (row["code"].strip().upper(), row["customer_id"],
                        str(row["unit"] or "").strip().upper(), row["tax_mode"])
            first_sales.setdefault(identity, row)

    notices = []
    previous_quotes = {}
    for (identity, effective_date), quote in sorted(daily_quotes.items(), key=lambda entry: entry[0][1]):
        price = Decimal(quote["price"])
        first_sale = first_sales.get(identity)
        original = previous_quotes.get(identity)
        if original is None and first_sale and first_sale["shipment_date"] < effective_date:
            original = Decimal(str(first_sale["price"]))
        if identity not in previous_quotes or original != price:
            adjusted = original is not None and original != price
            notices.append(dict(code=identity[0], customer_id=identity[1], unit=identity[2], tax_mode=identity[3],
                                customer_name=quote["customer_short_name"] or quote["customer_name"],
                                date=effective_date, price=price, previous_price=original if adjusted else None,
                                kind="價格調整" if adjusted else "報價生效"))
        previous_quotes[identity] = price

    for identity, row in first_sales.items():
        if identity not in previous_quotes:
            notices.append(dict(code=identity[0], customer_id=identity[1], unit=identity[2], tax_mode=identity[3],
                                customer_name=row["customer_name"], date=row["shipment_date"],
                                price=Decimal(str(row["price"])), previous_price=None, kind="最早成交價"))
    return sorted(notices, key=lambda item: (item["kind"] == "價格調整", item["kind"] == "報價生效", item["date"]),
                  reverse=True)
