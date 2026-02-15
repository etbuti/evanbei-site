from __future__ import annotations
import json
import datetime as dt
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent
LEDGER = BASE / "presence_ledger.v3.yaml"
OUTDIR = BASE / "out"
OUTDIR.mkdir(exist_ok=True)

OUT_KPI = OUTDIR / "kpi_presence.json"
OUT_THRESH = OUTDIR / "kpi_thresholds.json"

def dual_residency_advisor(kpi, thresholds):

    uk_days = thresholds["uk"]["rolling_12m_days"]
    cn_days = thresholds["cn"]["calendar_year_days"]

    advice = {
        "mode": "balanced_global",
        "uk_status": "",
        "cn_status": "",
        "advice": []
    }

    # --- UK 判断 ---
    if uk_days >= 183:
        advice["uk_status"] = "HIGH_RISK"
        advice["advice"].append("⚠️ UK rolling days exceed 183 — consider reducing UK presence.")
    elif uk_days >= 150:
        advice["uk_status"] = "APPROACHING"
        advice["advice"].append("UK days approaching threshold — consider scheduling non-UK travel.")
    else:
        advice["uk_status"] = "SAFE"

    # --- China 判断 ---
    if cn_days >= 183:
        advice["cn_status"] = "HIGH_RISK"
        advice["advice"].append("⚠️ China calendar days exceed 183 — global IIT risk increases.")
    elif cn_days >= 150:
        advice["cn_status"] = "APPROACHING"
        advice["advice"].append("China days approaching threshold — consider offshore period.")
    else:
        advice["cn_status"] = "SAFE"

    # --- 双边策略 ---
    if advice["uk_status"] == "APPROACHING" and advice["cn_status"] == "SAFE":
        advice["advice"].append("→ 建议短期转移到中国或第三地。")

    if advice["cn_status"] == "APPROACHING" and advice["uk_status"] == "SAFE":
        advice["advice"].append("→ 建议短期转移到英国或第三地。")

    if advice["cn_status"] == "SAFE" and advice["uk_status"] == "SAFE":
        advice["advice"].append("✓ 当前双阈值均安全，可自由安排。")

    return advice


def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)

def daterange_inclusive(a: dt.date, b: dt.date):
    cur = a
    one = dt.timedelta(days=1)
    while cur <= b:
        yield cur
        cur += one

def load_ledger() -> dict:
    return yaml.safe_load(LEDGER.read_text(encoding="utf-8"))

def dayset_for_country(stays: list[dict], country: str, start: dt.date, end: dt.date) -> set[dt.date]:
    """Return set of days in [start,end] inclusive that are inside 'country' stays."""
    s = set()
    for st in stays:
        if st.get("country") != country:
            continue
        entry = parse_date(st["entry"])
        exit_raw = st.get("exit")
        exit_d = parse_date(exit_raw) if exit_raw else end  # open-ended => assume still there until 'end'
        # intersect with window
        a = max(entry, start)
        b = min(exit_d, end)
        if a <= b:
            for d in daterange_inclusive(a, b):
                s.add(d)
    return s

def uk_tax_year_bounds(today: dt.date, starts_m: int, starts_d: int) -> tuple[dt.date, dt.date]:
    """
    UK tax year runs 6 Apr -> 5 Apr.
    Return current tax-year bounds containing 'today'.
    """
    start_this_year = dt.date(today.year, starts_m, starts_d)
    if today >= start_this_year:
        start = start_this_year
        end = dt.date(today.year + 1, starts_m, starts_d) - dt.timedelta(days=1)
    else:
        start = dt.date(today.year - 1, starts_m, starts_d)
        end = start_this_year - dt.timedelta(days=1)
    return start, end

def calendar_year_bounds(today: dt.date) -> tuple[dt.date, dt.date]:
    return dt.date(today.year, 1, 1), dt.date(today.year, 12, 31)

