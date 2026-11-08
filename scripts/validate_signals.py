# -*- coding: utf-8 -*-
"""
今あるシグナルが「偶然と区別できる成績」を出しているかを、過去3年分のデータで検証し、
レポート(docs/validation.html, data/validation.json)を出力する。手動実行用。

検証するもの
1. スクリーニングのスコア(0〜7点) … 点数の高い銘柄ほど、その後よく上がっているか
2. スクリーニングの「初動」バッジ   … バッジが付いた銘柄は、その後よく上がっているか
3. 予測モデルの「買い候補シグナル」 … シグナルが出た日は、その後よく上がっているか
4. 決定木の「買いやすいパターン」   … 学習期間で選んだパターンが、その後の期間でも通用するか

見方
- 成績は「その後5営業日 / 20営業日の値上がり率」を、絶対値とTOPIX比(超過リターン)の両方で見る
- 相場全体(TOPIXが75日移動平均より上か下か)ごとにも分けて見る
- 「偶然か」は t値 で判断する(目安: |t| ≥ 2 なら偶然とは言いにくい)。
  同じ日の銘柄どうしは値動きが似ているので、日ごと(または銘柄ごと)にまとめてから t値 を計算する
- 予測モデルと決定木は、株価の並び順をシャッフルした「予測できるはずのないデータ」(プラセボ)でも
  同じ処理を行い、本物のデータでの成績がプラセボと比べて良いかを見る
"""
import os
import json
import math
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from build_sector_strength import despike, TOPIX_PROXY_TICKER
from indicators import sma, adx, obv, atr
from screen_stocks import (
    download_ohlcv, GC_LOOKBACK_DAYS, GC_APPROACH_PCT, EARLY_TREND_LOOKBACK,
    ADX_LOW_THRESHOLD, ADX_EARLY_MAX, TOP_N_SECTORS, SMALL_CAP_MIN_VOLATILITY,
)
from universe import add_size_class, LARGE_MID_CLASSES, SMALL_CLASS
from ml_predict import process_ticker, load_macro_series

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
MASTER_PATH = os.path.join(BASE_DIR, "data", "master.csv")
OUT_JSON = os.path.join(BASE_DIR, "data", "validation.json")
OUT_HTML = os.path.join(BASE_DIR, "docs", "validation.html")
JST = timezone(timedelta(hours=9))

LOOKBACK = "3y"
SAMPLE_STEP = 5          # 5営業日おきの日付で集計(5日後リターンが重ならないように)
ML_SAMPLE_SIZE = 80      # 予測モデルの検証に使う銘柄数(時間短縮のため無作為抽出)
SEED = 42
SCORE_BUCKETS = [(0, 2, "0〜2点未満"), (2, 4, "2〜4点未満"), (4, 6, "4〜6点未満"), (6, 7.01, "6〜7点")]
HIGH_SCORE = 5.0         # 「高スコア」とみなす基準


# ---------------------------------------------------------------------------
# 統計のヘルパー
# ---------------------------------------------------------------------------
def t_stat(values):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if len(v) < 3 or v.std(ddof=1) == 0:
        return None
    return float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v))))


def verdict(t, higher_is_better=True):
    if t is None:
        return "判定不能（データ不足）"
    if not higher_is_better:
        t = -t
    if t >= 2:
        return "効果あり（偶然とは言いにくい）"
    if t <= -2:
        return "逆効果（偶然とは言いにくい）"
    return "偶然と区別できない"


def r(x, d=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), d)


