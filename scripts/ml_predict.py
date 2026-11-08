# -*- coding: utf-8 -*-
"""
銘柄ごとに「5営業日後に+2%以上上昇するか」を予測するモデル(LightGBM+ロジスティック回帰の
アンサンブル)を学習し、予測確率・評価指標・特徴量重要度・売買パターン・
売買閾値バックテスト結果を docs/predictions/<コード>.json に出力する。

対象銘柄: data/screening_all.json に含まれる全銘柄。
学習データを確保するため、株価は過去3年分をここで取得する
(画面表示用の docs/timeseries は1年分のまま)。

成績が実際より良く見えないように:
- 期間を「学習 → 検証(閾値・売買ルールの決定) → テスト(最終評価)」に分け、テストは何にも使わない
- 期間の境目は予測期間(5営業日)ぶん空ける
- マクロ指標は大引け後に確定するため1営業日ずらし、公表が遅れる企業物価指数は公表時期に合わせる
- 売買の成績は売買コストを差し引く
"""
import os
import json
import warnings

import pandas as pd

from build_sector_strength import despike
from ml_features import build_features, build_target
from ml_models import (
    time_series_split, train_ensemble, predict_ensemble, evaluate,
    get_feature_importance, extract_high_confidence_rules, backtest_thresholds,
    TEST_SIZE_DAYS, VALIDATION_SIZE_DAYS, MIN_TRAIN_ROWS, GAP_DAYS, HAS_LIGHTGBM,
)
from screen_stocks import download_ohlcv

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
PRICE_LOOKBACK = "3y"        # 学習用の株価取得期間
MACRO_MAX_MISSING = 0.10     # マクロ指標の欠損がこの割合を超える銘柄では、その指標を使わない


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
        # 月次(YYYY-MM)。企業物価指数は翌月の中旬に公表されるため、
        # 「翌月20日から使える値」として日付を付ける(その月の初日から分かっていた扱いにしない)
        idx = pd.to_datetime([f"{d}-01" for d in s["dates"]]) + pd.DateOffset(months=1, days=19)
        macro["cgpi"] = pd.Series(s["values"], index=idx)

    jgb = load_json(JGB_PATH) or {}
    jgb_key_map = {"短期(2年)": "jgb_2y", "中期(5年)": "jgb_5y", "長期(10年)": "jgb_10y"}
    for label, key in jgb_key_map.items():
        if label in jgb:
            s = jgb[label]
            macro[key] = pd.Series(s["values"], index=pd.to_datetime(s["dates"]))

    return macro


