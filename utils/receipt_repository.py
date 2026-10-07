"""Optional shipment-linked receipts with atomic overpayment protection."""

from .customer_repository import _mapping, _mappings
from .database import connect_from_config, utc_now_iso
from .shipment_repository import ShipmentError, _valid_date, decimal_value


def save_receipt(config, *, receipt_id, shipment_id, shipment_version, receipt_date, amount,
                 method="匯款", reference="", notes=""):
    receipt_date = _valid_date(receipt_date, "收款日期")
    amount = decimal_value(amount, "收款金額")
    if not amount or amount != amount.to_integral_value():
        raise ShipmentError("收款金額須為大於零的整數元")
    if not receipt_id or not shipment_id or not str(method).strip():
        raise ShipmentError("請選擇出貨單及收款方式")
    amount = str(int(amount))
    reference, notes, method = str(reference).strip(), str(notes).strip(), str(method).strip()
    with connect_from_config(config) as conn:
        previous = _mapping(conn.execute("SELECT * FROM shipment_receipts WHERE id=?", (receipt_id,)))
        if previous:
            expected = dict(shipment_id=shipment_id, receipt_date=receipt_date, amount=amount,
                            method=method, reference=reference, notes=notes)
            if previous["status"] != "active" or any(previous[k] != value for k, value in expected.items()):
                raise ShipmentError("收款識別碼已使用，請重新開啟收款登錄")
            return previous
        now = utc_now_iso()
        changed = _mapping(conn.execute(
            "UPDATE shipment_orders SET version=version+1,updated_at=? WHERE id=? AND version=? AND status='draft' "
            "AND CAST(total_amount AS INTEGER) - (SELECT COALESCE(SUM(CAST(amount AS INTEGER)),0) "
            "FROM shipment_receipts WHERE shipment_id=? AND status='active') >= ? RETURNING id",
            (now, shipment_id, shipment_version, shipment_id, int(amount))))
        if not changed:
            raise ShipmentError("出貨單已變更、作廢或收款超過未收金額，請重新讀取")
        conn.execute("INSERT INTO shipment_receipts(id,shipment_id,receipt_date,amount,method,reference,notes,created_at,updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (receipt_id, shipment_id, receipt_date, amount, method, reference, notes, now, now))
        return _mapping(conn.execute("SELECT * FROM shipment_receipts WHERE id=?", (receipt_id,)))


def list_receipts(config, shipment_id):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute("SELECT * FROM shipment_receipts WHERE shipment_id=? ORDER BY receipt_date,created_at,id", (shipment_id,)))


def void_receipt(config, receipt_id, reason):
    if not str(reason).strip():
        raise ShipmentError("請填寫收款作廢原因")
    with connect_from_config(config) as conn:
        now = utc_now_iso()
        changed = _mapping(conn.execute("UPDATE shipment_receipts SET status='void',void_reason=?,updated_at=? "
                           "WHERE id=? AND status='active' RETURNING shipment_id", (str(reason).strip(), now, receipt_id)))
        if not changed:
            raise ShipmentError("收款紀錄不存在或已作廢")
        conn.execute("UPDATE shipment_orders SET version=version+1,updated_at=? WHERE id=?", (now, changed["shipment_id"]))
