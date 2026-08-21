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

Streamlit secrets 可使用頂層鍵，也支援 `[turso]` 或 `[connections.turso]`
區段中的 `database_url` / `url` 與 `auth_token` / `token`。登入畫面不會連線
Turso；登入成功後的 schema 初始化與健康檢查會在同一個 app process 內快取，
避免每次輸入或操作 widget 都重新連線。

```bash
python scripts/import_google_sheets_to_sqlite.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" \
  --dry-run
```

建議先用 `--dry-run` 檢查 Turso 與 Sheet 的新增、修改、未變更、duplicate
及 conflict 統計，確認後再移除 `--dry-run`。若要明確使用本機 SQLite，才傳入
`--db data/colorpowder.db`。程式啟動時只會顯示所選 backend，不會輸出 Turso token。

登入網站後也可從側欄「設定 → 同步檢查」逐張執行相同的唯讀 dry-run，
查看 Sheet/Turso 筆數、新增、修改、未變更、duplicate、conflict、錯誤與警告，
並下載不含 Turso token 的 JSON 報告。大型 Sheet 會一次只讀取選定的工作表，
不會因開啟頁面就自動掃描所有工作表。Google API 若暫時回傳 408、429、
500、502、503 或 504，讀取會以短暫 exponential backoff 自動重試最多四次；
仍失敗時只顯示簡短狀態，不會把整張 Google HTML 錯誤頁塞進畫面。

當某張工作表的首次 dry-run 顯示 Turso baseline 為 0，且 error、duplicate、
conflict 都是 0 時，頁面會顯示受控的「第一次正式匯入」。使用者必須確認已備份
並輸入 `IMPORT <工作表名稱>`；系統會重新讀取 Sheet、再次 preflight，接著以
atomic transaction 匯入。任何安全問題都會整批 rollback，成功後會自動驗證
所有資料皆為 unchanged。已存在 baseline 的工作表不會再顯示首次匯入按鈕。
libsql 回傳的 tuple rows 會先依 cursor column metadata 正規化成欄位 mapping，
因此匯入後驗證可和本機 SQLite 的 `sqlite3.Row` 使用相同的增量判斷。
`供應商管理` 可使用 `供應商編號` 作為永久 ID，名稱欄則接受 `供應商名稱`、
`供應商簡稱` 或 `名稱`；因此既有的「供應商編號／供應商簡稱／備註」格式不需改欄名。
`庫存記錄` 必須使用永久 `_sync_id`；同步檢查頁可用單次 batch requests 只補齊
空白 ID。Turso schema v3 會保存 `廠商編號`／`廠商名稱`，網站新增「初始」或
「進貨」記錄時也會自動建立 `_sync_id`，新增一筆不再清空並重寫整張庫存表。
庫存 dry-run 也會一次載入 Turso 的已知色粉與供應商 ID 集合；任何不存在於
`color_powders` 的色粉編號，或非空但不存在於 `suppliers` 的廠商編號，都會列為
error。正式匯入不會自動建立空白色粉或未知供應商資料。
已有 baseline 的 `色粉管理`、`供應商管理` 與 `庫存記錄` 若 dry-run 發現新增或
修改，頁面會提供受控的增量套用：使用者輸入 `APPLY <工作表名稱>` 後，系統重新
preflight、以 atomic transaction 寫入 Turso，再驗證所有 rows 均為 unchanged。
這個階段不會將 Sheet 中消失的 row 當成刪除，刪除仍需後續 tombstone 流程。
Streamlit 的 database startup cache 會把 `SCHEMA_VERSION` 納入 cache key；每次
schema 升級都會重新執行 Turso migration。Health check 也會驗證必要欄位，
避免只看到 migration version、但實際 table column 尚未建立就開始正式匯入。
Schema v4 新增 `recipes` 與 `recipe_components`：配方主資料保存客戶、類別、狀態、
Pantone、比例、淨重與備註，每個配方最多 8 個色粉位置會拆成 component rows。
配方 dry-run 會驗證非空的色粉編號已存在 `color_powders`，首次匯入及後續修改都只
替換該配方自己的 components，不重寫其他配方。