# ---------------------------------------------------------------------------
# 1〜2. スクリーニング(スコア・初動)の過去の毎日の値を再現する
# ---------------------------------------------------------------------------
def screening_history(df, small_cap):
    """screen_stocks.py の判定を、最新日だけでなく過去の全日について計算する"""
    cleaned = despike(df[["Close", "High", "Low"]])
    close, high, low = cleaned["Close"], cleaned["High"], cleaned["Low"]
    volume = df["Volume"].astype(float)

    ma25, ma75 = sma(close, 25), sma(close, 75)
    adx14, plus_di, minus_di = adx(high, low, close, 14)
    obv_s = obv(close, volume)
    atr14 = atr(high, low, close, 14)

    diff = ma25 - ma75
    cross_today = (diff.shift(1) < 0) & (diff >= 0)
    crossed_recent = cross_today.astype(float).rolling(GC_LOOKBACK_DAYS + 1, min_periods=1).max().astype(bool) & (diff >= 0)
    approach = (diff < 0) & ((diff.abs() / ma75.abs()) <= GC_APPROACH_PCT) & (diff > diff.shift(4))
    lb = 20
    price_chg = close - close.shift(lb - 1)
    obv_chg = obv_s - obv_s.shift(lb - 1)
    obv_conf = ((price_chg > 0) & (obv_chg > 0)) | ((price_chg < 0) & (obv_chg < 0))

    score = (
        (close > ma25).astype(float)
        + (ma25 > ma75).astype(float)
        + 2 * crossed_recent.astype(float) + 1 * approach.astype(float)
        + ((adx14 / 50.0).clip(upper=1.0) * 2).fillna(0)
        + obv_conf.astype(float)
    )
    past = adx14.shift(EARLY_TREND_LOOKBACK)
    early = (past < ADX_LOW_THRESHOLD) & (adx14 > past) & (adx14 <= ADX_EARLY_MAX) & (plus_di > minus_di)

    valid = ma75.notna() & adx14.notna()
    if small_cap:
        valid &= (atr14 / close) >= SMALL_CAP_MIN_VOLATILITY
    score = score.where(valid)
    early = early.where(valid)
    return close, score, early


def build_panel(ohlcv, master, topix_close):
    """日付×銘柄の表(サンプル日のみ)に、スコア・初動・その後のリターンなどをまとめる"""
    tclose = topix_close.dropna()
    t_fwd5 = tclose.shift(-5) / tclose - 1
    t_fwd20 = tclose.shift(-20) / tclose - 1
    regime_up = tclose >= sma(tclose, 75)
    t_r21 = tclose / tclose.shift(21) - 1

    dates = tclose.index[75:-20:SAMPLE_STEP]   # 指標の助走期間と、20日後が分からない末尾を除く
    info = master.set_index("ticker")

    closes, rows = {}, []
    for ticker, df in ohlcv.items():
        if ticker not in info.index or len(df) < 120:
            continue
        cls = info.at[ticker, "size_class"]
        close, score, early = screening_history(df, small_cap=(cls == SMALL_CLASS))
        closes[ticker] = close
        fwd5 = close.shift(-5) / close - 1
        fwd20 = close.shift(-20) / close - 1
        part = pd.DataFrame({
            "score": score, "early": early, "fwd5": fwd5, "fwd20": fwd20,
        }).reindex(dates)
        part["ticker"] = ticker
        part["sector"] = info.at[ticker, "sector33"]
        part["size_class"] = cls
        rows.append(part)
    panel = pd.concat(rows)
    panel.index.name = "date"
    panel = panel.reset_index()
    panel["ex5"] = panel["fwd5"] - panel["date"].map(t_fwd5)
    panel["ex20"] = panel["fwd20"] - panel["date"].map(t_fwd20)
    panel["regime_up"] = panel["date"].map(regime_up)

    # その日時点での「強いセクター」(中〜大型株の21日リターンのセクター平均 − TOPIX、上位15)
    lm = [t for t in closes if info.at[t, "size_class"] in LARGE_MID_CLASSES]
    r21 = pd.DataFrame({t: closes[t] / closes[t].shift(21) - 1 for t in lm}).reindex(dates)
    sectors = info.loc[lm, "sector33"]
    sec_rel = r21.T.groupby(sectors).mean().T.sub(t_r21.reindex(dates), axis=0)
    strong = {d: set(sec_rel.loc[d].dropna().sort_values(ascending=False).head(TOP_N_SECTORS).index) for d in dates}
    panel["strong_sector"] = [s in strong.get(d, set()) for d, s in zip(panel["date"], panel["sector"])]
    return panel.dropna(subset=["score", "fwd5"])


def group_stats(sub, col):
    return {"n": int(sub[col].notna().sum()), "mean": r(sub[col].mean()), "hit_rate": r((sub[col] > 0).mean(), 3)}


