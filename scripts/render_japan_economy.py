# -*- coding: utf-8 -*-
"""
data/jgb_yields.json と data/cgpi.json から、日本の経済状況ページ(docs/japan_economy.html)を生成する。
国債利回りは日次データ用(1週間〜6ヶ月)、企業物価指数は月次データ用(1年〜全期間)の
別々の期間切り替えボタンを持つ。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_JGB_PATH = os.path.join(BASE_DIR, "data", "jgb_yields.json")
IN_CGPI_PATH = os.path.join(BASE_DIR, "data", "cgpi.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "japan_economy.html")

JST = timezone(timedelta(hours=9))
CHART_COLORS = ["#4caf50", "#2196f3", "#ff9800", "#e91e63"]


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    jgb = load_json(IN_JGB_PATH)
    cgpi = load_json(IN_CGPI_PATH)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    jgb_json = json.dumps(jgb, ensure_ascii=False)
    cgpi_json = json.dumps(cgpi, ensure_ascii=False)
    jgb_labels = list(jgb.keys())
    cgpi_labels = list(cgpi.keys())

    jgb_charts_html = "".join(
        f'<div class="chart-box"><h3>{label}</h3><canvas id="jgb-chart-{i}" height="160"></canvas></div>'
        for i, label in enumerate(jgb_labels)
    )
    cgpi_charts_html = "".join(
        f'<div class="chart-box"><h3>{label}</h3><canvas id="cgpi-chart-{i}" height="180"></canvas></div>'
        for i, label in enumerate(cgpi_labels)
    )

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>日本の経済状況</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  h2 {{ font-size: 1rem; margin: 24px 0 8px 0; }}
  h3 {{ font-size: 0.9rem; margin: 0 0 10px 0; color: #ccc; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 16px; }}
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}
  nav.nav-secondary {{ margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }}
  nav.nav-secondary a {{ color: #888; margin-right: 12px; text-decoration: none; }}
  nav.nav-secondary a.active {{ color: #6ab7ff; font-weight: 600; text-decoration: underline; }}

  .period-controls {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }}
  .period-controls button {{
    background: #23262e; color: #e8e8e8; border: 1px solid #333; border-radius: 6px;
    padding: 6px 10px; font-size: 0.72rem;
  }}
  .period-controls button.active-period {{ background: #1b2a3a; color: #6ab7ff; border-color: #2f4a63; }}

  .chart-box {{ background: #171a20; border-radius: 10px; padding: 14px; margin-bottom: 14px; }}
  .empty-note {{ font-size: 0.8rem; color: #888; padding: 12px 0; }}
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
    <a href="japan_economy.html" class="active">日本の経済状況</a>
    <a href="overseas.html">海外指標</a>
    <a href="commodities.html">資源</a>
    <a href="calendar.html">経済指標カレンダー</a>
  </nav>
  <h1>日本の経済状況</h1>
  <div class="updated">最終更新: {now}</div>

  <h2>国債利回り（短期・中期・長期）</h2>
  <div class="period-controls" id="jgb-period-controls">
    <button class="period-btn" data-days="5">1週間</button>
    <button class="period-btn" data-days="21">1ヶ月</button>
    <button class="period-btn" data-days="63">3ヶ月</button>
    <button class="period-btn active-period" data-days="126">6ヶ月</button>
  </div>
  {jgb_charts_html or '<div class="empty-note">データがありません</div>'}

  <h2>国内企業物価指数（総平均）</h2>
  <div class="period-controls" id="cgpi-period-controls">
    <button class="period-btn-cgpi" data-months="12">1年</button>
    <button class="period-btn-cgpi" data-months="36">3年</button>
    <button class="period-btn-cgpi" data-months="60">5年</button>
    <button class="period-btn-cgpi active-period" data-months="0">全期間</button>
  </div>
  {cgpi_charts_html or '<div class="empty-note">データがありません</div>'}
  <div class="empty-note">出典: 財務省(国債金利情報)／日本銀行 時系列統計データ検索サイト。企業物価指数は月次データのため、期間表示は月単位です。</div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const JGB_DATA = {jgb_json};
    const JGB_LABELS = {json.dumps(jgb_labels, ensure_ascii=False)};
    const CGPI_DATA = {cgpi_json};
    const CGPI_LABELS = {json.dumps(cgpi_labels, ensure_ascii=False)};
    const COLORS = {json.dumps(CHART_COLORS)};

    function sliceTail(arr, n) {{
      if (n <= 0 || arr.length <= n) return arr;
      return arr.slice(arr.length - n);
    }}

    // ==== 国債利回り(日次) ====
    let jgbDays = 126;
    let jgbCharts = [];
    function buildJgbCharts() {{
      jgbCharts.forEach(c => c.destroy());
      jgbCharts = [];
      JGB_LABELS.forEach((label, i) => {{
        const series = JGB_DATA[label];
        if (!series) return;
        const ctx = document.getElementById('jgb-chart-' + i).getContext('2d');
        const chart = new Chart(ctx, {{
          type: 'line',
          data: {{
            labels: sliceTail(series.dates, jgbDays),
            datasets: [{{
              label: label, data: sliceTail(series.values, jgbDays),
              borderColor: COLORS[i % COLORS.length], backgroundColor: COLORS[i % COLORS.length],
              borderWidth: 1.5, pointRadius: 0, tension: 0.15,
            }}],
          }},
          options: {{
            responsive: true, animation: false,
            interaction: {{ mode: 'index', intersect: false }},
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
              x: {{ ticks: {{ color: '#999', font: {{ size: 9 }}, maxTicksLimit: 6 }}, grid: {{ color: '#23262e' }} }},
              y: {{ ticks: {{ color: '#999', font: {{ size: 9 }} }}, grid: {{ color: '#23262e' }},
                    title: {{ display: true, text: '%', color: '#777', font: {{ size: 9 }} }} }},
            }},
          }},
        }});
        jgbCharts.push(chart);
      }});
    }}
    document.querySelectorAll('#jgb-period-controls .period-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        jgbDays = parseInt(btn.dataset.days, 10);
        document.querySelectorAll('#jgb-period-controls .period-btn').forEach(b => b.classList.remove('active-period'));
        btn.classList.add('active-period');
        buildJgbCharts();
      }});
    }});

    // ==== 企業物価指数(月次) ====
    let cgpiMonths = 0; // 0 = 全期間
    let cgpiCharts = [];
    function buildCgpiCharts() {{
      cgpiCharts.forEach(c => c.destroy());
      cgpiCharts = [];
      CGPI_LABELS.forEach((label, i) => {{
        const series = CGPI_DATA[label];
        if (!series) return;
        const ctx = document.getElementById('cgpi-chart-' + i).getContext('2d');
        const chart = new Chart(ctx, {{
          type: 'line',
          data: {{
            labels: sliceTail(series.dates, cgpiMonths),
            datasets: [{{
              label: label, data: sliceTail(series.values, cgpiMonths),
              borderColor: COLORS[(i + 1) % COLORS.length], backgroundColor: COLORS[(i + 1) % COLORS.length],
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
        cgpiCharts.push(chart);
      }});
    }}
    document.querySelectorAll('#cgpi-period-controls .period-btn-cgpi').forEach(btn => {{
      btn.addEventListener('click', () => {{
        cgpiMonths = parseInt(btn.dataset.months, 10);
        document.querySelectorAll('#cgpi-period-controls .period-btn-cgpi').forEach(b => b.classList.remove('active-period'));
        btn.classList.add('active-period');
        buildCgpiCharts();
      }});
    }});

    buildJgbCharts();
    buildCgpiCharts();
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
