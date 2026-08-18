# -*- coding: utf-8 -*-
"""
data/sector_strength.csv から、スマホ表示用の静的HTML(docs/index.html)を生成する。
"""
import os
import json
from urllib.parse import quote
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

    header_cells = "".join(
        f'<th class="sortable" data-period="{key}">{label}</th>'
        for key, label in PERIOD_LABELS.items()
    )

    sector_rows_json = json.dumps(
        [{"sector": sector, **{p: (None if pd.isna(row[p]) else round(float(row[p]), 2)) for p in PERIOD_LABELS.keys()}}
         for sector, row in df.iterrows()],
        ensure_ascii=False,
    )

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
  td.sector-name a {{
    color: #e8e8e8;
    text-decoration: none;
    border-bottom: 1px dotted #555;
  }}
  th {{
    color: #aaa;
    font-weight: 500;
    font-size: 0.72rem;
  }}
  th.sortable {{
    cursor: pointer;
    user-select: none;
  }}
  th.sortable.active-sort {{
    color: #6ab7ff;
    font-weight: 700;
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
  nav.nav-primary {{
    margin-bottom: 6px;
    font-size: 0.85rem;
  }}
  nav.nav-primary a {{
    color: #6ab7ff;
    margin-right: 14px;
    text-decoration: none;
    font-weight: 600;
  }}
  nav.nav-primary a.active {{
    color: #e8e8e8;
    text-decoration: underline;
  }}
  nav.nav-secondary {{
    margin-bottom: 16px;
    font-size: 0.75rem;
    padding-left: 2px;
  }}
  nav.nav-secondary a {{
    color: #888;
    margin-right: 12px;
    text-decoration: none;
  }}
  nav.nav-secondary a.active {{
    color: #6ab7ff;
    font-weight: 600;
    text-decoration: underline;
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
  .chart-controls button.active-period {{
    background: #1b2a3a;
    color: #6ab7ff;
    border-color: #2f4a63;
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
  <nav class="nav-primary">
    <a href="weather.html">天気</a>
    <a href="news.html">ニュース</a>
    <a href="index.html" class="active">株</a>
  </nav>
  <nav class="nav-secondary">
    <a href="index.html" class="active">セクター強度</a>
    <a href="screening.html">スクリーニング</a>
    <a href="stock.html">銘柄詳細</a>
    <a href="watch.html">ウォッチリスト</a>
    <a href="japan_economy.html">日本の経済状況</a>
    <a href="overseas.html">海外指標</a>
    <a href="commodities.html">資源</a>
  </nav>
  <h1>セクター強度ランキング（TOPIX比・相対強度）</h1>
  <div class="updated">最終更新: {now}</div>

  <div class="chart-box">
    <div class="chart-controls">
      <button id="btn-select-all">全て選択</button>
      <button id="btn-select-none">全て解除</button>
    </div>
    <div class="chart-controls" id="period-controls">
      <button class="period-btn" data-days="5">1週間</button>
      <button class="period-btn" data-days="21">1ヶ月</button>
      <button class="period-btn" data-days="63">3ヶ月</button>
      <button class="period-btn" data-days="126">6ヶ月</button>
      <button class="period-btn active-period" data-days="0">全期間</button>
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
    <tbody id="strength-table-body"></tbody>
  </table>
  <div class="note">
    ・数値はTOPIX（代理:1306.T）に対する相対リターン（ポイント差、単純平均）です。プラスがTOPIXより強い、マイナスが弱いことを示します。<br>
    ・対象は東証プライム市場の中〜大型株（TOPIX Core30/Large70/Mid400相当）のみ。<br>
    ・見出し（1週間〜6ヶ月）をタップすると、その期間の強さ順に並び替えられます（初期表示は1ヶ月）。<br>
    ・グラフは取得期間の最初の日を0とした、TOPIX対比の累積相対強度（ポイント）の推移です。
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const TIMESERIES = {timeseries_json};
    const COLORS = {colors_json};
    const sectorOrder = {json.dumps(list(df.index))};
    const SECTOR_ROWS = {sector_rows_json};
    const PERIOD_LABELS = {json.dumps(PERIOD_LABELS, ensure_ascii=False)};

    function fmtCell(v) {{
      if (v === null || v === undefined) return '<span class="na">-</span>';
      const cls = v > 0 ? 'pos' : (v < 0 ? 'neg' : 'zero');
      const sign = v > 0 ? '+' : '';
      return `<span class="${{cls}}">${{sign}}${{v.toFixed(1)}}</span>`;
    }}

    let currentSort = '1m';

    function renderTable() {{
      const sorted = [...SECTOR_ROWS].sort((a, b) => {{
        const av = a[currentSort], bv = b[currentSort];
        if (av === null && bv === null) return 0;
        if (av === null) return 1;
        if (bv === null) return -1;
        return bv - av;
      }});
      const tbody = document.getElementById('strength-table-body');
      tbody.innerHTML = sorted.map(row => {{
        const url = `screening.html?sector=${{encodeURIComponent(row.sector)}}`;
        const cells = Object.keys(PERIOD_LABELS).map(p => `<td>${{fmtCell(row[p])}}</td>`).join('');
        return `<tr><td class="sector-name"><a href="${{url}}">${{row.sector}}</a></td>${{cells}}</tr>`;
      }}).join('');

      document.querySelectorAll('th.sortable').forEach(th => {{
        th.classList.toggle('active-sort', th.dataset.period === currentSort);
      }});
    }}

    document.querySelectorAll('th.sortable').forEach(th => {{
      th.addEventListener('click', () => {{
        currentSort = th.dataset.period;
        renderTable();
      }});
    }});

    renderTable();

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

    let currentPeriodDays = 0; // 0 = 全期間

    function sliceByPeriod(arr) {{
      if (currentPeriodDays <= 0 || arr.length <= currentPeriodDays) return arr;
      return arr.slice(arr.length - currentPeriodDays);
    }}

    function rebuildDatasets() {{
      const checked = Array.from(document.querySelectorAll('.sector-chk:checked')).map(el => el.value);
      chart.data.labels = sliceByPeriod(TIMESERIES.dates);
      chart.data.datasets = checked.map(sector => ({{
        label: sector,
        data: sliceByPeriod(TIMESERIES.sectors[sector] || []),
        borderColor: colorOf(sector),
        backgroundColor: colorOf(sector),
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.15,
      }}));
      chart.update();
    }}

    document.querySelectorAll('.period-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        currentPeriodDays = parseInt(btn.dataset.days, 10);
        document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active-period'));
        btn.classList.add('active-period');
        rebuildDatasets();
      }});
    }});

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
