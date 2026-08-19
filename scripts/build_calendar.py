# -*- coding: utf-8 -*-
"""
日銀金融政策決定会合とFOMC(米連邦公開市場委員会)の日程カレンダーを生成する。

外部APIには依存せず、公式発表済みの年間スケジュールを直接コードに持つ方式。
(日銀・FRBとも、その年の日程を前年半ば〜年初に公式発表するため、
 年1回程度、このファイルの日程リストを更新する必要がある)

出典:
- 日銀: https://www.boj.or.jp/mopo/mpmsche_minu/index.htm
- FRB: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

出力: data/calendar.json
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(BASE_DIR, "data", "calendar.json")

JST = timezone(timedelta(hours=9))

# 日銀 金融政策決定会合(結果公表日=2日目の日付を採用)。2026年分。
BOJ_MEETINGS = [
    {"date": "2026-01-23", "range": "1/22-23"},
    {"date": "2026-03-19", "range": "3/18-19"},
    {"date": "2026-04-28", "range": "4/27-28"},
    {"date": "2026-06-16", "range": "6/15-16"},
    {"date": "2026-07-31", "range": "7/30-31"},
    {"date": "2026-09-18", "range": "9/17-18"},
    {"date": "2026-10-30", "range": "10/29-30"},
    {"date": "2026-12-18", "range": "12/17-18"},
]

# FOMC(米国時間、結果公表日=2日目の日付を採用)。日本時間では通常翌日未明(深夜)に発表。
FOMC_MEETINGS = [
    {"date": "2026-01-28", "range": "1/27-28(米国時間)"},
    {"date": "2026-03-18", "range": "3/17-18(米国時間)"},
    {"date": "2026-04-29", "range": "4/28-29(米国時間)"},
    {"date": "2026-06-17", "range": "6/16-17(米国時間)"},
    {"date": "2026-07-29", "range": "7/28-29(米国時間)"},
    {"date": "2026-09-16", "range": "9/15-16(米国時間)"},
    {"date": "2026-10-28", "range": "10/27-28(米国時間)"},
    {"date": "2026-12-09", "range": "12/8-9(米国時間)"},
    # 2027年分(参考、FRBが2025年9月に発表済み)
    {"date": "2027-01-27", "range": "1/26-27(米国時間)"},
    {"date": "2027-03-17", "range": "3/16-17(米国時間)"},
]


def build_events():
    events = []
    for m in BOJ_MEETINGS:
        events.append({
            "date": m["date"],
            "title": "日銀 金融政策決定会合",
            "detail": f"開催: {m['range']}（結果公表日を表示）",
            "category": "boj",
        })
    for m in FOMC_MEETINGS:
        events.append({
            "date": m["date"],
            "title": "FOMC(米連邦公開市場委員会)",
            "detail": f"開催: {m['range']}（日本時間では通常翌日未明に結果公表）",
            "category": "fomc",
        })
    events.sort(key=lambda e: e["date"])
    return events


def main():
    events = build_events()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    payload = {"generated_at": now, "events": events}

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"Saved {len(events)}件 -> {OUT_PATH}")


if __name__ == "__main__":
    main()
