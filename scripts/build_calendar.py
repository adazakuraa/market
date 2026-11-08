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
    # 2027年分(日銀が2026年7月31日に公表)
    {"date": "2027-01-22", "range": "1/21-22"},
    {"date": "2027-03-18", "range": "3/17-18"},
    {"date": "2027-04-28", "range": "4/27-28"},
    {"date": "2027-06-11", "range": "6/10-11"},
    {"date": "2027-07-22", "range": "7/21-22"},
    {"date": "2027-09-22", "range": "9/21-22"},
    {"date": "2027-10-29", "range": "10/28-29"},
    {"date": "2027-12-17", "range": "12/16-17"},
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
    # 2027年分(FRB公表の予定。各回の日程は直前の会合で正式確定)
    {"date": "2027-01-27", "range": "1/26-27(米国時間)"},
    {"date": "2027-03-17", "range": "3/16-17(米国時間)"},
    {"date": "2027-04-28", "range": "4/27-28(米国時間)"},
    {"date": "2027-06-09", "range": "6/8-9(米国時間)"},
    {"date": "2027-07-28", "range": "7/27-28(米国時間)"},
    {"date": "2027-09-15", "range": "9/14-15(米国時間)"},
    {"date": "2027-10-27", "range": "10/26-27(米国時間)"},
    {"date": "2027-12-08", "range": "12/7-8(米国時間)"},
]

# 登録済みの最終日程がこの日数以内に迫ったら、翌年分の追加が必要として失敗扱いにする
# (ワークフローが赤くなり、GitHubアプリに通知が届く)
REFILL_WARNING_DAYS = 60


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


def check_schedule_coverage():
    today = datetime.now(JST).date()
    problems = []
    for name, meetings in (("日銀", BOJ_MEETINGS), ("FOMC", FOMC_MEETINGS)):
        last = max(datetime.strptime(m["date"], "%Y-%m-%d").date() for m in meetings)
        if (last - today).days <= REFILL_WARNING_DAYS:
            problems.append(f"{name}の日程が{last}までしか登録されていません")
    return problems


def main():
    events = build_events()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    payload = {"generated_at": now, "events": events}

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"Saved {len(events)}件 -> {OUT_PATH}")

    problems = check_schedule_coverage()
    if problems:
        # カレンダー自体は保存したうえで、翌年分の追加が必要なことを知らせるため失敗終了する
        raise SystemExit("[要更新] " + " / ".join(problems) + "。build_calendar.py に翌年分の日程を追加してください。")


if __name__ == "__main__":
    main()
