# -*- coding: utf-8 -*-
"""
株価予測モデルの学習・評価・ルール抽出・売買閾値バックテストを行う関数群。
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    from sklearn.ensemble import HistGradientBoostingClassifier
    HAS_LIGHTGBM = False

TEST_SIZE_DAYS = 120        # 最終評価に使う直近の期間(学習にも閾値決めにも使わない)
VALIDATION_SIZE_DAYS = 120  # 学習データの中から切り出す、閾値・売買ルールを決めるための検証期間
MIN_TRAIN_ROWS = 200        # これ未満なら学習しない
GAP_DAYS = 5                # 予測期間(5営業日)ぶん、学習と検証/テストの間を空ける
COST_PER_TRADE = 0.002      # 売買1往復あたりのコスト想定(手数料・スプレッド等 0.2%)


def time_series_split(X, y, test_size=TEST_SIZE_DAYS, gap=GAP_DAYS):
    """
    時系列順を保ったまま、末尾test_size行をテスト、それより前を学習に使う。
    目的変数は「5営業日後の値動き」なので、学習データの末尾gap行はテスト期間の値動きを
    含んでしまう。その分を学習から外して、テスト期間の情報が学習に漏れないようにする。
    """
    n = len(X)
    split_idx = n - test_size
    train_end = max(split_idx - gap, 0)
    X_train, X_test = X.iloc[:train_end], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:train_end], y.iloc[split_idx:]
    return X_train, X_test, y_train, y_test


def find_best_threshold(y_true, probs, grid=None):
    """
    F1が最大になる閾値を探す(Precision/Recallどちらかに極端に偏らないようにするため、
    固定の0.5ではなく検証データ側で調整する)。
    """
    if grid is None:
        grid = np.arange(0.30, 0.71, 0.05)
    best_th, best_f1 = 0.5, -1.0
    for th in grid:
        pred = (probs >= th).astype(int)
        f1 = f1_score(y_true, pred, zero_division=0)
        if f1 > best_f1:
            best_f1, best_th = f1, th
    return float(best_th)


def train_gbm(X_train, y_train):
    if HAS_LIGHTGBM:
        model = LGBMClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.05,
            class_weight="balanced", random_state=42, verbosity=-1,
        )
        model.fit(X_train, y_train)
        return model
    else:
        # lightgbmが使えない環境向けのフォールバック
        model = HistGradientBoostingClassifier(
            max_depth=4, learning_rate=0.05, max_iter=150, random_state=42,
        )
        pos = y_train.sum()
        neg = len(y_train) - pos
        sample_weight = y_train.map(lambda v: (len(y_train) / (2 * pos)) if v == 1 else (len(y_train) / (2 * neg)))
        model.fit(X_train, y_train, sample_weight=sample_weight)
        return model


def train_logistic(X_train, y_train, scaler):
    X_scaled = scaler.fit_transform(X_train)
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_scaled, y_train)
    return model


def train_ensemble(X_train, y_train, gap=GAP_DAYS):
    """
    学習データをさらに「内部学習用」と「検証用(閾値調整用)」に時系列分割し、
    検証データでF1最大の閾値を決めてから、学習データ全体で最終モデルを再学習する。
    こうすることで、Precision/Recallのどちらかに極端に偏る閾値を避ける。
    """
    n = len(X_train)
    val_size = min(VALIDATION_SIZE_DAYS, max(int(n * 0.2), 10))
    inner_train_size = n - val_size

    # 内部学習と検証の間もgap行空ける(検証期間の値動きが内部学習に漏れないように)
    X_inner, X_val = X_train.iloc[:max(inner_train_size - gap, 1)], X_train.iloc[inner_train_size:]
    y_inner, y_val = y_train.iloc[:max(inner_train_size - gap, 1)], y_train.iloc[inner_train_size:]

    gbm_inner = train_gbm(X_inner, y_inner)
    scaler_inner = StandardScaler()
    logit_inner = train_logistic(X_inner, y_inner, scaler_inner)

    gbm_val_probs = gbm_inner.predict_proba(X_val)[:, 1]
    logit_val_probs = logit_inner.predict_proba(scaler_inner.transform(X_val))[:, 1]
    ensemble_val_probs = (gbm_val_probs + logit_val_probs) / 2

    best_threshold = find_best_threshold(y_val, ensemble_val_probs)

    # 最終モデルは学習データ全体(内部学習+検証)で再学習する
    gbm_final = train_gbm(X_train, y_train)
    scaler_final = StandardScaler()
    logit_final = train_logistic(X_train, y_train, scaler_final)

    return {
        "gbm": gbm_final,
        "logit": logit_final,
        "scaler": scaler_final,
        "threshold": best_threshold,
        "X_val": X_val,
        "y_val": y_val,
        "val_probs": ensemble_val_probs,   # 検証期間の予測確率(内部学習モデルによる)。売買ルールの決定に使う
    }


def predict_ensemble(models, X):
    gbm_probs = models["gbm"].predict_proba(X)[:, 1]
    logit_probs = models["logit"].predict_proba(models["scaler"].transform(X))[:, 1]
    return (gbm_probs + logit_probs) / 2


def evaluate(y_true, y_pred):
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 3),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 3),
        # 比較用: テスト期間に実際に「上昇」だった日の割合。
        # 毎日やみくもに買っても precision はこの値くらいになるので、これを上回っているかが目安
        "base_rate": round(float(np.mean(y_true)), 3) if len(y_true) else None,
        "n_signals": int(np.sum(y_pred)),
    }


def get_feature_importance(gbm_model, feature_names, X_val=None, y_val=None, top_n=8):
    importances = getattr(gbm_model, "feature_importances_", None)
    if importances is None and X_val is not None and y_val is not None:
        # HistGradientBoostingClassifier等、ネイティブの重要度を持たないモデル向けのフォールバック
        from sklearn.inspection import permutation_importance
        result = permutation_importance(gbm_model, X_val, y_val, n_repeats=5, random_state=42, scoring="f1")
        importances = result.importances_mean
        importances = np.clip(importances, 0, None)  # 負の重要度は0に丸める(表示上の意味がないため)
    if importances is None:
        return []
    pairs = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    total = sum(imp for _, imp in pairs) or 1.0
    return [
        {"feature": name, "importance": round(float(imp) / float(total), 4)}
        for name, imp in pairs[:top_n]
    ]


def extract_high_confidence_rules(X_train, y_train, X_test=None, y_test=None, min_leaf_ratio=0.05, max_depth=3):
    """
    浅い決定木を学習期間だけで学習し、上昇しやすい/しにくい条件(葉)を抽出する。
    学習期間での的中率に加えて、学習に使っていないテスト期間で同じ条件に当てはまった日の
    的中率も出す(学習期間の数字だけだと実際より良く見えるため)。
    """
    min_samples_leaf = max(int(len(X_train) * min_leaf_ratio), 5)
    tree = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_samples_leaf, random_state=42)
    tree.fit(X_train, y_train)

    feature_names = list(X_train.columns)
    t = tree.tree_
    leaves = []

    def walk(node_id, path):
        left = t.children_left[node_id]
        right = t.children_right[node_id]
        if left == -1 and right == -1:  # 葉ノード
            n_samples = int(t.n_node_samples[node_id])
            values = t.value[node_id][0]
            # sklearnのバージョンにより、value が「件数」か「割合(合計1)」かが異なるため両対応する
            if abs(float(values.sum()) - 1.0) < 1e-6:
                precision_up = float(values[1]) if len(values) > 1 else 0.0
            else:
                precision_up = float(values[1]) / n_samples if n_samples > 0 and len(values) > 1 else 0.0
            leaves.append({"node": node_id, "path": list(path), "n_samples": n_samples, "precision_up": precision_up})
            return
        feature = feature_names[t.feature[node_id]]
        threshold = t.threshold[node_id]
        walk(left, path + [f"{feature} <= {threshold:.3f}"])
        walk(right, path + [f"{feature} > {threshold:.3f}"])

    walk(0, [])
    if not leaves:
        return None, None

    test_leaf = tree.apply(X_test) if X_test is not None and len(X_test) else None
    y_test_arr = np.asarray(y_test) if y_test is not None else None

    def finish(leaf):
        if leaf is None:
            return None
        out = {k: leaf[k] for k in ("path", "n_samples", "precision_up")}
        out["precision_up"] = round(float(out["precision_up"]), 3)
        if test_leaf is not None:
            mask = test_leaf == leaf["node"]
            n_test = int(mask.sum())
            out["test_n_samples"] = n_test
            out["test_precision_up"] = round(float(y_test_arr[mask].mean()), 3) if n_test > 0 else None
        return out

    candidates = [l for l in leaves if l["n_samples"] >= min_samples_leaf]
    best_buy = max(candidates, key=lambda l: l["precision_up"]) if candidates else None
    best_sell = min(candidates, key=lambda l: l["precision_up"]) if candidates else None
    return finish(best_buy), finish(best_sell)


def simulate_trades(probs, close_arr, buy_th, sell_th, max_hold_days=10, cost=COST_PER_TRADE):
    """確率が buy_th 以上で買い、sell_th 以下 or max_hold_days 経過で売る。1取引ごとのリターン(コスト控除後)を返す"""
    trades = []
    position = False
    entry_price = None
    entry_idx = None
    for i, p in enumerate(probs):
        price = close_arr[i]
        if price is None or not np.isfinite(price):
            continue
        if not position and p >= buy_th:
            position, entry_price, entry_idx = True, price, i
        elif position and (p <= sell_th or i - entry_idx >= max_hold_days):
            trades.append(price / entry_price - 1 - cost)
            position = False
    if position:  # 期間末に保有中なら最終日に手じまい
        last = close_arr[-1]
        if last is not None and np.isfinite(last):
            trades.append(last / entry_price - 1 - cost)
    return trades


def backtest_thresholds(val_dates, val_probs, test_dates, test_probs, close_series,
                        buy_grid=None, sell_grid=None, max_hold_days=10, cost=COST_PER_TRADE):
    """
    売買の閾値は「検証期間」で一番成績の良い組み合わせを選び、
    その閾値を「テスト期間」(閾値選びにもモデルの学習にも使っていない期間)に当てはめた成績を返す。
    同じ期間で選んで同じ期間で評価すると、成績が実際より良く見えてしまうため。
    成績は売買コスト(1往復 cost)を差し引いた値。比較用に、テスト期間をずっと持ち続けた場合のリターンも返す。
    """
    if buy_grid is None:
        buy_grid = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    if sell_grid is None:
        sell_grid = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

    val_close = close_series.reindex(val_dates).values
    test_close = close_series.reindex(test_dates).values

    best = None
    for buy_th in buy_grid:
        for sell_th in sell_grid:
            if sell_th >= buy_th:
                continue
            trades = simulate_trades(val_probs, val_close, buy_th, sell_th, max_hold_days, cost)
            if len(trades) < 3:  # 取引数が少なすぎる組み合わせはノイズなので除外
                continue
            avg = float(np.mean(trades))
            if best is None or avg > best["val_avg"]:
                best = {"buy": buy_th, "sell": sell_th, "val_avg": avg, "val_n": len(trades)}
    if best is None:
        return None

    test_trades = simulate_trades(test_probs, test_close, best["buy"], best["sell"], max_hold_days, cost)
    finite = test_close[np.isfinite(test_close)]
    hold_return = float(finite[-1] / finite[0] - 1) if len(finite) >= 2 else None
    return {
        "buy_threshold": best["buy"],
        "sell_threshold": best["sell"],
        "selected_on": "validation",
        "val_n_trades": best["val_n"],
        "val_avg_return_per_trade": round(best["val_avg"], 4),
        "n_trades": len(test_trades),
        "total_return": round(float(np.sum(test_trades)), 4) if test_trades else 0.0,
        "avg_return_per_trade": round(float(np.mean(test_trades)), 4) if test_trades else None,
        "win_rate": round(float(np.mean([r > 0 for r in test_trades])), 3) if test_trades else None,
        "cost_per_trade": cost,
        "buy_and_hold_return": round(hold_return, 4) if hold_return is not None else None,
        "test_days": int(len(test_dates)),
    }
