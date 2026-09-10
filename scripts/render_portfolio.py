# -*- coding: utf-8 -*-
"""
NISA・iDeCo・国債(安全資産)への月々の配分を、年齢・リスク許容度に応じて
試算するポートフォリオ設計ページ(docs/portfolio.html)を生成する。

- 投資助言ではなく、公的制度の枠組み(NISA/iDeCoの上限額)と
  一般的な年齢別資産配分の考え方(グライドパス)に基づく試算ツールとして位置づける。
- 現在の10年国債利回りは data/jgb_yields.json から読み込んで参考表示する。
- 計算自体はすべてブラウザ側(JS)で行う。入力された年収等の個人情報は
  どこにも送信・保存されず、その場で計算されるだけ。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
JGB_PATH = os.path.join(BASE_DIR, "data", "jgb_yields.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "portfolio.html")

JST = timezone(timedelta(hours=9))


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_jgb_10y():
    jgb = load_json(JGB_PATH)
    if not jgb or "長期(10年)" not in jgb:
        return None
    series = jgb["長期(10年)"]
    if not series.get("values"):
        return None
    return {"value": series["values"][-1], "date": series["dates"][-1]}


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    jgb_10y = get_latest_jgb_10y()
    jgb_10y_json = json.dumps(jgb_10y, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ポートフォリオ設計</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px 0; }}
  h2 {{ font-size: 1rem; margin: 22px 0 8px 0; }}
  h3 {{ font-size: 0.88rem; margin: 0 0 8px 0; color: #ccc; }}
  .updated {{ font-size: 0.75rem; color: #999; margin-bottom: 8px; }}
  nav.nav-primary {{ margin-bottom: 6px; font-size: 0.85rem; }}
  nav.nav-primary a {{ color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }}
  nav.nav-primary a.active {{ color: #e8e8e8; text-decoration: underline; }}
  nav.nav-secondary {{ margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }}
  nav.nav-secondary a {{ color: #888; margin-right: 12px; text-decoration: none; }}
  nav.nav-secondary a.active {{ color: #6ab7ff; font-weight: 600; text-decoration: underline; }}

  .disclaimer {{
    background: #241b1b; border: 1px solid #4a2f2f; border-radius: 8px;
    padding: 10px 12px; font-size: 0.72rem; color: #ffb0a0; line-height: 1.6; margin-bottom: 16px;
  }}

  .form-box {{ background: #171a20; border-radius: 10px; padding: 14px; margin-bottom: 14px; }}
  .form-row {{ margin-bottom: 12px; }}
  .form-row label {{ display: block; font-size: 0.78rem; color: #999; margin-bottom: 4px; }}
  .form-row input {{
    width: 100%; box-sizing: border-box; background: #0f1115; color: #e8e8e8;
    border: 1px solid #333; border-radius: 6px; padding: 9px; font-size: 0.9rem;
  }}
  .risk-options {{ display: flex; gap: 8px; }}
  .risk-btn {{
    flex: 1; background: #0f1115; color: #ccc; border: 1px solid #333; border-radius: 8px;
    padding: 10px 6px; font-size: 0.75rem; text-align: center; cursor: pointer;
  }}
  .risk-btn.active {{ background: #1b2a3a; color: #6ab7ff; border-color: #2f4a63; font-weight: 600; }}
  .risk-desc {{ font-size: 0.68rem; color: #777; margin-top: 6px; line-height: 1.5; }}

  .calc-btn {{
    width: 100%; background: #1b2a3a; color: #6ab7ff; border: 1px solid #2f4a63;
    border-radius: 8px; padding: 12px; font-size: 0.9rem; font-weight: 700; cursor: pointer; margin-top: 6px;
  }}

  .result-box {{ display: none; }}
  .result-box.show {{ display: block; }}
  .alloc-card {{ background: #171a20; border-radius: 10px; padding: 14px; margin-bottom: 12px; }}
  .alloc-title {{ font-size: 0.85rem; font-weight: 700; margin-bottom: 4px; }}
  .alloc-amount {{ font-size: 1.4rem; font-weight: 700; color: #4caf50; }}
  .alloc-note {{ font-size: 0.72rem; color: #999; margin-top: 4px; line-height: 1.6; }}
  .bar-track {{ background: #0f1115; border-radius: 6px; height: 22px; overflow: hidden; display: flex; margin: 10px 0; }}
  .bar-seg {{ height: 100%; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; color: #0f1115; font-weight: 700; }}
  .legend {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.7rem; margin-bottom: 4px; }}
  .legend-item {{ display: flex; align-items: center; gap: 4px; }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
  .warn-box {{ background: #2a2413; border: 1px solid #4a3f1b; border-radius: 8px; padding: 10px 12px; font-size: 0.75rem; color: #ffd54f; margin-bottom: 12px; line-height: 1.6; }}
  .ref-box {{ font-size: 0.72rem; color: #888; line-height: 1.7; }}
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
    <a href="overseas.html">海外指標</a>
    <a href="commodities.html">資源</a>
    <a href="calendar.html">経済指標カレンダー</a>
    <a href="portfolio.html" class="active">ポートフォリオ設計</a>
  </nav>
  <h1>ポートフォリオ設計</h1>
  <div class="updated">最終更新: {now}</div>

  <div class="disclaimer">
    ⚠️ これは投資助言ではありません。NISA・iDeCoの制度上の上限額と、一般的な年齢別資産配分の考え方(目安)を使った試算ツールです。入力した情報はこの端末内で計算されるだけで、どこにも送信・保存されません。最終的な投資判断はご自身の責任で行ってください。
  </div>

  <div class="form-box">
    <h3>収入・投資可能額</h3>
    <div class="form-row">
      <label>月々の投資可能額（円）</label>
      <input type="number" id="in-monthly" placeholder="例: 50000" min="0" step="1000">
    </div>
    <div class="form-row">
      <label>ボーナス時の追加投資額（1回あたり・円、年2回想定）</label>
      <input type="number" id="in-bonus" placeholder="例: 100000" min="0" step="1000">
    </div>
    <div class="form-row">
      <label>年収（万円、参考表示のみ・任意）</label>
      <input type="number" id="in-income" placeholder="例: 500" min="0" step="10">
    </div>

    <h3 style="margin-top:18px;">属性</h3>
    <div class="form-row">
      <label>年齢</label>
      <input type="number" id="in-age" value="25" min="18" max="75" step="1">
    </div>
    <div class="form-row">
      <label>iDeCoの月額拠出上限（円）※お勤め先の制度により異なります</label>
      <input type="number" id="in-ideco-limit" value="4000" min="0" step="1000">
    </div>
    <div class="form-row">
      <label>生活防衛資金（現金での貯蓄額・円、任意）</label>
      <input type="number" id="in-emergency" placeholder="例: 1000000" min="0" step="10000">
    </div>

    <h3 style="margin-top:18px;">リスク許容度</h3>
    <div class="risk-options" id="risk-options">
      <div class="risk-btn" data-risk="stable">安定重視</div>
      <div class="risk-btn active" data-risk="balance">バランス</div>
      <div class="risk-btn" data-risk="aggressive">積極運用</div>
    </div>
    <div class="risk-desc" id="risk-desc"></div>

    <button class="calc-btn" id="calc-btn">試算する</button>
  </div>

  <div class="result-box" id="result-box"></div>

  <h2>参考情報</h2>
  <div class="ref-box" id="ref-box"></div>

  <script>
    const JGB_10Y = {jgb_10y_json};

    const RISK_CONFIG = {{
      stable: {{ label: '安定重視', baseStock: 40, desc: '値動きの小さい安全資産(国債など)を多めにする方針。値下がりリスクを抑えたい方向け。' }},
      balance: {{ label: 'バランス', baseStock: 60, desc: '株式と安全資産をバランスよく持つ方針。' }},
      aggressive: {{ label: '積極運用', baseStock: 80, desc: '値上がり期待の高い株式を多めにする方針。値下がり時の変動も大きくなります。' }},
    }};

    let selectedRisk = 'balance';

    document.querySelectorAll('.risk-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.risk-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedRisk = btn.dataset.risk;
        updateRiskDesc();
      }});
    }});

    function updateRiskDesc() {{
      document.getElementById('risk-desc').textContent = RISK_CONFIG[selectedRisk].desc;
    }}
    updateRiskDesc();

    function yen(n) {{
      return Math.round(n).toLocaleString() + '円';
    }}

    function calcStockRatio(age, risk) {{
      const base = RISK_CONFIG[risk].baseStock;
      // 25歳を基準に、1歳上がるごとに株式比率を0.5%ずつ下げる簡易グライドパス
      const adjusted = base - (age - 25) * 0.5;
      return Math.min(95, Math.max(10, adjusted));
    }}

    function calculate() {{
      const monthly = parseFloat(document.getElementById('in-monthly').value) || 0;
      const bonus = parseFloat(document.getElementById('in-bonus').value) || 0;
      const income = parseFloat(document.getElementById('in-income').value) || 0;
      const age = parseFloat(document.getElementById('in-age').value) || 25;
      const idecoLimit = parseFloat(document.getElementById('in-ideco-limit').value) || 0;
      const emergency = parseFloat(document.getElementById('in-emergency').value) || 0;

      const resultBox = document.getElementById('result-box');

      if (monthly <= 0 && bonus <= 0) {{
        resultBox.innerHTML = '<div class="warn-box">月々の投資可能額かボーナス投資額のどちらかを入力してください。</div>';
        resultBox.classList.add('show');
        return;
      }}

      const annualTotal = monthly * 12 + bonus * 2;

      // Step1: iDeCo優先配分(上限額まで、税制優遇が大きいため最優先)
      const idecoMonthly = Math.min(idecoLimit, monthly);
      const idecoAnnual = idecoMonthly * 12;
      const remainingMonthly = monthly - idecoMonthly;
      const remainingAnnual = remainingMonthly * 12 + bonus * 2;

      // Step2: 残りを株式(NISA活用)と安全資産(国債等)に按分
      const stockRatio = calcStockRatio(age, selectedRisk);
      const stockAnnual = remainingAnnual * (stockRatio / 100);
      const safeAnnual = remainingAnnual - stockAnnual;

      // NISA枠のチェック(つみたて投資枠 年120万円、成長投資枠 年240万円、生涯1800万円)
      const NISA_TSUMITATE_ANNUAL_MAX = 1200000;
      const NISA_GROWTH_ANNUAL_MAX = 2400000;
      const NISA_ANNUAL_MAX = NISA_TSUMITATE_ANNUAL_MAX + NISA_GROWTH_ANNUAL_MAX;
      const NISA_LIFETIME_MAX = 18000000;

      let nisaNote = '';
      if (stockAnnual > NISA_ANNUAL_MAX) {{
        nisaNote = `年間360万円のNISA年間上限を超えています。超過分(${{yen(stockAnnual - NISA_ANNUAL_MAX)}}/年)は課税口座での運用になります。`;
      }} else {{
        const yearsToFillLifetime = stockAnnual > 0 ? (NISA_LIFETIME_MAX / stockAnnual).toFixed(1) : '-';
        nisaNote = `この配分を続けた場合、生涯投資枠1,800万円を使い切るまで約${{yearsToFillLifetime}}年かかる計算です。`;
      }}

      // 生活防衛資金チェック(一般的な目安として50万円未満なら注意喚起)
      let emergencyNote = '';
      if (emergency > 0 && emergency < 500000) {{
        emergencyNote = `<div class="warn-box">生活防衛資金が少なめです。一般的には生活費の3〜6ヶ月分を現金で確保してから投資に回すのがセオリーとされています。</div>`;
      }}

      const total = idecoAnnual + stockAnnual + safeAnnual;
      const idecoPct = total > 0 ? (idecoAnnual / total * 100) : 0;
      const stockPct = total > 0 ? (stockAnnual / total * 100) : 0;
      const safePct = total > 0 ? (safeAnnual / total * 100) : 0;

      const jgbNote = JGB_10Y
        ? `参考: 現在の10年国債利回りは${{JGB_10Y.value}}%（${{JGB_10Y.date}}時点）です。`
        : '';

      resultBox.innerHTML = `
        ${{emergencyNote}}

        <div class="alloc-card">
          <h3>年間投資可能額の内訳（試算）</h3>
          <div class="legend">
            <div class="legend-item"><span class="legend-dot" style="background:#ffd54f;"></span>iDeCo</div>
            <div class="legend-item"><span class="legend-dot" style="background:#4caf50;"></span>株式(NISA活用)</div>
            <div class="legend-item"><span class="legend-dot" style="background:#6ab7ff;"></span>安全資産(国債等)</div>
          </div>
          <div class="bar-track">
            <div class="bar-seg" style="width:${{idecoPct}}%; background:#ffd54f;">${{idecoPct >= 8 ? idecoPct.toFixed(0)+'%' : ''}}</div>
            <div class="bar-seg" style="width:${{stockPct}}%; background:#4caf50;">${{stockPct >= 8 ? stockPct.toFixed(0)+'%' : ''}}</div>
            <div class="bar-seg" style="width:${{safePct}}%; background:#6ab7ff;">${{safePct >= 8 ? safePct.toFixed(0)+'%' : ''}}</div>
          </div>
          <div class="alloc-note">年間投資可能総額（月々×12＋ボーナス×2）: <b>${{yen(annualTotal)}}</b></div>
        </div>

        <div class="alloc-card">
          <div class="alloc-title">① iDeCo（最優先）</div>
          <div class="alloc-amount">${{yen(idecoMonthly)}}<span style="font-size:0.8rem;color:#999;">/月</span></div>
          <div class="alloc-note">
            年間 ${{yen(idecoAnnual)}}。掛金全額が所得控除の対象になるため、税制優遇の観点で最も優先度が高い制度です。
            ${{idecoMonthly < idecoLimit ? 'まだ上限まで余裕があります。' : '上限まで拠出する想定です。'}}
          </div>
        </div>

        <div class="alloc-card">
          <div class="alloc-title">② 株式（NISA活用、リスク許容度:${{RISK_CONFIG[selectedRisk].label}}）</div>
          <div class="alloc-amount">${{yen(stockAnnual / 12)}}<span style="font-size:0.8rem;color:#999;">/月換算</span></div>
          <div class="alloc-note">
            年間 ${{yen(stockAnnual)}}（残額の${{stockRatio.toFixed(0)}}%）。全世界株式・S&P500など低コストのインデックスファンドをNISAのつみたて投資枠・成長投資枠で保有するイメージです。<br>
            ${{nisaNote}}
          </div>
        </div>

        <div class="alloc-card">
          <div class="alloc-title">③ 安全資産（国債など）</div>
          <div class="alloc-amount">${{yen(safeAnnual / 12)}}<span style="font-size:0.8rem;color:#999;">/月換算</span></div>
          <div class="alloc-note">
            年間 ${{yen(safeAnnual)}}（残額の${{(100 - stockRatio).toFixed(0)}}%）。個人向け国債(変動10年など)は購入単位が1万円からのため、月々ではなくボーナス時にまとめて購入するのも現実的です。<br>
            ${{jgbNote}}
          </div>
        </div>
      `;
      resultBox.classList.add('show');
    }}

    document.getElementById('calc-btn').addEventListener('click', calculate);

    // 参考情報欄
    const refBox = document.getElementById('ref-box');
    let refHtml = '';
    if (JGB_10Y) {{
      refHtml += `・現在の10年国債利回り: ${{JGB_10Y.value}}%（${{JGB_10Y.date}}時点、詳細は「日本の経済状況」ページ）<br>`;
    }}
    refHtml += `
      ・NISA制度: つみたて投資枠(年120万円)＋成長投資枠(年240万円)＝年間最大360万円、生涯投資枠1,800万円(2024年以降の新NISA)<br>
      ・iDeCo: 掛金が全額所得控除の対象。ただし60歳まで原則引き出せません。<br>
      ・株式(S&amp;P500など)の過去の長期平均リターンは年率7〜10%程度と言われることが多いですが、あくまで過去の実績であり将来を保証するものではありません。短期的には大きく値下がりする年もあります。<br>
      ・このツールの配分ロジックは「年齢に応じて徐々に安全資産の比率を上げる」という一般的な考え方(グライドパス)の簡易版です。実際の最適な配分は、家計の状況やライフイベントの予定によって大きく変わります。
    `;
    refBox.innerHTML = refHtml;
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
