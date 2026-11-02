"""Wash-facility query formatting with the original per-code calculation."""
from datetime import datetime
import pandas as pd
from .carwash_product_repository import canonical_name


def _to_date(s):
    return pd.to_datetime(s, errors="coerce").date() if str(s).strip() else None


def _to_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def carwash_query_rows(df_carwash, query_ids=None, today=None):
    if query_ids is None:
        query_ids = sorted({str(value).strip() for value in df_carwash["貨品編號"] if str(value).strip()})
    result_rows = []
    today = today or datetime.now().date()
    
    for pid in query_ids:
    
        pid_df = df_carwash[
            df_carwash["貨品編號"].astype(str).str.strip() == pid
        ].copy()
    
        pid_df["初始庫存日期_dt"] = pid_df["初始庫存日期"].map(_to_date)
        pid_df["入庫日期_dt"] = pid_df["入庫日期"].map(_to_date)
        pid_df["出庫日期_dt"] = pid_df["出庫日期"].map(_to_date)
        pid_df["初始數量_num"] = pid_df["初始數量"].map(_to_float)
        pid_df["數量_num"] = pid_df["數量"].map(_to_float)
    
        latest_init = pid_df[
            pid_df["初始庫存日期_dt"].notna()
        ].sort_values("初始庫存日期_dt", ascending=False)
    
        if not latest_init.empty:
            init_row = latest_init.iloc[0]
            init_date = init_row["初始庫存日期_dt"]
            init_qty = init_row["初始數量_num"]
            unit = str(init_row.get("單位", "")).strip()
        else:
            init_date = None
            init_qty = 0.0
            unit = ""
    
        # 若期初記錄沒有單位，從所有記錄補齊
        if not unit:
            all_units = pid_df["單位"].astype(str).str.strip().replace("", pd.NA).dropna().tolist()
            unit = max(set(all_units), key=all_units.count) if all_units else "KG"
    
        if init_date is not None:
    
            in_mask = (
                (pid_df["類型"].astype(str).str.strip() == "入庫") &
                (pid_df["入庫日期_dt"].notna()) &
                (pid_df["入庫日期_dt"] >= init_date) &
                (pid_df["入庫日期_dt"] <= today)
            )
    
            out_mask = (
                (pid_df["類型"].astype(str).str.strip() == "出庫") &
                (pid_df["出庫日期_dt"].notna()) &
                (pid_df["出庫日期_dt"] >= init_date) &
                (pid_df["出庫日期_dt"] <= today)
            )
    
        else:
    
            in_mask = (
                (pid_df["類型"].astype(str).str.strip() == "入庫") &
                (pid_df["入庫日期_dt"].notna()) &
                (pid_df["入庫日期_dt"] <= today)
            )
    
            out_mask = (
                (pid_df["類型"].astype(str).str.strip() == "出庫") &
                (pid_df["出庫日期_dt"].notna()) &
                (pid_df["出庫日期_dt"] <= today)
            )
    
        in_qty = pid_df.loc[in_mask, "數量_num"].sum()
        out_qty = pid_df.loc[out_mask, "數量_num"].sum()
    
        current_qty = init_qty + in_qty - out_qty
    
        # 出入庫歷程
        history = []
    
        if init_date is not None:
    
            init_registrar = str(init_row.get("登記人", "")).strip()
    
            history.append((
                init_date,
                f"{init_date.strftime('%Y-%m-%d')}｜期初庫存 {init_qty:g}{unit}｜{init_registrar}"
            ))
    
            history_source = pid_df[
                ((pid_df["類型"].astype(str).str.strip() == "入庫") &
                 (pid_df["入庫日期_dt"] >= init_date)) |
                ((pid_df["類型"].astype(str).str.strip() == "出庫") &
                 (pid_df["出庫日期_dt"] >= init_date))
            ].copy()
    
        else:
    
            history_source = pid_df[
                pid_df["類型"].astype(str).str.strip().isin(["入庫", "出庫"])
            ].copy()
    
        for _, row in history_source.iterrows():
    
            rec_type = str(row.get("類型", "")).strip()
    
            rec_date = (
                row.get("入庫日期_dt") if rec_type == "入庫"
                else row.get("出庫日期_dt")
            )
    
            if rec_date is None:
                continue
    
            rec_qty = _to_float(row.get("數量_num", 0))
            rec_unit = str(row.get("單位", "")).strip()
            rec_name = str(row.get("登記人", "")).strip()
    
            history.append((
                rec_date,
                f"{rec_date.strftime('%Y-%m-%d')}｜{rec_type} {rec_qty:g}{rec_unit}｜{rec_name}"
            ))
    
        history_text = "\n".join([
            h[1] for h in sorted(history, key=lambda x: x[0], reverse=True)
        ])
    
        note_candidates = []
    
        for _, row in pid_df.iterrows():
    
            note_text = str(row.get("備註", "")).strip()
    
            if note_text:
    
                rec_type = str(row.get("類型", "")).strip()
    
                candidate_dates = []
    
                if rec_type == "初始庫存":
                    candidate_dates.append(row.get("初始庫存日期_dt"))
    
                elif rec_type == "入庫":
                    candidate_dates.append(row.get("入庫日期_dt"))
    
                elif rec_type == "出庫":
                    candidate_dates.append(row.get("出庫日期_dt"))
    
                else:
                    candidate_dates.extend([
                        row.get("初始庫存日期_dt"),
                        row.get("入庫日期_dt"),
                        row.get("出庫日期_dt"),
                    ])
    
                note_date = next((d for d in candidate_dates if d is not None), None)
    
                if note_date is not None:
                    note_candidates.append((note_date, note_text))
    
                else:
                    note_candidates.append((datetime.min.date(), note_text))
    
        latest_note = "-"
    
        if note_candidates:
            latest_note = sorted(note_candidates, key=lambda x: x[0], reverse=True)[0][1]
    
        current_qty_display = f"{current_qty:.6f}".rstrip("0").rstrip(".")

        result_rows.append({
            "產品編號": pid,
            "期初庫存": f"{init_qty:g} {unit}".strip(),
            "區間入庫": f"{in_qty:g} {unit}".strip(),
            "區間出庫": f"{out_qty:g} {unit}".strip(),
            "目前庫存": current_qty_display,
            "單位": unit,
            "出入庫歷程": history_text or "-",
            "備註": latest_note,
            "_目前庫存數值": current_qty,
            "_期初庫存數值": init_qty, "_入庫數值": in_qty, "_出庫數值": out_qty,
            "_單位種類": sorted({str(v).strip().upper() for v in pid_df["單位"] if str(v).strip()}),
        })
    
    result_df = pd.DataFrame(result_rows).sort_values("產品編號") if result_rows else pd.DataFrame()
    return result_df if result_rows else pd.DataFrame(columns=["產品編號", "目前庫存", "單位", "_目前庫存數值", "_期初庫存數值", "_入庫數值", "_出庫數值"])


