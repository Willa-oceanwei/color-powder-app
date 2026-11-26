"""Read-only shipment history with optional recipe code variants."""

from datetime import date
from decimal import Decimal
import json
import re
from collections import defaultdict

from .customer_repository import _mappings
from .database import connect_from_config
from .read_cache import cached_read
from .scheduled_quote_repository import list_scheduled_quotes, quote_today
from .shipment_repository import ShipmentError, is_blank_price


def _code_family(code, *, expanded=False):
    suffix = r"[A-Z]*(?:-[0-9]+)?" if expanded else r"[A-Z]*"
    match = re.fullmatch(r"(.*?\d)" + suffix, code)
    if not match:
        return None
    base = match[1]
    if expanded and re.fullmatch(r"[0-9]{5}", base):
        # Five-digit recipes with the same last four digits share the expanded family.
        glob_prefix = regex_prefix = "[0-9]" + base[1:]
    else:
        glob_prefix = re.sub(r"[\[*?]", r"[\g<0>]", base)
        regex_prefix = re.escape(base)
    return glob_prefix + "*", re.compile(regex_prefix + suffix)


@cached_read
def _expanded_recipe_codes(config, code):
    """Follow saved original-recipe links in both directions, including chains."""
    with connect_from_config(config) as conn:
        links = conn.execute(
            "SELECT UPPER(TRIM(recipe_id)), UPPER(TRIM(original_recipe)) "
            "FROM recipes WHERE TRIM(original_recipe) <> ''"
        ).fetchall()
    linked_codes = defaultdict(set)
    for recipe, original in links:
        linked_codes[original].add(recipe)
        linked_codes[recipe].add(original)

    related = {code}
    if family := _code_family(code, expanded=True):
        pattern = family[1]
        related.update(value for value in linked_codes if pattern.fullmatch(value))
    remaining = list(related)
    while remaining:
        new = linked_codes[remaining.pop()] - related
        related.update(new)
        remaining.extend(new)
    return tuple(sorted(related))


def product_transactions(config, code, start=None, end=None, *, include_prior=False,
                         include_related=False, expand_family=False):
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
    family = _code_family(code, expanded=expand_family) if include_related or expand_family else None
    code_expression = "UPPER(TRIM(json_extract(i.payload_json,'$.code')))"
    related = set(_expanded_recipe_codes(config, code)) if expand_family else {code}
    if expand_family:
        conditions = ["s.status='draft'", f"({code_expression} GLOB ? OR "
                      f"{code_expression} IN (SELECT value FROM json_each(?)))"]
        args = [family[0] if family else None, json.dumps(sorted(related))]
    elif family:
        conditions = ["s.status='draft'", code_expression + " GLOB ?"]
        args = [family[0]]
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
    if family:
        pattern = family[1]
        rows = [row for row in rows if (key := str(row["code"]).strip().upper()) in related or pattern.fullmatch(key)]
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


def product_price_notices(config, code, rows, *, expand_family=False):
    """Link dated quotes without treating ordinary sale-price changes as official adjustments."""
    code = code.strip().upper()
    scope = _code_family(code, expanded=expand_family)
    glob, family = scope if scope else (None, re.compile(re.escape(code)))
    related = _expanded_recipe_codes(config, code) if expand_family else ()
    if glob or related:
        quotes = list_scheduled_quotes(config, product_code_glob=glob, related_product_codes=related)
    else:
        quotes = list_scheduled_quotes(config, product_code_prefix=code)
    cutoff = quote_today().isoformat()
    daily_quotes = {}
    for quote in quotes:
        if quote["effective_date"] <= cutoff and (quote["product_code"] in related or family.fullmatch(quote["product_code"])):
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
