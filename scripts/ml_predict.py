# -*- coding: utf-8 -*-
"""
docs/timeseries/<コード>.json (既に計算済みの指標データ)を使って、
銘柄ごとに「5営業日後に+2%以上上昇するか」を予測するモデル(LightGBM+ロジスティック回帰の
アンサンブル)を学習し、予測確率・評価指標・特徴量重要度・売買パターン・
最適な売買閾値バックテスト結果を docs/predictions/<コード>.json に出力する。

対象銘柄: data/screening_all.json に含まれる全銘柄
(=毎日のスクリーニングで指標計算済みの範囲。全銘柄を毎回yfinanceから
再取得するのではなく、既存のtimeseries.jsonを再利用するため比較的軽量)
"""
import os
import json
import time
import warnings

import pandas as pd
import yfinance as yf

from ml_features import build_features_from_timeseries, build_target
from ml_models import (
    time_series_split, train_ensemble, predict_ensemble, evaluate,
    get_feature_importance, extract_high_confidence_rules, backtest_thresholds,
    TEST_SIZE_DAYS, MIN_TRAIN_ROWS, HAS_LIGHTGBM,
)

warnings.filterwarnings("ignore")

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
SCREENING_PATH = os.path.join(BASE_DIR, "data", "screening_all.json")
TIMESERIES_DIR = os.path.join(BASE_DIR, "docs", "timeseries")
PREDICTIONS_DIR = os.path.join(BASE_DIR, "docs", "predictions")
OVERSEAS_PATH = os.path.join(BASE_DIR, "data", "overseas.json")
COMMODITIES_PATH = os.path.join(BASE_DIR, "data", "commodities.json")
CGPI_PATH = os.path.join(BASE_DIR, "data", "cgpi.json")
JGB_PATH = os.path.join(BASE_DIR, "data", "jgb_yields.json")

HORIZON_DAYS = 5
UP_THRESHOLD = 0.02

FUNDAMENTAL_FIELDS = {
    "per": "trailingPE",
    "pbr": "priceToBook",
    "dividend_yield": "dividendYield",
}


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_macro_series():
    """為替・原油・企業物価指数を日次Seriesに揃えて読み込む(欠けていれば無視して続行)"""
    macro = {}

    overseas = load_json(OVERSEAS_PATH) or {}
    if "米ドル/円" in overseas:
        s = overseas["米ドル/円"]
        macro["usdjpy"] = pd.Series(s["values"], index=pd.to_datetime(s["dates"]))

    commodities = load_json(COMMODITIES_PATH) or {}
    if "原油(WTI)" in commodities:
        s = commodities["原油(WTI)"]
        macro["oil"] = pd.Series(s["values"], index=pd.to_datetime(s["dates"]))

    cgpi = load_json(CGPI_PATH) or {}
    if "国内企業物価指数(総平均)" in cgpi:
        s = cgpi["国内企業物価指数(総平均)"]
        # 月次(YYYY-MM)なので、月初日付にしてから日次にreindex+ffillできるようにする
        idx = pd.to_datetime([f"{d}-01" for d in s["dates"]])
        macro["cgpi"] = pd.Series(s["values"], index=idx)

    jgb = load_json(JGB_PATH) or {}
    jgb_key_map = {"短期(2年)": "jgb_2y", "中期(5年)": "jgb_5y", "長期(10年)": "jgb_10y"}
    for label, key in jgb_key_map.items():
        if label in jgb:
            s = jgb[label]
            macro[key] = pd.Series(s["values"], index=pd.to_datetime(s["dates"]))

    return macro


def fetch_fundamentals(ticker):
    """yfinanceから現在のPER/PBR/配当利回りを取得する(失敗しても空dictで継続)"""
    result = {}
    try:
        info = yf.Ticker(ticker).info
        for key, yf_key in FUNDAMENTAL_FIELDS.items():
            val = info.get(yf_key)
            if val is not None:
                result[key] = float(val)
    except Exception as e:
        print(f"[warn] {ticker}: ファンダメンタル取得失敗 ({e})")
    return result