def diff_by_date(panel, mask, col, step=1):
    """日ごとに「条件に当てはまる銘柄の平均 − その日の全銘柄の平均」を出し、日をまたいだ t値 を返す"""
    dates = sorted(panel["date"].unique())[::step]
    diffs = []
    for d in dates:
        day = panel[panel["date"] == d]
        sel = day[mask.loc[day.index]]
        if len(sel) == 0 or day[col].notna().sum() == 0:
            continue
        diffs.append(sel[col].mean() - day[col].mean())
    return {"mean_diff": r(np.mean(diffs)) if diffs else None, "t": r(t_stat(diffs), 2), "n_dates": len(diffs)}


def rank_ic(panel, col, step=1):
    """日ごとの「スコアの順位」と「その後のリターンの順位」の相関(情報係数, IC)の平均と t値"""
    dates = sorted(panel["date"].unique())[::step]
    ics = []
    for d in dates:
        day = panel[panel["date"] == d][["score", col]].dropna()
        if len(day) >= 20 and day["score"].nunique() > 1:
            ics.append(day["score"].rank().corr(day[col].rank()))
    return {"mean_ic": r(np.mean(ics)) if ics else None, "t": r(t_stat(ics), 2), "n_dates": len(ics)}


def evaluate_screening(panel):
    out = {"n_rows": int(len(panel)), "n_dates": int(panel["date"].nunique()), "n_tickers": int(panel["ticker"].nunique())}
    # 20日後リターンは、20日おき(=サンプル日4つおき)にして重なりを避ける
    step20 = 20 // SAMPLE_STEP

    out["ic"] = {
        "ex5": rank_ic(panel, "ex5"),
        "ex20": rank_ic(panel, "ex20", step=step20),
        "fwd5": rank_ic(panel, "fwd5"),
    }
    buckets = []
    for lo, hi, label in SCORE_BUCKETS:
        sub = panel[(panel["score"] >= lo) & (panel["score"] < hi)]
        buckets.append({"label": label, "fwd5": group_stats(sub, "fwd5"), "ex5": group_stats(sub, "ex5"), "ex20": group_stats(sub, "ex20")})
    out["buckets"] = buckets

    high = panel["score"] >= HIGH_SCORE
    screen_view = high & panel["strong_sector"]     # 画面の既定表示(強いセクター内の高スコア)に近い条件
    early = panel["early"] == True  # noqa: E712
    out["conditions"] = {}
    for key, mask, label in [
        ("high_score", high, f"スコア{HIGH_SCORE:g}点以上"),
        ("screen_view", screen_view, f"強いセクター内でスコア{HIGH_SCORE:g}点以上"),
        ("early", early, "「初動」バッジあり"),
    ]:
        res = {"label": label}
        for regime_key, regime_mask in [("all", pd.Series(True, index=panel.index)),
                                        ("up", panel["regime_up"] == True),     # noqa: E712
                                        ("down", panel["regime_up"] == False)]:  # noqa: E712
            sub = panel[mask & regime_mask]
            res[regime_key] = {
                "count": int(len(sub)),
                "fwd5": group_stats(sub, "fwd5"),
                "ex5_vs_all": diff_by_date(panel[regime_mask], mask[regime_mask], "ex5"),
                "ex20_vs_all": diff_by_date(panel[regime_mask], mask[regime_mask], "ex20", step=step20),
            }
        out["conditions"][key] = res

    # 相場全体の状態ごとの、全銘柄平均(比較の土台)
    out["market"] = {
        "up": group_stats(panel[panel["regime_up"] == True], "fwd5"),     # noqa: E712
        "down": group_stats(panel[panel["regime_up"] == False], "fwd5"),  # noqa: E712
    }
    return out


