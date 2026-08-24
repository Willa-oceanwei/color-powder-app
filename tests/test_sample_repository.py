from utils.database import DatabaseConfig, connect, initialize_database
from utils.sample_repository import archive_sample_record, list_sample_records, save_sample_record
from utils.sheet_import import import_sheet_values

def cfg(tmp_path):
    path=tmp_path/"sample.db";initialize_database(path);return path,DatabaseConfig(backend="sqlite",path=path)

def test_sample_create_update_archive_outbox(tmp_path):
    path,config=cfg(tmp_path); row={"樣品編號":"S001","日期":"2026-08-24","客戶名稱":"甲","樣品名稱":"紅","樣品數量":"10"}
    save_sample_record(config,row,create=True);row["樣品數量"]="20";save_sample_record(config,row,create=False)
    archive_sample_record(config,"S001",reason="測試")
    assert list_sample_records(config)==[]
    with connect(path) as conn: ops=conn.execute("SELECT operation FROM sync_outbox ORDER BY entity_version").fetchall()
    assert [x[0] for x in ops]==["insert","update","delete"]

def test_sample_initial_import(tmp_path):
    path,_=cfg(tmp_path); values=[["日期","客戶名稱","樣品編號","樣品名稱","樣品數量"],["2026/08/24","甲","S001","紅","10"]]
    assert import_sheet_values("樣品記錄",values,db_path=path,abort_on_issues=True).inserted_or_updated==1
    assert import_sheet_values("樣品記錄",values,db_path=path,dry_run=True).unchanged==1