def main():
    ledger = load_ledger()
    stays = ledger.get("stays", [])
    t = ledger["thresholds"]

    today = dt.date.today()

    # --- UK rolling 12 months ---
    rolling_days = int(t["uk"]["rolling_days_window"])
    rolling_start = today - dt.timedelta(days=rolling_days - 1)
    uk_roll = dayset_for_country(stays, "GB", rolling_start, today)

    # --- UK tax year ---
    uk_ty_start, uk_ty_end = uk_tax_year_bounds(
        today,
        int(t["uk"]["tax_year"]["starts_month"]),
        int(t["uk"]["tax_year"]["starts_day"]),
    )
    uk_ty = dayset_for_country(stays, "GB", uk_ty_start, min(today, uk_ty_end))

    # --- China calendar year ---
    cn_year_start, cn_year_end = calendar_year_bounds(today)
    cn_year = dayset_for_country(stays, "CN", cn_year_start, min(today, cn_year_end))

    # --- Results ---
    kpi = {
        "as_of": today.isoformat(),
        "uk": {
            "rolling_12m": {
                "window_start": rolling_start.isoformat(),
                "window_end": today.isoformat(),
                "days": len(uk_roll),
            },
            "tax_year": {
                "tax_year_start": uk_ty_start.isoformat(),
                "tax_year_end": uk_ty_end.isoformat(),
                "days_so_far": len(uk_ty),
            }
        },
        "cn": {
            "calendar_year": {
                "year_start": cn_year_start.isoformat(),
                "year_end": cn_year_end.isoformat(),
                "days_so_far": len(cn_year),
            }
        }
    }

    thresh = {
        "as_of": today.isoformat(),
        "uk": {
            "rolling_12m_days": len(uk_roll),
            "threshold_183_met": len(uk_roll) >= int(t["uk"]["rolling_day_threshold"]),
            "note": "UK residency is determined by Statutory Residence Test (SRT). 183-day is a useful trigger, not the full test."
        },
        "cn": {
            "calendar_year_days": len(cn_year),
            "threshold_183_met": len(cn_year) >= int(t["cn"]["calendar_year_day_threshold"]),
            "six_year_rule_enabled": bool(t["cn"]["six_year_rule"]["enabled"]),
            "note": "China IIT residency uses calendar year day count (183). Six-year rule needs consecutive-year tracking + 30-day single-trip reset details."
        }
    }

    OUT_KPI.write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_THRESH.write_text(json.dumps(thresh, ensure_ascii=False, indent=2), encoding="utf-8")