# ---------------------------------------------------------------------------
# 3〜4. 予測モデル・決定木パターン(本物 vs プラセボ)
# ---------------------------------------------------------------------------
def placebo(df, perm):
    """
    日々の値動きの順番をシャッフルした株価を作る(値動きの大きさの分布は同じだが、予測できる要素はない)。
    全銘柄とTOPIXに同じ並べ替え(perm)を使うことで、「相場全体と一緒に動く」性質は残す。
    (銘柄ごとに別々にシャッフルすると相場全体の動きが消え、本物との比較が不公平になるため)
    """
    close = df["Close"].astype(float)
    ret = np.log(close).diff().dropna().values
    new_close = close.iloc[0] * np.exp(np.concatenate([[0.0], np.cumsum(ret[perm])]))
    hi_ratio = (df["High"] / df["Close"]).values[1:][perm]
    lo_ratio = (df["Low"] / df["Close"]).values[1:][perm]
    vol = df["Volume"].values[1:][perm]
    out = pd.DataFrame(index=df.index)
    out["Close"] = new_close
    out["Open"] = new_close
    out["High"] = new_close * np.concatenate([[1.0], hi_ratio])
    out["Low"] = new_close * np.concatenate([[1.0], lo_ratio])
    out["Volume"] = np.concatenate([[df["Volume"].values[0]], vol])
    return out


def tree_rule_edge(d, fwd5, ex5):
    """学習期間で「上昇的中率が一番高いパターン」を選び、テスト期間でそのパターンに当てはまった日の成績を見る"""
    X_train, y_train, X_test, y_test = d["X_train"], d["y_train"], d["X_test"], d["y_test"]
    min_leaf = max(int(len(X_train) * 0.05), 5)
    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=min_leaf, random_state=42).fit(X_train, y_train)
    train_leaf = tree.apply(X_train)
    leaves = pd.Series(np.asarray(y_train)).groupby(train_leaf).agg(["mean", "size"])
    leaves = leaves[leaves["size"] >= min_leaf]
    if leaves.empty:
        return None
    best = leaves["mean"].idxmax()
    mask = tree.apply(X_test) == best
    f = fwd5.reindex(X_test.index).values
    res = {"train_precision": float(leaves.loc[best, "mean"]), "test_n": int(mask.sum()),
           "test_precision": float(np.asarray(y_test)[mask].mean()) if mask.sum() else None,
           "base_rate": float(np.mean(y_test))}
    ex = ex5.reindex(X_test.index).values
    res["edge"] = float(np.nanmean(f[mask]) - np.nanmean(f)) if mask.sum() else None
    res["edge_ex"] = float(np.nanmean(ex[mask]) - np.nanmean(ex)) if mask.sum() else None
    return res


def run_ml(ohlcv_sample, macro, topix_close, label):
    """
    各銘柄で予測モデルを動かし、テスト期間の成績を集める。
    判定には「TOPIX比」(edge5_ex)を使う。絶対リターン(edge5)は、シグナルが同じ日に固まると
    相場全体の上げ下げだけで差が出てしまい、偶然でも有意に見えやすいため参考値とする。
    """
    t_fwd5 = topix_close.shift(-5) / topix_close - 1
    per_stock = []
    for ticker, df in ohlcv_sample.items():
        try:
            res = process_ticker(df, macro, details=True)
        except Exception as e:
            print(f"[{label}] {ticker}: {e}")
            continue
        if res.get("status") != "ok":
            continue
        d = res["_details"]
        close = d["close"]
        fwd5 = close.shift(-5) / close - 1
        idx = d["test_index"]
        f = fwd5.reindex(idx).values
        ex = f - t_fwd5.reindex(idx).values
        sig = d["test_probs"] >= d["threshold"]
        m = res["metrics"]
        bt = res.get("backtest") or {}
        item = {
            "ticker": ticker,
            "precision_minus_base": (m["precision"] - m["base_rate"]) if m["n_signals"] > 0 else None,
            "n_signals": int(sig.sum()),
            "edge5": float(np.nanmean(f[sig]) - np.nanmean(f)) if sig.sum() else None,
            "edge5_ex": float(np.nanmean(ex[sig]) - np.nanmean(ex)) if sig.sum() else None,
            "bt_minus_hold": (bt["total_return"] - bt["buy_and_hold_return"])
                             if bt.get("buy_and_hold_return") is not None else None,
            "tree": tree_rule_edge(d, fwd5, fwd5 - t_fwd5.reindex(fwd5.index)),
        }
        per_stock.append(item)
    return per_stock


