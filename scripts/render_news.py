# -*- coding: utf-8 -*-
"""
data/news.json から、タブ切り替え形式のニュースページ(docs/news.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "news.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "news.html")

JST = timezone(timedelta(hours=9))

CATEGORY_ORDER = ["政治", "経済", "国際", "社会", "IT", "AI", "科学", "論文"]
CATEGORY_ICON = {
    "政治": "🏛️", "経済": "💹", "国際": "🌍", "社会": "🏙️",
    "IT": "💻", "AI": "🤖", "科学": "🔬", "論文": "📄",
}


def render_items(items):
    if not items:
        return '<div class="empty">該当するニュースがありません</div>'
    rows = ""
    for item in items:
        published = item.get("published") or ""
        source = item.get("source") or ""
        rows += f"""<a class="news-item" href="{item['link']}" target="_blank" rel="noopener">
  <div class="news-title">{item['title']}</div>
  <div class="news-meta">{source}｜{published}</div>
</a>
"""
    return rows


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    categories = payload.get("categories", {})
    generated_at = payload.get("generated_at", "")
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    tabs_html = ""
    panels_html = ""
    for i, cat in enumerate(CATEGORY_ORDER):
        items = categories.get(cat, [])
        icon = CATEGORY_ICON.get(cat, "")
        active_tab = "active" if i == 0 else ""
        active_panel = "active" if i == 0 else ""

        tabs_html += f"""<button class="tab-btn {active_tab}" data-target="panel-{cat}">
  {icon} {cat}<span class="tab-count">{len(items)}</span>
</button>
"""
        panels_html += f"""<div class="category-panel {active_panel}" id="panel-{cat}">
  {render_items(items)}
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
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}

  .tab-bar {{
    display: flex; gap: 6px; overflow-x: auto; -webkit-overflow-scrolling: touch;
    margin-bottom: 12px; padding-bottom: 4px;
  }}
  .tab-btn {{
    flex: 0 0 auto;
    background: #171a20; color: #999; border: 1px solid #262a33;
    border-radius: 20px; padding: 8px 14px; font-size: 0.8rem; white-space: nowrap;
  }}
  .tab-btn.active {{
    background: #1b2a3a; color: #6ab7ff; border-color: #2f4a63; font-weight: 600;
  }}
  .tab-count {{
    display: inline-block; margin-left: 4px; font-size: 0.68rem; color: #888;
  }}
  .tab-btn.active .tab-count {{ color: #6ab7ff; }}

  .category-panel {{ display: none; background: #171a20; border-radius: 10px; overflow: hidden; }}
  .category-panel.active {{ display: block; }}
  .news-item {{
    display: block; padding: 10px 14px; text-decoration: none; color: inherit;
    border-bottom: 1px solid #1d2027;
  }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-title {{ font-size: 0.82rem; line-height: 1.4; color: #e8e8e8; }}
  .news-meta {{ font-size: 0.68rem; color: #777; margin-top: 3px; }}
  .empty {{ padding: 24px 16px; font-size: 0.8rem; color: #777; text-align: center; }}
</style>
</head>
<body>
  <nav class="nav-primary">
    <a href="index.html">株</a>
    <a href="news.html" class="active">ニュース</a>
    <a href="weather.html">天気</a>
  </nav>
  <h1>ニュース</h1>
  <div class="updated">最終更新: {now}（データ取得: {generated_at}）</div>
  <div class="source-note">
    出典: NHK／JCAST／AFPBB News／CNN.co.jp／朝日新聞／毎日新聞／日経ビジネス／ITmedia／GIGAZINE／はてなブックマーク／窓の杜／INTERNET Watch／Publickey／Qiita／WIRED.jp／ナゾロジー／Science Japan／arXiv。<br>
    分類はタイトルのキーワードによる自動判定です。スポーツ・芸能は除外していますが、まれに実際のジャンルと異なる場合があります。見出しをタップすると出典元の記事に移動します。
  </div>

  <div class="tab-bar">
    {tabs_html}
  </div>

  {panels_html}

  <script>
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.category-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active');
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