第二階段的 Turso → Sheet 同步先從 `色粉管理` 開始。網站或 repository 在同一個
database transaction 更新色粉後，須呼叫 `enqueue_sheet_sync()`，將該 entity version
寫入 `sync_outbox`。傳送程式預設只做 dry-run；只有加上 `--apply` 才會寫入 Sheet：

```bash
python scripts/sync_color_powders_to_sheet.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit"

# 確認 insert/update/conflict 統計後才執行：
python scripts/sync_color_powders_to_sheet.py \
  --credentials-json /path/to/service-account.json \
  --sheet-url "https://docs.google.com/spreadsheets/d/.../edit" \
  --apply
```

傳送前會把目前 Sheet row 與 `sheet_rows` baseline 比較；若人工已修改 Sheet，會寫入
`sync_conflicts` 而不覆蓋。成功後才完成 outbox 並更新 baseline。刪除目前一律阻擋，
等待 tombstone 階段完成後才會開放。

網站「配方管理 → 色粉管理」的清單、新增與修改已改以 Turso 為正式資料來源。
每次新增或修改會在同一個 database transaction 更新 `color_powders` 並建立 outbox；
網站不再直接 append/update 色粉 Sheet。若同一筆新色粉在送出前連續修改，worker
只傳送最新 entity version，完成後一併關閉較舊事件，避免 Sheet 出現重複列。
色粉編號是永久 ID，修改時不可變更。停用會在 Turso 保留資料與歷史引用，並建立
tombstone outbox；只有 Sheet row 仍符合已同步 baseline 時，後續 PUSH 才會移除 Sheet
副本。停用資料可由網站恢復。

登入網站後可在「設定 → 同步檢查」的「Turso → Sheet：色粉 outbox」先執行唯讀
preflight，下載包含 queued/insert/update/unchanged/conflict 的 JSON。只有結果安全且
仍有 pending event 時才會出現 PUSH；輸入 `PUSH 色粉管理` 後，系統會重新讀取 Sheet、
再次 preflight、套用 outbox，最後強制重讀 Sheet 並驗證 queued 已歸零。這是後續工作表
可重用的控制流程；但各工作表的永久 ID、外鍵、數量 ledger、component transaction
與 tombstone 規則仍須分別測試，不能只因色粉通過就直接全面開放。

`採購管理 → 供應商管理` 也已使用相同的 Turso-first/outbox/PUSH 流程：供應商編號
是永久 ID，新增與修改會原子更新 `suppliers`、保留新舊名稱於 `supplier_aliases`，
並建立 `供應商管理` outbox。進貨表單的供應商選項也直接讀 Turso，因此不必等待
Sheet PUSH 才能選到新供應商。「設定 → 同步檢查」提供獨立的供應商 preflight JSON
與 `PUSH 供應商管理`；供應商停用、恢復及受 baseline 保護的 tombstone 已開放。

Schema v6 將 `配方管理` 改為 Turso-first，並在 `recipes` 保存 `oem_multiplier`；升級時
會從既有 `sheet_rows` baseline 回填倍率，避免舊配方遺失資料。配方新增或修改會在
同一 transaction 寫入 recipe 主表、完整替換該配方最多 8 筆 components，並建立
versioned outbox。生產單頁也直接讀 Turso 配方。「設定 → 同步檢查」提供
`PUSH 配方管理`；配方停用、恢復及受 baseline 保護的 tombstone 已開放。

`庫存記錄` 已改為 Turso-first movement ledger。進貨新增、進貨修改、初始庫存與洗車廠
轉入都先原子寫入 `inventory_movements`，並以永久 `_sync_id` 建立 versioned outbox；
查詢與庫存計算直接讀 Turso。初始庫存再次儲存會更新同一個永久 movement，不會先刪
Sheet row 再 append。進貨可用 append-only 沖銷，原始 movement 與反向 movement 都保留
於 Turso，且已沖銷記錄不可再次修改或重複沖銷。同步檢查提供 `PUSH 庫存記錄`；安全的
tombstone 只移除 Sheet 副本，不會破壞 Turso 的庫存稽核軌跡。

