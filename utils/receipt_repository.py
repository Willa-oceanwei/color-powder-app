"""Optional shipment-linked receipts with atomic overpayment protection."""

import json
from uuid import NAMESPACE_URL, uuid5, uuid4

from .read_cache import cached_read
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


@cached_read
def list_receipts(config, shipment_id):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute("SELECT r.*,a.batch_id FROM shipment_receipts r LEFT JOIN receipt_batch_allocations a ON a.receipt_id=r.id "
                                     "WHERE r.shipment_id=? ORDER BY r.receipt_date,r.created_at,r.id", (shipment_id,)))


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


def _tracking_start(conn, customer_id):
    first = _mapping(conn.execute(
        "SELECT start_date,request_json FROM ("
        "SELECT substr(b.receipt_date,1,7)||'-01' AS start_date,b.request_json,b.created_at,b.id "
        "FROM receipt_batches b WHERE b.customer_id=? UNION ALL "
        "SELECT substr(s.shipment_date,1,7)||'-01' AS start_date,NULL AS request_json,r.created_at,r.id "
        "FROM shipment_receipts r JOIN shipment_orders s ON s.id=r.shipment_id "
        "WHERE s.customer_id=? AND NOT EXISTS(SELECT 1 FROM receipt_batch_allocations a WHERE a.receipt_id=r.id)"
        ") ORDER BY created_at,id LIMIT 1", (customer_id, customer_id)))
    if not first:
        return None
    request = json.loads(first['request_json']) if first['request_json'] else {}
    return request.get('ledger_start') or request.get('tracking_start') or first['start_date']


def receipt_tracking_start(config, customer_id):
    with connect_from_config(config) as conn:
        return _tracking_start(conn, customer_id)


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


def _apply_batch_allocations(conn, batch, allocations, request_id, allocation_date, tracking_start=None):
    now = utc_now_iso()
    tracking_start = tracking_start or _tracking_start(conn, batch['customer_id']) or allocation_date[:7] + '-01'
    for row in allocations:
        changed = _mapping(conn.execute(
            "UPDATE shipment_orders SET version=version+1,updated_at=? "
            "WHERE id=? AND customer_id=? AND version=? AND status='draft' "
            "AND shipment_date>=? AND shipment_date<=? AND CAST(total_amount AS INTEGER)-(SELECT COALESCE(SUM(CAST(amount AS INTEGER)),0) "
            "FROM shipment_receipts WHERE shipment_id=? AND status='active')>=? RETURNING id",
            (now, row['shipment_id'], batch['customer_id'], row['shipment_version'], tracking_start, allocation_date, row['shipment_id'], row['amount'])))
        if not changed:
            raise ShipmentError("出貨單已變更、作廢、早於收款起算日、晚於收款日期或沖抵超過未收金額，請重新讀取")
        receipt_id = str(uuid5(NAMESPACE_URL, json.dumps([batch['id'], request_id, row['shipment_id']])))
        conn.execute("INSERT INTO shipment_receipts(id,shipment_id,receipt_date,amount,method,reference,notes,created_at,updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (receipt_id, row['shipment_id'], allocation_date, str(row['amount']),
                     batch['method'], batch['reference'], batch['notes'], now, now))
        conn.execute("INSERT INTO receipt_batch_allocations(receipt_id,batch_id,request_id) VALUES (?,?,?)",
                     (receipt_id, batch['id'], request_id))


