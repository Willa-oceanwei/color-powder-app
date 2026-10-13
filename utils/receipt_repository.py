"""Optional shipment-linked receipts with atomic overpayment protection."""

import json
from uuid import NAMESPACE_URL, uuid5

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
        if _mapping(conn.execute("SELECT batch_id FROM receipt_batch_allocations WHERE receipt_id=?", (receipt_id,))):
            raise ShipmentError("此筆屬於批次收款，請到月結／批次收款作廢整批紀錄")
        now = utc_now_iso()
        changed = _mapping(conn.execute("UPDATE shipment_receipts SET status='void',void_reason=?,updated_at=? "
                           "WHERE id=? AND status='active' RETURNING shipment_id", (str(reason).strip(), now, receipt_id)))
        if not changed:
            raise ShipmentError("收款紀錄不存在或已作廢")
        conn.execute("UPDATE shipment_orders SET version=version+1,updated_at=? WHERE id=?", (now, changed["shipment_id"]))


def outstanding_shipments(config, customer_id):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT s.id,s.shipment_number,s.shipment_date,s.version,s.total_amount,"
            "CAST(s.total_amount AS INTEGER)-COALESCE(SUM(CASE WHEN r.status='active' THEN CAST(r.amount AS INTEGER) ELSE 0 END),0) AS balance "
            "FROM shipment_orders s LEFT JOIN shipment_receipts r ON r.shipment_id=s.id "
            "WHERE s.customer_id=? AND s.status='draft' GROUP BY s.id HAVING balance>0 "
            "ORDER BY s.shipment_date,s.shipment_number,s.id", (customer_id,)))


def _allocation_values(allocations):
    result, seen = [], set()
    for allocation in allocations:
        amount = decimal_value(allocation['amount'], '沖抵金額')
        if amount != amount.to_integral_value():
            raise ShipmentError("沖抵金額須為整數元")
        if not amount:
            continue
        shipment_id = allocation['shipment_id']
        if not shipment_id or shipment_id in seen:
            raise ShipmentError("沖抵出貨單不可重複")
        seen.add(shipment_id)
        result.append(dict(shipment_id=shipment_id, shipment_version=int(allocation['shipment_version']), amount=int(amount)))
    return sorted(result, key=lambda row: row['shipment_id'])


def _apply_batch_allocations(conn, batch, allocations, request_id, allocation_date):
    now = utc_now_iso()
    for row in allocations:
        changed = _mapping(conn.execute(
            "UPDATE shipment_orders SET version=version+1,updated_at=? "
            "WHERE id=? AND customer_id=? AND version=? AND status='draft' "
            "AND shipment_date<=? AND CAST(total_amount AS INTEGER)-(SELECT COALESCE(SUM(CAST(amount AS INTEGER)),0) "
            "FROM shipment_receipts WHERE shipment_id=? AND status='active')>=? RETURNING id",
            (now, row['shipment_id'], batch['customer_id'], row['shipment_version'], allocation_date, row['shipment_id'], row['amount'])))
        if not changed:
            raise ShipmentError("出貨單已變更、作廢、日期晚於收款日期或沖抵超過未收金額，請重新讀取")
        receipt_id = str(uuid5(NAMESPACE_URL, json.dumps([batch['id'], request_id, row['shipment_id']])))
        conn.execute("INSERT INTO shipment_receipts(id,shipment_id,receipt_date,amount,method,reference,notes,created_at,updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (receipt_id, row['shipment_id'], allocation_date, str(row['amount']),
                     batch['method'], batch['reference'], batch['notes'], now, now))
        conn.execute("INSERT INTO receipt_batch_allocations(receipt_id,batch_id,request_id) VALUES (?,?,?)",
                     (receipt_id, batch['id'], request_id))


def save_receipt_batch(config, *, batch_id, customer_id, receipt_date, amount, allocations,
                       method='匯款', reference='', notes=''):
    receipt_date = _valid_date(receipt_date, '收款日期')
    amount = decimal_value(amount, '收款金額')
    if not amount or amount != amount.to_integral_value() or not batch_id or not str(method).strip():
        raise ShipmentError("請填寫大於零的整數收款金額及收款方式")
    allocations = _allocation_values(allocations)
    if sum(row['amount'] for row in allocations) > amount:
        raise ShipmentError("沖抵合計不可超過本次收款金額")
    values = dict(customer_id=customer_id, receipt_date=receipt_date, amount=str(int(amount)),
                  method=str(method).strip(), reference=str(reference).strip(), notes=str(notes).strip())
    signature = json.dumps(dict(values, allocations=allocations), sort_keys=True, ensure_ascii=False)
    with connect_from_config(config) as conn:
        previous = _mapping(conn.execute("SELECT * FROM receipt_batches WHERE id=?", (batch_id,)))
        if previous:
            if previous['status'] != 'active' or previous['request_json'] != signature:
                raise ShipmentError("收款識別碼已使用，請重新開啟收款登錄")
            return previous
        if not _mapping(conn.execute("SELECT customer_id FROM customers WHERE customer_id=?", (customer_id,))):
            raise ShipmentError("請選擇有效客戶")
        now = utc_now_iso()
        conn.execute("INSERT INTO receipt_batches(id,customer_id,receipt_date,amount,method,reference,notes,request_json,created_at,updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", (batch_id, *values.values(), signature, now, now))
        batch = dict(values, id=batch_id)
        _apply_batch_allocations(conn, batch, allocations, batch_id, receipt_date)
        return _mapping(conn.execute("SELECT * FROM receipt_batches WHERE id=?", (batch_id,)))


