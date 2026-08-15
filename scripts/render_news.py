# -*- coding: utf-8 -*-
"""
data/news.json から、カテゴリ別ニュース一覧ページ(docs/news.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "news.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "news.html")

JST = timezone(timedelta(hours=9))

CATEGORY_ORDER = ["政治", "経済", "国際", "社会", "日銀"]
CATEGORY_ICON = {"政治": "🏛️", "経済": "💹", "国際": "🌍", "社会": "🏙️", "日銀": "🏦"}


def render_items(items):
    if not items:
        return '<div class="empty">該当するニュースがありません</div>'
    rows = ""
    for item in items:
        published = item.get("published") or ""
        rows += f"""<a class="news-item" href="{item['link']}" target="_blank" rel="noopener">
  <div class="news-title">{item['title']}</div>
  <div class="news-meta">{published}</div>
</a>
"""
    return rows


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    categories = payload.get("categories", {})
    generated_at = payload.get("generated_at", "")
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    sections_html = ""
    for cat in CATEGORY_ORDER:
        items = categories.get(cat, [])
        icon = CATEGORY_ICON.get(cat, "")
        sections_html += f"""
  <div class="category-box">
    <div class="category-header" data-target="cat-{cat}">
      <span>{icon} {cat}</span>
      <span class="count">{len(items)}件</span>
    </div>
    <div class="category-list" id="cat-{cat}">
      {render_items(items)}
    </div>
  </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ニュース</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 8px; }}
  .source-note {{ font-size: 0.68rem; color: #666; margin-bottom: 16px; line-height: 1.5; }}
  nav {{ margin-bottom: 16px; font-size: 0.8rem; }}
  nav a {{ color: #6ab7ff; margin-right: 12px; text-decoration: none; }}
  nav a.active {{ color: #e8e8e8; font-weight: 600; text-decoration: underline; }}

  .category-box {{
    background: #171a20; border-radius: 10px; margin-bottom: 10px; overflow: hidden;
  }}
  .category-header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 14px; font-size: 0.9rem; font-weight: 600; cursor: pointer;
  }}
  .category-header .count {{ color: #888; font-weight: 400; font-size: 0.72rem; }}
  .category-list {{ border-top: 1px solid #23262e; }}
  .category-list.collapsed {{ display: none; }}
  .news-item {{
    display: block; padding: 10px 14px; text-decoration: none; color: inherit;
    border-bottom: 1px solid #1d2027;
  }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-title {{ font-size: 0.82rem; line-height: 1.4; color: #e8e8e8; }}
  .news-meta {{ font-size: 0.68rem; color: #777; margin-top: 3px; }}
  .empty {{ padding: 16px; font-size: 0.8rem; color: #777; text-align: center; }}
</style>
</head>
<body>
  <nav>
    <a href="index.html">セクター強度</a>
    <a href="screening.html">スクリーニング</a>
    <a href="stock.html">銘柄詳細</a>
    <a href="watch.html">ウォッチリスト</a>
    <a href="news.html" class="active">ニュース</a>
  </nav>
  <h1>ニュース</h1>
  <div class="updated">最終更新: {now}（データ取得: {generated_at}）</div>
  <div class="source-note">
    出典: NHKニュース（キーワードによる自動分類、スポーツ・芸能は除外）／日本銀行 新着情報。<br>
    見出しをタップすると出典サイトの元記事に移動します。分類は簡易的なキーワード判定のため、まれに実際のジャンルと異なる場合があります。
  </div>

  {sections_html}

  <script>
    document.querySelectorAll('.category-header').forEach(header => {{
      header.addEventListener('click', () => {{
        const target = document.getElementById(header.dataset.target);
        target.classList.toggle('collapsed');
      }});
    }});
  </script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()