def save_receipt_batch(config, *, batch_id, customer_id, receipt_date, amount, allocations,
                       method='匯款', reference='', notes='', tracking_start=None):
    receipt_date = _valid_date(receipt_date, '收款日期')
    amount = decimal_value(amount, '收款金額')
    if not amount or amount != amount.to_integral_value() or not batch_id or not str(method).strip():
        raise ShipmentError("請填寫大於零的整數收款金額及收款方式")
    allocations = _allocation_values(allocations)
    if sum(row['amount'] for row in allocations) > amount:
        raise ShipmentError("沖抵合計不可超過本次收款金額")
    values = dict(customer_id=customer_id, receipt_date=receipt_date, amount=str(int(amount)),
                  method=str(method).strip(), reference=str(reference).strip(), notes=str(notes).strip())
    request = dict(values, allocations=allocations)
    if tracking_start is not None:
        tracking_start = _valid_date(tracking_start, '收款起算日')
        if tracking_start > receipt_date:
            raise ShipmentError('收款日期不可早於帳款期間起日')
        request['tracking_start'] = tracking_start
    signature = json.dumps(request, sort_keys=True, ensure_ascii=False)
    with connect_from_config(config) as conn:
        previous = _mapping(conn.execute("SELECT * FROM receipt_batches WHERE id=?", (batch_id,)))
        if previous:
            previous_request = json.loads(previous['request_json'])
            previous_request.pop('ledger_start', None)
            if previous['status'] != 'active' or json.dumps(previous_request, sort_keys=True, ensure_ascii=False) != signature:
                raise ShipmentError("收款識別碼已使用，請重新開啟收款登錄")
            return previous
        if not _mapping(conn.execute("SELECT customer_id FROM customers WHERE customer_id=?", (customer_id,))):
            raise ShipmentError("請選擇有效客戶")
        now = utc_now_iso()
        ledger_start = _tracking_start(conn, customer_id) or tracking_start or receipt_date[:7] + '-01'
        stored_request = json.dumps(dict(request, ledger_start=ledger_start), sort_keys=True, ensure_ascii=False)
        conn.execute("INSERT INTO receipt_batches(id,customer_id,receipt_date,amount,method,reference,notes,request_json,created_at,updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?)", (batch_id, *values.values(), stored_request, now, now))
        batch = dict(values, id=batch_id)
        _apply_batch_allocations(conn, batch, allocations, batch_id, receipt_date, ledger_start)
        return _mapping(conn.execute("SELECT * FROM receipt_batches WHERE id=?", (batch_id,)))


@cached_read
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
            "SELECT r.*,s.shipment_number,s.shipment_date,s.version AS shipment_version FROM receipt_batch_allocations a "
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


def _edit_amount(value):
    amount = decimal_value(value, '收款金額')
    if not amount or amount != amount.to_integral_value():
        raise ShipmentError('收款金額須為大於零的整數元')
    return int(amount)


def _log_receipt_edit(conn, entity_id, entity_type, before, after, reason):
    if not str(reason).strip():
        raise ShipmentError('請填寫修改原因')
    conn.execute('INSERT INTO receipt_change_log VALUES (?,?,?,?,?,?,?)',
                 (str(uuid4()), entity_id, entity_type, json.dumps(before, ensure_ascii=False),
                  json.dumps(after, ensure_ascii=False), str(reason).strip(), utc_now_iso()))


def receipt_changes(config, entity_id):
    with connect_from_config(config) as conn:
        return _mappings(conn.execute('SELECT * FROM receipt_change_log WHERE entity_id=? ORDER BY created_at,id', (entity_id,)))


def update_receipt_amount(config, *, receipt_id, shipment_version, amount, reason):
    amount = _edit_amount(amount)
    with connect_from_config(config) as conn:
        old = _mapping(conn.execute("SELECT * FROM shipment_receipts WHERE id=? AND status='active'", (receipt_id,)))
        if not old:
            raise ShipmentError('收款紀錄不存在或已作廢')
        if _mapping(conn.execute('SELECT batch_id FROM receipt_batch_allocations WHERE receipt_id=?', (receipt_id,))):
            raise ShipmentError('此筆屬於批次收款，請修改整批收款')
        now = utc_now_iso()
        changed = _mapping(conn.execute(
            "UPDATE shipment_orders SET version=version+1,updated_at=? WHERE id=? AND version=? AND status='draft' "
            "AND CAST(total_amount AS INTEGER)-(SELECT COALESCE(SUM(CAST(amount AS INTEGER)),0) FROM shipment_receipts "
            "WHERE shipment_id=? AND status='active' AND id<>?)>=? RETURNING id",
            (now, old['shipment_id'], shipment_version, old['shipment_id'], receipt_id, amount)))
        if not changed:
            raise ShipmentError('單據已變更或修改後收款超過出貨總額，請重新讀取')
        conn.execute('UPDATE shipment_receipts SET amount=?,updated_at=? WHERE id=?', (str(amount), now, receipt_id))
        _log_receipt_edit(conn, receipt_id, 'single', {'amount': old['amount']}, {'amount': str(amount)}, reason)