def list_receipt_batches(config, customer_id):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT b.*,COALESCE(SUM(CASE WHEN r.status='active' THEN CAST(r.amount AS INTEGER) ELSE 0 END),0) AS allocated "
            "FROM receipt_batches b LEFT JOIN receipt_batch_allocations a ON a.batch_id=b.id "
            "LEFT JOIN shipment_receipts r ON r.id=a.receipt_id WHERE b.customer_id=? GROUP BY b.id "
            "ORDER BY b.receipt_date DESC,b.created_at DESC,b.id", (customer_id,)))


def receipt_batch_details(config, batch_id):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT r.*,s.shipment_number,s.shipment_date FROM receipt_batch_allocations a "
            "JOIN shipment_receipts r ON r.id=a.receipt_id JOIN shipment_orders s ON s.id=r.shipment_id "
            "WHERE a.batch_id=? ORDER BY r.receipt_date,s.shipment_date,s.shipment_number", (batch_id,)))


def apply_prepaid_batch(config, *, batch_id, batch_version, request_id, allocation_date, allocations):
    allocation_date = _valid_date(allocation_date, '沖帳日期')
    allocations = _allocation_values(allocations)
    if not request_id or not allocations:
        raise ShipmentError("請輸入本次沖抵金額")
    with connect_from_config(config) as conn:
        batch = _mapping(conn.execute("SELECT * FROM receipt_batches WHERE id=?", (batch_id,)))
        if not batch or batch['status'] != 'active' or allocation_date < batch['receipt_date']:
            raise ShipmentError("預收款不存在、已作廢或沖帳日期早於收款日期")
        prior = _mappings(conn.execute(
            "SELECT r.* FROM receipt_batch_allocations a JOIN shipment_receipts r ON r.id=a.receipt_id "
            "WHERE a.batch_id=? AND a.request_id=?", (batch_id, request_id)))
        if prior:
            actual = sorted((r['shipment_id'], int(r['amount']), r['receipt_date']) for r in prior)
            expected = sorted((r['shipment_id'], r['amount'], allocation_date) for r in allocations)
            if actual != expected:
                raise ShipmentError("沖帳識別碼已使用，請重新讀取")
            return
        allocated = _mapping(conn.execute(
            "SELECT COALESCE(SUM(CAST(r.amount AS INTEGER)),0) AS total FROM receipt_batch_allocations a "
            "JOIN shipment_receipts r ON r.id=a.receipt_id WHERE a.batch_id=? AND r.status='active'", (batch_id,)))['total']
        if sum(r['amount'] for r in allocations) > int(batch['amount']) - allocated:
            raise ShipmentError("沖抵合計不可超過預收餘額")
        changed = _mapping(conn.execute("UPDATE receipt_batches SET version=version+1,updated_at=? "
                           "WHERE id=? AND version=? AND status='active' RETURNING id", (utc_now_iso(), batch_id, batch_version)))
        if not changed:
            raise ShipmentError("預收款已變更，請重新讀取")
        _apply_batch_allocations(conn, batch, allocations, request_id, allocation_date)


def void_receipt_batch(config, batch_id, reason):
    if not str(reason).strip():
        raise ShipmentError("請填寫收款作廢原因")
    with connect_from_config(config) as conn:
        now = utc_now_iso()
        changed = _mapping(conn.execute("UPDATE receipt_batches SET status='void',void_reason=?,version=version+1,updated_at=? "
                           "WHERE id=? AND status='active' RETURNING id", (str(reason).strip(), now, batch_id)))
        if not changed:
            raise ShipmentError("批次收款不存在或已作廢")
        conn.execute("UPDATE shipment_orders SET version=version+1,updated_at=? WHERE id IN "
                     "(SELECT r.shipment_id FROM shipment_receipts r JOIN receipt_batch_allocations a ON a.receipt_id=r.id WHERE a.batch_id=?)",
                     (now, batch_id))
        conn.execute("UPDATE shipment_receipts SET status='void',void_reason=?,updated_at=? WHERE id IN "
                     "(SELECT receipt_id FROM receipt_batch_allocations WHERE batch_id=?)", (str(reason).strip(), now, batch_id))

