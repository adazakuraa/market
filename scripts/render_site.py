# -*- coding: utf-8 -*-
"""
data/sector_strength.csv から、スマホ表示用の静的HTML(docs/index.html)を生成する。
"""
import os
from datetime import datetime, timezone, timedelta
import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "sector_strength.csv")
OUT_PATH = os.path.join(BASE_DIR, "docs", "index.html")

JST = timezone(timedelta(hours=9))

PERIOD_LABELS = {
    "1w": "1週間",
    "2w": "2週間",
    "1m": "1ヶ月",
    "3m": "3ヶ月",
    "6m": "6ヶ月",
}


def fmt(v):
    if pd.isna(v):
        return '<span class="na">-</span>'
    cls = "pos" if v > 0 else ("neg" if v < 0 else "zero")
    sign = "+" if v > 0 else ""
    return f'<span class="{cls}">{sign}{v:.1f}</span>'


def main():
    df = pd.read_csv(IN_PATH, index_col=0)
    df = df.sort_values("1m", ascending=False)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    rows_html = ""
    for sector, row in df.iterrows():
        cells = "".join(f"<td>{fmt(row[p])}</td>" for p in PERIOD_LABELS.keys())
        rows_html += f"<tr><td class='sector-name'>{sector}</td>{cells}</tr>\n"

    header_cells = "".join(f"<th>{label}</th>" for label in PERIOD_LABELS.values())

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>セクター強度ランキング</title>
<style>
  :root {{
    color-scheme: light dark;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0;
    padding: 16px;
    background: #0f1115;
    color: #e8e8e8;
  }}
  h1 {{
    font-size: 1.2rem;
    margin: 0 0 4px 0;
  }}
  .updated {{
    font-size: 0.75rem;
    color: #999;
    margin-bottom: 16px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }}
  th, td {{
    padding: 8px 6px;
    text-align: right;
    border-bottom: 1px solid #2a2d34;
    white-space: nowrap;
  }}
  th:first-child, td.sector-name {{
    text-align: left;
  }}
  td.sector-name {{
    font-weight: 600;
  }}
  th {{
    color: #aaa;
    font-weight: 500;
    font-size: 0.72rem;
  }}
  .pos {{ color: #4caf50; font-weight: 600; }}
  .neg {{ color: #f44336; font-weight: 600; }}
  .zero, .na {{ color: #888; }}
  .note {{
    margin-top: 16px;
    font-size: 0.72rem;
    color: #777;
    line-height: 1.5;
  }}
  nav {{
    margin-bottom: 16px;
    font-size: 0.8rem;
  }}
  nav a {{
    color: #6ab7ff;
    margin-right: 12px;
    text-decoration: none;
  }}
</style>
</head>
<body>
  <nav><a href="#">セクター強度</a></nav>
  <h1>セクター強度ランキング（TOPIX比・相対強度）</h1>
  <div class="updated">最終更新: {now}</div>
  <table>
    <thead>
      <tr><th>業種</th>{header_cells}</tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <div class="note">
    ・数値はTOPIX（代理:1306.T）に対する相対リターン（ポイント差、単純平均）です。プラスがTOPIXより強い、マイナスが弱いことを示します。<br>
    ・対象は東証プライム市場の中〜大型株（TOPIX Core30/Large70/Mid400相当）のみ。<br>
    ・1ヶ月の強さ順に並んでいます。
  </div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
