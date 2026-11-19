"""Sales returns linked to saved shipment lines."""

import json
from collections import defaultdict
from decimal import Decimal

from .customer_repository import _mapping, _mappings
from .database import connect_from_config, utc_now_iso
from .shipment_repository import ShipmentError, _valid_date, calculate, decimal_value, is_blank_price, money


def list_sales_returns(config, shipment_id):
    with connect_from_config(config) as conn:
        rows = _mappings(conn.execute(
            "SELECT * FROM sales_returns WHERE shipment_id=? ORDER BY source_version DESC",
            (shipment_id,),
        ))
    for row in rows:
        row["items"] = json.loads(row.pop("items_json"))
    return rows


def returned_quantities(returns):
    totals = defaultdict(Decimal)
    for record in returns:
        if record["status"] == "active":
            for item in record["items"]:
                totals[item["line_number"]] += Decimal(item["quantity"])
    return totals


def _remaining_amounts(items, returned, header):
    remaining = [dict(item, quantity=quantity) for number, item in items.items()
                 if (quantity := Decimal(item["quantity"]) - returned[number]) > 0]
    return calculate(remaining, header["tax_mode"], header["tax_rate"])


def _save_return(conn, return_id, shipment_id, shipment_version, return_date, reason, requested):
    now = utc_now_iso()
    shipment = _mapping(conn.execute(
        "UPDATE shipment_orders SET version=version+1,updated_at=? "
        "WHERE id=? AND version=? AND status='draft' RETURNING *",
        (now, shipment_id, shipment_version),
    ))
    if not shipment:
        raise ShipmentError("原出貨單已變更或作廢，請重新讀取後再登錄")
    if return_date < shipment["shipment_date"]:
        raise ShipmentError("退回日期不可早於原出貨日期")
    previous = _mappings(conn.execute(
        "SELECT return_date,items_json,status FROM sales_returns WHERE shipment_id=? AND status='active' "
        "ORDER BY source_version DESC", (shipment_id,),
    ))
    if previous and return_date < previous[0]["return_date"]:
        raise ShipmentError("退回日期不可早於這張出貨單最近一筆有效退回")
    for record in previous:
        record["items"] = json.loads(record["items_json"])
    returned = returned_quantities(previous)
    items = {row["line_number"]: json.loads(row["payload_json"]) for row in _mappings(conn.execute(
        "SELECT line_number,payload_json FROM shipment_order_items WHERE shipment_id=? ORDER BY line_number",
        (shipment_id,),
    ))}
    header = json.loads(shipment["payload_json"])
    before = _remaining_amounts(items, returned, header)
    lines = []
    for number, quantity in requested.items():
        item = items.get(number)
        if item is None or quantity > Decimal(item["quantity"]) - returned[number]:
            raise ShipmentError("退回數量不可超過原出貨品項剩餘可退數量")
        available = Decimal(item["quantity"]) - returned[number]
        amount = ""
        if not is_blank_price(item["price"]):
            price = Decimal(item["price"])
            amount = str(money(available * price) - money((available - quantity) * price))
        returned[number] += quantity
        lines.append(dict(item, line_number=number, quantity=str(quantity), amount=amount))
    after = _remaining_amounts(items, returned, header)
    amounts = [str(Decimal(before[key]) - Decimal(after[key])) for key in ("net_amount", "tax_amount", "total_amount")]
    prefix = "SR" + return_date.replace("-", "")
    serial = conn.execute(
        "SELECT COALESCE(MAX(CAST(substr(return_number,11) AS INTEGER)),0)+1 FROM sales_returns "
        "WHERE return_date=?", (return_date,),
    ).fetchone()[0]
    number = f"{prefix}{serial:04d}"
    return _mapping(conn.execute(
        "INSERT INTO sales_returns(id,shipment_id,source_version,shipment_number,return_number,return_date,reason,"
        "items_json,net_amount,tax_amount,total_amount,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING *",
        (return_id, shipment_id, shipment["version"], shipment["shipment_number"], number, return_date, reason,
         json.dumps(lines, ensure_ascii=False), *amounts, now, now),
    ))


def save_sales_return(config, *, return_id, shipment_id, shipment_version, return_date, reason, quantities):
    return_date = _valid_date(return_date, "退回日期")
    reason = str(reason or "").strip()
    if not return_id or not shipment_id or not reason:
        raise ShipmentError("請選擇原出貨單並填寫退回原因")
    requested = {number: decimal_value(value, "退回數量") for number, value in quantities.items()}
    requested = {number: quantity for number, quantity in sorted(requested.items()) if quantity > 0}
    if not requested:
        raise ShipmentError("請輸入至少一項退回數量")
    with connect_from_config(config) as conn:
        existing = _mapping(conn.execute("SELECT * FROM sales_returns WHERE id=?", (return_id,)))
        if existing:
            saved = {item["line_number"]: Decimal(item["quantity"]) for item in json.loads(existing["items_json"])}
            if (existing["status"], existing["shipment_id"], existing["return_date"], existing["reason"], saved) != (
                    "active", shipment_id, return_date, reason, requested):
                raise ShipmentError("退回識別碼已使用，請重新開啟退回登錄")
            return existing
        record = _save_return(conn, return_id, shipment_id, shipment_version, return_date, reason, requested)
    return record


def void_sales_return(config, return_id, shipment_version, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise ShipmentError("請填寫作廢原因")
    with connect_from_config(config) as conn:
        now = utc_now_iso()
        shipment = _mapping(conn.execute(
            "UPDATE shipment_orders SET version=version+1,updated_at=? "
            "WHERE version=? AND status='draft' AND id=(SELECT shipment_id FROM sales_returns WHERE id=?) RETURNING id",
            (now, shipment_version, return_id),
        ))
        if not shipment:
            raise ShipmentError("退回單不存在或原出貨單已變更，請重新讀取")
        changed = _mapping(conn.execute(
            "UPDATE sales_returns SET status='void',void_reason=?,updated_at=? "
            "WHERE id=? AND status='active' AND source_version=(SELECT MAX(source_version) FROM sales_returns "
            "WHERE shipment_id=? AND status='active') RETURNING id",
            (reason, now, return_id, shipment["id"]),
        ))
        if not changed:
            raise ShipmentError("僅可作廢同一張出貨單的最後一筆有效退回")