def update_receipt_batch_amounts(config, *, batch_id, batch_version, amount, allocations, reason):
    amount = _edit_amount(amount)
    with connect_from_config(config) as conn:
        batch = _mapping(conn.execute("SELECT * FROM receipt_batches WHERE id=? AND status='active'", (batch_id,)))
        if not batch:
            raise ShipmentError('批次收款不存在或已作廢')
        old = _mappings(conn.execute(
            'SELECT r.*,s.version AS shipment_version FROM receipt_batch_allocations a '
            'JOIN shipment_receipts r ON r.id=a.receipt_id JOIN shipment_orders s ON s.id=r.shipment_id WHERE a.batch_id=?', (batch_id,)))
        proposed = {}
        for a in allocations:
            value = decimal_value(a['amount'], '沖抵金額')
            if value != value.to_integral_value() or a['receipt_id'] in proposed:
                raise ShipmentError('沖抵金額須為整數，紀錄不可重複')
            proposed[a['receipt_id']] = dict(amount=int(value), shipment_version=int(a['shipment_version']))
        if set(proposed) != {r['id'] for r in old}:
            raise ShipmentError('沖抵明細已變更，請重新讀取')
        if sum(a['amount'] for a in proposed.values()) > amount:
            raise ShipmentError('沖抵合計不可超過修改後的收款總額')
        now = utc_now_iso()
        changed = _mapping(conn.execute('UPDATE receipt_batches SET amount=?,version=version+1,updated_at=? '
                                       "WHERE id=? AND version=? AND status='active' RETURNING id",
                                       (str(amount), now, batch_id, batch_version)))
        if not changed:
            raise ShipmentError('批次收款已變更，請重新讀取')
        shipments = {}
        for r in old:
            entry = proposed[r['id']]
            if r['shipment_version'] != entry['shipment_version'] or r['status'] != 'active':
                raise ShipmentError('出貨單或沖抵明細已變更，請重新讀取')
            group = shipments.setdefault(r['shipment_id'], dict(amount=0, version=entry['shipment_version']))
            group['amount'] += entry['amount']
        for shipment_id, group in shipments.items():
            changed = _mapping(conn.execute(
                "UPDATE shipment_orders SET version=version+1,updated_at=? WHERE id=? AND version=? AND status='draft' "
                "AND CAST(total_amount AS INTEGER)-(SELECT COALESCE(SUM(CAST(r.amount AS INTEGER)),0) FROM shipment_receipts r "
                "WHERE r.shipment_id=? AND r.status='active' AND NOT EXISTS(SELECT 1 FROM receipt_batch_allocations a "
                "WHERE a.receipt_id=r.id AND a.batch_id=?))>=? RETURNING id",
                (now, shipment_id, group['version'], shipment_id, batch_id, group['amount'])))
            if not changed:
                raise ShipmentError('修改後的沖抵超過未收金額或出貨單已變更，請重新讀取')
        for receipt_id, row in proposed.items():
            conn.execute('UPDATE shipment_receipts SET amount=?,updated_at=? WHERE id=?', (str(row['amount']), now, receipt_id))
        _log_receipt_edit(conn, batch_id, 'batch',
                          dict(amount=batch['amount'], allocations={r['id']: r['amount'] for r in old}),
                          dict(amount=str(amount), allocations={i: str(a['amount']) for i, a in proposed.items()}), reason)

