/**
 * Google Forms leave-management helpers.
 *
 * This file intentionally avoids Form.getResponses() in the submit trigger. That
 * call loads every historical response and can make the Drive-backed Forms
 * service time out as the form grows.
 */

const LEAVE_REPORT_EMAIL = "chaihe.tw@gmail.com";
const LEAVE_TIME_ZONE = "Asia/Taipei";
const RESPONSE_SHEET_NAME = "表單回覆 1";
const DUPLICATE_PROPERTY_PREFIX = "leave-response:";

function onOpen() {
  const form = FormApp.getActiveForm();
  const found = form
    .getItems(FormApp.ItemType.DATE)
    .find(item => item.getTitle() === "請假日期");

  if (!found) {
    form.addDateItem().setTitle("請假日期");
  }
}

/**
 * Installed Google Forms submit trigger.
 *
 * Only the submitted response is read. A script-property index makes the check
 * O(1), while a script lock prevents simultaneous submissions racing each other.
 */
function onFormSubmit(e) {
  if (!e || !e.response) {
    console.warn("讀不到表單回覆事件");
    return;
  }

  const current = responseToLeaveRecord_(e.response);
  if (!current.name || !current.date || !current.start || !current.end) {
    console.warn("回覆缺少姓名、日期或起訖時間");
    return;
  }

  const key = duplicatePropertyKey_(current);
  const responseMarker = responseMarker_(e.response);
  const lock = LockService.getScriptLock();
  let previousMarker;

  lock.waitLock(10000);
  try {
    const properties = PropertiesService.getScriptProperties();
    previousMarker = properties.getProperty(key);

    // A retried delivery of the same event is idempotent and sends no warning.
    if (!previousMarker) {
      properties.setProperty(key, responseMarker);
    }
  } finally {
    lock.releaseLock();
  }

  if (previousMarker && previousMarker !== responseMarker) {
    sendSubmitDuplicateWarning_(current);
  }
}

function responseToLeaveRecord_(response) {
  const result = {name: "", type: "", date: "", start: "", end: "", reason: ""};

  response.getItemResponses().forEach(itemResponse => {
    const title = itemResponse.getItem().getTitle();
    const value = itemResponse.getResponse();

    if (title === "姓名") result.name = normalizeText_(value);
    if (title === "請假類型") result.type = normalizeText_(value);
    if (title === "事由") result.reason = normalizeText_(value);
    if (title === "請假起始時間") result.start = normalizeTime_(value);
    if (title === "請假結束時間") result.end = normalizeTime_(value);
    if (title === "請假日期") {
      const date = parseDate_(value);
      if (date) {
        result.date = Utilities.formatDate(date, LEAVE_TIME_ZONE, "yyyy/M/d");
      }
    }
  });

  return result;
}

function duplicatePropertyKey_(record) {
  const raw = [
    normalizeText_(record.name),
    record.date,
    normalizeTime_(record.start),
    normalizeTime_(record.end)
  ].join("|");
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, raw);
  return DUPLICATE_PROPERTY_PREFIX + Utilities.base64EncodeWebSafe(digest);
}

function responseMarker_(response) {
  if (typeof response.getId === "function" && response.getId()) {
    return response.getId();
  }
  return String(response.getTimestamp().getTime());
}

function sendSubmitDuplicateWarning_(record) {
  const cells = [record.name, record.type, record.date, record.start, record.end, record.reason]
    .map(value => "<td>" + escapeHtml_(value) + "</td>")
    .join("");
  const html =
    '<h2 style="color:#b91c1c">請假資料重複通知</h2>' +
    "<p>剛送出的資料與既有紀錄的姓名、日期及起訖時間完全相同，請檢查是否誤送。</p>" +
    '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">' +
    "<tr><th>姓名</th><th>類型</th><th>日期</th><th>起</th><th>迄</th><th>事由</th></tr>" +
    "<tr>" + cells + "</tr></table>";

  GmailApp.sendEmail(
    LEAVE_REPORT_EMAIL,
    record.date + " " + record.name + " 請假資料重複通知",
    "偵測到同一位員工在相同日期及相同起訖時間重複請假。",
    {htmlBody: html}
  );
}

/**
 * Run once after installing this version. It builds the O(1) duplicate index
 * from the linked response sheet without calling Form.getResponses().
 */
function rebuildDuplicateIndex() {
  const sheet = getResponseSheet_();
  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return;

  const columns = headerColumns_(values[0]);
  const required = ["姓名", "請假日期", "請假起始時間", "請假結束時間"];
  assertHeaders_(columns, required);

  const properties = PropertiesService.getScriptProperties();
  const oldIndex = properties.getProperties();
  Object.keys(oldIndex)
    .filter(key => key.indexOf(DUPLICATE_PROPERTY_PREFIX) === 0)
    .forEach(key => properties.deleteProperty(key));

  // setProperties() is batched to avoid one remote call per response.
  const batch = {};
  values.slice(1).forEach((row, index) => {
    const date = parseDate_(row[columns["請假日期"]]);
    const record = {
      name: normalizeText_(row[columns["姓名"]]),
      date: date ? Utilities.formatDate(date, LEAVE_TIME_ZONE, "yyyy/M/d") : "",
      start: normalizeTime_(row[columns["請假起始時間"]]),
      end: normalizeTime_(row[columns["請假結束時間"]])
    };
    if (record.name && record.date && record.start && record.end) {
      batch[duplicatePropertyKey_(record)] = "sheet-row-" + (index + 2);
    }
  });
  properties.setProperties(batch, false);
}

function getResponseSheet_() {
  const destinationId = FormApp.getActiveForm().getDestinationId();
  if (!destinationId) throw new Error("這份表單尚未連結回覆試算表。");
  const sheet = SpreadsheetApp.openById(destinationId).getSheetByName(RESPONSE_SHEET_NAME);
  if (!sheet) throw new Error("找不到工作表「" + RESPONSE_SHEET_NAME + "」。");
  return sheet;
}

function headerColumns_(headers) {
  return headers.reduce((result, header, index) => {
    result[normalizeText_(header)] = index;
    return result;
  }, {});
}

function assertHeaders_(columns, required) {
  const missing = required.filter(header => columns[header] === undefined);
  if (missing.length) throw new Error("找不到以下欄位：" + missing.join("、"));
}

function normalizeText_(value) {
  return value === null || value === undefined ? "" : String(value).trim();
}

function normalizeTime_(value) {
  if (!value) return "";
  if (value instanceof Date) {
    return Utilities.formatDate(value, LEAVE_TIME_ZONE, "HH:mm");
  }
  const text = String(value).trim();
  const afternoon = text.indexOf("下午") !== -1;
  const morning = text.indexOf("上午") !== -1;
  const parts = text.replace("上午", "").replace("下午", "").trim().split(":");
  let hour = Number(parts[0]);
  const minute = Number(parts[1]);
  if (!Number.isFinite(hour) || !Number.isFinite(minute) || minute < 0 || minute > 59) return "";
  if (afternoon && hour < 12) hour += 12;
  if (morning && hour === 12) hour = 0;
  if (hour < 0 || hour > 23) return "";
  return String(hour).padStart(2, "0") + ":" + String(minute).padStart(2, "0");
}

function parseDate_(value) {
  if (!value) return null;
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value;
  const match = String(value).trim().match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return date.getFullYear() === Number(match[1]) &&
    date.getMonth() === Number(match[2]) - 1 &&
    date.getDate() === Number(match[3]) ? date : null;
}

function escapeHtml_(value) {
  return normalizeText_(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
