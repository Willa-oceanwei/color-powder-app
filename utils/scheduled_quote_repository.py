"""Customer-specific scheduled price notices; shipment prices remain explicit."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from zoneinfo import ZoneInfo

from .customer_repository import _mapping, _mappings
from .database import connect_from_config, utc_now_iso
from .read_cache import cached_read
from .shipment_repository import TAX_MODES


class QuoteError(ValueError):
    pass


def quote_today():
    return datetime.now(ZoneInfo("Asia/Taipei")).date()


@cached_read
def list_scheduled_quotes(config, customer_id=None, *, include_inactive=False):
    clauses, args = [], []
    if customer_id is not None:
        clauses.append("q.customer_id=?")
        args.append(customer_id)
    if not include_inactive:
        clauses.append("q.active=1")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    with connect_from_config(config) as conn:
        return _mappings(conn.execute(
            "SELECT q.*,c.name AS customer_name,c.short_name AS customer_short_name "
            "FROM scheduled_quotes q JOIN customers c ON c.customer_id=q.customer_id "
            + where + " ORDER BY q.effective_date DESC,q.updated_at DESC,q.quote_id DESC", tuple(args)))


def save_scheduled_quote(config, data):
    customer_id = str(data.get("customer_id") or "").strip()
    code = str(data.get("product_code") or "").strip().upper()
    unit = str(data.get("unit") or "").strip().upper()
    tax_mode = data.get("tax_mode", "外加")
    if not customer_id or not code or not unit:
        raise QuoteError("請填寫客戶、貨品編號與單位")
    if len(code) > 100 or len(unit) > 30:
        raise QuoteError("貨品編號或單位過長")
    if tax_mode not in TAX_MODES:
        raise QuoteError("請選擇有效課稅方式")
    try:
        price = Decimal(str(data.get("price", "")))
        if not price.is_finite() or price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise QuoteError("新單價需為大於或等於 0 的數字") from None
    try:
        effective_date = date.fromisoformat(str(data.get("effective_date", ""))).isoformat()
    except ValueError:
        raise QuoteError("請填寫有效生效日期") from None
    quote_id = data.get("quote_id") or str(uuid4())
    now = utc_now_iso()
    values = (customer_id, code, str(price), unit, tax_mode, effective_date,
              str(data.get("notes") or "").strip(), int(bool(data.get("active", True))))
    with connect_from_config(config) as conn:
        customer = _mapping(conn.execute("SELECT lifecycle_status FROM customers WHERE customer_id=?", (customer_id,)))
        if not customer or customer["lifecycle_status"] != "active":
            raise QuoteError("請選擇有效客戶")
        if data.get("quote_id"):
            saved = _mapping(conn.execute(
                "UPDATE scheduled_quotes SET customer_id=?,product_code=?,price=?,unit=?,tax_mode=?,"
                "effective_date=?,notes=?,active=?,version=version+1,updated_at=? "
                "WHERE quote_id=? AND version=? RETURNING *",
                (*values, now, quote_id, data.get("version"))))
            if not saved:
                raise QuoteError("報價已被其他人修改，請重新讀取後再儲存")
        else:
            saved = _mapping(conn.execute(
                "INSERT INTO scheduled_quotes(quote_id,customer_id,product_code,price,unit,tax_mode,"
                "effective_date,notes,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING *",
                (quote_id, *values, now, now)))
    return saved


def effective_quote_notices(config, customer_id, items, *, today=None):
    """Match exact canonical codes; the newest due quote wins per unit/tax basis."""
    codes = {str(item.get("code") or "").strip().upper() for item in items}
    codes.discard("")
    if not customer_id or not codes:
        return []
    cutoff = (today or quote_today()).isoformat()
    found = {}
    for quote in list_scheduled_quotes(config, customer_id):
        if quote["effective_date"] > cutoff or quote["product_code"] not in codes:
            continue
        identity = (quote["product_code"], quote["unit"], quote["tax_mode"])
        found.setdefault(identity, quote)
    return list(found.values())