def summarize_ml(items):
    def col(key):
        return [x[key] for x in items if x.get(key) is not None]
    tree = [x["tree"] for x in items if x.get("tree")]
    tree_edges = [t["edge"] for t in tree if t.get("edge") is not None]
    tree_edges_ex = [t["edge_ex"] for t in tree if t.get("edge_ex") is not None]
    tree_gap = [t["test_precision"] - t["train_precision"] for t in tree if t.get("test_precision") is not None]
    pmb = col("precision_minus_base")
    return {
        "n_stocks": len(items),
        "share_signal_stocks": r(np.mean([x["n_signals"] > 0 for x in items]), 3) if items else None,
        "share_precision_above_base": r(np.mean([v > 0 for v in pmb]), 3) if pmb else None,
        "precision_minus_base": {"mean": r(np.mean(pmb)) if pmb else None, "t": r(t_stat(pmb), 2)},
        "edge5": {"mean": r(np.mean(col("edge5"))) if col("edge5") else None, "t": r(t_stat(col("edge5")), 2), "n": len(col("edge5"))},
        "edge5_ex": {"mean": r(np.mean(col("edge5_ex"))) if col("edge5_ex") else None, "t": r(t_stat(col("edge5_ex")), 2)},
        "bt_minus_hold": {"mean": r(np.mean(col("bt_minus_hold"))) if col("bt_minus_hold") else None,
                          "t": r(t_stat(col("bt_minus_hold")), 2), "n": len(col("bt_minus_hold"))},
        "tree": {
            "n": len(tree),
            "train_precision": r(np.mean([t["train_precision"] for t in tree])) if tree else None,
            "test_precision": r(np.mean([t["test_precision"] for t in tree if t["test_precision"] is not None])) if tree_gap else None,
            "base_rate": r(np.mean([t["base_rate"] for t in tree])) if tree else None,
            "precision_drop": {"mean": r(np.mean(tree_gap)) if tree_gap else None, "t": r(t_stat(tree_gap), 2)},
            "edge5": {"mean": r(np.mean(tree_edges)) if tree_edges else None, "t": r(t_stat(tree_edges), 2), "n": len(tree_edges)},
            "edge5_ex": {"mean": r(np.mean(tree_edges_ex)) if tree_edges_ex else None, "t": r(t_stat(tree_edges_ex), 2), "n": len(tree_edges_ex)},
            "no_match_share": r(np.mean([t["test_n"] == 0 for t in tree]), 3) if tree else None,
        },
    }


# ---------------------------------------------------------------------------
# レポート
# ---------------------------------------------------------------------------
def pct(x, d=2, sign=True):
    if x is None:
        return "-"
    return f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


def tval(t):
    return "-" if t is None else f"{t:+.2f}"


