from __future__ import annotations
import json
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER_JSON = ROOT / "uk_presence_ledger.v2.json"
OUT_ROLLING = ROOT / "presence_rolling_12m.json"
OUT_TAX = ROOT / "presence_tax_flags.json"

ROLLING_DAYS = 365
TAX_THRESHOLD_DAYS = 183  # 常用粗略阈值（你后面要做更完整 SRT 再升级）

def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)

def daterange_inclusive(a: dt.date, b: dt.date):
    # inclusive [a, b]
    cur = a
    one = dt.timedelta(days=1)
    while cur <= b:
        yield cur
        cur += one

def load_ledger() -> dict:
    return json.loads(LEDGER_JSON.read_text(encoding="utf-8"))

def compute_gb_days_last_rolling(ledger: dict, as_of: dt.date | None = None) -> dict:
    if as_of is None:
        as_of = dt.datetime.utcnow().date()

    window_start = as_of - dt.timedelta(days=ROLLING_DAYS - 1)  # 含当天，共 365 天
    gb_days = set()

    for stay in ledger.get("stays", []):
        if stay.get("country") != "GB":
            continue
        entry = parse_date(stay["entry"])
        exit_raw = stay.get("exit")
        exit_date = parse_date(exit_raw) if exit_raw else as_of

        # 跟滚动窗口求交集
        a = max(entry, window_start)
        b = min(exit_date, as_of)
        if a > b:
            continue

        for d in daterange_inclusive(a, b):
            gb_days.add(d)

    total = len(gb_days)
    return {
        "as_of": as_of.isoformat(),
        "window_start": window_start.isoformat(),
        "window_days": ROLLING_DAYS,
        "gb_days_count": total,
        "gb_days_list": sorted([d.isoformat() for d in gb_days])
    }

def compute_tax_flags(rolling: dict) -> dict:
    days = rolling["gb_days_count"]
    return {
        "as_of": rolling["as_of"],
        "gb_days_count": days,
        "threshold_183_met": days >= TAX_THRESHOLD_DAYS,
        "note": "这是粗略阈值判断；若你要严谨的 UK Statutory Residence Test (SRT)，后续我给你 v3.0。"
    }

def main():
    ledger = load_ledger()
    rolling = compute_gb_days_last_rolling(ledger)
    tax = compute_tax_flags(rolling)

    OUT_ROLLING.write_text(json.dumps(rolling, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_TAX.write_text(json.dumps(tax, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK")
    print("Rolling:", OUT_ROLLING)
    print("Tax:", OUT_TAX)

if __name__ == "__main__":
    main()
