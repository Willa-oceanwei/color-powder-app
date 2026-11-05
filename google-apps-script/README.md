# 請假表單逾時修正

失敗通知中的 `Service Drive timed out` 最可能出現在原始
`checkDuplicateOnFormSubmit_()` 呼叫 `FormApp.getActiveForm().getResponses()` 時。每次送出都讀取整份表單的歷史回覆，資料越多，觸發器越容易超時。

`leave-management.gs` 改以 Script Properties 儲存雜湊後的「姓名＋日期＋起訖時間」索引，提交時只處理本次回覆，並以 `LockService` 防止同時提交造成競爭。重送同一個觸發事件不會重複寄信。

## 部署

1. 原始碼目前看起來被完整貼了兩次；先刪除第二份，否則重複的 `const` 宣告會造成語法錯誤。
2. 將 `leave-management.gs` 中的提交檢查函式及共用函式合併到 Apps Script 專案；月報函式可保留原版。
3. 儲存後，手動執行一次 `rebuildDuplicateIndex()` 並授權。它會從回覆試算表批次建立既有資料的索引，不會呼叫 `Form.getResponses()`。
4. 確認安裝型表單提交觸發器指向 `onFormSubmit`，再送出一筆測試資料。

若專案已累積非常大量的回覆，Script Properties 仍可能達到 Google 配額；此時應改在回覆試算表增加「重複索引」欄，或將索引存入獨立工作表。