# --- Dual advisor (already added previously) ---
advisor = dual_residency_advisor(kpi, thresh)
(Path("out/dual_advisor.json")).write_text(
    json.dumps(advisor, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

# --- Residency Autopilot ---
# 你当前在英国，因此“继续英国”从明天开始模拟（今天已计入现状）
tomorrow = today + dt.timedelta(days=1)

# 假设：若你从现在起回中国并一直待着，也从明天开始模拟
# （如果你想把“今天”也算进中国那边，把 tomorrow 改成 today 即可）
autopilot = {
    "as_of": today.isoformat(),
    "assumptions": {
        "uk_continue_from": tomorrow.isoformat(),
        "cn_switch_from": tomorrow.isoformat(),
        "count_method": ledger.get("meta", {}).get("count_method", "inclusive"),
        "note": "simulation assumes continuous daily presence in the target country from the start date."
    },
    "uk": {},
    "cn": {},
    "recommended_moves": []
}

# UK rolling 12m trigger + buffer
uk_threshold = int(t["uk"]["rolling_day_threshold"])
uk_buffer = 170  # 你可改：160/170/175/180
autopilot["uk"]["current_rolling_12m_days"] = thresh["uk"]["rolling_12m_days"]
autopilot["uk"]["buffer"] = simulate_buffer_date(stays, "GB", tomorrow, uk_buffer, "uk_rolling")
autopilot["uk"]["threshold"] = simulate_threshold_date(stays, "GB", tomorrow, uk_threshold, "uk_rolling")

# China calendar-year trigger + buffer
cn_threshold = int(t["cn"]["calendar_year_day_threshold"])
cn_buffer = 170  # 你可改
autopilot["cn"]["current_calendar_year_days"] = thresh["cn"]["calendar_year_days"]
autopilot["cn"]["buffer"] = simulate_buffer_date(stays, "CN", tomorrow, cn_buffer, "cn_calendar")
autopilot["cn"]["threshold"] = simulate_threshold_date(stays, "CN", tomorrow, cn_threshold, "cn_calendar")

# Simple actionable recommendations
uk_buf_date = autopilot["uk"]["buffer"]["buffer_date"]
uk_trig_date = autopilot["uk"]["threshold"]["trigger_date"]
cn_buf_date = autopilot["cn"]["buffer"]["buffer_date"]
cn_trig_date = autopilot["cn"]["threshold"]["trigger_date"]

if uk_buf_date:
    autopilot["recommended_moves"].append(
        f"UK预警线({uk_buffer})预计触达日：{uk_buf_date}；建议在此日前安排离境/第三地缓冲。"
    )
if uk_trig_date:
    autopilot["recommended_moves"].append(
        f"UK 183(rolling)预计触达日：{uk_trig_date}；这之前务必规划停留结构。"
    )

if cn_buf_date:
    autopilot["recommended_moves"].append(
        f"中国预警线({cn_buffer})预计触达日：{cn_buf_date}（按当年累计）；建议在此日前安排海外窗口。"
    )
if cn_trig_date:
    autopilot["recommended_moves"].append(
        f"中国 183(公历年)预计触达日：{cn_trig_date}；这之前务必规划停留结构。"
    )

(Path("out/residency_autopilot.json")).write_text(
    json.dumps(autopilot, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

    
    print("OK")
    print("Wrote:", OUT_KPI)
    print("Wrote:", OUT_THRESH)

if __name__ == "__main__":
    main()

advisor = dual_residency_advisor(kpi, thresh)
(Path("out/dual_advisor.json")).write_text(
    json.dumps(advisor, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

def compute_uk_rolling_days(stays, day, rolling_days=365):
    window_start = day - dt.timedelta(days=rolling_days - 1)
    uk_roll = dayset_for_country(stays, "GB", window_start, day)
    return len(uk_roll), window_start

def compute_cn_calendar_days(stays, day):
    year_start = dt.date(day.year, 1, 1)
    cn_year = dayset_for_country(stays, "CN", year_start, day)
    return len(cn_year), year_start

def simulate_threshold_date(
    stays,
    country: str,
    start_day: dt.date,
    threshold: int,
    mode: str,
    max_forward_days: int = 800,
):
    """
    mode:
      - "uk_rolling": rolling 365-day window count for GB
      - "cn_calendar": calendar-year count for CN (current year)
    assumption:
      from start_day onward, person stays in 'country' every day (inclusive).
    returns:
      dict with trigger_date, days_needed, and a small trace
    """
    d = start_day
    trace = []
    for i in range(max_forward_days + 1):
        # Build an "assumed presence" stay from start_day -> d for simulation
        sim_stays = list(stays) + [{
            "country": country,
            "entry": start_day.isoformat(),
            "exit": d.isoformat()
        }]

        if mode == "uk_rolling":
            count, win_start = compute_uk_rolling_days(sim_stays, d, 365)
            trace_item = {"day": d.isoformat(), "count": count, "window_start": win_start.isoformat()}
        elif mode == "cn_calendar":
            count, ystart = compute_cn_calendar_days(sim_stays, d)
            trace_item = {"day": d.isoformat(), "count": count, "year_start": ystart.isoformat()}
        else:
            raise ValueError("unknown mode")

        if i in (0, 1, 7, 30, 60, 120) or count >= threshold - 3:
            trace.append(trace_item)

        if count >= threshold:
            return {
                "trigger_date": d.isoformat(),
                "days_forward": i,
                "count_on_trigger": count,
                "trace": trace[-12:],  # keep last few
            }

        d = d + dt.timedelta(days=1)

    return {
        "trigger_date": None,
        "days_forward": None,
        "count_on_trigger": None,
        "trace": trace[-12:],
        "note": "not reached within simulation horizon"
    }

def simulate_buffer_date(
    stays,
    country: str,
    start_day: dt.date,
    buffer_value: int,
    mode: str,
    max_forward_days: int = 800,
):
    """Same as simulate_threshold_date but for buffer (early warning) point."""
    d = start_day
    for i in range(max_forward_days + 1):
        sim_stays = list(stays) + [{
            "country": country,
            "entry": start_day.isoformat(),
            "exit": d.isoformat()
        }]
        if mode == "uk_rolling":
            count, _ = compute_uk_rolling_days(sim_stays, d, 365)
        elif mode == "cn_calendar":
            count, _ = compute_cn_calendar_days(sim_stays, d)
        else:
            raise ValueError("unknown mode")

        if count >= buffer_value:
            return {"buffer_date": d.isoformat(), "days_forward": i, "count": count}
        d = d + dt.timedelta(days=1)

    return {"buffer_date": None, "days_forward": None, "count": None}



