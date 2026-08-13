# -*- coding: utf-8 -*-
"""
data/sector_strength.csv から、スマホ表示用の静的HTML(docs/index.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta
import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "sector_strength.csv")
TIMESERIES_PATH = os.path.join(BASE_DIR, "data", "sector_timeseries.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "index.html")

# チャートの線の色（33業種あっても見分けやすいよう固定パレットを使い回す）
CHART_COLORS = [
    "#4caf50", "#f44336", "#2196f3", "#ff9800", "#9c27b0",
    "#00bcd4", "#ffeb3b", "#e91e63", "#8bc34a", "#3f51b5",
    "#ff5722", "#009688", "#cddc39", "#607d8b", "#795548",
    "#03a9f4", "#ffc107", "#673ab7", "#4db6ac", "#f06292",
]

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

    with open(TIMESERIES_PATH, "r", encoding="utf-8") as f:
        timeseries = json.load(f)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    rows_html = ""
    for sector, row in df.iterrows():
        cells = "".join(f"<td>{fmt(row[p])}</td>" for p in PERIOD_LABELS.keys())
        rows_html += f"<tr><td class='sector-name'>{sector}</td>{cells}</tr>\n"

    header_cells = "".join(f"<th>{label}</th>" for label in PERIOD_LABELS.values())

    # チェックボックス一覧（表と同じ、1ヶ月の強い順）。上位5つをデフォルトでON
    default_checked = set(df.index[:5])
    checkbox_html = ""
    for i, sector in enumerate(df.index):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        checked = "checked" if sector in default_checked else ""
        checkbox_html += (
            f'<label class="chk-item">'
            f'<input type="checkbox" class="sector-chk" value="{sector}" {checked}>'
            f'<span class="swatch" style="background:{color}"></span>{sector}'
            f'</label>\n'
        )

    colors_json = json.dumps(CHART_COLORS)
    timeseries_json = json.dumps(timeseries, ensure_ascii=False)

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
  .chart-box {{
    background: #171a20;
    border-radius: 10px;
    padding: 12px;
    margin-bottom: 12px;
  }}
  .chart-controls {{
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .chart-controls button {{
    background: #23262e;
    color: #e8e8e8;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.72rem;
  }}
  .chk-list {{
    max-height: 180px;
    overflow-y: auto;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    margin-bottom: 10px;
    padding: 8px;
    background: #0f1115;
    border-radius: 8px;
  }}
  .chk-item {{
    display: flex;
    align-items: center;
    font-size: 0.72rem;
    gap: 4px;
    white-space: nowrap;
  }}
  .swatch {{
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
  }}
</style>
</head>
<body>
  <nav><a href="#">セクター強度</a></nav>
  <h1>セクター強度ランキング（TOPIX比・相対強度）</h1>
  <div class="updated">最終更新: {now}</div>

  <div class="chart-box">
    <div class="chart-controls">
      <button id="btn-select-all">全て選択</button>
      <button id="btn-select-none">全て解除</button>
    </div>
    <div class="chk-list">
      {checkbox_html}
    </div>
    <canvas id="sectorChart" height="220"></canvas>
  </div>

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
    ・1ヶ月の強さ順に並んでいます。<br>
    ・グラフは取得期間の最初の日を0とした、TOPIX対比の累積相対強度（ポイント）の推移です。
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const TIMESERIES = {timeseries_json};
    const COLORS = {colors_json};
    const sectorOrder = {json.dumps(list(df.index))};

    const colorOf = (sector) => {{
      const idx = sectorOrder.indexOf(sector);
      return COLORS[idx % COLORS.length];
    }};

    const ctx = document.getElementById('sectorChart').getContext('2d');
    const chart = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: TIMESERIES.dates,
        datasets: []
      }},
      options: {{
        responsive: true,
        animation: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ titleFont: {{ size: 10 }}, bodyFont: {{ size: 10 }} }}
        }},
        scales: {{
          x: {{
            ticks: {{ color: '#999', font: {{ size: 9 }}, maxTicksLimit: 6 }},
            grid: {{ color: '#23262e' }}
          }},
          y: {{
            ticks: {{ color: '#999', font: {{ size: 9 }} }},
            grid: {{ color: '#23262e' }},
            title: {{ display: true, text: 'ポイント(TOPIX対比)', color: '#777', font: {{ size: 9 }} }}
          }}
        }}
      }}
    }});

    function rebuildDatasets() {{
      const checked = Array.from(document.querySelectorAll('.sector-chk:checked')).map(el => el.value);
      chart.data.datasets = checked.map(sector => ({{
        label: sector,
        data: TIMESERIES.sectors[sector] || [],
        borderColor: colorOf(sector),
        backgroundColor: colorOf(sector),
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.15,
      }}));
      chart.update();
    }}

    document.querySelectorAll('.sector-chk').forEach(el => {{
      el.addEventListener('change', rebuildDatasets);
    }});
    document.getElementById('btn-select-all').addEventListener('click', () => {{
      document.querySelectorAll('.sector-chk').forEach(el => el.checked = true);
      rebuildDatasets();
    }});
    document.getElementById('btn-select-none').addEventListener('click', () => {{
      document.querySelectorAll('.sector-chk').forEach(el => el.checked = false);
      rebuildDatasets();
    }});

    rebuildDatasets();
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
