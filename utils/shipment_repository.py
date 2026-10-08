"""Shipment documents, exact decimal calculations and atomic persistence."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

from .customer_repository import _mapping, _mappings
from .database import connect_from_config, utc_now_iso

TAX_MODES = ("外加", "內含", "免稅", "零稅率")
HEADER_FIELDS = ("shipment_date", "customer_id", "customer_name", "recipient_id", "recipient_name",
                 "address", "tax_mode", "tax_rate", "account_date", "payment_terms", "notes", "order_number", "number_mode",
                 "contact", "phone", "fax", "tax_id")
ITEM_FIELDS = ("code", "name", "quantity", "unit", "price", "order_number", "notes")
INVOICE_FIELDS = ("date", "number", "method", "type", "amount")


class ShipmentError(ValueError):
    pass


def decimal_value(value, label, *, maximum=None):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ShipmentError(f"{label}必須是有效數字") from None
    if not number.is_finite() or number < 0 or (maximum is not None and number > maximum):
        raise ShipmentError(f"{label}超出可用範圍")
    if number.as_tuple().exponent < -3:
        raise ShipmentError(f"{label}最多三位小數")
    if number > Decimal('1000000000000'):
        raise ShipmentError(f"{label}超出可用範圍")
    return number


def money(value):
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def item_exempt(item):
    value = item.get("tax_exempt", False)
    if value in (False, None, "", 0):
        return False
    if value in (True, 1):
        return True
    raise ShipmentError("品項免稅須為勾選或未勾選")


def calculate(items, tax_mode, tax_rate):
    if tax_mode not in TAX_MODES:
        raise ShipmentError("請選擇課稅類別")
    rate = decimal_value(tax_rate, "稅率", maximum=100) / 100
    lines = []
    for item in items:
        quantity = decimal_value(item.get("quantity"), "數量")
        price = decimal_value(item.get("price"), "單價")
        if quantity <= 0:
            raise ShipmentError("品項數量必須大於 0")
        lines.append(money(quantity * price))
    subtotal = sum(lines, Decimal(0))
    taxable = sum((amount for item, amount in zip(items, lines) if not item_exempt(item)), Decimal(0))
    tax = money(taxable * rate) if tax_mode == "外加" else taxable - money(taxable / (1 + rate)) if tax_mode == "內含" else Decimal(0)
    net = subtotal - tax if tax_mode == "內含" else subtotal
    return {"line_amounts": [str(x) for x in lines], "net_amount": str(net),
            "tax_amount": str(tax), "total_amount": str(net + tax)}


def blank_shipment():
    today = date.today().isoformat()
    return {"shipment_number": "", "number_mode": "date", "shipment_date": today, "customer_id": "", "customer_name": "",
            "recipient_id": "", "recipient_name": "", "address": "", "tax_mode": "外加", "tax_rate": "5",
            "account_date": today, "payment_terms": "", "notes": "", "order_number": "", "items": [],
            "invoice": {"date": "", "number": "", "method": "", "type": "", "amount": ""}}


def copy_shipment(document):
    result = blank_shipment()
    result.update({key: deepcopy(document.get(key, result.get(key, ""))) for key in HEADER_FIELDS})
    result["items"] = deepcopy(document["items"])
    result["number_mode"] = "date"
    return result


def list_shipment_recipes(config, customer_id=None):
    """Load sales-facing recipe fields without powder/component data."""
    if customer_id == "":
        return []
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT recipe_id,color,measurement_unit FROM recipes WHERE lifecycle_status='active' "
            "AND (? IS NULL OR customer_id=? OR COALESCE(customer_id,'')='') ORDER BY recipe_id", (customer_id, customer_id)))


def shipment_price_history(config, customer_id, shipment_date, exclude_id=""):
    """Load customer-scoped price rows once for an editing snapshot."""
    if not customer_id or not shipment_date:
        return []
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT json_extract(i.payload_json,'$.code') AS code,"
            "json_extract(i.payload_json,'$.unit') AS unit,json_extract(i.payload_json,'$.price') AS price,"
            "json_extract(i.payload_json,'$.name') AS name,COALESCE(json_extract(i.payload_json,'$.tax_exempt'),0) AS tax_exempt,"
            "CASE WHEN json_extract(i.payload_json,'$.tax_exempt')=1 THEN '免稅' ELSE json_extract(s.payload_json,'$.tax_mode') END AS tax_mode,s.shipment_number,s.shipment_date "
            "FROM shipment_orders s JOIN shipment_order_items i ON i.shipment_id=s.id "
            "WHERE s.status='draft' AND s.customer_id=? AND s.id<>? AND s.shipment_date<=? "
            "ORDER BY s.shipment_date DESC,s.created_at DESC,s.shipment_number DESC,i.line_number DESC",
            (customer_id, exclude_id or "", shipment_date)))


def customer_purchase_history(config, customer_id, code=""):
    """Saved non-void customer lines, across all dates and units."""
    customer_id, code = str(customer_id or "").strip(), str(code or "").strip()
    if not customer_id:
        return []
    condition = " AND UPPER(TRIM(json_extract(i.payload_json,'$.code')))=UPPER(?)" if code else ""
    args = (customer_id, code) if code else (customer_id,)
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT s.shipment_number,s.shipment_date,json_extract(i.payload_json,'$.code') AS code,"
            "json_extract(i.payload_json,'$.name') AS name,json_extract(i.payload_json,'$.quantity') AS quantity,"
            "json_extract(i.payload_json,'$.unit') AS unit,json_extract(i.payload_json,'$.price') AS price,"
            "json_extract(i.payload_json,'$.amount') AS amount,json_extract(i.payload_json,'$.order_number') AS order_number,"
            "CASE WHEN json_extract(i.payload_json,'$.tax_exempt')=1 THEN '免稅' ELSE json_extract(s.payload_json,'$.tax_mode') END AS tax_mode "
            "FROM shipment_orders s JOIN shipment_order_items i ON i.shipment_id=s.id "
            "WHERE s.status='draft' AND s.customer_id=?" + condition +
            " ORDER BY s.shipment_date DESC,s.created_at DESC,s.shipment_number DESC,i.line_number", args))


def recent_shipment_price(config, customer_id, code, unit, *, shipment_date, tax_mode, exclude_id="", history=None):
    """Use saved, non-void documents on or before the new shipment date."""
    if not all((customer_id, code, unit)):
        return None
    # Exempt and externally taxed lines both store a tax-exclusive unit price.
    compatible_modes = ("外加", "免稅", "零稅率") if tax_mode in ("外加", "免稅", "零稅率") else (tax_mode,)
    if history is not None:
        return next((row for row in history if str(row["code"]).strip().upper() == code.strip().upper()
                     and str(row["unit"]).strip().upper() == unit.strip().upper()
                     and row["tax_mode"] in compatible_modes), None)
    placeholders = ",".join("?" for _ in compatible_modes)
    with connect_from_config(config) as conn:
        return _mapping(conn.execute(
            "SELECT json_extract(i.payload_json,'$.price') AS price,s.shipment_number,s.shipment_date "
            "FROM shipment_orders s JOIN shipment_order_items i ON i.shipment_id=s.id "
            "WHERE s.status='draft' AND s.customer_id=? AND s.id<>? AND s.shipment_date<=? "
            "AND UPPER(TRIM(json_extract(i.payload_json,'$.code')))=UPPER(TRIM(?)) "
            "AND UPPER(TRIM(json_extract(i.payload_json,'$.unit')))=UPPER(TRIM(?)) "
            f"AND (CASE WHEN json_extract(i.payload_json,'$.tax_exempt')=1 THEN '免稅' ELSE json_extract(s.payload_json,'$.tax_mode') END) IN ({placeholders}) "
            "ORDER BY s.shipment_date DESC,s.created_at DESC,s.shipment_number DESC,i.line_number DESC LIMIT 1",
            (customer_id, exclude_id or "", shipment_date, code, unit, *compatible_modes)))


def _valid_date(value, label, optional=False):
    if optional and not value:
        return ""
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        raise ShipmentError(f"請填寫有效的{label}") from None


def _validated(document):
    header = {key: str(document.get(key) or "").strip() for key in HEADER_FIELDS}
    header["number_mode"] = document.get("number_mode") or ("manual" if document.get("shipment_number") else "date")
    if header["number_mode"] not in ("manual", "date"):
        raise ShipmentError("請選擇單號方式")
    header["shipment_date"] = _valid_date(header["shipment_date"], "出貨日期")
    header["account_date"] = _valid_date(header["account_date"], "帳款日期")
    if not header["customer_id"] or not header["customer_name"]:
        raise ShipmentError("請選擇客戶")
    items = []
    for source in document.get("items", []):
        item = {key: str(source.get(key) if source.get(key) is not None else "").strip() for key in ITEM_FIELDS}
        item["tax_exempt"] = item_exempt(source)
        if not all(item[key] for key in ("code", "name", "unit")):
            raise ShipmentError("每筆品項須填寫貨品編號、品名及單位")
        items.append(item)
    if not items:
        raise ShipmentError("至少需要一筆出貨品項")
    amounts = calculate(items, header["tax_mode"], header["tax_rate"])
    for item, amount in zip(items, amounts.pop("line_amounts")):
        item["amount"] = amount
    invoice = {key: str(document.get("invoice", {}).get(key) or "").strip() for key in INVOICE_FIELDS}
    invoice["date"] = _valid_date(invoice["date"], "發票日期", optional=not invoice["number"])
    if invoice["amount"]:
        invoice["amount"] = str(money(decimal_value(invoice["amount"], "發票金額")))
    return header, items, invoice, amounts


def list_shipments(config, *, query="", start=None, end=None, include_void=False, customer_start="", customer_end=""):
    if start:
        start = _valid_date(start, "起始出貨日期")
    if end:
        end = _valid_date(end, "結束出貨日期")
    if start and end and start > end:
        raise ShipmentError("起始日期不可晚於結束日期")
    customer_start, customer_end = str(customer_start or "").strip(), str(customer_end or "").strip()
    if customer_start and customer_end and customer_start > customer_end:
        raise ShipmentError("起始客戶編號不可大於結束編號")
    clauses, args = [], []
    if not include_void:
        clauses.append("status='draft'")
    if query:
        clauses.append("(shipment_number LIKE ? OR customer_id LIKE ? OR customer_name LIKE ? OR EXISTS "
                       "(SELECT 1 FROM shipment_order_items i WHERE i.shipment_id=shipment_orders.id "
                       "AND json_extract(i.payload_json,'$.code') LIKE ?))")
        args.extend([f"%{query}%"] * 4)
    for value, operator in ((start, ">="), (end, "<=")):
        if value:
            clauses.append(f"shipment_date {operator} ?")
            args.append(str(value))
    for value, operator in ((customer_start, ">="), (customer_end, "<=")):
        if value:
            clauses.append(f"customer_id {operator} ?")
            args.append(value)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(f"SELECT * FROM shipment_orders {where} ORDER BY shipment_date,shipment_number,id", tuple(args)))


def get_shipment(config, shipment_id):
    with connect_from_config(config) as conn:
        rows = _mappings(conn.execute(
            "SELECT s.*,i.payload_json AS item_payload,v.payload_json AS invoice_payload "
            "FROM shipment_orders s LEFT JOIN shipment_order_items i ON i.shipment_id=s.id "
            "LEFT JOIN shipment_invoices v ON v.shipment_id=s.id WHERE s.id=? ORDER BY i.line_number", (shipment_id,)))
        if not rows:
            raise ShipmentError("出貨單不存在")
        row = dict(rows[0])
        invoice = row.pop("invoice_payload")
        row.pop("item_payload")
        result = json.loads(row.pop("payload_json"))
        result.update(row)
        result["items"] = [json.loads(item["item_payload"]) for item in rows if item["item_payload"] is not None]
        result["invoice"] = json.loads(invoice) if invoice else blank_shipment()["invoice"]
        return result


def _next_number(conn, shipment_date):
    prefix = date.fromisoformat(shipment_date).strftime("%y%m%d")
    # Reserve in the same transaction as the document; include manual/void numbers.
    row = _mapping(conn.execute("""SELECT COALESCE(MAX(CAST(substr(shipment_number,7,4) AS INTEGER)),0) AS maximum
                   FROM shipment_orders WHERE length(shipment_number)=10 AND shipment_number LIKE ?
                   AND shipment_number NOT GLOB '*[^0-9]*'""", (prefix + "%",)))
    reserved = _mapping(conn.execute("""INSERT INTO shipment_number_sequences(date_prefix,last_number) VALUES (?,?)
                         ON CONFLICT(date_prefix) DO UPDATE SET last_number=MAX(last_number+1,excluded.last_number)
                         RETURNING last_number""", (prefix, int(row["maximum"]) + 1)))
    if reserved["last_number"] > 9999:
        raise ShipmentError("當日流水號已滿 9999 筆，請使用手動單號")
    return prefix + f"{reserved['last_number']:04d}"


def save_shipment(config, document, *, sync_products=False):
    header, items, invoice, amounts = _validated(document)
    shipment_id, now = document.get("id") or str(uuid4()), utc_now_iso()
    number = str(document.get("shipment_number") or "").strip()
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM shipment_orders WHERE id=?", (shipment_id,)))
        if document.get("id") and not existing:
            raise ShipmentError("原出貨單已不存在，不能另存為新單")
        if existing and existing["status"] != "draft":
            raise ShipmentError("已作廢出貨單不可修改")
        if existing and existing["version"] != document.get("version"):
            raise ShipmentError("單據已被其他人修改或作廢，請取消編輯後重新讀取")
        if existing:
            receipts = _mapping(conn.execute("SELECT COALESCE(SUM(CAST(amount AS INTEGER)),0) AS paid "
                               "FROM shipment_receipts WHERE shipment_id=? AND status='active'", (shipment_id,)))
            if receipts["paid"] and (header["customer_id"] != existing["customer_id"]
                                     or Decimal(amounts["total_amount"]) < receipts["paid"]):
                raise ShipmentError("已有收款，不可變更客戶或將總額減至已收款以下；請先作廢相關收款")
        if header["number_mode"] == "date":
            prior_mode = json.loads(existing["payload_json"]).get("number_mode", "manual") if existing else None
            if existing and prior_mode == "date" and header["shipment_date"] == existing["shipment_date"]:
                number = existing["shipment_number"]
            else:
                number = _next_number(conn, header["shipment_date"])
        elif not number:
            raise ShipmentError("請輸入出貨單號")
        if len(number) > 40 or any(char in number for char in ('/', '\\', '\n', '\r')):
            raise ShipmentError("出貨單號最多 40 字，不能含斜線或換行")
        duplicate = _mapping(conn.execute("SELECT id FROM shipment_orders WHERE shipment_number=? AND id!=?", (number, shipment_id)))
        if duplicate:
            raise ShipmentError("出貨單號已存在，請使用其他單號")
        if not existing or existing["customer_id"] != header["customer_id"]:
            customer = _mapping(conn.execute("SELECT name,lifecycle_status FROM customers WHERE customer_id=?", (header["customer_id"],)))
            if not customer or customer["lifecycle_status"] != "active":
                raise ShipmentError("請選擇有效客戶")
            header["customer_name"] = customer["name"]
        if existing:
            if existing["status"] != "draft":
                raise ShipmentError("已作廢出貨單不可修改")
            changed = _mapping(conn.execute(
                """UPDATE shipment_orders SET shipment_number=?,shipment_date=?,customer_id=?,customer_name=?,payload_json=?,
                   net_amount=?,tax_amount=?,total_amount=?,version=version+1,updated_at=?
                   WHERE id=? AND version=? AND status='draft' RETURNING id""",
                (number, header["shipment_date"], header["customer_id"], header["customer_name"], json.dumps(header, ensure_ascii=False),
                 amounts["net_amount"], amounts["tax_amount"], amounts["total_amount"], now, shipment_id, document.get("version"))))
            if not changed:
                raise ShipmentError("單據已被其他人修改，請取消編輯後重新讀取")
        else:
            if document.get("id"):
                raise ShipmentError("原出貨單已不存在，不能另存為新單")
            conn.execute("""INSERT INTO shipment_orders(id,shipment_number,shipment_date,customer_id,customer_name,
                         payload_json,net_amount,tax_amount,total_amount,created_at,updated_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         (shipment_id, number, header["shipment_date"], header["customer_id"], header["customer_name"],
                          json.dumps(header, ensure_ascii=False), amounts["net_amount"], amounts["tax_amount"], amounts["total_amount"], now, now))
        conn.execute("DELETE FROM shipment_order_items WHERE shipment_id=?", (shipment_id,))
        for line, item in enumerate(items, 1):
            conn.execute("INSERT INTO shipment_order_items VALUES (?,?,?)", (shipment_id, line, json.dumps(item, ensure_ascii=False)))
        owner = _mapping(conn.execute("SELECT shipment_id FROM shipment_invoices WHERE invoice_number=? AND shipment_id!=?",
                                      (invoice["number"], shipment_id))) if invoice["number"] else None
        if owner:
            raise ShipmentError("此發票編號已用於其他出貨單；第一版採一單一張發票")
        conn.execute("""INSERT INTO shipment_invoices(shipment_id,invoice_number,payload_json) VALUES (?,?,?)
                     ON CONFLICT(shipment_id) DO UPDATE SET invoice_number=excluded.invoice_number,payload_json=excluded.payload_json""",
                     (shipment_id, invoice["number"] or None, json.dumps(invoice, ensure_ascii=False)))
        if sync_products:
            from .shipment_catalog import sync_shipment_products
            sync_shipment_products(config, conn, items, header["tax_mode"])
    return get_shipment(config, shipment_id)


def void_shipment(config, shipment_id, version, reason):
    if not str(reason).strip():
        raise ShipmentError("請填寫作廢原因")
    with connect_from_config(config) as conn:
        changed = _mapping(conn.execute("""UPDATE shipment_orders SET status='void',void_reason=?,
                  version=version+1,updated_at=? WHERE id=? AND version=? AND status='draft'
                  AND NOT EXISTS (SELECT 1 FROM shipment_receipts r WHERE r.shipment_id=shipment_orders.id AND r.status='active') RETURNING id""",
                  (str(reason).strip(), utc_now_iso(), shipment_id, version)))
        if not changed:
            raise ShipmentError("單據已修改、作廢或有收款紀錄；請重新讀取，已有收款須先作廢收款")


def printable_shipment(document, *, show_prices=True, orientation="landscape"):
    from .shipment_print import render_shipment_print
    return render_shipment_print(document, show_prices=show_prices, orientation=orientation)
