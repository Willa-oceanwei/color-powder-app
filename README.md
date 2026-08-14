# color-powder-app
My color powder management system


## 現在怎麼開始

1. 安裝 Python 依賴：

   ```bash
   pip install -r requirements.txt
   ```

2. 啟動 Streamlit：

   ```bash
   streamlit run app.py
   ```

3. 第一次啟動會自動建立 `data/colorpowder.db` 與 SQLite schema。登入後主畫面會先完成 UI rendering；Google Sheets 連線已改為 lazy loading，只有進入需要工作表資料的功能時才會連線。

4. 若要先把現有 Google Sheets 安全複製進 SQLite，請執行下方「第一次安全匯入 Google Sheets」指令。這個匯入不會修改原始 Google Sheets。

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

若部署環境已設定 `TURSO_DATABASE_URL` 與 `TURSO_AUTH_TOKEN`，省略 `--db`
即可把資料匯入 Turso；Google Sheets 仍會永久保留作為人工操作介面，匯入程式不會修改它：

```bash
python scripts/import_google_sheets_to_sqlite.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" \
  --dry-run
```

建議先用 `--dry-run` 檢查 Turso 與 Sheet 的新增、修改、未變更、duplicate
及 conflict 統計，確認後再移除 `--dry-run`。若要明確使用本機 SQLite，才傳入
`--db data/colorpowder.db`。程式啟動時只會顯示所選 backend，不會輸出 Turso token。

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

## Streamlit Cloud 持久化注意事項（正式匯入前必讀）

Streamlit app process、SQLite file、Google Sheets、background sync 是四個不同角色：

- **Streamlit app process**：執行 `app.py` 的 Python process，可重新啟動、redeploy 或 rebuild。
- **SQLite file**：目前預設為 `data/colorpowder.db`，只適合作為可靠磁碟存在時的 Source of Truth。
- **Google Sheets**：同步副本、報表、管理介面，可被使用者偶爾直接修改，但不應阻塞網站查詢。
- **background sync**：未來負責 SQLite ↔ Google Sheets 的背景同步；一般網站查詢仍應走 `Web → Python → SQLite`。

在 **Streamlit Cloud** 上，本地 filesystem 通常不應視為永久持久化資料庫儲存。app redeploy、restart、rebuild 或 container 被替換後，`data/colorpowder.db` 可能遺失或回到 repository 內的初始狀態。因此，在確認 SQLite 檔案有可靠持久化方案以前，**不要把正式 Google Sheets 大量匯入只存在於 Streamlit Cloud 本地磁碟的 SQLite**。

最小且安全的持久化方案建議：

1. **短期驗證 / dry-run**：可在本機或暫時環境執行 `--dry-run`，只檢查筆數、重複 ID、validation errors、預計新增/更新數，不寫入正式 SQLite 資料。
2. **正式匯入前**：先選定可靠的 SQLite 檔案持久化位置，例如部署在有 persistent disk / volume 的 VM、NAS-backed server、或可掛載持久磁碟的平台。
3. **備份策略**：正式 SQLite 需定期備份，可使用 `utils.database.backup_database()` 產生 timestamped backup；Google Sheets 同步失敗不得刪除或覆寫 SQLite。
4. **未來替代**：若無法提供可靠 persistent disk，應暫緩正式切換 Source of Truth，或改部署到支援持久化 volume 的環境；目前仍不需要 PostgreSQL，但不可假設 Streamlit Cloud ephemeral filesystem 可永久保存 SQLite。

## Dry-run / validation 模式

在正式匯入前，先使用 dry-run 檢查 Google Sheets 與目前 SQLite 狀態。dry-run 不會寫入 `color_powders`、`inventory_movements`、`suppliers` 或 `sheet_rows`：

```bash
python scripts/import_google_sheets_to_sqlite.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" \
  --db data/colorpowder.db \
  --dry-run
```

輸出會包含：

- Google Sheets 工作表筆數
- SQLite 目前已知筆數
- 預計新增數 `insert`
- 預計更新數 `update`
- 未變更數 `unchanged`
- duplicate IDs
- validation errors
- conflicts
- inventory duplicate risk

如果 Google Sheets 沒有明確的 `updated_at` / `更新時間` 欄位，同步程式不會把「匯入當下時間」誤當成 Sheet 修改時間；會改用 `sheet_rows.row_hash` 做增量變更偵測，並在 SQLite 端自上次同步後也有修改時記錄 conflict，避免靜默覆蓋較新的 SQLite 資料。
