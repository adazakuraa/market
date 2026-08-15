# -*- coding: utf-8 -*-
"""
data/screening_all.json から、スマホ表示用の静的HTML(docs/screening.html)を生成する。

URLパラメータ ?sector=セクター名 を付けると、そのセクターの銘柄だけを
全件(スコア順)表示する。パラメータがなければ、相対強度上位セクターの
銘柄から上位50件を表示する(従来の挙動)。
絞り込みはこのHTML内のJavaScriptで行うため、Python側は全データを埋め込むだけ。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "screening_all.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "screening.html")

JST = timezone(timedelta(hours=9))


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    stocks_json = json.dumps(payload["stocks"], ensure_ascii=False)
    strong_sectors_json = json.dumps(payload["strong_sectors"], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>銘柄スクリーニング</title>
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
  nav a {{ color: #6ab7ff; margin-right: 12px; text-decoration: none; }}
  nav a.active {{ color: #e8e8e8; font-weight: 600; text-decoration: underline; }}

  .filter-bar {{
    display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
    font-size: 0.78rem; flex-wrap: wrap;
  }}
  .filter-bar .sector-badge {{
    background: #1b2a3a; color: #6ab7ff; padding: 4px 10px; border-radius: 12px;
  }}
  .filter-bar a.clear-link {{ color: #ff8a65; text-decoration: none; }}

  .table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  table {{ border-collapse: collapse; font-size: 0.75rem; width: 100%; min-width: 800px; table-layout: fixed; }}
  th, td {{ padding: 7px 6px; text-align: right; border-bottom: 1px solid #2a2d34; white-space: nowrap; }}
  th:first-child, td:first-child {{
    text-align: left;
    position: sticky;
    left: 0;
    background: #0f1115;
    width: 92px;
    max-width: 92px;
  }}
  td.name-cell {{
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  td.name-cell a {{
    color: #e8e8e8;
    text-decoration: none;
  }}
  .ticker {{ color: #888; font-weight: 400; font-size: 0.68rem; }}
  th {{ color: #aaa; font-weight: 500; font-size: 0.68rem; }}
  th.sortable {{ cursor: pointer; user-select: none; }}
  th.sortable.active-sort {{ color: #6ab7ff; font-weight: 700; }}
  .na {{ color: #666; }}
  .badge {{ font-size: 0.65rem; padding: 2px 6px; border-radius: 10px; white-space: nowrap; }}
  .badge-gc {{ background: #1b3a24; color: #4caf50; }}
  .badge-near {{ background: #3a331b; color: #ffb74d; }}
  .badge-early {{ background: #3a2f1b; color: #ffd54f; }}

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
  .empty-note {{ font-size: 0.8rem; color: #999; padding: 20px 0; text-align: center; }}
</style>
</head>
<body>
  <nav>
    <a href="index.html">セクター強度</a>
    <a href="screening.html" class="active">スクリーニング</a>
    <a href="stock.html">銘柄詳細</a>
  </nav>
  <h1>銘柄スクリーニング</h1>
  <div class="updated">最終更新: {now}</div>
  <div class="filter-bar" id="filter-bar"></div>
  <div class="sub-note" id="sub-note"></div>

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
      <label>銘柄を選択（上の表に表示中の銘柄）</label>
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

  <script>
    const ALL_STOCKS = {stocks_json};
    const STRONG_SECTORS = {strong_sectors_json};
    const MAX_DEFAULT = 50;

    const $ = (id) => document.getElementById(id);
    const params = new URLSearchParams(window.location.search);
    const sectorFilter = params.get('sector');

    function fmtNum(v, digits) {{
      if (v === null || v === undefined) return '<span class="na">-</span>';
      return Number(v).toFixed(digits === undefined ? 1 : digits);
    }}

    function crossBadge(status) {{
      if (status === 'ゴールデンクロス済み') return '<span class="badge badge-gc">GC済</span>';
      if (status === '接近中') return '<span class="badge badge-near">接近中</span>';
      return '<span class="na">-</span>';
    }}

    function crossRank(status) {{
      if (status === 'ゴールデンクロス済み') return 2;
      if (status === '接近中') return 1;
      return 0;
    }}
    ALL_STOCKS.forEach(s => {{ s.cross_rank = crossRank(s.cross_status); }});

    function earlyBadge(flag) {{
      return flag ? '<span class="badge badge-early">初動</span>' : '<span class="na">-</span>';
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

    function getFilteredStocks() {{
      let list;
      if (sectorFilter) {{
        list = ALL_STOCKS.filter(s => s.sector33 === sectorFilter);
        list.sort((a, b) => b.score - a.score);
        list = list.slice(0, MAX_DEFAULT);
      }} else {{
        list = ALL_STOCKS.filter(s => STRONG_SECTORS.includes(s.sector33));
        list.sort((a, b) => b.score - a.score);
        list = list.slice(0, MAX_DEFAULT);
      }}
      return list;
    }}

    function renderFilterBar() {{
      const bar = $('filter-bar');
      const note = $('sub-note');
      if (sectorFilter) {{
        bar.innerHTML = `<span class="sector-badge">セクター: ${{sectorFilter}}</span><a class="clear-link" href="screening.html">✕ 絞り込み解除(全セクター表示)</a>`;
        note.textContent = `「${{sectorFilter}}」セクターの銘柄をスコア順に全件表示しています。`;
      }} else {{
        bar.innerHTML = '';
        note.textContent = '対象セクター（相対強度上位）: ' + STRONG_SECTORS.join('、') + '。スコアは「MAの並び・ゴールデンクロス状況・ADXの強さ・OBVの追従」を合成した目安です。「初動」バッジは、ADXが無トレンド水準(20未満)から上昇し始めた銘柄(まだ強すぎない段階)につきます。厳密なフィルタではなく、幅広く候補を並べています。最終判断はご自身の目でチャートと合わせて行ってください。';
      }}
    }}

    function renderTable(list) {{
      const tbody = $('table-body');
      const sorted = sortList(list);
      if (sorted.length === 0) {{
        tbody.innerHTML = '';
        tbody.closest('table').style.display = 'none';
        return;
      }}
      tbody.closest('table').style.display = '';
      tbody.innerHTML = sorted.map(s => {{
        const obvMark = s.obv_confirm ? '◯' : '-';
        return `<tr>
          <td class="name-cell"><a href="stock.html?ticker=${{s.ticker}}">${{s.name}}<br><span class="ticker">${{s.ticker.replace('.T','')}}</span></a></td>
          <td><a href="screening.html?sector=${{encodeURIComponent(s.sector33)}}" style="color:#888;text-decoration:none;">${{s.sector33}}</a></td>
          <td>${{fmtNum(s.price)}}</td>
          <td>${{crossBadge(s.cross_status)}}</td>
          <td>${{fmtNum(s.adx14)}}</td>
          <td>${{earlyBadge(s.adx_early_signal)}}</td>
          <td>${{obvMark}}</td>
          <td>${{fmtNum(s.rsi14)}}</td>
          <td>${{fmtNum(s.macd_hist, 2)}}</td>
          <td>${{fmtNum(s.atr14)}}</td>
          <td>${{fmtNum(s.score, 2)}}</td>
        </tr>`;
      }}).join('');

      document.querySelectorAll('th.sortable').forEach(th => {{
        th.classList.toggle('active-sort', th.dataset.key === currentSort.key);
      }});
    }}

    function renderCalcOptions(list) {{
      const sel = $('calc-ticker');
      sel.innerHTML = list.map(s => `<option value="${{s.ticker}}">${{s.name}}(${{s.ticker.replace('.T','')}})</option>`).join('');
    }}

    function recalc() {{
      const list = getFilteredStocks();
      const ticker = $('calc-ticker').value;
      const stock = list.find(s => s.ticker === ticker) || ALL_STOCKS.find(s => s.ticker === ticker);
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

    let selectedList = [];

    function init() {{
      renderFilterBar();
      selectedList = getFilteredStocks();
      renderTable(selectedList);
      renderCalcOptions(selectedList);
      recalc();
    }}

    document.querySelectorAll('th.sortable').forEach(th => {{
      th.addEventListener('click', () => {{
        const key = th.dataset.key;
        if (currentSort.key === key) {{
          currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
        }} else {{
          currentSort = {{ key, dir: 'desc' }};
        }}
        renderTable(selectedList);
      }});
    }});

    ['calc-ticker', 'calc-equity', 'calc-risk-pct', 'calc-atr-mult'].forEach(id => {{
      $(id).addEventListener('input', recalc);
      $(id).addEventListener('change', recalc);
    }});

    init();
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
