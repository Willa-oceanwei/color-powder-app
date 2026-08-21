# Lifecycle、沖銷與 Tombstone 正式環境驗收清單

本清單用於 Schema v8 上線驗收。目標是確認 Turso 永遠保留可稽核的業務歷史，且
Google Sheets 副本只會在 row 仍符合同步 baseline 時被移除。此流程支援完全使用
Streamlit Community Cloud，不需要另備 VM 或常駐主機。**請使用隔離的測試 app、測試
Turso database 與測試 Sheet；尚未完成全部放行條件前，不得啟用自動 worker。**

## 1. Streamlit Cloud 驗收拓撲

- [ ] 在 Turso 建立獨立的測試 database；不可讓驗收 app 指向正式 database。
- [ ] 複製正式 Google Spreadsheet 作為獨立測試 Sheet，並移除不需要的正式資料。
- [ ] 建立獨立的 Google service account，權限只授予測試 Sheet。
- [ ] 在 Streamlit Community Cloud 建立獨立的測試 app，可部署同一 repository 的測試 branch。
- [ ] 測試 app 的 Secrets 只填入測試 Turso URL/token、測試 Sheet URL 與測試 service account。
- [ ] 不要把正式 secrets 複製到測試 app，也不要把任何 token 寫入 repository 或驗收報告。
- [ ] GitHub Actions 的 `tests` workflow 必須通過；Streamlit app process 不負責執行 pytest。
- [ ] 開啟測試 app，登入後確認 database health check 顯示 Schema v8。
- [ ] 為色粉、供應商、配方、庫存與生產單各建立一筆容易辨識的測試資料。
- [ ] 對五張工作表執行一次安全 PUSH，建立可供 tombstone 比對的 `sheet_rows` baseline。
- [ ] 下載並保存每次 preflight JSON；紀錄測試人員、時間、環境與測試資料 ID。

Streamlit Cloud 的 filesystem 不是備份位置，也不適合常駐排程。驗收證據應下載至管理者
可控的持久儲存；未來自動 worker 應部署在具有排程觸發能力的服務，而不是依賴 Streamlit
app session 持續運行。

## 2. 色粉、供應商與配方

以下流程須分別對 `色粉管理`、`供應商管理` 與 `配方管理` 執行：

- [ ] 從網站停用測試資料，且必須填寫可辨識的停用原因。
- [ ] 一般選單不再提供已停用資料，但歷史資料與既有引用仍可查閱。
- [ ] Turso row 仍存在，`lifecycle_status` 為 `inactive`，並保存停用時間與原因。
- [ ] outbox 產生正確 row key、entity version 與 `delete` operation。
- [ ] 唯讀 preflight 顯示一筆安全的待刪除事件，且沒有 error 或 conflict。
- [ ] 輸入對應的 `PUSH <工作表名稱>` 後，只有測試 Sheet 的副本列被移除。
- [ ] 從網站恢復資料後，Turso row 回到 `active` 並建立新的同步事件。
- [ ] 再次 PUSH 後，Sheet 使用原永久 ID 恢復列，沒有重複 ID。

## 3. 庫存沖銷

- [ ] 建立一筆測試進貨並完成 `PUSH 庫存記錄`。
- [ ] 以明確原因沖銷該筆進貨。
- [ ] Turso 保留原始 movement，並新增數量正負相反的 reversal movement。
- [ ] 原始 movement 的 `reversed_at` 已填入，reversal 正確指向原始 movement key。
- [ ] 庫存淨額在沖銷前後相差原始進貨量的負值，原始與 reversal 合計為零。
- [ ] 網站禁止修改已沖銷 movement，也禁止對同一 movement 再次沖銷。
- [ ] preflight 與 PUSH 只處理對應 Sheet 副本；Turso 的兩筆稽核記錄均保留。

## 4. 生產單取消與恢復

- [ ] 建立生產單並完成 `PUSH 生產單`。
- [ ] 從網站取消生產單，且取消原因必填。
- [ ] 一般生產單查詢不顯示已取消單；開啟「顯示已取消生產單」後仍可查閱。
- [ ] Turso 保留永久生產單號、取消時間、取消原因與原 recipe snapshot。
- [ ] 取消後不可修改，且不可重複取消。
- [ ] 安全 PUSH 後只移除 Sheet 副本。
- [ ] 恢復後沿用原永久單號，取消欄位清除，並可重新 PUSH 至 Sheet。

## 5. Tombstone 衝突保護

以下流程至少對一張主資料工作表與一張交易工作表執行：

- [ ] 先完成正常 PUSH，確保 Turso 中存在最新 Sheet baseline。
- [ ] 在網站產生停用、沖銷或取消事件，但先不要 PUSH。
- [ ] 人工修改測試 Sheet 的同一列，使目前 row hash 與 baseline 不同。
- [ ] 執行唯讀 preflight；結果必須是 conflict，且 PUSH 按鈕不可用。
- [ ] Sheet 人工修改內容未被覆寫或刪除。
- [ ] `sync_conflicts` 留下 entity、Turso/Sheet payload 與衝突原因，不含 credentials/token。
- [ ] 依人工決策處理衝突後重新建立 baseline，再驗證事件可以安全完成。

## 6. 失敗與重送

