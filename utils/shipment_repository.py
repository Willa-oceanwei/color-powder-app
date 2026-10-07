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
    net = money(subtotal / (1 + rate)) if tax_mode == "內含" else subtotal
    tax = money(net * rate) if tax_mode == "外加" else subtotal - net if tax_mode == "內含" else Decimal(0)
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


def list_shipments(config, *, query="", start=None, end=None, include_void=False):
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
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(f"SELECT * FROM shipment_orders {where} ORDER BY shipment_date,shipment_number,id", tuple(args)))


def get_shipment(config, shipment_id):
    with connect_from_config(config) as conn:
        row = _mapping(conn.execute("SELECT * FROM shipment_orders WHERE id=?", (shipment_id,)))
        if not row:
            raise ShipmentError("出貨單不存在")
        result = json.loads(row.pop("payload_json"))
        result.update(row)
        result["items"] = [json.loads(item["payload_json"]) for item in _mappings(conn.execute(
            "SELECT payload_json FROM shipment_order_items WHERE shipment_id=? ORDER BY line_number", (shipment_id,)))]
        invoice = _mapping(conn.execute("SELECT payload_json FROM shipment_invoices WHERE shipment_id=?", (shipment_id,)))
        result["invoice"] = json.loads(invoice["payload_json"]) if invoice else blank_shipment()["invoice"]
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


def save_shipment(config, document):
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
    return get_shipment(config, shipment_id)


def void_shipment(config, shipment_id, version, reason):
    if not str(reason).strip():
        raise ShipmentError("請填寫作廢原因")
    with connect_from_config(config) as conn:
        changed = _mapping(conn.execute("""UPDATE shipment_orders SET status='void',void_reason=?,
                  version=version+1,updated_at=? WHERE id=? AND version=? AND status='draft' RETURNING id""",
                  (str(reason).strip(), utc_now_iso(), shipment_id, version)))
        if not changed:
            raise ShipmentError("單據已修改或作廢，請重新讀取")


def printable_shipment(document, *, show_prices=True):
    from .shipment_print import render_shipment_print
    return render_shipment_print(document, show_prices=show_prices)
