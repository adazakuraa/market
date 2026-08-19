# -*- coding: utf-8 -*-
"""
data/calendar.json から、経済指標カレンダーページ(docs/calendar.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "calendar.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "calendar.html")

JST = timezone(timedelta(hours=9))


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    events = payload.get("events", [])
    generated_at = payload.get("generated_at", "")
    now_dt = datetime.now(JST)
    now = now_dt.strftime("%Y-%m-%d %H:%M JST")
    today_str = now_dt.strftime("%Y-%m-%d")

    CATEGORY_LABEL = {"boj": "🏦 日銀", "fomc": "🇺🇸 FOMC"}
    CATEGORY_CLASS = {"boj": "badge-boj", "fomc": "badge-fomc"}

    rows_html = ""
    next_marked = False
    for e in events:
        is_past = e["date"] < today_str
        is_next = (not is_past) and (not next_marked)
        if is_next:
            next_marked = True
        row_class = "past" if is_past else ("next" if is_next else "")
        cat = e.get("category", "")
        badge = f'<span class="badge {CATEGORY_CLASS.get(cat, "")}">{CATEGORY_LABEL.get(cat, cat)}</span>'
        next_tag = '<span class="next-tag">次回</span>' if is_next else ""
        rows_html += f"""<div class="event-row {row_class}">
  <div class="event-date">{e['date']}</div>
  <div class="event-body">
    {badge}{next_tag}
    <div class="event-title">{e['title']}</div>
    <div class="event-detail">{e['detail']}</div>
  </div>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>経済指標カレンダー</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 8px; }}
  .source-note {{ font-size: 0.68rem; color: #666; margin-bottom: 16px; line-height: 1.5; }}
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}
  nav.nav-secondary {{ margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }}
  nav.nav-secondary a {{ color: #888; margin-right: 12px; text-decoration: none; }}
  nav.nav-secondary a.active {{ color: #6ab7ff; font-weight: 600; text-decoration: underline; }}

  .event-row {{
    display: flex; gap: 12px; background: #171a20; border-radius: 10px;
    padding: 12px 14px; margin-bottom: 8px;
  }}
  .event-row.past {{ opacity: 0.45; }}
  .event-row.next {{ border: 1px solid #2f4a63; background: #141c26; }}
  .event-date {{ font-size: 0.8rem; color: #ccc; min-width: 78px; }}
  .event-title {{ font-size: 0.9rem; font-weight: 600; margin-top: 4px; }}
  .event-detail {{ font-size: 0.72rem; color: #999; margin-top: 2px; }}
  .badge {{ font-size: 0.68rem; padding: 2px 8px; border-radius: 10px; }}
  .badge-boj {{ background: #1b2a3a; color: #6ab7ff; }}
  .badge-fomc {{ background: #1b3a24; color: #4caf50; }}
  .next-tag {{
    font-size: 0.65rem; background: #3a2f1b; color: #ffd54f;
    padding: 2px 8px; border-radius: 10px; margin-left: 6px;
  }}
</style>
</head>
<body>
  <nav class="nav-primary">
    <a href="weather.html">天気</a>
    <a href="news.html">ニュース</a>
    <a href="index.html" class="active">株</a>
  </nav>
  <nav class="nav-secondary">
    <a href="index.html">セクター強度</a>
    <a href="screening.html">スクリーニング</a>
    <a href="stock.html">銘柄詳細</a>
    <a href="watch.html">ウォッチリスト</a>
    <a href="japan_economy.html">日本の経済状況</a>
    <a href="overseas.html">海外指標</a>
    <a href="commodities.html">資源</a>
    <a href="calendar.html" class="active">経済指標カレンダー</a>
  </nav>
  <h1>経済指標カレンダー</h1>
  <div class="updated">最終更新: {now}（データ更新: {generated_at}）</div>
  <div class="source-note">
    日銀金融政策決定会合・FOMCの日程を表示しています（結果公表日ベース）。出典: 日本銀行／FRB公式発表。<br>
    年1回、日銀・FRBが翌年分の日程を公式発表するタイミングで更新が必要です。
  </div>

  {rows_html}
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
