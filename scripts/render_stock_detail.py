# -*- coding: utf-8 -*-
"""
data/stock_timeseries.json から、個別銘柄の詳細チャートページ(docs/stock.html)を生成する。
URLパラメータ ?ticker=XXXX.T で表示銘柄を指定できる(未指定なら先頭の銘柄)。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "stock_timeseries.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "stock.html")

JST = timezone(timedelta(hours=9))


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    options_html = "".join(
        f'<option value="{ticker}">{d["name"]}({ticker.replace(".T","")})</option>'
        for ticker, d in data.items()
    )

    data_json = json.dumps(data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>銘柄詳細</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  h3 {{ font-size: 0.8rem; margin: 16px 0 6px 0; color: #ccc; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 12px; }}
  nav {{ margin-bottom: 16px; font-size: 0.8rem; }}
  nav a {{ color: #6ab7ff; margin-right: 12px; text-decoration: none; }}
  nav a.active {{ color: #e8e8e8; font-weight: 600; text-decoration: underline; }}
  select {{
    width: 100%; background: #171a20; color: #e8e8e8; border: 1px solid #333;
    border-radius: 8px; padding: 10px; font-size: 0.9rem; margin-bottom: 12px;
  }}
  .chart-box {{ background: #171a20; border-radius: 10px; padding: 10px; margin-bottom: 12px; }}
  .stat-row {{
    display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; font-size: 0.72rem;
  }}
  .stat-chip {{ background: #171a20; border-radius: 8px; padding: 6px 10px; }}
  .stat-chip b {{ display: block; font-size: 0.95rem; margin-top: 2px; }}
  .legend-line {{ font-size: 0.68rem; color: #999; margin-bottom: 4px; }}
</style>
</head>
<body>
  <nav>
    <a href="index.html">セクター強度</a>
    <a href="screening.html">スクリーニング</a>
    <a href="stock.html" class="active">銘柄詳細</a>
  </nav>
  <h1>銘柄詳細</h1>
  <div class="updated">最終更新: {now}</div>

  <select id="ticker-select">{options_html}</select>

  <div class="stat-row" id="stat-row"></div>

  <h3>株価 / MA25 / MA75</h3>
  <div class="chart-box"><canvas id="priceChart" height="200"></canvas></div>

  <h3>出来高 / OBV</h3>
  <div class="chart-box"><canvas id="obvChart" height="140"></canvas></div>

  <h3>RSI14</h3>
  <div class="chart-box"><canvas id="rsiChart" height="120"></canvas></div>

  <h3>MACD</h3>
  <div class="chart-box"><canvas id="macdChart" height="140"></canvas></div>

  <h3>ADX14 / +DI / -DI</h3>
  <div class="chart-box"><canvas id="adxChart" height="140"></canvas></div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const DATA = {data_json};
    const params = new URLSearchParams(window.location.search);
    const initialTicker = params.get('ticker');

    const select = document.getElementById('ticker-select');
    if (initialTicker && DATA[initialTicker]) {{
      select.value = initialTicker;
    }}

    const commonOptions = (yTitle) => ({{
      responsive: true,
      animation: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{ legend: {{ labels: {{ color: '#ccc', font: {{ size: 9 }} }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#999', font: {{ size: 8 }}, maxTicksLimit: 6 }}, grid: {{ color: '#23262e' }} }},
        y: {{ ticks: {{ color: '#999', font: {{ size: 8 }} }}, grid: {{ color: '#23262e' }},
              title: {{ display: !!yTitle, text: yTitle, color: '#777', font: {{ size: 8 }} }} }}
      }}
    }});

    let charts = {{}};

    function makeLineChart(id, datasets, labels, yTitle) {{
      if (charts[id]) charts[id].destroy();
      const ctx = document.getElementById(id).getContext('2d');
      charts[id] = new Chart(ctx, {{
        type: 'line',
        data: {{ labels, datasets }},
        options: commonOptions(yTitle),
      }});
    }}

    function makeBarChart(id, datasets, labels, yTitle) {{
      if (charts[id]) charts[id].destroy();
      const ctx = document.getElementById(id).getContext('2d');
      charts[id] = new Chart(ctx, {{
        type: 'bar',
        data: {{ labels, datasets }},
        options: commonOptions(yTitle),
      }});
    }}

    function lastValid(arr) {{
      for (let i = arr.length - 1; i >= 0; i--) {{
        if (arr[i] !== null && arr[i] !== undefined) return arr[i];
      }}
      return null;
    }}

    function render() {{
      const ticker = select.value;
      const d = DATA[ticker];
      if (!d) return;

      const statRow = document.getElementById('stat-row');
      const chips = [
        ['株価', lastValid(d.close)],
        ['RSI14', lastValid(d.rsi14)],
        ['ADX14', lastValid(d.adx14)],
        ['ATR14', lastValid(d.atr14)],
      ];
      statRow.innerHTML = chips.map(([label, v]) =>
        `<div class="stat-chip">${{label}}<b>${{v !== null ? v.toLocaleString() : '-'}}</b></div>`
      ).join('');

      makeLineChart('priceChart', [
        {{ label: '株価', data: d.close, borderColor: '#4caf50', borderWidth: 1.5, pointRadius: 0, tension: 0.1 }},
        {{ label: 'MA25', data: d.ma25, borderColor: '#2196f3', borderWidth: 1, pointRadius: 0, tension: 0.1 }},
        {{ label: 'MA75', data: d.ma75, borderColor: '#ff9800', borderWidth: 1, pointRadius: 0, tension: 0.1 }},
      ], d.dates, '円');

      makeLineChart('obvChart', [
        {{ label: 'OBV', data: d.obv, borderColor: '#9c27b0', borderWidth: 1.2, pointRadius: 0, tension: 0.1, yAxisID: 'y' }},
      ], d.dates, '');

      makeLineChart('rsiChart', [
        {{ label: 'RSI14', data: d.rsi14, borderColor: '#e91e63', borderWidth: 1.2, pointRadius: 0, tension: 0.1 }},
        {{ label: '70', data: d.rsi14.map(() => 70), borderColor: '#555', borderWidth: 1, pointRadius: 0, borderDash: [4, 4] }},
        {{ label: '30', data: d.rsi14.map(() => 30), borderColor: '#555', borderWidth: 1, pointRadius: 0, borderDash: [4, 4] }},
      ], d.dates, '');

      makeBarChart('macdChart', [
        {{ label: 'ヒストグラム', data: d.macd_hist, backgroundColor: d.macd_hist.map(v => (v || 0) >= 0 ? '#4caf5088' : '#f4433688') }},
      ], d.dates, '');

      makeLineChart('adxChart', [
        {{ label: 'ADX14', data: d.adx14, borderColor: '#ffeb3b', borderWidth: 1.5, pointRadius: 0, tension: 0.1 }},
        {{ label: '+DI', data: d.plus_di, borderColor: '#4caf50', borderWidth: 1, pointRadius: 0, tension: 0.1 }},
        {{ label: '-DI', data: d.minus_di, borderColor: '#f44336', borderWidth: 1, pointRadius: 0, tension: 0.1 }},
      ], d.dates, '');
    }}

    select.addEventListener('change', render);
    render();
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
