# -*- coding: utf-8 -*-
"""
data/screening_all.json の全銘柄データを埋め込み、ブラウザのlocalStorageに
保存されたウォッチリスト銘柄だけを抽出して表示するページ(docs/watch.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "screening_all.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "watch.html")

JST = timezone(timedelta(hours=9))


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    stocks_json = json.dumps(payload["stocks"], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ウォッチリスト</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  h2 {{ font-size: 1rem; margin: 20px 0 8px 0; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 8px; }}
  .sub-note {{ font-size: 0.72rem; color: #777; margin-bottom: 16px; line-height: 1.5; }}
  nav {{ margin-bottom: 16px; font-size: 0.8rem; }}
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}
  nav.nav-secondary {{ margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }}
  nav.nav-secondary a {{ color: #888; margin-right: 12px; text-decoration: none; }}
  nav.nav-secondary a.active {{ color: #6ab7ff; font-weight: 600; text-decoration: underline; }}

  .table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  table {{ border-collapse: collapse; font-size: 0.75rem; width: 100%; min-width: 820px; table-layout: fixed; }}
  th, td {{ padding: 7px 6px; text-align: right; border-bottom: 1px solid #2a2d34; white-space: nowrap; }}
  th:first-child, td:first-child {{
    text-align: left; position: sticky; left: 0; background: #0f1115;
    width: 110px; max-width: 110px;
  }}
  td.name-cell {{ font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  td.name-cell a {{ color: #e8e8e8; text-decoration: none; }}
  .ticker {{ color: #888; font-weight: 400; font-size: 0.68rem; }}
  th {{ color: #aaa; font-weight: 500; font-size: 0.68rem; }}
  th.sortable {{ cursor: pointer; user-select: none; }}
  th.sortable.active-sort {{ color: #6ab7ff; font-weight: 700; }}
  .na {{ color: #666; }}
  .badge {{ font-size: 0.65rem; padding: 2px 6px; border-radius: 10px; white-space: nowrap; }}
  .badge-gc {{ background: #1b3a24; color: #4caf50; }}
  .badge-near {{ background: #3a331b; color: #ffb74d; }}
  .badge-early {{ background: #3a2f1b; color: #ffd54f; }}
  .star-btn {{
    background: none; border: none; color: #ffd54f; font-size: 0.95rem;
    cursor: pointer; padding: 0 6px 0 0; vertical-align: middle;
  }}
  .empty-note {{
    font-size: 0.85rem; color: #999; padding: 40px 16px; text-align: center; line-height: 1.7;
  }}

  .calc-box {{ background: #171a20; border-radius: 10px; padding: 14px; margin-top: 8px; }}
  .calc-row {{ display: flex; flex-direction: column; margin-bottom: 10px; }}
  .calc-row label {{ font-size: 0.72rem; color: #999; margin-bottom: 4px; }}
  .calc-row select, .calc-row input {{
    background: #0f1115; color: #e8e8e8; border: 1px solid #333;
    border-radius: 6px; padding: 8px; font-size: 0.85rem;
  }}
  .calc-result {{
    margin-top: 12px; padding: 12px; background: #0f1115; border-radius: 8px;
    font-size: 0.8rem; line-height: 1.9;
  }}
  .calc-result .highlight {{ color: #4caf50; font-weight: 700; font-size: 0.95rem; }}
  .calc-result .warn {{ color: #ffb74d; }}
</style>
</head>
<body>
  <nav class="nav-primary">
    <a href="index.html" class="active">株</a>
    <a href="news.html">ニュース</a>
    <a href="weather.html">天気</a>
  </nav>
  <nav class="nav-secondary">
    <a href="index.html">セクター強度</a>
    <a href="screening.html">スクリーニング</a>
    <a href="stock.html">銘柄詳細</a>
    <a href="watch.html" class="active">ウォッチリスト</a>
  </nav>
  <h1>ウォッチリスト</h1>
  <div class="updated">最終更新: {now}</div>
  <div class="sub-note">このブラウザに保存された銘柄のみ表示されます。他の端末・ブラウザとは同期されません。</div>

  <div id="content"></div>

  <script src="watchlist.js"></script>
  <script>
    const ALL_STOCKS = {stocks_json};
    const $ = (id) => document.getElementById(id);

    function fmtNum(v, digits) {{
      if (v === null || v === undefined) return '<span class="na">-</span>';
      return Number(v).toFixed(digits === undefined ? 1 : digits);
    }}
    function crossBadge(status) {{
      if (status === 'ゴールデンクロス済み') return '<span class="badge badge-gc">GC済</span>';
      if (status === '接近中') return '<span class="badge badge-near">接近中</span>';
      return '<span class="na">-</span>';
    }}
    function earlyBadge(flag) {{
      return flag ? '<span class="badge badge-early">初動</span>' : '<span class="na">-</span>';
    }}
    function crossRank(status) {{
      if (status === 'ゴールデンクロス済み') return 2;
      if (status === '接近中') return 1;
      return 0;
    }}

    let currentSort = {{ key: 'score', dir: 'desc' }};

    function sortList(list) {{
      const {{ key, dir }} = currentSort;
      const sign = dir === 'asc' ? 1 : -1;
      return [...list].sort((a, b) => {{
        let av = a[key], bv = b[key];
        if (typeof av === 'boolean') av = av ? 1 : 0;
        if (typeof bv === 'boolean') bv = bv ? 1 : 0;
        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;
        if (typeof av === 'string') return sign * av.localeCompare(bv, 'ja');
        return sign * (av - bv);
      }});
    }}

    function getWatchedStocks() {{
      const watched = getWatchlist();
      return ALL_STOCKS.filter(s => watched.includes(s.ticker))
        .map(s => ({{ ...s, cross_rank: crossRank(s.cross_status) }}));
    }}

    function renderEmpty() {{
      $('content').innerHTML = `
        <div class="empty-note">
          ウォッチリストはまだ空です。<br>
          スクリーニングページや銘柄詳細ページの「☆」ボタンをタップすると、ここに追加されます。
        </div>`;
    }}

    function renderContent() {{
      const list = getWatchedStocks();
      if (list.length === 0) {{
        renderEmpty();
        return;
      }}

      $('content').innerHTML = `
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>銘柄</th>
                <th class="sortable" data-key="sector33">セクター</th>
                <th class="sortable" data-key="price">株価</th>
                <th class="sortable" data-key="cross_rank">MA状況</th>
                <th class="sortable" data-key="adx14">ADX14</th>
                <th class="sortable" data-key="adx_early_signal">初動</th>
                <th class="sortable" data-key="obv_confirm">OBV追従</th>
                <th class="sortable" data-key="rsi14">RSI14</th>
                <th class="sortable" data-key="macd_hist">MACDヒスト</th>
                <th class="sortable" data-key="atr14">ATR14</th>
                <th class="sortable active-sort" data-key="score">スコア</th>
              </tr>
            </thead>
            <tbody id="table-body"></tbody>
          </table>
        </div>

        <h2>ポジションサイズ・ストップ計算（ATRベース）</h2>
        <div class="calc-box">
          <div class="calc-row">
            <label>銘柄を選択</label>
            <select id="calc-ticker"></select>
          </div>
          <div class="calc-row">
            <label>総資金（円）</label>
            <input type="number" id="calc-equity" value="1000000" min="0" step="10000">
          </div>
          <div class="calc-row">
            <label>1トレードあたりの許容損失（総資金に対する%）</label>
            <input type="number" id="calc-risk-pct" value="1" min="0.1" step="0.1">
          </div>
          <div class="calc-row">
            <label>ATR倍率（ストップまでの距離）</label>
            <input type="number" id="calc-atr-mult" value="1.5" min="0.1" step="0.1">
          </div>
          <div class="calc-result" id="calc-result"></div>
        </div>
      `;

      renderTable(list);
      renderCalcOptions(list);
      wireCalc(list);

      document.querySelectorAll('th.sortable').forEach(th => {{
        th.addEventListener('click', () => {{
          const key = th.dataset.key;
          if (currentSort.key === key) {{
            currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
          }} else {{
            currentSort = {{ key, dir: 'desc' }};
          }}
          renderTable(list);
        }});
      }});
    }}

    function renderTable(list) {{
      const tbody = $('table-body');
      const sorted = sortList(list);
      tbody.innerHTML = sorted.map(s => `<tr>
          <td class="name-cell">
            <button class="star-btn" data-ticker="${{s.ticker}}">★</button>
            <a href="stock.html?ticker=${{s.ticker}}">${{s.name}}<br><span class="ticker">${{s.ticker.replace('.T','')}}</span></a>
          </td>
          <td><a href="screening.html?sector=${{encodeURIComponent(s.sector33)}}" style="color:#888;text-decoration:none;">${{s.sector33}}</a></td>
          <td>${{fmtNum(s.price)}}</td>
          <td>${{crossBadge(s.cross_status)}}</td>
          <td>${{fmtNum(s.adx14)}}</td>
          <td>${{earlyBadge(s.adx_early_signal)}}</td>
          <td>${{s.obv_confirm ? '◯' : '-'}}</td>
          <td>${{fmtNum(s.rsi14)}}</td>
          <td>${{fmtNum(s.macd_hist, 2)}}</td>
          <td>${{fmtNum(s.atr14)}}</td>
          <td>${{fmtNum(s.score, 2)}}</td>
        </tr>`).join('');

      document.querySelectorAll('.star-btn').forEach(btn => {{
        btn.addEventListener('click', () => {{
          toggleWatch(btn.dataset.ticker);
          renderContent(); // 削除されたら一覧を再描画
        }});
      }});

      document.querySelectorAll('th.sortable').forEach(th => {{
        th.classList.toggle('active-sort', th.dataset.key === currentSort.key);
      }});
    }}

    function renderCalcOptions(list) {{
      const sel = $('calc-ticker');
      if (!sel) return;
      sel.innerHTML = list.map(s => `<option value="${{s.ticker}}">${{s.name}}(${{s.ticker.replace('.T','')}})</option>`).join('');
    }}

    function wireCalc(list) {{
      function recalc() {{
        const ticker = $('calc-ticker').value;
        const stock = list.find(s => s.ticker === ticker);
        const equity = parseFloat($('calc-equity').value) || 0;
        const riskPct = parseFloat($('calc-risk-pct').value) || 0;
        const atrMult = parseFloat($('calc-atr-mult').value) || 0;
        const resultEl = $('calc-result');

        if (!stock || !stock.atr14 || !stock.price) {{
          resultEl.innerHTML = '<span class="warn">この銘柄はATRデータが不足しており計算できません。</span>';
          return;
        }}

        const price = stock.price;
        const atrVal = stock.atr14;
        const stopPrice = price - atrVal * atrMult;
        const riskPerShare = atrVal * atrMult;
        const riskBudget = equity * (riskPct / 100);

        if (riskPerShare <= 0 || riskBudget <= 0) {{
          resultEl.innerHTML = '<span class="warn">入力値を確認してください。</span>';
          return;
        }}

        let shares = Math.floor((riskBudget / riskPerShare) / 100) * 100;
        if (shares < 0) shares = 0;
        const positionValue = shares * price;
        const positionPct = equity > 0 ? (positionValue / equity) * 100 : 0;
        const actualRisk = shares * riskPerShare;

        let warn = '';
        if (shares === 0) {{
          warn = '<div class="warn">許容損失に対してATRが大きすぎるため、100株(単元株)も購入できません。総資金かリスク%を見直してください。</div>';
        }}

        resultEl.innerHTML = `
          現在値: ${{price.toLocaleString()}}円 / ATR14: ${{atrVal.toLocaleString()}}<br>
          想定ストップ価格: <b>${{stopPrice.toFixed(1)}}円</b><br>
          1株あたり許容損失: ${{riskPerShare.toFixed(1)}}円<br>
          推奨株数: <span class="highlight">${{shares.toLocaleString()}}株</span>（単元株=100株単位）<br>
          建玉金額: ${{positionValue.toLocaleString()}}円（総資金の${{positionPct.toFixed(1)}}%）<br>
          実際の想定損失額: ${{actualRisk.toLocaleString()}}円
          ${{warn}}
        `;
      }}
      ['calc-ticker', 'calc-equity', 'calc-risk-pct', 'calc-atr-mult'].forEach(id => {{
        $(id).addEventListener('input', recalc);
        $(id).addEventListener('change', recalc);
      }});
      recalc();
    }}

    renderContent();
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
