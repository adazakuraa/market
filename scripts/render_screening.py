# -*- coding: utf-8 -*-
"""
data/screening.json から、スマホ表示用の静的HTML(docs/screening.html)を生成する。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
IN_PATH = os.path.join(BASE_DIR, "data", "screening.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "screening.html")

JST = timezone(timedelta(hours=9))


def fmt_num(v, digits=1):
    if v is None:
        return '<span class="na">-</span>'
    return f"{v:.{digits}f}"


def cross_badge(status):
    if status == "ゴールデンクロス済み":
        return '<span class="badge badge-gc">GC済</span>'
    if status == "接近中":
        return '<span class="badge badge-near">接近中</span>'
    return '<span class="na">-</span>'


def main():
    with open(IN_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    stocks = payload["stocks"]
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    target_sectors = "、".join(payload["target_sectors"])

    rows_html = ""
    for s in stocks:
        obv_mark = "◯" if s["obv_confirm"] else "-"
        rows_html += f"""<tr data-ticker="{s['ticker']}">
  <td class="name-cell">{s['name']}<br><span class="ticker">{s['ticker'].replace('.T','')}</span></td>
  <td>{s['sector33']}</td>
  <td>{fmt_num(s['price'])}</td>
  <td>{cross_badge(s['cross_status'])}</td>
  <td>{fmt_num(s['adx14'])}</td>
  <td>{obv_mark}</td>
  <td>{fmt_num(s['rsi14'])}</td>
  <td>{fmt_num(s['macd_hist'], 2)}</td>
  <td>{fmt_num(s['atr14'])}</td>
  <td>{fmt_num(s['score'], 2)}</td>
</tr>
"""

    options_html = "".join(
        f'<option value="{s["ticker"]}">{s["name"]}({s["ticker"].replace(".T","")})</option>'
        for s in stocks
    )

    stocks_json = json.dumps(stocks, ensure_ascii=False)

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

  .table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table { border-collapse: collapse; font-size: 0.75rem; width: 100%; min-width: 720px; table-layout: fixed; }
  th, td { padding: 7px 6px; text-align: right; border-bottom: 1px solid #2a2d34; white-space: nowrap; }
  th:first-child, td:first-child {
    text-align: left;
    position: sticky;
    left: 0;
    background: #0f1115;
    width: 92px;
    max-width: 92px;
  }
  td.name-cell {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ticker {{ color: #888; font-weight: 400; font-size: 0.68rem; }}
  th {{ color: #aaa; font-weight: 500; font-size: 0.68rem; }}
  .na {{ color: #666; }}
  .badge {{ font-size: 0.65rem; padding: 2px 6px; border-radius: 10px; white-space: nowrap; }}
  .badge-gc {{ background: #1b3a24; color: #4caf50; }}
  .badge-near {{ background: #3a331b; color: #ffb74d; }}

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
  <nav>
    <a href="index.html">セクター強度</a>
    <a href="screening.html" class="active">スクリーニング</a>
  </nav>
  <h1>銘柄スクリーニング</h1>
  <div class="updated">最終更新: {now}</div>
  <div class="sub-note">
    対象セクター（相対強度上位）: {target_sectors}<br>
    スコアは「MAの並び・ゴールデンクロス状況・ADXの強さ・OBVの追従」を合成した目安です。厳密なフィルタではなく、幅広く候補を並べています。最終判断はご自身の目でチャートと合わせて行ってください。
  </div>

  <div class="table-scroll">
    <table>
      <thead>
        <tr>
          <th>銘柄</th><th>セクター</th><th>株価</th><th>MA状況</th>
          <th>ADX14</th><th>OBV追従</th><th>RSI14</th><th>MACDヒスト</th>
          <th>ATR14</th><th>スコア</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <h2>ポジションサイズ・ストップ計算（ATRベース）</h2>
  <div class="calc-box">
    <div class="calc-row">
      <label>銘柄を選択</label>
      <select id="calc-ticker">{options_html}</select>
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
    const STOCKS = {stocks_json};

    const $ = (id) => document.getElementById(id);

    function recalc() {{
      const ticker = $('calc-ticker').value;
      const stock = STOCKS.find(s => s.ticker === ticker);
      const equity = parseFloat($('calc-equity').value) || 0;
      const riskPct = parseFloat($('calc-risk-pct').value) || 0;
      const atrMult = parseFloat($('calc-atr-mult').value) || 0;
      const resultEl = $('calc-result');

      if (!stock || !stock.atr14 || !stock.price) {{
        resultEl.innerHTML = '<span class="warn">この銘柄はATRデータが不足しており計算できません。</span>';
        return;
      }}

      const price = stock.price;
      const atr = stock.atr14;
      const stopPrice = price - atr * atrMult;
      const riskPerShare = atr * atrMult;
      const riskBudget = equity * (riskPct / 100);

      if (riskPerShare <= 0 || riskBudget <= 0) {{
        resultEl.innerHTML = '<span class="warn">入力値を確認してください。</span>';
        return;
      }}

      let shares = Math.floor((riskBudget / riskPerShare) / 100) * 100; // 単元株(100株)単位に切り捨て
      if (shares < 0) shares = 0;
      const positionValue = shares * price;
      const positionPct = equity > 0 ? (positionValue / equity) * 100 : 0;
      const actualRisk = shares * riskPerShare;

      let warn = '';
      if (shares === 0) {{
        warn = '<div class="warn">許容損失に対してATRが大きすぎるため、100株(単元株)も購入できません。総資金かリスク%を見直してください。</div>';
      }}

      resultEl.innerHTML = `
        現在値: ${{price.toLocaleString()}}円 / ATR14: ${{atr.toLocaleString()}}<br>
        想定ストップ価格: <b>${{stopPrice.toFixed(1).toLocaleString()}}円</b><br>
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
