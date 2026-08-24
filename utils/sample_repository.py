"""Turso-first sample records with lifecycle-safe Sheet synchronization."""
from __future__ import annotations
from typing import Any
from .database import DatabaseConfig, connect_from_config, enqueue_sheet_sync, utc_now_iso

class SampleError(RuntimeError): pass

def _mapping(cursor):
    row=cursor.fetchone()
    if row is None: return None
    if hasattr(row,"keys"): return {k:row[k] for k in row.keys()}
    return dict(zip((c[0] for c in cursor.description),row))

def _mappings(cursor):
    rows=cursor.fetchall()
    if not rows:return []
    if hasattr(rows[0],"keys"):return [{k:r[k] for k in r.keys()} for r in rows]
    cols=[c[0] for c in cursor.description];return [dict(zip(cols,r)) for r in rows]

def sample_sheet_payload(e:dict[str,Any])->dict[str,str]:
    return {"日期":str(e.get("sample_date") or ""),"客戶名稱":str(e.get("customer_name") or ""),
            "樣品編號":str(e.get("sample_id") or ""),"樣品名稱":str(e.get("sample_name") or ""),
            "樣品數量":str(e.get("quantity") or ""),"生命週期":str(e.get("lifecycle_status") or "active"),
            "停用時間":str(e.get("deleted_at") or ""),"停用原因":str(e.get("delete_reason") or "")}

def list_sample_records(config:DatabaseConfig,*,include_inactive=False):
    with connect_from_config(config) as conn:
        where="" if include_inactive else "WHERE lifecycle_status='active'"
        return _mappings(conn.execute(f"SELECT * FROM sample_records {where} ORDER BY sample_date,sample_id"))

def save_sample_record(config:DatabaseConfig,row:dict[str,Any],*,create:bool):
    sid=str(row.get("樣品編號") or "").strip()
    if not sid: raise SampleError("請輸入樣品編號")
    now=utc_now_iso()
    with connect_from_config(config) as conn:
        old=_mapping(conn.execute("SELECT * FROM sample_records WHERE sample_id=?",(sid,)))
        if create and old: raise SampleError(f"樣品編號 {sid} 已存在")
        if not create and not old: raise SampleError(f"找不到樣品編號 {sid}")
        if old and old["lifecycle_status"]!="active":raise SampleError("已停用樣品不可修改")
        version=1 if not old else int(old["version"])+1; created=now if not old else old["created_at"]
        conn.execute("""INSERT INTO sample_records(sample_id,sample_date,customer_name,sample_name,quantity,source,version,created_at,updated_at)
        VALUES (?,?,?,?,?,'app',?,?,?) ON CONFLICT(sample_id) DO UPDATE SET sample_date=excluded.sample_date,
        customer_name=excluded.customer_name,sample_name=excluded.sample_name,quantity=excluded.quantity,
        source='app',version=excluded.version,updated_at=excluded.updated_at""",
        (sid,str(row.get("日期") or ""),str(row.get("客戶名稱") or "").strip(),str(row.get("樣品名稱") or "").strip(),
         str(row.get("樣品數量") or "").strip(),version,created,now))
        e=_mapping(conn.execute("SELECT * FROM sample_records WHERE sample_id=?",(sid,)))
        enqueue_sheet_sync(conn,sheet_name="樣品記錄",row_key=sid,operation="insert" if create else "update",
                           payload=sample_sheet_payload(e),entity_version=version)
        return e

def archive_sample_record(config:DatabaseConfig,sample_id:str,*,reason="使用者停用"):
    now=utc_now_iso(); sample_id=str(sample_id).strip()
    with connect_from_config(config) as conn:
        old=_mapping(conn.execute("SELECT * FROM sample_records WHERE sample_id=?",(sample_id,)))
        if not old or old["lifecycle_status"]!="active":raise SampleError("找不到有效樣品")
        version=int(old["version"])+1
        conn.execute("UPDATE sample_records SET lifecycle_status='inactive',deleted_at=?,delete_reason=?,version=?,updated_at=? WHERE sample_id=?",
                     (now,str(reason).strip(),version,now,sample_id))
        enqueue_sheet_sync(conn,sheet_name="樣品記錄",row_key=sample_id,operation="delete",payload=None,entity_version=version)
