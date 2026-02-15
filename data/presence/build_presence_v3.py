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

    print("OK")
    print("Wrote:", OUT_KPI)
    print("Wrote:", OUT_THRESH)

if __name__ == "__main__":
    main()
