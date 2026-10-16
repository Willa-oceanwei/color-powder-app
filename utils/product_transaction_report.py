"""Read-only history of saved shipment lines for an exact product/recipe code."""

from datetime import date

from .customer_repository import _mappings
from .database import connect_from_config
from .shipment_repository import ShipmentError


def product_transactions(config, code, start=None, end=None):
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
    conditions = ["s.status='draft'", "UPPER(TRIM(json_extract(i.payload_json,'$.code')))=?"]
    args = [code]
    if start:
        conditions.append("s.shipment_date>=?")
        args.append(start)
    if end:
        conditions.append("s.shipment_date<=?")
        args.append(end)
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
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