def process_ticker(ohlcv, macro, details=False):
    """
    details=True のときは、検証用(validate_signals.py)にテスト期間の予測確率などを
    "_details" に入れて返し、最新予測用の再学習は省く。
    """
    cleaned = despike(ohlcv[["Close", "High", "Low"]])
    close, high, low = cleaned["Close"], cleaned["High"], cleaned["Low"]
    volume = ohlcv["Volume"].astype("float64")

    features = build_features(close, high, low, volume, macro=macro)
    target = build_target(close, horizon=HORIZON_DAYS, threshold=UP_THRESHOLD)

    # 指標の計算に必要な助走期間(MA75など)を除いたうえで、欠損の多いマクロ指標は外す
    warm = features.dropna(subset=[c for c in features.columns if not c.startswith("macro_")])
    for col in [c for c in features.columns if c.startswith("macro_")]:
        if len(warm) == 0 or warm[col].isna().mean() > MACRO_MAX_MISSING:
            features = features.drop(columns=[col])

    data = features.copy()
    data["target"] = target
    data_full = data.dropna(subset=[c for c in data.columns if c != "target"])  # 特徴量が揃っている行
    data_labeled = data_full.dropna(subset=["target"])  # さらに目的変数がわかる行(学習・評価用)

    needed = MIN_TRAIN_ROWS + VALIDATION_SIZE_DAYS + TEST_SIZE_DAYS + 2 * GAP_DAYS
    if len(data_labeled) < needed:
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

    best_buy, best_sell = extract_high_confidence_rules(X_train, y_train, X_test, y_test)

    bt = backtest_thresholds(
        models["X_val"].index, models["val_probs"], X_test.index, test_probs, close,
    )

    if details:
        return {
            "status": "ok",
            "metrics": metrics,
            "backtest": bt,
            "_details": {
                "test_index": X_test.index, "test_probs": test_probs, "threshold": models["threshold"],
                "X_train": X_train, "y_train": y_train, "X_test": X_test, "y_test": y_test, "close": close,
            },
        }

    # 最新時点(特徴量が揃っている最終行)での予測。
    # 評価が終わったので、直近のテスト期間も含めた全データで学習し直したモデルを使う
    live_models = train_ensemble(X_labeled, y_labeled)
    latest_row = data_full.drop(columns=["target"]).iloc[[-1]]
    latest_prob = float(predict_ensemble(live_models, latest_row)[0])

    return {
        "status": "ok",
        "generated_at_row_date": str(data_full.index[-1].date()),
        "horizon_days": HORIZON_DAYS,
        "up_threshold": UP_THRESHOLD,
        "latest_prob_up": round(latest_prob, 3),
        "decision_threshold": round(live_models["threshold"], 3),
        "signal": "buy_candidate" if latest_prob >= live_models["threshold"] else "no_signal",
        "metrics": metrics,
        "n_train": len(X_train),
        "n_val": len(models["X_val"]),
        "n_test": len(X_test),
        "test_start": str(X_test.index[0].date()),
        "test_end": str(X_test.index[-1].date()),
        "model_used": "lightgbm+logistic" if HAS_LIGHTGBM else "histgbm(fallback)+logistic",
        "feature_importance": importance,
        "buy_rule": best_buy,
        "sell_rule": best_sell,
        "backtest": bt,
    }


def remove_stale_predictions(keep_codes):
    """今回の対象外になった銘柄(上場廃止・ユニバース外・データ不足など)の古い予測ファイルを消す"""
    removed = 0
    for fname in os.listdir(PREDICTIONS_DIR):
        if fname.endswith(".json") and fname[:-5] not in keep_codes:
            os.remove(os.path.join(PREDICTIONS_DIR, fname))
            removed += 1
    if removed:
        print(f"古い予測ファイルを{removed}件削除しました")


def main():
    screening = load_json(SCREENING_PATH)
    if not screening:
        raise RuntimeError("data/screening_all.json が見つかりません。先にscreen_stocks.pyを実行してください。")

    tickers = [s["ticker"] for s in screening["stocks"]]
    print(f"対象銘柄数: {len(tickers)}")

    macro = load_macro_series()
    print(f"マクロ特徴量: {list(macro.keys())}")

    os.makedirs(PREDICTIONS_DIR, exist_ok=True)

    print(f"学習用の株価({PRICE_LOOKBACK})を取得します")
    ohlcv_all = download_ohlcv(tickers, period=PRICE_LOOKBACK)

    n_ok, n_skip, n_error = 0, 0, 0
    written = set()
    for i, ticker in enumerate(tickers):
        code = ticker.replace(".T", "")
        try:
            ohlcv = ohlcv_all.get(ticker)
            if ohlcv is None or ohlcv.empty:
                n_skip += 1
                continue
            result = process_ticker(ohlcv, macro)
            if result.get("status") != "ok":
                n_skip += 1
                continue

            out_path = os.path.join(PREDICTIONS_DIR, f"{code}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            written.add(code)
            n_ok += 1

            if (i + 1) % 50 == 0:
                print(f"進捗: {i + 1}/{len(tickers)} (成功{n_ok}件)")
        except Exception as e:
            n_error += 1
            print(f"[error] {ticker}: {e}")

    print(f"完了: 成功{n_ok}件 / スキップ{n_skip}件 / エラー{n_error}件")
    if n_ok == 0:
        raise RuntimeError("予測が1件も作れませんでした。株価の取得に失敗している可能性があります。")
    remove_stale_predictions(written)


if __name__ == "__main__":
    main()