def render_html(result):
    sc = result["screening"]
    ml_real, ml_pl = result["ml"]["real"], result["ml"]["placebo"]
    cond = sc["conditions"]

    def cond_rows(key):
        c = cond[key]
        rows = ""
        for rk, rl in [("all", "全期間"), ("up", "上昇相場"), ("down", "下落相場")]:
            x = c[rk]
            rows += (f"<tr><td>{rl}</td><td>{x['count']}</td><td>{pct(x['fwd5']['mean'])}</td>"
                     f"<td>{pct(x['ex5_vs_all']['mean_diff'])}<br><span class='t'>t={tval(x['ex5_vs_all']['t'])}</span></td>"
                     f"<td>{pct(x['ex20_vs_all']['mean_diff'])}<br><span class='t'>t={tval(x['ex20_vs_all']['t'])}</span></td></tr>")
        return rows

    bucket_rows = "".join(
        f"<tr><td>{b['label']}</td><td>{b['fwd5']['n']}</td><td>{pct(b['fwd5']['mean'])}</td>"
        f"<td>{pct(b['ex5']['mean'])}</td><td>{pct(b['ex20']['mean'])}</td></tr>" for b in sc["buckets"])

    def ml_row(label, key, sub=None, fmt=pct):
        a = ml_real[key] if sub is None else ml_real[key][sub]
        b = ml_pl[key] if sub is None else ml_pl[key][sub]
        if isinstance(a, dict):
            return (f"<tr><td>{label}</td><td>{fmt(a['mean'])}<br><span class='t'>t={tval(a['t'])}</span></td>"
                    f"<td>{fmt(b['mean'])}<br><span class='t'>t={tval(b['t'])}</span></td></tr>")
        return f"<tr><td>{label}</td><td>{fmt(a)}</td><td>{fmt(b)}</td></tr>"

    v = result["verdicts"]
    verdict_rows = "".join(f"<tr><td>{x['name']}</td><td><b>{x['verdict']}</b><br><span class='t'>{x['basis']}</span></td></tr>" for x in v)

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>シグナル検証レポート</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", sans-serif; margin: 0; padding: 16px; background: #0f1115; color: #e8e8e8; }}
  h1 {{ font-size: 1.2rem; margin: 0 0 4px; }} h2 {{ font-size: 1rem; margin: 22px 0 8px; }}
  .updated, .note {{ font-size: 0.72rem; color: #999; line-height: 1.6; }}
  .box {{ background: #171a20; border-radius: 10px; padding: 12px; margin-bottom: 12px; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.72rem; }}
  th, td {{ padding: 6px 5px; border-bottom: 1px solid #23262e; text-align: right; vertical-align: top; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ color: #999; font-weight: 600; }}
  .t {{ color: #888; font-size: 0.66rem; }}
  a {{ color: #6ab7ff; }}
</style></head><body>
<a href="index.html">← ダッシュボードへ</a>
<h1>シグナル検証レポート</h1>
<div class="updated">作成: {result['generated_at']} / 期間: {result['period']['start']}〜{result['period']['end']} / 対象 {sc['n_tickers']}銘柄</div>

<h2>結論</h2>
<div class="box"><div class="table-wrap"><table><tr><th>シグナル</th><th>判定</th></tr>{verdict_rows}</table></div>
<div class="note">t値は「偶然でもこのくらいの差は出るか」の目安です。|t|が2以上なら偶然とは言いにくく、2未満なら偶然と区別できません。超過リターンはTOPIX(1306)比です。</div></div>

<h2>① スクリーニングのスコア</h2>
<div class="box">
<div class="note">スコアの順位と、その後のリターンの順位の相関（情報係数・IC）。0なら無関係、プラスなら高スコアほど上がりやすい。実務では0.02〜0.05でも有用とされます。</div>
<div class="table-wrap"><table><tr><th>対象</th><th>平均IC</th><th>t値</th><th>日数</th></tr>
<tr><td>5日後・TOPIX比</td><td>{r(sc['ic']['ex5']['mean_ic'], 3)}</td><td>{tval(sc['ic']['ex5']['t'])}</td><td>{sc['ic']['ex5']['n_dates']}</td></tr>
<tr><td>20日後・TOPIX比</td><td>{r(sc['ic']['ex20']['mean_ic'], 3)}</td><td>{tval(sc['ic']['ex20']['t'])}</td><td>{sc['ic']['ex20']['n_dates']}</td></tr>
<tr><td>5日後・絶対</td><td>{r(sc['ic']['fwd5']['mean_ic'], 3)}</td><td>{tval(sc['ic']['fwd5']['t'])}</td><td>{sc['ic']['fwd5']['n_dates']}</td></tr>
</table></div>
<h2 style="font-size:0.9rem;">点数帯ごとの平均リターン</h2>
<div class="table-wrap"><table><tr><th>スコア</th><th>件数</th><th>5日後</th><th>5日後TOPIX比</th><th>20日後TOPIX比</th></tr>{bucket_rows}</table></div>
</div>

<h2>② 条件ごとの成績（その日の全銘柄平均との差）</h2>
<div class="box">
<div class="note">上昇相場＝TOPIXが75日移動平均より上の日、下落相場＝下の日。比較の土台として、全銘柄の5日後平均は 上昇相場 {pct(sc['market']['up']['mean'])}・下落相場 {pct(sc['market']['down']['mean'])}。</div>
<h2 style="font-size:0.9rem;">{cond['high_score']['label']}</h2>
<div class="table-wrap"><table><tr><th>相場</th><th>件数</th><th>5日後(絶対)</th><th>5日後 差</th><th>20日後 差</th></tr>{cond_rows('high_score')}</table></div>
<h2 style="font-size:0.9rem;">{cond['screen_view']['label']}（画面の既定表示に近い条件）</h2>
<div class="table-wrap"><table><tr><th>相場</th><th>件数</th><th>5日後(絶対)</th><th>5日後 差</th><th>20日後 差</th></tr>{cond_rows('screen_view')}</table></div>
<h2 style="font-size:0.9rem;">{cond['early']['label']}</h2>
<div class="table-wrap"><table><tr><th>相場</th><th>件数</th><th>5日後(絶対)</th><th>5日後 差</th><th>20日後 差</th></tr>{cond_rows('early')}</table></div>
</div>

<h2>③④ 予測モデル・決定木パターン（本物 vs プラセボ）</h2>
<div class="box">
<div class="note">無作為に選んだ{ml_real['n_stocks']}銘柄で、現在の予測モデルをそのまま動かし、テスト期間（学習に使っていない直近120営業日）の成績を見ています。
プラセボは、同じ銘柄の日々の値動きの順番をシャッフルした「予測できるはずのない株価」です。本物がプラセボより明確に良くなければ、成績は偶然の範囲です。t値は銘柄をまたいで計算しています。</div>
<div class="table-wrap"><table><tr><th>項目</th><th>本物</th><th>プラセボ</th></tr>
{ml_row('シグナルが出た銘柄の割合', 'share_signal_stocks', fmt=lambda x: pct(x, 0, False))}
{ml_row('Precisionが「毎日買う」を上回った割合', 'share_precision_above_base', fmt=lambda x: pct(x, 0, False))}
{ml_row('Precision − 毎日買った場合', 'precision_minus_base')}
{ml_row('シグナル日の5日後リターン − 全日平均（参考）', 'edge5')}
{ml_row('同上（TOPIX比）※判定に使用', 'edge5_ex')}
{ml_row('売買ルールの成績 − 持ち続けた場合', 'bt_minus_hold')}
</table></div>
<h2 style="font-size:0.9rem;">決定木の「買いやすいパターン」に当てはまったら買う場合</h2>
<div class="table-wrap"><table><tr><th>項目</th><th>本物</th><th>プラセボ</th></tr>
<tr><td>学習期間での上昇的中率</td><td>{pct(ml_real['tree']['train_precision'], 1, False)}</td><td>{pct(ml_pl['tree']['train_precision'], 1, False)}</td></tr>
<tr><td>テスト期間での上昇的中率</td><td>{pct(ml_real['tree']['test_precision'], 1, False)}</td><td>{pct(ml_pl['tree']['test_precision'], 1, False)}</td></tr>
<tr><td>（参考）テスト期間に毎日買った場合</td><td>{pct(ml_real['tree']['base_rate'], 1, False)}</td><td>{pct(ml_pl['tree']['base_rate'], 1, False)}</td></tr>
<tr><td>パターン該当日の5日後リターン − 全日平均</td><td>{pct(ml_real['tree']['edge5']['mean'])}<br><span class='t'>t={tval(ml_real['tree']['edge5']['t'])}</span></td><td>{pct(ml_pl['tree']['edge5']['mean'])}<br><span class='t'>t={tval(ml_pl['tree']['edge5']['t'])}</span></td></tr>
<tr><td>同上（TOPIX比）</td><td>{pct(ml_real['tree']['edge5_ex']['mean'])}<br><span class='t'>t={tval(ml_real['tree']['edge5_ex']['t'])}</span></td><td>{pct(ml_pl['tree']['edge5_ex']['mean'])}<br><span class='t'>t={tval(ml_pl['tree']['edge5_ex']['t'])}</span></td></tr>
<tr><td>テスト期間に該当日がなかった銘柄</td><td>{pct(ml_real['tree']['no_match_share'], 0, False)}</td><td>{pct(ml_pl['tree']['no_match_share'], 0, False)}</td></tr>
</table></div>
<div class="note">学習期間の的中率とテスト期間の的中率の差が大きいほど、パターンは「過去にたまたま当たっていただけ」ということになります。</div>
</div>
</body></html>"""


def build_verdicts(sc, ml_real, ml_pl):
    v = []
    ic = sc["ic"]["ex20"]
    v.append({"name": "スクリーニングのスコア（20日後・TOPIX比）", "verdict": verdict(ic["t"]),
              "basis": f"平均IC {r(ic['mean_ic'], 3)}、t={tval(ic['t'])}"})
    for key, name in [("screen_view", "画面の既定表示（強いセクター×高スコア）"), ("early", "「初動」バッジ")]:
        x = sc["conditions"][key]["all"]["ex20_vs_all"]
        v.append({"name": f"{name}（20日後・全銘柄平均との差）", "verdict": verdict(x["t"]),
                  "basis": f"差 {pct(x['mean_diff'])}、t={tval(x['t'])}"})
    e = ml_real["edge5_ex"]
    v.append({"name": "予測モデルの買い候補シグナル（5日後・TOPIX比）", "verdict": verdict(e["t"]),
              "basis": f"差 {pct(e['mean'])}、t={tval(e['t'])}（プラセボ {pct(ml_pl['edge5_ex']['mean'])}、t={tval(ml_pl['edge5_ex']['t'])}）"})
    t = ml_real["tree"]["edge5_ex"]
    v.append({"name": "決定木の買いやすいパターン（5日後・TOPIX比）", "verdict": verdict(t["t"]),
              "basis": f"差 {pct(t['mean'])}、t={tval(t['t'])}（{t['n']}銘柄）／的中率 学習{pct(ml_real['tree']['train_precision'], 0, False)}→テスト{pct(ml_real['tree']['test_precision'], 0, False)}"
                       f"／テスト期間に該当日がなかった銘柄 {pct(ml_real['tree']['no_match_share'], 0, False)}"})
    return v


def main():
    master = add_size_class(pd.read_csv(MASTER_PATH, dtype=str))
    master = master[master["size_class"].isin(LARGE_MID_CLASSES + (SMALL_CLASS,))]
    tickers = master["ticker"].tolist()
    print(f"対象銘柄: {len(tickers)}  期間: {LOOKBACK}")

    ohlcv = download_ohlcv(tickers + [TOPIX_PROXY_TICKER], period=LOOKBACK)
    if TOPIX_PROXY_TICKER not in ohlcv:
        raise RuntimeError("TOPIX代理ETF(1306.T)の価格が取得できませんでした")
    topix_close = despike(ohlcv.pop(TOPIX_PROXY_TICKER)[["Close"]])["Close"]
    print(f"取得できた銘柄: {len(ohlcv)}")

    # 1〜2. スクリーニング
    panel = build_panel(ohlcv, master, topix_close)
    screening = evaluate_screening(panel)
    print("スクリーニング検証 完了")

    # 3〜4. 予測モデル(中〜大型株から無作為抽出)
    rng = np.random.default_rng(SEED)
    tidx = topix_close.index
    # プラセボで全銘柄に同じ並べ替えを使うため、TOPIXとほぼ同じ期間のデータがある銘柄だけを使う
    lm = [t for t in master[master["size_class"].isin(LARGE_MID_CLASSES)]["ticker"]
          if t in ohlcv and ohlcv[t].reindex(tidx)["Close"].notna().mean() >= 0.98]
    sample = list(rng.choice(lm, size=min(ML_SAMPLE_SIZE, len(lm)), replace=False))
    aligned = {t: ohlcv[t].reindex(tidx).ffill().bfill() for t in sample}
    macro = load_macro_series()
    real_items = run_ml(aligned, macro, topix_close, "real")

    perm = rng.permutation(len(tidx) - 1)
    topix_df = pd.DataFrame({"Close": topix_close, "High": topix_close, "Low": topix_close, "Volume": 1.0})
    topix_placebo = placebo(topix_df, perm)["Close"]
    placebo_items = run_ml({t: placebo(aligned[t], perm) for t in sample}, macro, topix_placebo, "placebo")
    ml = {"real": summarize_ml(real_items), "placebo": summarize_ml(placebo_items)}
    print("予測モデル検証 完了")

    result = {
        "generated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "period": {"start": str(topix_close.index[0].date()), "end": str(topix_close.index[-1].date())},
        "screening": screening,
        "ml": ml,
    }
    result["verdicts"] = build_verdicts(screening, ml["real"], ml["placebo"])

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(render_html(result))
    print(f"Saved -> {OUT_JSON}, {OUT_HTML}")
    for x in result["verdicts"]:
        print(f"- {x['name']}: {x['verdict']} ({x['basis']})")


if __name__ == "__main__":
    main()
