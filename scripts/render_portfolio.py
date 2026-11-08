# -*- coding: utf-8 -*-
"""
余剰資金の配分シミュレーター(docs/portfolio.html)を生成する。

対象資産: 現金(預金) / 短期国債 / 長期国債(10年) / NISAつみたて投資枠(S&P500) / iDeCo(S&P500)

考え方:
- 各資産の期待リターンを「税引後」「インフレ控除後(実質)」に直して比較する。
  - 預金利息・国債利子は 20.315% の源泉分離課税
  - NISA は運用益非課税
  - iDeCo は運用益非課税 + 掛金が全額所得控除(所得税+住民税の限界税率ぶん戻ってくる)。
    受取時の課税は「受取時の想定税率」で差し引く。
- 「1年で〇%までの損失なら耐えられる」というリスク上限(約20年に1度の悪い年 = 平均-1.645σ)
  を満たす範囲で、実質の期待値が最大になる配分を探索する(グリッド探索)。
- NISA(年120万円 / 生涯1,800万円)、iDeCo(月額上限・65歳まで)の枠を制約として扱い、
  運用期間の毎年について同じ方針で配分を決め直す。国債・預金は毎年組み替え、NISA/iDeCoは買い増しのみ。
- 将来の資産額はモンテカルロ法で幅(下位10%〜上位10%)も出す。

期待リターン等のデフォルト値はこのファイルで定義し、画面上で変更できる。
国債利回りの初期値は data/jgb_yields.json(財務省データ)の最新値を使う。
計算はすべてブラウザ側で行い、入力値はどこにも送信されない
(入力の保存はその端末のブラウザ内 localStorage のみ)。
"""
import os
import json
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
JGB_PATH = os.path.join(BASE_DIR, "data", "jgb_yields.json")
OUT_PATH = os.path.join(BASE_DIR, "docs", "portfolio.html")

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# デフォルトの前提値(すべて画面で変更可能)。リターン・リスクは年率%。
# ---------------------------------------------------------------------------
DEFAULT_ASSUMPTIONS = {
    "infl": 2.0,          # 想定インフレ率(日銀の物価目標)
    "rCash": 0.3,         # 普通預金金利
    "rShort": 1.0,        # 短期国債利回り(データが取れれば2年国債の最新値で上書き)
    "vShort": 1.0,        # 短期国債の価格変動リスク
    "rLong": 1.5,         # 長期国債利回り(データが取れれば10年国債の最新値で上書き)
    "vLong": 5.0,         # 長期国債の価格変動リスク(途中売却する場合の時価の振れ)
    "rStock": 6.0,        # S&P500(円建て)の期待リターン。為替込みの控えめな想定
    "vStock": 18.0,       # S&P500(円建て)のリスク
    "fee": 0.1,           # 投資信託の信託報酬
    "rho": 0.0,           # 株式と長期国債の相関
    "taxInterest": 20.315,  # 利子・譲渡益の税率
}

# 入力項目のデフォルト
DEFAULT_INPUTS = {
    "monthly": 50000,     # 毎月投資に回すお金(生活防衛資金は別に確保済みの前提)
    "age": 25,
    "income": 500,        # 年収(万円)
    "spouseIncome": 0,    # 扶養している配偶者の年収(万円・額面)。配偶者控除/特別控除の計算用
    "years": 20,          # 運用期間
    "nisaBal": 0,         # NISA残高(時価)
    "nisaUsed": 0,        # NISA生涯枠の使用済み額(簿価)
    "idecoBal": 0,        # iDeCo残高
    "idecoLimit": 4000,   # iDeCo月額上限(勤務先の制度により異なる)
    "idecoFee": 171,      # iDeCo口座の手数料(月額, 国民年金基金連合会105円+事務委託66円の一般的な例)
    "idecoOutTax": 0,     # iDeCo受取時の想定税率(%) 退職所得控除の範囲内なら0
    "lossLimit": 20,      # 1年で耐えられる損失(%)
}


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_yield(jgb, key):
    if not jgb or key not in jgb:
        return None
    series = jgb[key]
    if not series.get("values"):
        return None
    return {"value": series["values"][-1], "date": series["dates"][-1]}


