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
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}
  nav.nav-secondary {{ margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }}
  nav.nav-secondary a {{ color: #888; margin-right: 12px; text-decoration: none; }}
  nav.nav-secondary a.active {{ color: #6ab7ff; font-weight: 600; text-decoration: underline; }}
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
  .analyze-btn {{
    display: block; width: 100%; margin-bottom: 14px;
    background: #171a20; color: #b39ddb; border: 1px solid #3d2f5c;
    border-radius: 8px; padding: 12px; font-size: 0.88rem; font-weight: 600; cursor: pointer;
  }}
  .analyze-btn:disabled {{ opacity: 0.5; }}
  .analysis-box {{ background: #171a20; border-radius: 10px; padding: 16px; margin-bottom: 16px; }}
  .prob-row {{ display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }}
  .prob-value {{ font-size: 1.8rem; font-weight: 700; }}
  .prob-value.up {{ color: #4caf50; }}
  .prob-value.down {{ color: #f44336; }}
  .prob-label {{ font-size: 0.78rem; color: #999; }}
  .signal-badge {{ font-size: 0.75rem; padding: 4px 10px; border-radius: 12px; font-weight: 600; }}
  .signal-buy {{ background: #1b3a24; color: #4caf50; }}
  .signal-none {{ background: #23262e; color: #999; }}
  .metric-grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }}
  .metric-chip {{ background: #0f1115; border-radius: 8px; padding: 8px 12px; font-size: 0.72rem; flex: 1; min-width: 70px; text-align: center; }}
  .metric-chip b {{ display: block; font-size: 1rem; margin-top: 2px; }}
  .imp-bar-row {{ display: flex; align-items: center; gap: 8px; font-size: 0.72rem; margin-bottom: 5px; }}
  .imp-bar-label {{ width: 110px; color: #ccc; text-align: right; flex-shrink: 0; }}
  .imp-bar-track {{ flex: 1; background: #0f1115; border-radius: 4px; height: 10px; overflow: hidden; }}
  .imp-bar-fill {{ background: #6ab7ff; height: 100%; }}
  .rule-box {{ background: #0f1115; border-radius: 8px; padding: 10px 12px; font-size: 0.75rem; margin-bottom: 8px; line-height: 1.6; }}
  .rule-box.buy {{ border-left: 3px solid #4caf50; }}
  .rule-box.sell {{ border-left: 3px solid #f44336; }}
  .analysis-note {{ font-size: 0.68rem; color: #777; line-height: 1.6; margin-top: 10px; }}
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
    <a href="stock.html" class="active">銘柄詳細</a>
    <a href="watch.html">ウォッチリスト</a>
    <a href="japan_economy.html">日本の経済状況</a>
    <a href="overseas.html">海外指標</a>
    <a href="commodities.html">資源</a>
    <a href="calendar.html">経済指標カレンダー</a>
  </nav>
  <h1>銘柄詳細</h1>
  <div class="updated">最終更新: {now}</div>

  <select id="ticker-select"></select>
  <button id="star-btn" class="star-btn">★ ウォッチに追加</button>
  <button id="analyze-btn" class="analyze-btn">🔮 AI分析する（上昇予測・売買パターン）</button>

  <div id="analysis-area" style="display:none;"></div>

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

    // ==== AI分析(予測モデル結果の取得・表示) ====
    function featureLabel(name) {{
      const labels = {{
        rsi14: 'RSI14', macd: 'MACD', macd_signal: 'MACDシグナル', macd_hist: 'MACDヒスト',
        atr14: 'ATR14', adx14: 'ADX14', plus_di: '+DI', minus_di: '-DI',
        obv_change_20d: 'OBV20日変化', price_vs_ma25: '価格/MA25乖離', price_vs_ma75: '価格/MA75乖離',
        ma25_vs_ma75: 'MA25/MA75乖離', return_1d: '1日リターン', return_3d: '3日リターン',
        return_5d: '5日リターン', return_10d: '10日リターン', volume_ratio: '出来高比率',
        bb_width: 'ボリンジャー幅', macro_usdjpy: '米ドル/円', macro_usdjpy_chg20d: '米ドル/円20日変化',
        macro_oil: '原油価格', macro_oil_chg20d: '原油20日変化', macro_cgpi: '企業物価指数',
        macro_cgpi_chg20d: '企業物価指数変化', fund_per: 'PER', fund_pbr: 'PBR', fund_dividend_yield: '配当利回り',
        macro_jgb_2y: '国債利回り(2年)', macro_jgb_2y_chg20d: '国債利回り2年20日変化',
        macro_jgb_5y: '国債利回り(5年)', macro_jgb_5y_chg20d: '国債利回り5年20日変化',
        macro_jgb_10y: '国債利回り(10年)', macro_jgb_10y_chg20d: '国債利回り10年20日変化',
      }};
      return labels[name] || name;
    }}

    function ruleHtml(rule, kind) {{
      if (!rule) return `<div class="rule-box ${{kind}}">十分な確信度のパターンは見つかりませんでした。</div>`;
      const pct = (rule.precision_up * 100).toFixed(1);
      return `<div class="rule-box ${{kind}}">
        条件: ${{rule.path.join(' かつ ')}}<br>
        該当${{rule.n_samples}}件中、上昇的中率 <b>${{pct}}%</b>
      </div>`;
    }}

    function renderAnalysis(result) {{
      const area = document.getElementById('analysis-area');
      if (result.status !== 'ok') {{
        area.innerHTML = `<div class="analysis-box"><div class="analysis-note">この銘柄はデータ不足のため分析できませんでした（学習に必要な期間が足りません）。</div></div>`;
        area.style.display = 'block';
        return;
      }}

      const probPct = (result.latest_prob_up * 100).toFixed(1);
      const isUp = result.latest_prob_up >= result.decision_threshold;
      const signalHtml = result.signal === 'buy_candidate'
        ? '<span class="signal-badge signal-buy">買い候補シグナル</span>'
        : '<span class="signal-badge signal-none">シグナルなし</span>';

      const m = result.metrics;
      const metricsHtml = `
        <div class="metric-grid">
          <div class="metric-chip">Accuracy<b>${{(m.accuracy*100).toFixed(0)}}%</b></div>
          <div class="metric-chip">Precision<b>${{(m.precision*100).toFixed(0)}}%</b></div>
          <div class="metric-chip">Recall<b>${{(m.recall*100).toFixed(0)}}%</b></div>
          <div class="metric-chip">F1<b>${{(m.f1*100).toFixed(0)}}%</b></div>
        </div>`;

      const maxImp = result.feature_importance.length ? result.feature_importance[0].importance : 1;
      const impHtml = result.feature_importance.map(f => `
        <div class="imp-bar-row">
          <div class="imp-bar-label">${{featureLabel(f.feature)}}</div>
          <div class="imp-bar-track"><div class="imp-bar-fill" style="width:${{(f.importance/maxImp*100).toFixed(0)}}%"></div></div>
          <div>${{(f.importance*100).toFixed(1)}}%</div>
        </div>`).join('');

      let btHtml = '<div class="analysis-note">有効な売買閾値の組み合わせが見つかりませんでした。</div>';
      if (result.backtest) {{
        const bt = result.backtest;
        btHtml = `<div class="rule-box">
          確率${{(bt.buy_threshold*100).toFixed(0)}}%以上で買い、${{(bt.sell_threshold*100).toFixed(0)}}%以下(または保有10日)で売る場合:<br>
          過去${{bt.n_trades}}回の取引で、平均リターン <b>${{(bt.avg_return_per_trade*100).toFixed(2)}}%/回</b>
        </div>`;
      }}

      area.innerHTML = `
        <div class="analysis-box">
          <div class="prob-row">
            <div>
              <div class="prob-value ${{isUp ? 'up' : 'down'}}">${{probPct}}%</div>
              <div class="prob-label">${{result.horizon_days}}営業日後に${{(result.up_threshold*100).toFixed(0)}}%以上上昇する確率</div>
            </div>
            ${{signalHtml}}
          </div>
          ${{metricsHtml}}
          <div class="analysis-note">評価指標はテスト期間(直近${{result.n_test}}営業日、学習には使っていない期間)での成績です。学習データ${{result.n_train}}件。使用モデル: ${{result.model_used}}</div>

          <h3 style="margin-top:16px;">特徴量重要度</h3>
          ${{impHtml}}

          <h3 style="margin-top:16px;">買いやすいパターン</h3>
          ${{ruleHtml(result.buy_rule, 'buy')}}

          <h3 style="margin-top:10px;">売りやすい(下落しやすい)パターン</h3>
          ${{ruleHtml(result.sell_rule, 'sell')}}

          <h3 style="margin-top:16px;">売買閾値バックテスト</h3>
          ${{btHtml}}
          <div class="analysis-note">※ 過去データ上の最適化であり、将来の利益を保証するものではありません。投資判断はご自身の責任でお願いします。</div>
        </div>`;
      area.style.display = 'block';
    }}

    async function analyzeCurrentTicker() {{
      const ticker = select.value;
      const code = ticker.replace('.T', '');
      const btn = document.getElementById('analyze-btn');
      const area = document.getElementById('analysis-area');
      btn.disabled = true;
      btn.textContent = '分析中...';
      area.style.display = 'block';
      area.innerHTML = '<div class="analysis-box"><div class="loading">読み込み中...</div></div>';

      try {{
        const res = await fetch(`predictions/${{code}}.json`);
        if (!res.ok) throw new Error('この銘柄の分析データはまだありません');
        const result = await res.json();
        renderAnalysis(result);
      }} catch (e) {{
        area.innerHTML = `<div class="analysis-box"><div class="analysis-note">分析データを取得できませんでした（${{e.message}}）。この銘柄は日次バッチの対象外か、まだ分析が実行されていない可能性があります。</div></div>`;
      }} finally {{
        btn.disabled = false;
        btn.textContent = '🔮 AI分析する（上昇予測・売買パターン）';
      }}
    }}

    document.getElementById('analyze-btn').addEventListener('click', analyzeCurrentTicker);

    select.addEventListener('change', () => {{
      loadAndRender(select.value);
      updateStarBtn();
      document.getElementById('analysis-area').style.display = 'none';
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
