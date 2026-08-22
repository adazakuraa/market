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

TEST_SIZE_DAYS = 40
VALIDATION_SIZE_DAYS = 40  # 学習データの中からさらに切り出す、閾値調整用の検証期間
MIN_TRAIN_ROWS = 120  # これ未満なら学習しない


def time_series_split(X, y, test_size=TEST_SIZE_DAYS):
    """時系列順を保ったまま、末尾test_size行をテスト、それより前を学習に使う"""
    n = len(X)
    split_idx = n - test_size
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
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


def train_ensemble(X_train, y_train):
    """
    学習データをさらに「内部学習用」と「検証用(閾値調整用)」に時系列分割し、
    検証データでF1最大の閾値を決めてから、学習データ全体で最終モデルを再学習する。
    こうすることで、Precision/Recallのどちらかに極端に偏る閾値を避ける。
    """
    n = len(X_train)
    val_size = min(VALIDATION_SIZE_DAYS, max(int(n * 0.2), 10))
    inner_train_size = n - val_size

    X_inner, X_val = X_train.iloc[:inner_train_size], X_train.iloc[inner_train_size:]
    y_inner, y_val = y_train.iloc[:inner_train_size], y_train.iloc[inner_train_size:]

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


def extract_high_confidence_rules(X, y, min_leaf_ratio=0.05, max_depth=3):
    """
    浅い決定木を学習し、精度が高い葉(買いやすいパターン・売りやすいパターン)を抽出する。
    X, yは学習・テストを合わせた全期間のデータ(ルール発見が目的で、予測精度の検証はしないため)。
    """
    min_samples_leaf = max(int(len(X) * min_leaf_ratio), 5)
    tree = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_samples_leaf, random_state=42)
    tree.fit(X, y)

    feature_names = list(X.columns)
    t = tree.tree_

    leaves = []

    def walk(node_id, path):
        left = t.children_left[node_id]
        right = t.children_right[node_id]
        if left == -1 and right == -1:  # 葉ノード
            n_samples = int(t.n_node_samples[node_id])  # 生の件数はn_node_samplesから取る(確実)
            values = t.value[node_id][0]
            # sklearnのバージョンにより、value が「件数」か「割合(合計1)」かが異なるため両対応する
            if abs(float(values.sum()) - 1.0) < 1e-6:
                precision_up = float(values[1]) if len(values) > 1 else 0.0
            else:
                precision_up = float(values[1]) / n_samples if n_samples > 0 and len(values) > 1 else 0.0
            leaves.append({"path": list(path), "n_samples": n_samples, "precision_up": precision_up})
            return
        feature = feature_names[t.feature[node_id]]
        threshold = t.threshold[node_id]
        walk(left, path + [f"{feature} <= {threshold:.3f}"])
        walk(right, path + [f"{feature} > {threshold:.3f}"])

    walk(0, [])

    if not leaves:
        return None, None

    # 買いシグナル: 上昇的中率が最も高い葉(十分なサンプル数があるもの)
    buy_candidates = [l for l in leaves if l["n_samples"] >= min_samples_leaf]
    best_buy = max(buy_candidates, key=lambda l: l["precision_up"]) if buy_candidates else None
    # 売りシグナル: 上昇的中率が最も低い(=下落しやすい)葉
    best_sell = min(buy_candidates, key=lambda l: l["precision_up"]) if buy_candidates else None

    return best_buy, best_sell


def backtest_thresholds(dates, probs, close_series, buy_grid=None, sell_grid=None, max_hold_days=10):
    """
    予測確率の時系列を使い、買い/売り閾値の組み合わせをグリッドサーチして
    過去データ上の累積リターンが最大になる組み合わせを探す。
    """
    if buy_grid is None:
        buy_grid = [0.55, 0.60, 0.65, 0.70, 0.75]
    if sell_grid is None:
        sell_grid = [0.30, 0.35, 0.40, 0.45, 0.50]

    close_arr = close_series.reindex(dates).values
    best = None

    for buy_th in buy_grid:
        for sell_th in sell_grid:
            if sell_th >= buy_th:
                continue
            position = False
            entry_price = None
            entry_idx = None
            total_return = 0.0
            n_trades = 0

            for i, p in enumerate(probs):
                if not position and p >= buy_th:
                    position = True
                    entry_price = close_arr[i]
                    entry_idx = i
                elif position:
                    held = i - entry_idx
                    if p <= sell_th or held >= max_hold_days:
                        total_return += (close_arr[i] / entry_price) - 1
                        n_trades += 1
                        position = False

            if n_trades < 3:  # 取引数が少なすぎる組み合わせはノイズなので除外
                continue

            avg_return = total_return / n_trades
            if best is None or avg_return > best["avg_return_per_trade"]:
                best = {
                    "buy_threshold": buy_th,
                    "sell_threshold": sell_th,
                    "n_trades": n_trades,
                    "total_return": round(float(total_return), 4),
                    "avg_return_per_trade": round(float(avg_return), 4),
                }

    return best
