# -*- coding: utf-8 -*-
"""
data/overseas.json から、為替・米国株指数の期間別チャートページ(docs/overseas.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "overseas.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "overseas.html")

JST = timezone(timedelta(hours=9))
CHART_COLORS = ["#4caf50", "#2196f3", "#ff9800", "#e91e63", "#9c27b0"]


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    data_json = json.dumps(data, ensure_ascii=False)
    labels = list(data.keys())

    charts_html = ""
    for i, label in enumerate(labels):
        charts_html += f"""
  <div class="chart-box">
    <h3>{label}</h3>
    <canvas id="chart-{i}" height="180"></canvas>
  </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>海外指標</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  h3 {{ font-size: 0.9rem; margin: 0 0 10px 0; color: #ccc; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 16px; }}
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}
  nav.nav-secondary {{ margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }}
  nav.nav-secondary a {{ color: #888; margin-right: 12px; text-decoration: none; }}
  nav.nav-secondary a.active {{ color: #6ab7ff; font-weight: 600; text-decoration: underline; }}

  .period-controls {{ display: flex; gap: 8px; margin-bottom: 16px; }}
  .period-controls button {{
    background: #23262e; color: #e8e8e8; border: 1px solid #333; border-radius: 6px;
    padding: 6px 10px; font-size: 0.72rem;
  }}
  .period-controls button.active-period {{ background: #1b2a3a; color: #6ab7ff; border-color: #2f4a63; }}

  .chart-box {{ background: #171a20; border-radius: 10px; padding: 14px; margin-bottom: 14px; }}
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
    <a href="overseas.html" class="active">海外指標</a>
    <a href="commodities.html">資源</a>
  </nav>
  <h1>海外指標</h1>
  <div class="updated">最終更新: {now}</div>

  <div class="period-controls" id="period-controls">
    <button class="period-btn" data-days="5">1週間</button>
    <button class="period-btn" data-days="21">1ヶ月</button>
    <button class="period-btn" data-days="63">3ヶ月</button>
    <button class="period-btn active-period" data-days="126">6ヶ月</button>
  </div>

  {charts_html}

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const DATA = {data_json};
    const LABELS = {json.dumps(labels, ensure_ascii=False)};
    const COLORS = {json.dumps(CHART_COLORS)};
    let currentDays = 126;
    let charts = [];

    function sliceByPeriod(arr) {{
      if (arr.length <= currentDays) return arr;
      return arr.slice(arr.length - currentDays);
    }}

    function buildCharts() {{
      charts.forEach(c => c.destroy());
      charts = [];
      LABELS.forEach((label, i) => {{
        const series = DATA[label];
        if (!series) return;
        const ctx = document.getElementById('chart-' + i).getContext('2d');
        const chart = new Chart(ctx, {{
          type: 'line',
          data: {{
            labels: sliceByPeriod(series.dates),
            datasets: [{{
              label: label,
              data: sliceByPeriod(series.values),
              borderColor: COLORS[i % COLORS.length],
              backgroundColor: COLORS[i % COLORS.length],
              borderWidth: 1.5, pointRadius: 0, tension: 0.15,
            }}],
          }},
          options: {{
            responsive: true, animation: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
              x: {{ ticks: {{ color: '#999', font: {{ size: 9 }}, maxTicksLimit: 6 }}, grid: {{ color: '#23262e' }} }},
              y: {{ ticks: {{ color: '#999', font: {{ size: 9 }} }}, grid: {{ color: '#23262e' }} }},
            }},
          }},
        }});
        charts.push(chart);
      }});
    }}

    document.querySelectorAll('.period-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        currentDays = parseInt(btn.dataset.days, 10);
        document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active-period'));
        btn.classList.add('active-period');
        buildCharts();
      }});
    }});

    buildCharts();
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
