# color-powder-app
My color powder management system

## SQLite 主資料庫升級（第一階段）

本專案正在由 Google Sheets 主要資料來源逐步升級為：

- **SQLite：唯一 Source of Truth**，預設資料庫檔案為 `data/colorpowder.db`。
- **Google Sheets：同步副本、管理介面、報表與人工檢查介面**。
- **Python：Web Backend、商業邏輯、SQLite 存取與 Google Sheets 同步**。

第一階段已加入自動初始化的 SQLite database layer。啟動 `app.py` 時會自動建立資料庫、核心 tables 與 indexes，不需要使用者手動建立 database server。現有網頁功能仍保留 Google Sheets 流程，後續階段會逐步把新增/查詢改到 SQLite，並把 Google Sheets 同步移到背景工作，避免網站查詢依賴 Google Sheets。

### 已建立的核心資料表

- `color_powders`：色粉基本資料，`colorpowder_id` 是 primary key，避免重複 ID。
- `suppliers`：供應商資料。
- `inventory_movements`：庫存入庫/出庫/初始等紀錄。
- `sheet_rows`：保留每個工作表列資料的 JSON 副本，供安全匯入、欄位檢查與後續增量同步比對。
- `sync_state`、`sync_log`、`sync_conflicts`：同步狀態、同步紀錄與衝突紀錄。

### 第一次安全匯入 Google Sheets

匯入指令只會讀取 Google Sheets 並複製到 SQLite，不會清空、刪除或覆寫原始 Google Sheets：

```bash
python scripts/import_google_sheets_to_sqlite.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" \
  --db data/colorpowder.db
```

可以只匯入指定工作表：

```bash
python scripts/import_google_sheets_to_sqlite.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" \
  --sheets 色粉管理 庫存記錄 供應商管理
```

匯入完成後會輸出每個工作表的 Google Sheets 筆數、SQLite 筆數、寫入筆數、錯誤數與重複 ID。若偵測到重複 `色粉編號` 或必要欄位缺漏，會記錄在匯入結果與 `sync_log`，不會靜默覆蓋資料。

### 後續階段原則

1. Web request 必須逐步改為 `Web → Python → SQLite → Response`。
2. Google Sheets API 呼叫應集中在同步模組，不應散落在網頁查詢流程。
3. 正常新增/修改資料先寫 SQLite，成功後由背景同步推送 Google Sheets。
4. 使用者直接修改 Google Sheets 時，由同步程序依 `updated_at` / hash / sync metadata 判斷增量變更並寫回 SQLite。
5. 無法安全判斷雙邊修改時，必須寫入 `sync_conflicts`，保留人工處理空間，不可靜默覆蓋。
6. SQLite 備份可由 `utils.database.backup_database()` 建立 timestamped backup。