def group_carwash_rows(frame, aliases):
    if not aliases or frame.empty:
        return frame.copy()
    groups = {}
    for row in frame.to_dict("records"):
        groups.setdefault(canonical_name(row["產品編號"], aliases), []).append(row)
    result = []
    for name, rows in groups.items():
        if len(rows) == 1 and rows[0]["產品編號"] == name:
            result.append(rows[0])
            continue
        units = {value for row in rows for value in row.get("_單位種類", [str(row["單位"]).strip().upper()])}
        if len(units) != 1:
            result.extend(dict(row, 備註=f"合併群組單位不一致，保留原編號；{row['備註']}") for row in rows)
            continue
        unit = rows[0]["單位"]
        totals = {key: sum(row[key] for row in rows) for key in
                  ("_目前庫存數值", "_期初庫存數值", "_入庫數值", "_出庫數值")}
        result.append({
            "產品編號": name,
            "期初庫存": f"{totals['_期初庫存數值']:g} {unit}".strip(),
            "區間入庫": f"{totals['_入庫數值']:g} {unit}".strip(),
            "區間出庫": f"{totals['_出庫數值']:g} {unit}".strip(),
            "目前庫存": f"{totals['_目前庫存數值']:.6f}".rstrip("0").rstrip("."),
            "單位": unit,
            "出入庫歷程": "\n".join(f"【{row['產品編號']}】\n{row['出入庫歷程']}" for row in rows),
            "備註": "；".join(f"{row['產品編號']}：{row['備註']}" for row in rows if row["備註"] != "-") or "-",
            **totals,
        })
    return pd.DataFrame(result).sort_values("產品編號")