- [ ] 在自動測試中模擬 Google API 暫時錯誤，確認 retry/backoff 不會產生重複 Sheet row。
- [ ] 模擬寫入結果不確定，確認系統要求重新 preflight，而不是盲目重送。
- [ ] 同一 entity 的較舊 version 不會覆蓋較新的 pending event。
- [ ] failed event 與錯誤摘要可從同步檢查頁辨識，且不洩漏 Turso token。
- [ ] 從 Streamlit Cloud 重新啟動測試 app 後，pending outbox、baseline 與 conflict 仍存在於 Turso。

## 7. 放行條件

只有同時滿足下列條件，才能開始實作或啟用排程 worker：

- [ ] GitHub Actions 的自動測試全部通過。
- [ ] 第 2～6 節所有測試均在測試 Sheet 通過。
- [ ] 每張工作表都有成功、衝突及失敗案例的 preflight JSON 證據。
- [ ] 已依所選 Turso 備份方案完成還原演練，並確認 Sheet 不能取代 Source of Truth。
- [ ] 已指定 conflict/failed event 的人工負責人與處理時限。
- [ ] worker 初期仍保留人工 PUSH 作為復原與除錯管道。

驗收通過後，下一階段 worker 應具備單一執行鎖、批次上限、有限重試、exponential
backoff、結構化 sync log，以及「只自動處理安全事件」的預設策略；conflict 與 failed
event 必須留給人工處理。

## 8. 備份後的安全模式 worker

若已完成 Turso 與 Google Spreadsheet 備份，可先使用 GitHub Actions 的
`safe Turso to Sheets sync`，不必先啟用定時排程：

1. 在 repository Actions secrets 設定 `TURSO_DATABASE_URL`、`TURSO_AUTH_TOKEN`、
   `GOOGLE_SERVICE_ACCOUNT_JSON` 與 `GOOGLE_SHEET_URL`。
2. 從 Actions 頁面手動執行 `dry-run`，batch size 保持預設 25。
3. 確認 JSON 結果沒有 error/conflict，再手動執行 `apply`。
4. `apply` 只處理 insert/update；`skipped_deletes` 大於零是預期結果，delete 仍回網站人工 PUSH。
5. 初期每次執行後抽查 Sheet；穩定運作一段時間後，才另行評估加入 schedule。

### 手動觀察紀錄

每次 workflow 完成後，從該次 run 的 **Artifacts** 下載 `safe-sync-...` JSON。至少記錄
三組成功循環，每組包含 dry-run、apply、再次 dry-run，並確認最後一次 `queued` 為 0、
`conflicts` 為 0、`errors` 為空。若 `skipped_deletes` 大於 0，改回網站人工 PUSH，不把
它視為 safe worker 失敗。三組紀錄通過後，才開始加入定時 schedule。

## 9. 定時 schedule

- 排程在每小時 UTC 第 17、47 分執行一次，每次最多處理 25 筆安全事件。
- schedule 只執行 apply insert/update；delete、tombstone、沖銷移除與取消移除不會自動執行。
- 每次排程仍產生保留 14 天的 JSON artifact，可由 Actions 執行紀錄抽查。
- 若 scheduled run 出現 conflict/error，worker 會停止後續工作表並以失敗狀態提醒人工處理。
- 緊急暫停請使用 workflow 頁面的 **Disable workflow**；不要刪除 outbox 或 database lock row。
- 合併後先確認第一筆 `schedule` 觸發的 run 為 Success，再用一次網站新增／修改驗證無需人工操作即可進入 Sheet。

## 10. 受控 Sheet → Turso inbound

1. 從 Actions 手動開啟 `controlled Sheets to Turso sync`，先選單一工作表與 `dry-run`。
2. 確認 `preflight` 中只有預期的 `to_insert`／`to_update`，且 conflict、error、duplicate 均為 0。
3. 重新 Run workflow，選相同工作表與 `apply`，並輸入 `APPLY SHEET TO TURSO`；apply 會重新讀取並再次 preflight，不沿用舊報告。
4. 確認 `applied[].inserted_or_updated` 符合預期，再從網站查詢 Turso 正式資料。
5. 從 Artifacts 下載 `inbound-...` JSON 留存；若任何安全檢查失敗，不得反覆重按 apply。

安全限制：一次最多 25 個變更（可手動降低）；選定工作表必須全部安全才開始 apply；Sheet
消失的 row 永遠不當成刪除；inbound 不建立 outbound event。
建議第一次只修改一筆既有資料的備註，不要測試停用、取消、沖銷或大量新增。

## 11. Inbound 安全自動套用

- 每小時 UTC 第 7、37 分自動對全部支援工作表重新讀取、preflight，再安全 apply。
- 排程與 outbound apply 錯開 10 分鐘，且仍共用 concurrency group。
- 無變更時所有工作表應為 `to_insert: 0`、`to_update: 0`、`conflicts: 0`、`errors: []`。
- 有安全 insert/update 時，preflight 全部通過才寫入 Turso，結果記錄於 `applied`。
- conflict、duplicate、validation error 或超過 25 個變更會在任何寫入前使 run Failure。
- Sheet row 消失不視為刪除；停用、取消、沖銷及其他 lifecycle 操作仍由網站人工流程處理。
- scheduled run 失敗時先下載 artifact 確認原因，不得以手動 apply 繞過安全檢查。