def build_defaults():
    assumptions = dict(DEFAULT_ASSUMPTIONS)
    jgb = load_json(JGB_PATH)
    y2 = get_latest_yield(jgb, "短期(2年)")
    y10 = get_latest_yield(jgb, "長期(10年)")
    if y2:
        assumptions["rShort"] = round(float(y2["value"]), 3)
    if y10:
        assumptions["rLong"] = round(float(y10["value"]), 3)
    return assumptions, {"jgb2y": y2, "jgb10y": y10}


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>資金配分シミュレーター</title>
<style>
  :root { color-scheme: dark; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif;
    margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8;
  }
  h1 { font-size: 1.2rem; margin: 0 0 4px 0; }
  h2 { font-size: 1rem; margin: 22px 0 8px 0; }
  h3 { font-size: 0.88rem; margin: 0 0 8px 0; color: #ccc; }
  .updated { font-size: 0.75rem; color: #999; margin-bottom: 8px; }
  nav.nav-primary { margin-bottom: 6px; font-size: 0.85rem; }
  nav.nav-primary a { color: #6ab7ff; margin-right: 14px; text-decoration: none; font-weight: 600; }
  nav.nav-primary a.active { color: #e8e8e8; text-decoration: underline; }
  nav.nav-secondary { margin-bottom: 16px; font-size: 0.75rem; padding-left: 2px; }
  nav.nav-secondary a { color: #888; margin-right: 12px; text-decoration: none; }
  nav.nav-secondary a.active { color: #6ab7ff; font-weight: 600; text-decoration: underline; }

  .disclaimer {
    background: #241b1b; border: 1px solid #4a2f2f; border-radius: 8px;
    padding: 10px 12px; font-size: 0.72rem; color: #ffb0a0; line-height: 1.6; margin-bottom: 16px;
  }
  .box { background: #171a20; border-radius: 10px; padding: 14px; margin-bottom: 14px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; }
  @media (max-width: 380px) { .grid2 { grid-template-columns: 1fr; } }
  .form-row label { display: block; font-size: 0.72rem; color: #999; margin-bottom: 4px; line-height: 1.4; }
  .form-row input[type=number], .form-row select {
    width: 100%; box-sizing: border-box; background: #0f1115; color: #e8e8e8;
    border: 1px solid #333; border-radius: 6px; padding: 8px; font-size: 0.9rem;
  }
  .check-row { font-size: 0.78rem; color: #ccc; margin: 10px 0 0 0; display: flex; gap: 8px; align-items: flex-start; line-height: 1.5; }
  .hint { font-size: 0.68rem; color: #777; margin-top: 6px; line-height: 1.5; }
  details summary { cursor: pointer; font-size: 0.85rem; font-weight: 600; color: #ccc; }
  details[open] summary { margin-bottom: 10px; }
  .risk-options { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
  .risk-btn {
    flex: 1; min-width: 56px; background: #0f1115; color: #ccc; border: 1px solid #333; border-radius: 8px;
    padding: 8px 4px; font-size: 0.75rem; text-align: center; cursor: pointer;
  }
  .risk-btn.active { background: #1b2a3a; color: #6ab7ff; border-color: #2f4a63; font-weight: 600; }
  .btn {
    width: 100%; background: #1b2a3a; color: #6ab7ff; border: 1px solid #2f4a63;
    border-radius: 8px; padding: 12px; font-size: 0.9rem; font-weight: 700; cursor: pointer; margin-top: 6px;
  }
  .btn.sub { background: #0f1115; color: #999; border-color: #333; font-weight: 400; font-size: 0.78rem; padding: 8px; }

  .alloc-row { display: flex; justify-content: space-between; align-items: baseline; padding: 9px 0; border-bottom: 1px solid #23262e; gap: 8px; }
  .alloc-row:last-child { border-bottom: none; }
  .alloc-name { font-size: 0.85rem; display: flex; align-items: center; gap: 6px; }
  .alloc-val { text-align: right; font-size: 1.05rem; font-weight: 700; white-space: nowrap; }
  .alloc-sub { font-size: 0.68rem; color: #999; font-weight: 400; display: block; }
  .dot { width: 10px; height: 10px; border-radius: 3px; display: inline-block; flex: none; }
  .bar-track { background: #0f1115; border-radius: 6px; height: 22px; overflow: hidden; display: flex; margin: 10px 0; }
  .bar-seg { height: 100%; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; color: #0f1115; font-weight: 700; }
  .kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }
  .kpi { background: #0f1115; border-radius: 8px; padding: 8px; }
  .kpi .k { font-size: 0.64rem; color: #999; }
  .kpi .v { font-size: 0.95rem; font-weight: 700; margin-top: 2px; }
  .pos { color: #4caf50; } .neg { color: #ef5350; }
  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table { border-collapse: collapse; width: 100%; font-size: 0.72rem; }
  th, td { padding: 6px 5px; text-align: right; border-bottom: 1px solid #23262e; white-space: nowrap; }
  th { color: #999; font-weight: 600; }
  th:first-child, td:first-child { text-align: left; }
  tr.current td { background: #1b2a3a; }
  .warn-box { background: #2a2413; border: 1px solid #4a3f1b; border-radius: 8px; padding: 10px 12px; font-size: 0.75rem; color: #ffd54f; margin-bottom: 12px; line-height: 1.6; }
  .info-box { background: #13202a; border: 1px solid #1f3a4f; border-radius: 8px; padding: 10px 12px; font-size: 0.75rem; color: #9fd0ff; margin-bottom: 12px; line-height: 1.6; }
  .ref-box { font-size: 0.72rem; color: #888; line-height: 1.7; }
  .note { font-size: 0.68rem; color: #888; margin-top: 8px; line-height: 1.6; }
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
    <a href="portfolio.html" class="active">資金配分</a>
  </nav>
  <h1>余剰資金の配分シミュレーター</h1>
  <div class="updated">最終更新: __UPDATED__</div>

  <div class="disclaimer">
    ⚠️ 投資助言ではありません。前提（期待リターン・リスク・インフレ率）を置いたときに「リスク上限の範囲で実質の期待値が最大になる配分」を計算する試算ツールです。将来のリターンは保証されません。入力内容はこの端末内で計算され、外部には送信されません（入力の保存はこのブラウザ内のみ）。
  </div>

  <div class="box">
    <h3>投資に回すお金</h3>
    <div class="grid2">
      <div class="form-row"><label>毎月投資に回すお金（円）</label><input type="number" id="monthly" min="0" step="1000"></div>
      <div class="form-row"><label>運用期間（年）＝このお金を使う予定の時期</label><input type="number" id="years" min="1" max="50" step="1"></div>
    </div>
    <div class="hint">生活防衛資金（生活費の数ヶ月分の現金）は別に十分確保してある前提で、毎月のこの金額をどこに振り分けるかを計算します。</div>

    <h3 style="margin-top:16px;">あなたについて（税金の計算用）</h3>
    <div class="grid2">
      <div class="form-row"><label>年齢</label><input type="number" id="age" min="18" max="80" step="1"></div>
      <div class="form-row"><label>年収（万円・額面）</label><input type="number" id="income" min="0" step="10"></div>
      <div class="form-row">
        <label>配偶者の扶養</label>
        <select id="spouse">
          <option value="none">扶養していない</option>
          <option value="normal">扶養している（配偶者70歳未満）</option>
          <option value="elderly">扶養している（配偶者70歳以上）</option>
        </select>
      </div>
      <div class="form-row" id="spouse-income-row">
        <label>配偶者の年収（万円・額面）※パート等。なしなら0</label>
        <input type="number" id="spouseIncome" min="0" step="1">
      </div>
      <div class="form-row" style="grid-column: 1 / -1;">
        <label>所得税＋住民税の税率（iDeCoの節税額の計算に使用）</label>
        <select id="taxMode">
          <option value="auto">年収から自動推定（会社員の場合）</option>
          <option value="15">15%（所得税5%＋住民税10%）</option>
          <option value="20">20%（所得税10%＋住民税10%）</option>
          <option value="30">30%（所得税20%＋住民税10%）</option>
          <option value="33">33%（所得税23%＋住民税10%）</option>
          <option value="43">43%（所得税33%＋住民税10%）</option>
          <option value="50">50%（所得税40%＋住民税10%）</option>
          <option value="55">55%（所得税45%＋住民税10%）</option>
        </select>
        <div class="hint" id="tax-hint"></div>
      </div>
    </div>

    <h3 style="margin-top:16px;">NISA・iDeCo</h3>
    <div class="grid2">
      <div class="form-row"><label>NISAの現在の残高（時価・円）</label><input type="number" id="nisaBal" min="0" step="10000"></div>
      <div class="form-row"><label>NISA生涯枠の使用済み額（買付額・円）</label><input type="number" id="nisaUsed" min="0" step="10000"></div>
      <div class="form-row"><label>iDeCoの現在の残高（円）</label><input type="number" id="idecoBal" min="0" step="10000"></div>
      <div class="form-row"><label>iDeCoの月額上限（円）※勤務先の制度で異なる</label><input type="number" id="idecoLimit" min="0" step="1000"></div>
      <div class="form-row"><label>iDeCo口座手数料（月額・円）</label><input type="number" id="idecoFee" min="0" step="1"></div>
      <div class="form-row"><label>iDeCo受取時の想定税率（%）</label><input type="number" id="idecoOutTax" min="0" max="55" step="1"></div>
    </div>
    <label class="check-row"><input type="checkbox" id="useIdeco"> iDeCoを使う（60歳まで引き出せないお金にしてよい）</label>
    <label class="check-row"><input type="checkbox" id="useGrowth"> NISA成長投資枠も使う（年120万円→360万円に拡大。中身は同じS&amp;P500として計算）</label>
    <div class="hint">iDeCo受取時の税率: 一時金で受け取り、退職所得控除の範囲内に収まるなら0%。退職金が多い場合などは5〜10%程度を入れておくと保守的です。</div>
  </div>

  <div class="box">
    <h3>リスク許容度：1年でどこまでの損失なら耐えられるか</h3>
    <div class="risk-options" id="risk-options">
      <div class="risk-btn" data-loss="0">0%</div>
      <div class="risk-btn" data-loss="5">5%</div>
      <div class="risk-btn" data-loss="10">10%</div>
      <div class="risk-btn" data-loss="20">20%</div>
      <div class="risk-btn" data-loss="30">30%</div>
    </div>
    <div class="form-row"><label>許容損失（%・自由入力）</label><input type="number" id="lossLimit" min="0" max="80" step="1"></div>
    <div class="hint">「20年に1回くらい来る悪い年」（平均−1.645×標準偏差）に、運用資産全体が<b>実質で</b>（インフレによる目減り込みで）この%以上減らないように配分します。現金でもインフレ分は目減りするため、0%は「現金と同程度」の意味になります。実際にはこれ以上下がる年もあり得ます（リーマンショック級など）。</div>
  </div>

  <div class="box">
    <details id="assump-details">
      <summary>前提条件（期待リターン・リスク・インフレ率）を変更する</summary>
      <div class="grid2">
        <div class="form-row"><label>インフレ率（%/年）</label><input type="number" id="infl" step="0.1"></div>
        <div class="form-row"><label>利子・譲渡益の税率（%）</label><input type="number" id="taxInterest" step="0.001"></div>
        <div class="form-row"><label>預金金利（%/年）</label><input type="number" id="rCash" step="0.01"></div>
        <div class="form-row"><label>―</label><div class="hint" style="margin-top:8px;">預金のリスクは0として計算</div></div>
        <div class="form-row"><label>短期国債 利回り（%/年）</label><input type="number" id="rShort" step="0.01"></div>
        <div class="form-row"><label>短期国債 リスク（%）</label><input type="number" id="vShort" step="0.1"></div>
        <div class="form-row"><label>長期国債(10年) 利回り（%/年）</label><input type="number" id="rLong" step="0.01"></div>
        <div class="form-row"><label>長期国債 リスク（%）</label><input type="number" id="vLong" step="0.1"></div>
        <div class="form-row"><label>S&amp;P500(円建て) 期待リターン（%/年）</label><input type="number" id="rStock" step="0.1"></div>
        <div class="form-row"><label>S&amp;P500 リスク（%）</label><input type="number" id="vStock" step="0.1"></div>
        <div class="form-row"><label>投資信託の信託報酬（%/年）</label><input type="number" id="fee" step="0.01"></div>
        <div class="form-row"><label>株式と長期国債の相関（−1〜1）</label><input type="number" id="rho" step="0.1" min="-1" max="1"></div>
      </div>
      <div class="hint" id="assump-hint"></div>
      <button class="btn sub" id="reset-assump">前提条件を初期値に戻す</button>
    </details>
  </div>

  <button class="btn" id="calc-btn">計算する</button>
  <button class="btn sub" id="reset-all">入力をすべて初期値に戻す</button>

  <div id="result" style="margin-top:16px;"></div>

  <h2>計算の前提と注意</h2>
  <div class="ref-box">
    ・金額はすべて<b>実質（今のお金の価値）</b>で表示しています。インフレ率2%なら、現金のまま持っていると購買力が毎年約2%目減りします。<br>
    ・預金利息・国債の利子には20.315%が課税されます。NISA・iDeCoの運用益は非課税です。<br>
    ・iDeCoは掛金が全額所得控除となり、掛金×（所得税＋住民税の税率）が翌年の税金から戻る（減る）として計算します。受取時の税金は「受取時の想定税率」で差し引きます。60歳まで引き出せません。掛金を出せるのは65歳になるまでとして計算しています。<br>
    ・NISAはつみたて投資枠 年120万円（成長投資枠も使う場合は年360万円）、生涯1,800万円が上限です。枠は名目額なので、インフレが進むと実質的な枠は少しずつ小さくなる計算にしています。<br>
    ・毎年「その年に使えるお金（預金・国債と新たな積立額）」を配分し直します。国債は必要に応じて売却して組み替える想定、NISA・iDeCoは一度買ったら売らない（買い増しのみ）想定です。長期国債の途中売却による価格変動はリスク（標準偏差）として織り込んでいます。課税口座での株式投資は対象外のため、NISA・iDeCoの枠を超える株式は買いません。<br>
    ・生活防衛資金は別に十分確保してある前提です。毎月の投資額は実質で一定（給料がインフレ並みに上がる）と仮定しています。年の途中の積立タイミングは年初にまとめて計算しています。<br>
    ・短期国債は個人向け国債（変動10年、1年経てば中途換金可）や新窓販国債の2年債など、長期国債は新窓販国債の10年債を想定しています。初期値は財務省の国債金利データの最新値（__JGB_NOTE__）です。<br>
    ・将来の幅はモンテカルロ法（1,000通りの乱数シナリオ）で出した目安です。リターンは正規分布を仮定しているため、実際の暴落のような極端な値動きは過小評価されがちです。
  </div>

  <script>
  (function () {
    'use strict';
    const DEFAULT_ASSUMPTIONS = __DEFAULT_ASSUMPTIONS__;
    const DEFAULT_INPUTS = __DEFAULT_INPUTS__;
    const MARKET = __MARKET__;
    const STORAGE_KEY = 'portfolio-sim-v3';   // v3: 前提条件(利回り等)は保存しない
    const Z = 1.645;               // 20年に1度の悪い年(片側5%)
    const NISA_LIFETIME = 18000000;
    const IDECO_MAX_CONTRIB_AGE = 65;
    const IDECO_UNLOCK_AGE = 60;

    const ASSETS = [
      { key: 'cash',  name: '現金（預金）',        color: '#9e9e9e' },
      { key: 'short', name: '短期国債',            color: '#90caf9' },
      { key: 'long',  name: '長期国債（10年）',     color: '#4f8fd6' },
      { key: 'nisa',  name: 'NISA（S&P500）',      color: '#4caf50' },
      { key: 'ideco', name: 'iDeCo（S&P500）',     color: '#ffd54f' },
    ];
    const N_ASSET = ASSETS.length;
    const NUM_FIELDS = Object.keys(DEFAULT_INPUTS).concat(Object.keys(DEFAULT_ASSUMPTIONS));
    // 保存するのは個人の入力だけ。国債利回りなどの前提条件は毎回最新の初期値から始める
    const SAVE_FIELDS = Object.keys(DEFAULT_INPUTS);
    const $ = (id) => document.getElementById(id);

    // ---------------- 入力の保存・復元 ----------------
    function setDefaults(which) {
      const src = which === 'assump' ? DEFAULT_ASSUMPTIONS : Object.assign({}, DEFAULT_INPUTS, DEFAULT_ASSUMPTIONS);
      Object.keys(src).forEach(k => { if ($(k)) $(k).value = src[k]; });
      if (which !== 'assump') {
        $('taxMode').value = 'auto';
        $('spouse').value = 'none';
        $('useIdeco').checked = true;
        $('useGrowth').checked = false;
      }
    }
    function saveInputs() {
      const o = {};
      SAVE_FIELDS.forEach(k => { o[k] = $(k).value; });
      o.taxMode = $('taxMode').value;
      o.spouse = $('spouse').value;
      o.useIdeco = $('useIdeco').checked;
      o.useGrowth = $('useGrowth').checked;
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(o)); } catch (e) { /* 保存できない環境では無視 */ }
    }
    function loadInputs() {
      setDefaults('all');
      let o = null;
      try { o = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch (e) { o = null; }
      if (!o) return;
      SAVE_FIELDS.forEach(k => { if (o[k] !== undefined && o[k] !== '') $(k).value = o[k]; });
      if (o.taxMode) $('taxMode').value = o.taxMode;
      if (o.spouse) $('spouse').value = o.spouse;
      if (typeof o.useIdeco === 'boolean') $('useIdeco').checked = o.useIdeco;
      if (typeof o.useGrowth === 'boolean') $('useGrowth').checked = o.useGrowth;
    }

    function num(id) {
      const v = parseFloat($(id).value);
      return isFinite(v) ? v : (DEFAULT_INPUTS[id] !== undefined ? DEFAULT_INPUTS[id] : DEFAULT_ASSUMPTIONS[id]);
    }

    // ---------------- 税率の推定(会社員・社会保険料14.5%の簡易計算) ----------------
    // 給与所得控除(2025年分以降、最低65万円)
    function kyuyoKojo(g) {
      if (g <= 1900000) return Math.min(g, 650000);
      if (g <= 3600000) return g * 0.3 + 80000;
      if (g <= 6600000) return g * 0.2 + 440000;
      if (g <= 8500000) return g * 0.1 + 1100000;
      return 1950000;
    }

    // 配偶者控除・配偶者特別控除(所得税)。本人の合計所得と、配偶者の合計所得で決まる
    // ・配偶者の所得58万円以下(給与のみなら年収123万円以下) → 配偶者控除 38万円(70歳以上は48万円)
    // ・58万円超〜133万円以下 → 配偶者特別控除(38万円から段階的に減る)
    // ・本人の所得が900万円超で2/3、950万円超で1/3、1,000万円超で0
    const SPOUSE_SPECIAL = [[950000, 380000], [1000000, 360000], [1050000, 310000], [1100000, 260000],
      [1150000, 210000], [1200000, 160000], [1250000, 110000], [1300000, 60000], [1330000, 30000]];
    function spouseDeduction(selfShotoku, spouseSalary, elderly) {
      const spouseShotoku = Math.max(0, spouseSalary - kyuyoKojo(spouseSalary));
      let amount = 0, kind = '';
      if (spouseShotoku <= 580000) {
        amount = elderly ? 480000 : 380000; kind = '配偶者控除';
      } else {
        const band = SPOUSE_SPECIAL.find(([lim]) => spouseShotoku <= lim);
        amount = band ? band[1] : 0; kind = band ? '配偶者特別控除' : '';
      }
      if (selfShotoku > 10000000) amount = 0;
      else if (selfShotoku > 9500000) amount = Math.ceil(amount / 3 / 10000) * 10000;
      else if (selfShotoku > 9000000) amount = Math.ceil(amount * 2 / 3 / 10000) * 10000;
      if (amount === 0) kind = selfShotoku > 10000000 ? '本人の所得が1,000万円超のため控除なし' : '配偶者の年収が多いため控除なし';
      return { amount, kind };
    }

    function estimateTax(incomeMan, spouse) {
      const g = incomeMan * 10000;
      const shotoku = Math.max(0, g - kyuyoKojo(g));
      const shaho = g * 0.145;
      let sp = { amount: 0, kind: '' };
      if (spouse && spouse.type !== 'none') {
        sp = spouseDeduction(shotoku, spouse.incomeMan * 10000, spouse.type === 'elderly');
      }
      const taxable = Math.max(0, shotoku - shaho - 580000 - sp.amount);
      const brackets = [[1950000, 5], [3300000, 10], [6950000, 20], [9000000, 23], [18000000, 33], [40000000, 40], [Infinity, 45]];
      let incomeRate = 45;
      for (const [lim, r] of brackets) { if (taxable <= lim) { incomeRate = r; break; } }
      if (taxable <= 0) incomeRate = 0;   // 課税所得がなければ所得税の節税効果はない
      return { taxable, incomeRate, total: incomeRate * 1.021 + 10, spouse: sp };
    }

    function readParams() {
      const p = {};
      NUM_FIELDS.forEach(k => { p[k] = num(k); });
      p.useIdeco = $('useIdeco').checked;
      p.useGrowth = $('useGrowth').checked;
      p.years = Math.max(1, Math.min(50, Math.round(p.years)));
      p.age = Math.round(p.age);
      p.rho = Math.max(-1, Math.min(1, p.rho));
      p.spouse = $('spouse').value;
      $('spouse-income-row').style.display = p.spouse === 'none' ? 'none' : '';
      const est = estimateTax(p.income, { type: p.spouse, incomeMan: p.spouseIncome });
      if ($('taxMode').value === 'auto') {
        p.taxRate = est.total;
        const spText = p.spouse === 'none' ? '' :
          (est.spouse.amount > 0 ? `（${est.spouse.kind} ${Math.round(est.spouse.amount / 10000)}万円を反映）` : `（${est.spouse.kind}）`);
        $('tax-hint').textContent = `推定課税所得 約${Math.round(est.taxable / 10000)}万円${spText} → 所得税${est.incomeRate}%(復興税込${(est.incomeRate * 1.021).toFixed(1)}%)＋住民税10% ＝ ${p.taxRate.toFixed(1)}%。子どもや親の扶養・住宅ローン控除などがある場合は手動で選んでください。`;
      } else {
        p.taxRate = parseFloat($('taxMode').value);
        $('tax-hint').textContent = '';
      }
      return p;
    }

    // ---------------- 資産ごとの実質・税引後リターンと共分散 ----------------
    function assetStats(p) {
      const infl = p.infl / 100, ti = p.taxInterest / 100;
      const nominalAfterTax = [
        p.rCash / 100 * (1 - ti),
        p.rShort / 100 * (1 - ti),
        p.rLong / 100 * (1 - ti),
        (p.rStock - p.fee) / 100,      // NISA: 非課税
        (p.rStock - p.fee) / 100,      // iDeCo: 運用益非課税
      ];
      const mu = nominalAfterTax.map(n => (1 + n) / (1 + infl) - 1);
      const vol = [0, p.vShort / 100, p.vLong / 100, p.vStock / 100, p.vStock / 100];
      const corr = [
        [1, 0, 0, 0, 0],
        [0, 1, 0.6, 0, 0],
        [0, 0.6, 1, p.rho, p.rho],
        [0, 0, p.rho, 1, 1],
        [0, 0, p.rho, 1, 1],
      ];
      const cov = corr.map((row, i) => row.map((c, j) => c * vol[i] * vol[j]));
      return { mu, vol, cov, nominalAfterTax };
    }

    function portStats(w, mu, cov) {
      let m = 0, v = 0;
      for (let i = 0; i < N_ASSET; i++) {
        m += w[i] * mu[i];
        for (let j = 0; j < N_ASSET; j++) v += w[i] * w[j] * cov[i][j];
      }
      return { mean: m, sd: Math.sqrt(Math.max(0, v)) };
    }

    // ---------------- 最適化(グリッド探索) ----------------
    // 重み w_i = lb_i + x_i * R (R = 1 - Σlb)。x は和が1、x_i ≤ cap_i。
    // 目的: 実質期待リターン + iDeCo新規拠出の節税効果 - iDeCo手数料
    // 制約: 平均 - Z*標準偏差 ≥ -L
    // 列挙順は ideco, nisa, long, short で、残り(cash)は上限なし。
    function optimize(lb, ub, mu, cov, L, ded, feeW) {
      const R = 1 - lb.reduce((a, b) => a + b, 0);
      if (R <= 1e-12) return { w: lb.slice(), feasible: portStats(lb, mu, cov).mean - Z * portStats(lb, mu, cov).sd >= -L - 1e-12 };
      const cap = ub.map((u, i) => Math.max(0, (u - lb[i]) / R));
      const order = [4, 3, 2, 1];   // 残りは index 0 (cash)
      let best = null, bestObj = -Infinity;
      let fallback = null, fallbackRisk = -Infinity;
      const w = new Array(N_ASSET);
      const x = new Array(N_ASSET).fill(0);

      function evaluate() {
        let s = 0;
        for (const i of order) s += x[i];
        const rest = 1 - s;
        if (rest < -1e-9) return;
        x[0] = Math.max(0, rest);
        for (let i = 0; i < N_ASSET; i++) w[i] = lb[i] + x[i] * R;
        const st = portStats(w, mu, cov);
        const worst = st.mean - Z * st.sd;
        const idecoFlow = w[4] - lb[4];
        const obj = st.mean + idecoFlow * ded - (idecoFlow > 1e-9 ? feeW : 0);
        if (worst >= -L - 1e-12) {
          if (obj > bestObj + 1e-12) { bestObj = obj; best = x.slice(); }
        } else if (worst > fallbackRisk) {
          fallbackRisk = worst; fallback = x.slice();
        }
      }

      function candidates(i, step, center, radius) {
        const out = new Set();
        if (center === null) {
          for (let v = 0; v < cap[i] - 1e-12 && v <= 1; v += step) out.add(+v.toFixed(6));
          out.add(+Math.min(cap[i], 1).toFixed(6));
        } else {
          for (let k = -radius; k <= radius; k++) {
            const v = Math.min(cap[i], Math.min(1, Math.max(0, center[i] + k * step)));
            out.add(+v.toFixed(6));
          }
        }
        return Array.from(out);
      }

      function search(step, center, radius) {
        const lists = order.map(i => candidates(i, step, center, radius));
        const rec = (d, used) => {
          if (d === order.length) { evaluate(); return; }
          const i = order[d];
          for (const v of lists[d]) {
            if (used + v > 1 + 1e-9) continue;
            x[i] = v;
            rec(d + 1, used + v);
          }
          x[i] = 0;
        };
        rec(0, 0);
      }

      search(0.05, null, 0);
      let center = best || fallback;
      search(0.01, center, 5);
      center = best || fallback;
      search(0.0025, center, 4);
      const xs = best || fallback;
      const wOut = xs.map((xi, i) => lb[i] + xi * R);
      return { w: wOut, feasible: !!best };
    }

    // ---------------- 年ごとのシミュレーション(期待値ベース) ----------------
    function simulate(p, stats, Lpct) {
      const { mu, cov } = stats;
      const L = Lpct / 100;
      const infl = p.infl / 100;
      const ded = p.useIdeco ? (p.taxRate - p.idecoOutTax) / 100 : 0;
      let H = [0, 0, 0, p.nisaBal, p.idecoBal];
      let nisaBook = p.nisaUsed;
      const annualSave = p.monthly * 12;
      let refund = 0;
      const years = [];
      let infeasibleYears = 0, nisaBindingYears = 0;

      for (let y = 1; y <= p.years; y++) {
        const defl = Math.pow(1 + infl, y - 1);
        const age = p.age + y - 1;
        const add = annualSave + refund;
        refund = 0;
        const start = H.slice();
        H[0] += add;
        const T = H.reduce((a, b) => a + b, 0);
        const nisaAnnual = p.useGrowth ? 3600000 : 1200000;
        const capN = Math.min(nisaAnnual, Math.max(0, NISA_LIFETIME - nisaBook)) / defl;
        const idecoOpen = p.useIdeco && age < IDECO_MAX_CONTRIB_AGE;
        const capI = idecoOpen ? p.idecoLimit * 12 / defl : 0;
        const feeAnnual = p.idecoFee * 12 / defl;
        let w, feasible = true;
        if (T <= 1) {
          w = [1, 0, 0, 0, 0];
        } else {
          const lb = [0, 0, 0, H[3] / T, H[4] / T];
          const ub = [1, 1, 1, (H[3] + capN) / T, (H[4] + capI) / T];
          const res = optimize(lb, ub, mu, cov, L, ded, feeAnnual / T);
          w = res.w; feasible = res.feasible;
          if (!feasible) infeasibleYears++;
          if (feasible && capN > 0 && w[3] >= ub[3] - 1e-6) nisaBindingYears++;
        }
        const newH = w.map(wi => wi * T);
        const flow = newH.map((v, i) => v - H[i]);
        const idecoFlow = Math.max(0, flow[4]);
        let fee = 0;
        if (idecoFlow > 1) {
          fee = feeAnnual;
          let rest = fee;
          for (const i of [0, 1, 2]) { const take = Math.min(rest, newH[i]); newH[i] -= take; rest -= take; }
        }
        nisaBook += Math.max(0, flow[3]) * defl;
        refund = idecoFlow * p.taxRate / 100;
        const st = portStats(w, mu, cov);
        years.push({
          y, age, start, add, T, w, newH, flow, fee, refundNext: refund, feasible,
          mean: st.mean, sd: st.sd, capN, capI,
        });
        H = newH.map((v, i) => v * (1 + mu[i]));
        years[years.length - 1].end = H.slice();
        years[years.length - 1].endTotal = H.reduce((a, b) => a + b, 0) - H[4] * p.idecoOutTax / 100 + refund;
      }
      return { years, infeasibleYears, nisaBindingYears };
    }

    // 全額現金のまま置いておいた場合
    function simulateCash(p, stats) {
      let c = p.nisaBal + p.idecoBal * (1 - p.idecoOutTax / 100);
      const annualSave = p.monthly * 12;
      const out = [];
      for (let y = 1; y <= p.years; y++) {
        c = (c + annualSave) * (1 + stats.mu[0]);
        out.push(c);
      }
      return out;
    }

    // ---------------- モンテカルロ(計画した買付を固定し、リターンだけ乱数) ----------------
    function mulberry32(a) {
      return function () {
        a |= 0; a = a + 0x6D2B79F5 | 0;
        let t = Math.imul(a ^ a >>> 15, 1 | a);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      };
    }
    function cholesky(A) {
      const n = A.length, Lm = A.map(r => r.map(() => 0));
      for (let i = 0; i < n; i++) for (let j = 0; j <= i; j++) {
        let s = A[i][j];
        for (let k = 0; k < j; k++) s -= Lm[i][k] * Lm[j][k];
        Lm[i][j] = i === j ? Math.sqrt(Math.max(s, 0)) : (Lm[j][j] > 0 ? s / Lm[j][j] : 0);
      }
      return Lm;
    }
    function monteCarlo(p, stats, sim, nPaths) {
      const { mu, cov } = stats;
      const idx = [1, 2, 3];   // short, long, stock(=nisa/ideco 共通)
      const sub = idx.map(i => idx.map(j => cov[i][j]));
      const Lc = cholesky(sub);
      const rand = mulberry32(12345);
      const gauss = () => {
        let u = 0, v = 0;
        while (u === 0) u = rand();
        while (v === 0) v = rand();
        return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
      };
      const nY = sim.years.length;
      const totals = Array.from({ length: nY }, () => new Float64Array(nPaths));
      for (let path = 0; path < nPaths; path++) {
        let H = sim.years[0].start.slice();
        for (let t = 0; t < nY; t++) {
          const yr = sim.years[t];
          // 計画どおりの入金とNISA・iDeCoの買付
          H[0] += yr.add;
          const buyN = Math.max(0, yr.flow[3]), buyI = Math.max(0, yr.flow[4]);
          H[3] += buyN; H[4] += buyI;
          // 残りの流動資産(預金・短期国債・長期国債)は計画の比率で持ち直す。足りなければ0で止める
          const liq = Math.max(0, H[0] + H[1] + H[2] - buyN - buyI - yr.fee);
          const liquidTarget = yr.newH[0] + yr.newH[1] + yr.newH[2];
          for (let i = 0; i < 3; i++) H[i] = liquidTarget > 0 ? liq * yr.newH[i] / liquidTarget : (i === 0 ? liq : 0);
          const z = [gauss(), gauss(), gauss()];
          const r = idx.map((_, a) => {
            let s = 0; for (let b = 0; b <= a; b++) s += Lc[a][b] * z[b];
            return mu[idx[a]] + s;
          });
          H[0] *= 1 + mu[0];
          H[1] *= 1 + r[0];
          H[2] *= 1 + r[1];
          const rs = Math.max(-0.95, r[2]);
          H[3] *= 1 + rs;
          H[4] *= 1 + rs;
          // 翌年の還付は計画値を使う(sim.years[t+1].add に含まれる)
          const refundNow = t === nY - 1 ? yr.refundNext : 0;
          totals[t][path] = H.reduce((a, b) => a + b, 0) - H[4] * p.idecoOutTax / 100 + refundNow;
        }
      }
      const pct = (arr, q) => { const s = Array.from(arr).sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };
      return totals.map(a => ({ p10: pct(a, 0.1), p50: pct(a, 0.5), p90: pct(a, 0.9) }));
    }

    // ---------------- 表示 ----------------
    const man = (v) => {
      const m = v / 10000;
      if (Math.abs(m) >= 1000) return Math.round(m).toLocaleString() + '万円';
      if (Math.abs(m) >= 100) return m.toFixed(0) + '万円';
      return m.toFixed(1) + '万円';
    };
    const yen = (v) => Math.round(v).toLocaleString() + '円';
    const pctf = (v, d = 1) => (v * 100).toFixed(d) + '%';
    const signPct = (v, d = 2) => `<span class="${v >= 0 ? 'pos' : 'neg'}">${v >= 0 ? '+' : ''}${(v * 100).toFixed(d)}%</span>`;

    function render() {
      const p = readParams();
      saveInputs();
      const stats = assetStats(p);
      const sim = simulate(p, stats, p.lossLimit);
      const mc = monteCarlo(p, stats, sim, 1000);
      const cash = simulateCash(p, stats);
      const y1 = sim.years[0];
      let html = '';

      // 警告
      const warns = [];
      if (p.monthly <= 0) warns.push('毎月投資に回すお金を入力してください。');
      if (p.useIdeco && p.age < IDECO_UNLOCK_AGE && p.age + p.years < IDECO_UNLOCK_AGE) warns.push(`運用期間（${p.years}年後＝${p.age + p.years}歳）の時点ではiDeCoはまだ引き出せません（${IDECO_UNLOCK_AGE}歳から）。その時にお金が必要なら「iDeCoを使う」のチェックを外して比べてください。`);
      if (p.useIdeco && p.age >= IDECO_MAX_CONTRIB_AGE) warns.push('65歳以上のため、iDeCoへの新規拠出はない計算です。');
      if (sim.infeasibleYears > 0) warns.push(`${sim.infeasibleYears}年分で、どう配分しても許容損失（実質${p.lossLimit}%）に収まりません（現金でもインフレで目減りする／すでに持っているNISA・iDeCoの株式だけで超えている、など）。その年は「悪い年の損失」が最も小さくなる配分にしています。`);
      if (warns.length) html += `<div class="warn-box">${warns.join('<br>')}</div>`;

      // 1. 資産比較
      html += `<h2>① 資産ごとの実質リターン（税・インフレ考慮後）</h2><div class="box"><div class="table-wrap"><table>
        <tr><th>資産</th><th>名目</th><th>税引後</th><th>実質</th><th>リスク</th></tr>`;
      const nominal = [p.rCash, p.rShort, p.rLong, p.rStock - p.fee, p.rStock - p.fee];
      ASSETS.forEach((a, i) => {
        html += `<tr><td><span class="dot" style="background:${a.color}"></span> ${a.name}</td>
          <td>${nominal[i].toFixed(2)}%</td><td>${(stats.nominalAfterTax[i] * 100).toFixed(2)}%</td>
          <td>${signPct(stats.mu[i])}</td><td>${(stats.vol[i] * 100).toFixed(1)}%</td></tr>`;
      });
      html += `</table></div>
        <div class="note">実質＝(1＋税引後リターン)÷(1＋インフレ率${p.infl}%)−1。株式はS&amp;P500の期待リターンから信託報酬を引いた値です。
        iDeCoはこれに加えて<b>掛金の${p.taxRate.toFixed(1)}%が節税で戻る</b>（受取時の想定税率${p.idecoOutTax}%を差し引いて計算）ので、同じ商品でもNISAより有利になります（ただし60歳まで引き出し不可）。</div></div>`;

      // 2. 1年目の配分
      const flows = [y1.newH[0], y1.newH[1], y1.newH[2], Math.max(0, y1.flow[3]), Math.max(0, y1.flow[4])];
      const flowTotal = flows.reduce((a, b) => a + b, 0);
      html += `<h2>② 毎月の振り分け（1年目・リスク上限 ${p.lossLimit}%）</h2><div class="box">
        <div class="note" style="margin-top:0;">毎月 <b>${yen(p.monthly)}</b>（年間 ${man(p.monthly * 12)}）の振り分け先です。</div>
        <div class="bar-track">`;
      flows.forEach((f, i) => {
        const pc = flowTotal > 0 ? f / flowTotal * 100 : 0;
        if (pc > 0.05) html += `<div class="bar-seg" style="width:${pc}%;background:${ASSETS[i].color}">${pc >= 9 ? pc.toFixed(0) + '%' : ''}</div>`;
      });
      html += `</div>`;
      const notes = [
        '普通預金のまま置いておく分',
        '個人向け国債(変動10年)や2年債など。1万円〜5万円単位',
        '新窓販国債の10年債など。時価で売却可',
        `年間枠 ${man(y1.capN)} のうち`,
        y1.capI > 0 ? `月額上限 ${yen(y1.capI / 12)} のうち。節税で翌年 約${man(y1.refundNext)} 戻る` : 'iDeCoは使わない設定・または対象外',
      ];
      ASSETS.forEach((a, i) => {
        html += `<div class="alloc-row"><div class="alloc-name"><span class="dot" style="background:${a.color}"></span><div>${a.name}<span class="alloc-sub">${notes[i]}</span></div></div>
          <div class="alloc-val">${yen(Math.round(flows[i] / 12 / 100) * 100)}<span class="alloc-sub">/月（年 ${man(flows[i])}）</span></div></div>`;
      });
      if (y1.fee > 0) html += `<div class="note">iDeCo口座手数料 年${yen(y1.fee)}は差し引き済みです。</div>`;
      const worst = y1.mean - Z * y1.sd;
      const cashReal = stats.mu[0];
      html += `<div class="kpis">
          <div class="kpi"><div class="k">期待リターン(実質/年)</div><div class="v">${signPct(y1.mean)}</div></div>
          <div class="kpi"><div class="k">リスク(標準偏差)</div><div class="v">${pctf(y1.sd)}</div></div>
          <div class="kpi"><div class="k">20年に1度の悪い年</div><div class="v">${signPct(worst, 1)}</div></div>
        </div>
        <div class="note">リスク・リターンは1年目末の運用資産全体（既存のNISA・iDeCo残高を含む）の値です。国債は毎月ではなく、数ヶ月分たまったら購入（1万円〜5万円単位）するのが現実的です。ちなみに現金のままだと実質 ${signPct(cashReal)}／年です。</div>`;
      const stockW = y1.w[3] + y1.w[4];
      if (y1.feasible && y1.capN > 0 && y1.w[3] >= (y1.start[3] + y1.capN) / y1.T - 1e-6 && worst > -p.lossLimit / 100 + 0.005) {
        html += `<div class="info-box">株式の比率（${pctf(stockW, 0)}）はリスク上限ではなく<b>NISA・iDeCoの年間枠</b>で止まっています。枠を超える分は国債・現金に回しています。株式を増やしたい場合は「成長投資枠も使う」を試してください。</div>`;
      }
      html += `</div>`;

      // 3. 将来の見込み
      const checkpoints = [1, 3, 5, 10, 15, 20, 25, 30, 40, 50].filter(c => c < p.years);
      checkpoints.push(p.years);
      html += `<h2>③ 将来の資産額の見込み（実質・今のお金の価値）</h2><div class="box"><div class="table-wrap"><table>
        <tr><th>経過</th><th>下位10%</th><th>中央値</th><th>上位10%</th><th>期待値</th><th>全部現金</th></tr>`;
      checkpoints.forEach(c => {
        const t = c - 1, yr = sim.years[t];
        html += `<tr><td>${c}年後<br><span class="alloc-sub">${p.age + c}歳</span></td><td>${man(mc[t].p10)}</td><td>${man(mc[t].p50)}</td><td>${man(mc[t].p90)}</td>
          <td><b>${man(yr.endTotal)}</b></td><td>${man(cash[t])}</td></tr>`;
      });
      const last = sim.years[sim.years.length - 1];
      const invested = p.nisaBal + p.idecoBal + p.monthly * 12 * p.years;
      html += `</table></div>
        <div class="note">投資に回したお金（と既存のNISA・iDeCo残高）の合計額です。元本合計（実質）は約${man(invested)}。
        期待値は平均的なシナリオ、中央値は「半々の確率でこれより上/下」の値です。
        ${p.years}年後の内訳（期待値）: 現金 ${man(last.end[0])}・短期国債 ${man(last.end[1])}・長期国債 ${man(last.end[2])}・NISA ${man(last.end[3])}・iDeCo ${man(last.end[4])}（受取時課税前）。
        ${(p.age + p.years < IDECO_UNLOCK_AGE && last.end[4] > 0) ? '<b>うちiDeCo分はこの時点では引き出せません。</b>' : ''}</div></div>`;

      // 4. リスク許容度別の比較
      const levels = Array.from(new Set([0, 5, 10, 15, 20, 30, 40, Math.round(p.lossLimit)])).sort((a, b) => a - b);
      html += `<h2>④ リスク許容度ごとの比較</h2><div class="box"><div class="table-wrap"><table>
        <tr><th>許容損失</th><th>今年の株式比率</th><th>期待リターン</th><th>悪い年</th><th>${p.years}年後(期待値)</th></tr>`;
      levels.forEach(lv => {
        const s = lv === Math.round(p.lossLimit) && lv === p.lossLimit ? sim : simulate(p, stats, lv);
        const a = s.years[0];
        const cur = lv === Math.round(p.lossLimit) ? ' class="current"' : '';
        html += `<tr${cur}><td>${lv}%</td><td>${pctf(a.w[3] + a.w[4], 0)}</td><td>${signPct(a.mean)}</td>
          <td>${signPct(a.mean - Z * a.sd, 1)}</td><td>${man(s.years[s.years.length - 1].endTotal)}</td></tr>`;
      });
      html += `<tr><td>全部現金</td><td>0%</td><td>${signPct(cashReal)}</td><td>${signPct(cashReal, 1)}</td><td>${man(cash[cash.length - 1])}</td></tr>`;
      html += `</table></div><div class="note">リスクを取るほど期待値は上がりますが、悪い年の落ち込みも大きくなります。「この下落なら売らずに持ち続けられるか」で選ぶのがポイントです。</div></div>`;

      // 5. 年ごとの計画
      html += `<h2>⑤ 年ごとの配分計画（期待値ベース）</h2><div class="box"><details><summary>表を開く</summary><div class="table-wrap"><table>
        <tr><th>年</th><th>NISA</th><th>iDeCo</th><th>長期国債</th><th>短期国債</th><th>現金</th><th>株式比率</th></tr>`;
      sim.years.forEach(yr => {
        html += `<tr><td>${yr.y}年目</td><td>${man(Math.max(0, yr.flow[3]))}</td><td>${man(Math.max(0, yr.flow[4]))}</td>
          <td>${man(yr.newH[2])}</td><td>${man(yr.newH[1])}</td><td>${man(yr.newH[0])}</td><td>${pctf(yr.w[3] + yr.w[4], 0)}</td></tr>`;
      });
      html += `</table></div><div class="note">NISA・iDeCoは「その年に買い増す額」、国債・現金は「その年の保有額」です。</div></details></div>`;

      $('result').innerHTML = html;
    }

    // ---------------- イベント ----------------
    function syncRiskButtons() {
      const v = parseFloat($('lossLimit').value);
      document.querySelectorAll('.risk-btn').forEach(b => b.classList.toggle('active', parseFloat(b.dataset.loss) === v));
    }
    document.querySelectorAll('.risk-btn').forEach(btn => {
      btn.addEventListener('click', () => { $('lossLimit').value = btn.dataset.loss; syncRiskButtons(); render(); });
    });
    $('lossLimit').addEventListener('input', syncRiskButtons);
    $('calc-btn').addEventListener('click', render);
    $('reset-assump').addEventListener('click', () => { setDefaults('assump'); render(); });
    $('reset-all').addEventListener('click', () => {
      try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
      setDefaults('all'); syncRiskButtons(); render();
    });
    $('taxMode').addEventListener('change', render);
    $('spouse').addEventListener('change', render);
    $('useIdeco').addEventListener('change', render);
    $('useGrowth').addEventListener('change', render);

    const hints = [];
    if (MARKET.jgb2y) hints.push(`短期国債の初期値: 2年国債利回り ${MARKET.jgb2y.value}%（${MARKET.jgb2y.date}）`);
    if (MARKET.jgb10y) hints.push(`長期国債の初期値: 10年国債利回り ${MARKET.jgb10y.value}%（${MARKET.jgb10y.date}）`);
    hints.push('S&P500の期待リターン6%は、過去の長期平均(円建てで年7〜10%程度)より控えめに置いた値です。');
    $('assump-hint').textContent = hints.join(' / ');

    loadInputs();
    syncRiskButtons();
    render();

    // テスト用に公開
    window.__portfolioSim = { readParams, assetStats, simulate, optimize, monteCarlo, estimateTax };
  })();
  </script>
</body>
</html>
"""


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    assumptions, market = build_defaults()
    jgb_note_parts = []
    if market["jgb2y"]:
        jgb_note_parts.append(f"2年 {market['jgb2y']['value']}%")
    if market["jgb10y"]:
        jgb_note_parts.append(f"10年 {market['jgb10y']['value']}%（{market['jgb10y']['date']}時点）")
    jgb_note = "・".join(jgb_note_parts) if jgb_note_parts else "データ取得なし・固定の初期値"

    html = (
        HTML_TEMPLATE
        .replace("__UPDATED__", now)
        .replace("__JGB_NOTE__", jgb_note)
        .replace("__DEFAULT_ASSUMPTIONS__", json.dumps(assumptions, ensure_ascii=False))
        .replace("__DEFAULT_INPUTS__", json.dumps(DEFAULT_INPUTS, ensure_ascii=False))
        .replace("__MARKET__", json.dumps(market, ensure_ascii=False))
    )
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