def process_ticker(ticker, macro, fundamentals):
    ts_path = os.path.join(TIMESERIES_DIR, f"{ticker.replace('.T', '')}.json")
    ts = load_json(ts_path)
    if ts is None:
        return None

    features, close = build_features_from_timeseries(ts, macro=macro, fundamentals=fundamentals)
    target = build_target(close, horizon=HORIZON_DAYS, threshold=UP_THRESHOLD)

    data = features.copy()
    data["target"] = target
    data_full = data.dropna(subset=[c for c in data.columns if c != "target"])  # 特徴量が揃っている行
    data_labeled = data_full.dropna(subset=["target"])  # さらに目的変数がわかる行(学習・評価用)

    if len(data_labeled) < MIN_TRAIN_ROWS + TEST_SIZE_DAYS:
        return {"status": "insufficient_data", "n_rows": len(data_labeled)}

    X_labeled = data_labeled.drop(columns=["target"])
    y_labeled = data_labeled["target"].astype(int)

    X_train, X_test, y_train, y_test = time_series_split(X_labeled, y_labeled, test_size=TEST_SIZE_DAYS)

    models = train_ensemble(X_train, y_train)
    test_probs = predict_ensemble(models, X_test)
    test_pred = (test_probs >= models["threshold"]).astype(int)
    metrics = evaluate(y_test, test_pred)

    importance = get_feature_importance(
        models["gbm"], list(X_labeled.columns), X_val=models["X_val"], y_val=models["y_val"]
    )

    best_buy, best_sell = extract_high_confidence_rules(X_labeled, y_labeled)

    bt = backtest_thresholds(X_test.index, test_probs, close)

    # 最新時点(特徴量が揃っている最終行)での予測
    latest_row = data_full.drop(columns=["target"]).iloc[[-1]]
    latest_prob = float(predict_ensemble(models, latest_row)[0])

    return {
        "status": "ok",
        "generated_at_row_date": str(data_full.index[-1].date()),
        "horizon_days": HORIZON_DAYS,
        "up_threshold": UP_THRESHOLD,
        "latest_prob_up": round(latest_prob, 3),
        "decision_threshold": round(models["threshold"], 3),
        "signal": "buy_candidate" if latest_prob >= models["threshold"] else "no_signal",
        "metrics": metrics,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "model_used": "lightgbm+logistic" if HAS_LIGHTGBM else "histgbm(fallback)+logistic",
        "feature_importance": importance,
        "buy_rule": best_buy,
        "sell_rule": best_sell,
        "backtest": bt,
    }


def main():
    screening = load_json(SCREENING_PATH)
    if not screening:
        raise RuntimeError("data/screening_all.json が見つかりません。先にscreen_stocks.pyを実行してください。")

    tickers = [s["ticker"] for s in screening["stocks"]]
    print(f"対象銘柄数: {len(tickers)}")

    macro = load_macro_series()
    print(f"マクロ特徴量: {list(macro.keys())}")

    os.makedirs(PREDICTIONS_DIR, exist_ok=True)

    n_ok, n_skip, n_error = 0, 0, 0
    for i, ticker in enumerate(tickers):
        try:
            fundamentals = fetch_fundamentals(ticker)
            result = process_ticker(ticker, macro, fundamentals)
            if result is None:
                n_skip += 1
                continue
            if result.get("status") != "ok":
                n_skip += 1
                continue

            out_path = os.path.join(PREDICTIONS_DIR, f"{ticker.replace('.T', '')}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            n_ok += 1

            if (i + 1) % 25 == 0:
                print(f"進捗: {i + 1}/{len(tickers)} (成功{n_ok}件)")
        except Exception as e:
            n_error += 1
            print(f"[error] {ticker}: {e}")

        time.sleep(0.2)  # yfinanceのfundamentals取得に対するレート制限対策

    print(f"完了: 成功{n_ok}件 / スキップ{n_skip}件 / エラー{n_error}件")


if __name__ == "__main__":
    main()