Schema v7 新增 `production_orders` 與 `production_order_packages`，並從既有「生產單」
`sheet_rows` baseline 回填歷史主資料與包裝組。網站建立或修改生產單時會保存當下的
recipe version/snapshot、最多 4 組包裝資料與完整 Sheet payload，再建立 versioned
outbox；生產單查詢、預覽與列印改讀 Turso。一般合併會沿用既有生產單永久 ID，
不再刪除舊 Sheet row 後新增另一個 ID。同步檢查提供 `PUSH 生產單`；生產單可取消或
恢復，取消原因與 recipe snapshot 會保留在 Turso，安全 PUSH 才移除 Sheet 副本。庫存
`_sync_id` 仍永久保存在 Turso、outbox 與 Sheet，但一般網站查詢已隱藏此技術欄位，
畫面只顯示業務資料。

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

## Schema v8 lifecycle、沖銷與 tombstone

Schema v8 已建立 lifecycle 資料層與受控 UI；網站不會實體刪除 Turso 的業務歷史：

- 色粉、供應商、配方使用 `lifecycle_status` / `deleted_at` / `delete_reason`
  保留歷史引用，不實體刪除。
- 庫存記錄使用 `reversal_of_movement_key` / `reversed_at` 建立 append-only 沖銷鏈；
  同一筆 movement 只允許一筆 reversal，且沖銷原因必填。
- 生產單使用現有 `status` 搭配 `cancelled_at` / `cancel_reason`，
  以「取消／恢復」取代刪除永久單號並保留 recipe snapshot。
- lifecycle、沖銷及取消會建立 versioned delete outbox；PUSH 前若 Sheet row 已被人工修改，
  系統會建立 conflict 並阻擋刪除，不會靜默覆寫。

目前 Turso → Sheet 仍採人工 preflight + `PUSH`。在 lifecycle/reversal 測試完整
之前不啟用自動 worker；後續可改為定時自動傳送，只將 conflict
與 failed event 留給人工處理。

正式環境驗收與放行條件請依 [`docs/lifecycle-acceptance-checklist.md`](docs/lifecycle-acceptance-checklist.md)
逐項執行並保存 preflight JSON；所有項目通過後才進入排程 worker 階段。

若系統完全部署在 Streamlit Community Cloud，不需要另外準備主機。請建立一個獨立的
Streamlit Cloud 測試 app（可使用同一 repository 的測試 branch），讓它連到獨立的測試
Turso database 與正式 Spreadsheet 的測試副本。自動測試交由 GitHub Actions 執行；
不要在 Streamlit app process 中執行 pytest、排程常駐 worker，或把本機 SQLite file
當成備份。Cloud 專用步驟與 secrets 隔離方式請見驗收清單。

### 安全模式 worker（手動 GitHub Actions）

備份完成後可從 GitHub repository 的 **Actions → safe Turso to Sheets sync → Run workflow**
執行單次 worker。第一次請選 `dry-run`；確認輸出無 error/conflict 後才選 `apply`。
此 worker 每次最多處理指定 batch（預設 25 筆），只自動傳送 insert/update；所有 delete、
tombstone、沖銷移除與取消移除都保留給網站既有的人工 preflight + `PUSH`。Database lock
與 GitHub concurrency 會阻止兩個 apply worker 同時傳送。

請先在 GitHub Actions secrets 設定 `TURSO_DATABASE_URL`、`TURSO_AUTH_TOKEN`、
`GOOGLE_SERVICE_ACCOUNT_JSON`、`GOOGLE_SHEET_URL`。這些值只放在 GitHub Secrets，不能
提交到 repository。workflow 目前只有手動觸發，尚未設定定時排程。

Schema v9 新增 `sync_worker_locks`。Apply worker 會取得具期限的 database lock，結束時只
能釋放自己持有的 lock；若另一個 worker 已持有 lock，本次執行會安全停止。即使 GitHub
Actions concurrency 設定失效，database lock 仍提供第二層重複傳送保護。

每次手動執行都會產生保留 14 天的 `safe-sync-...` JSON artifact，方便比較 dry-run 與
apply 的 queued/written/conflict/error 結果。正式加入 schedule 前，建議至少完成三組
「網站新增或修改 → dry-run → apply → 再次 dry-run queued 歸零」，並下載報告留存。
