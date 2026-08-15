# -*- coding: utf-8 -*-
"""
docs/timeseries/<コード>.json を、選んだ銘柄の分だけその場でfetchして表示する
個別銘柄詳細ページ(docs/stock.html)を生成する。
銘柄一覧(ドロップダウン用)は data/screening_all.json から作る(軽量な名前・セクターのみ)。
URLパラメータ ?ticker=XXXX.T で表示銘柄を指定できる。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "screening_all.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "stock.html")

JST = timezone(timedelta(hours=9))


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    # ドロップダウン用の軽量な一覧(名前・セクターのみ)
    index_list = [
        {"ticker": s["ticker"], "name": s["name"], "sector33": s["sector33"]}
        for s in payload["stocks"]
    ]
    index_json = json.dumps(index_list, ensure_ascii=False)

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
  .stat-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; font-size: 0.72rem; }}
  .stat-chip {{ background: #171a20; border-radius: 8px; padding: 6px 10px; }}
  .stat-chip b {{ display: block; font-size: 0.95rem; margin-top: 2px; }}
  .loading {{ font-size: 0.8rem; color: #999; padding: 20px 0; text-align: center; }}
  .star-btn {{
    display: block; width: 100%; margin-bottom: 12px;
    background: #171a20; color: #ffd54f; border: 1px solid #333;
    border-radius: 8px; padding: 10px; font-size: 0.85rem; cursor: pointer;
  }}
  .star-btn.active {{ background: #3a2f1b; border-color: #ffd54f; }}
</style>
</head>
<body>
  <nav>
    <a href="index.html">セクター強度</a>
    <a href="screening.html">スクリーニング</a>
    <a href="stock.html" class="active">銘柄詳細</a>
    <a href="watch.html">ウォッチリスト</a>
    <a href="news.html">ニュース</a>
  </nav>
  <h1>銘柄詳細</h1>
  <div class="updated">最終更新: {now}</div>

  <select id="ticker-select"></select>
  <button id="star-btn" class="star-btn">★ ウォッチに追加</button>

  <div class="stat-row" id="stat-row"></div>
  <div id="loading" class="loading" style="display:none;">読み込み中...</div>

  <div id="chart-area" style="display:none;">
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
  </div>

  <script src="watchlist.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script>
    const INDEX = {index_json};
    const params = new URLSearchParams(window.location.search);
    const initialTicker = params.get('ticker');

    const select = document.getElementById('ticker-select');
    select.innerHTML = INDEX.map(s =>
      `<option value="${{s.ticker}}">${{s.name}}(${{s.ticker.replace('.T','')}}) - ${{s.sector33}}</option>`
    ).join('');
    if (initialTicker && INDEX.some(s => s.ticker === initialTicker)) {{
      select.value = initialTicker;
    }}

    const starBtn = document.getElementById('star-btn');
    function updateStarBtn() {{
      const ticker = select.value;
      if (isWatched(ticker)) {{
        starBtn.textContent = '★ ウォッチ済み(タップで解除)';
        starBtn.classList.add('active');
      }} else {{
        starBtn.textContent = '☆ ウォッチに追加';
        starBtn.classList.remove('active');
      }}
    }}
    starBtn.addEventListener('click', () => {{
      toggleWatch(select.value);
      updateStarBtn();
    }});

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
      charts[id] = new Chart(ctx, {{ type: 'line', data: {{ labels, datasets }}, options: commonOptions(yTitle) }});
    }}

    function makeBarChart(id, datasets, labels, yTitle) {{
      if (charts[id]) charts[id].destroy();
      const ctx = document.getElementById(id).getContext('2d');
      charts[id] = new Chart(ctx, {{ type: 'bar', data: {{ labels, datasets }}, options: commonOptions(yTitle) }});
    }}

    function lastValid(arr) {{
      for (let i = arr.length - 1; i >= 0; i--) {{
        if (arr[i] !== null && arr[i] !== undefined) return arr[i];
      }}
      return null;
    }}

    async function loadAndRender(ticker) {{
      const code = ticker.replace('.T', '');
      document.getElementById('loading').style.display = 'block';
      document.getElementById('chart-area').style.display = 'none';

      let d;
      try {{
        const res = await fetch(`timeseries/${{code}}.json`);
        if (!res.ok) throw new Error('not found');
        d = await res.json();
      }} catch (e) {{
        document.getElementById('loading').textContent = 'この銘柄のデータが見つかりませんでした。';
        return;
      }}

      document.getElementById('loading').style.display = 'none';
      document.getElementById('chart-area').style.display = 'block';

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
        {{ label: 'OBV', data: d.obv, borderColor: '#9c27b0', borderWidth: 1.2, pointRadius: 0, tension: 0.1 }},
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

    select.addEventListener('change', () => {{
      loadAndRender(select.value);
      updateStarBtn();
    }});
    if (INDEX.length > 0) {{
      loadAndRender(select.value || INDEX[0].ticker);
      updateStarBtn();
    }}
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

