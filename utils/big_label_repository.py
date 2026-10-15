"""Persist editable label layouts by formula number in the configured database."""

import json
import math
import re

from .database import connect_from_config, utc_now_iso

BIG_LABEL_EDITOR_COLUMNS = ["編號", "品名", "日期", "比例", "數量", "列印張數"]


def _cell(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def format_label_ratio_value(value, *, add_unit=False):
    text = _cell(value)
    ratio = re.sub(r"\s*g\s*/\s*kg\s*$", "", text, flags=re.IGNORECASE).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?(?:\s*[:：]\s*\d+(?:\.\d+)?)+", ratio):
        return re.sub(r"\s*[:：]\s*", ":", ratio)
    if add_unit and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        return f"{text}g/kg"
    return text

def normalize_big_label_editor_rows(rows):
    normalized = []
    for row in rows:
        try:
            count = max(0, int(float(row.get("列印張數", 0) or 0)))
        except (TypeError, ValueError, OverflowError):
            count = 0
        clean = {field: _cell(row.get(field, "")) for field in BIG_LABEL_EDITOR_COLUMNS[:-1]}
        clean["比例"] = format_label_ratio_value(clean["比例"])
        clean["列印張數"] = count
        if any(clean.values()):
            normalized.append(clean)
    return normalized


def _memory_key(order, label_kind="big"):
    key = _cell(order.get("配方編號") or order.get("生產單號"))
    return json.dumps(["small", key], ensure_ascii=False) if label_kind == "small" and key else key


def build_big_label_editor_defaults(config, order, labels, *, label_kind="big"):
    with connect_from_config(config) as conn:
        saved = conn.execute("SELECT rows_json FROM big_label_templates WHERE label_key=?", (_memory_key(order, label_kind),)).fetchone()
    if saved:
        remembered = normalize_big_label_editor_rows(json.loads(saved[0]))
        if remembered:
            return remembered
    grouped = {}
    for label in labels:
        key = tuple(_cell(label.get(field)) for field in ("編號", "名稱", "日期", "比例", "數量"))
        grouped[key] = grouped.get(key, 0) + 1
    return [
        {"編號": no, "品名": name, "日期": date, "比例": ratio, "數量": qty + "KG" if qty else "", "列印張數": count}
        for (no, name, date, ratio, qty), count in grouped.items()
    ] or [{"編號": _memory_key(order), "品名": _cell(order.get("顏色")), "日期": "", "比例": "", "數量": "", "列印張數": 1}]


def remember_big_label_rows(config, order, rows, *, label_kind="big"):
    key = _memory_key(order, label_kind)
    if not key:
        raise ValueError("請先填寫標籤編號")
    payload = json.dumps(normalize_big_label_editor_rows(rows), ensure_ascii=False, allow_nan=False)
    with connect_from_config(config) as conn:
        conn.execute(
            "INSERT INTO big_label_templates(label_key,rows_json,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(label_key) DO UPDATE SET rows_json=excluded.rows_json,updated_at=excluded.updated_at",
            (key, payload, utc_now_iso()),
        )


def expand_big_label_editor_rows(rows):
    labels = []
    for row in normalize_big_label_editor_rows(rows):
        label = {"編號": row["編號"], "名稱": row["品名"], "日期": row["日期"], "比例": row["比例"], "數量": row["數量"]}
        labels.extend(label.copy() for _ in range(row["列印張數"]))
    return labels
