import yaml, datetime as dt
from pathlib import Path

LEDGER = Path("uk_presence_ledger.v2.yaml")

ROLLING_DAYS = 365
TAX_THRESHOLD = 183

def daterange(a,b):
    d=a
    while d<=b:
        yield d
        d+=dt.timedelta(days=1)

def load():
    return yaml.safe_load(LEDGER.read_text())

def compute():
    data=load()
    today=dt.date.today()
    window_start=today-dt.timedelta(days=ROLLING_DAYS-1)

    days=set()

    for s in data["stays"]:
        if s["country"]!="GB":
            continue
        entry=dt.date.fromisoformat(s["entry"])
        exit=dt.date.fromisoformat(s["exit"]) if s["exit"] else today

        a=max(entry,window_start)
        b=min(exit,today)

        if a<=b:
            for d in daterange(a,b):
                days.add(d)

    total=len(days)

    print("=== UK Presence Auto Result ===")
    print("Rolling 12 months UK days:",total)
    print("183-day threshold met:", total>=TAX_THRESHOLD)

if __name__=="__main__":
    compute()
