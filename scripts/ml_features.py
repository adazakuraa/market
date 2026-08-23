# -*- coding: utf-8 -*-
"""
株価予測モデル用の特徴量エンジニアリング。
既存のindicators.pyの指標に加えて、予測モデル向けの追加特徴量を作る。
"""
import pandas as pd
import numpy as np

from indicators import sma, rsi, macd, atr, adx, obv


def bollinger_width(close, window=20, num_std=2):
    """ボリンジャーバンドの幅(標準化済み、価格に対する比率)"""
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return (upper - lower) / mid


def build_features(close, high, low, volume, macro=None, fundamentals=None):
    """
    OHLCVから予測モデル用の特徴量DataFrameを作る。
    列はすべて「その日時点で観測可能な値」のみで構成する(未来の情報を混ぜない)。

    macro: {列名: pd.Series(日次にreindex・ffill済み)} のdict。為替・原油・企業物価指数など。
    fundamentals: {列名: スカラー値} のdict。PER・PBR等、現在値を全期間の定数として使う。
    """
    df = pd.DataFrame(index=close.index)

    df["rsi14"] = rsi(close, 14)
    macd_line, macd_signal, macd_hist = macd(close)
    df["macd"] = macd_line
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist
    df["atr14"] = atr(high, low, close, 14)
    adx14, plus_di, minus_di = adx(high, low, close, 14)
    df["adx14"] = adx14
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di
    df["obv"] = obv(close, volume)
    df["obv_change_20d"] = df["obv"].diff(20)

    ma25 = sma(close, 25)
    ma75 = sma(close, 75)
    df["price_vs_ma25"] = close / ma25 - 1
    df["price_vs_ma75"] = close / ma75 - 1
    df["ma25_vs_ma75"] = ma25 / ma75 - 1

    df["return_1d"] = close.pct_change(1)
    df["return_3d"] = close.pct_change(3)
    df["return_5d"] = close.pct_change(5)
    df["return_10d"] = close.pct_change(10)

    vol_ma20 = volume.rolling(20).mean()
    df["volume_ratio"] = volume / vol_ma20

    df["bb_width"] = bollinger_width(close, 20, 2)

    # OBVは絶対水準に意味がないので変化量のみ使い、生の値は特徴量から除外
    df = df.drop(columns=["obv"])

    # ==== マクロ特徴量(為替・原油・企業物価指数など) ====
    if macro:
        for name, series in macro.items():
            aligned = series.reindex(df.index).ffill().bfill()  # 先頭がわずかに欠けても切り捨てないための保険
            df[f"macro_{name}"] = aligned
            df[f"macro_{name}_chg20d"] = aligned.pct_change(20)

    # ==== ファンダメンタル特徴量(現在値を定数として使用) ====
    if fundamentals:
        for name, value in fundamentals.items():
            df[f"fund_{name}"] = value

    return df


def build_target(close, horizon=5, threshold=0.02):
    """
    horizon営業日後の株価が、今よりthreshold以上上昇していれば1、そうでなければ0。
    直近horizon日分は「未来が観測できない」ため、必ずNaNのまま返す
    (int型にキャストしてしまうとNaNが0扱いになり、存在しないデータで学習することになるため注意)。
    """
    future_return = close.shift(-horizon) / close - 1
    target = pd.Series(np.where(future_return >= threshold, 1, 0), index=close.index, dtype="float64")
    target[future_return.isna()] = np.nan
    return target



def build_features_from_timeseries(ts, macro=None, fundamentals=None):
    """
    docs/timeseries/<コード>.json (screen_stocks.pyが既に計算済みの指標データ)を
    そのまま使って特徴量DataFrameを作る。yfinanceへの再アクセスを避けるための経路。

    ts: {"dates":[...], "close":[...], "volume":[...], "rsi14":[...], ...} の辞書
    戻り値: (特徴量DataFrame, 終値Series)
    """
    dates = pd.to_datetime(ts["dates"])
    close = pd.Series(ts["close"], index=dates, dtype="float64")
    volume = pd.Series(ts["volume"], index=dates, dtype="float64")
    ma25 = pd.Series(ts["ma25"], index=dates, dtype="float64")
    ma75 = pd.Series(ts["ma75"], index=dates, dtype="float64")

    df = pd.DataFrame(index=dates)
    df["rsi14"] = pd.Series(ts["rsi14"], index=dates, dtype="float64")
    df["macd"] = pd.Series(ts["macd"], index=dates, dtype="float64")
    df["macd_signal"] = pd.Series(ts["macd_signal"], index=dates, dtype="float64")
    df["macd_hist"] = pd.Series(ts["macd_hist"], index=dates, dtype="float64")
    df["atr14"] = pd.Series(ts["atr14"], index=dates, dtype="float64")
    df["adx14"] = pd.Series(ts["adx14"], index=dates, dtype="float64")
    df["plus_di"] = pd.Series(ts["plus_di"], index=dates, dtype="float64")
    df["minus_di"] = pd.Series(ts["minus_di"], index=dates, dtype="float64")

    obv = pd.Series(ts["obv"], index=dates, dtype="float64")
    df["obv_change_20d"] = obv.diff(20)

    df["price_vs_ma25"] = close / ma25 - 1
    df["price_vs_ma75"] = close / ma75 - 1
    df["ma25_vs_ma75"] = ma25 / ma75 - 1

    df["return_1d"] = close.pct_change(1)
    df["return_3d"] = close.pct_change(3)
    df["return_5d"] = close.pct_change(5)
    df["return_10d"] = close.pct_change(10)

    vol_ma20 = volume.rolling(20).mean()
    df["volume_ratio"] = volume / vol_ma20

    df["bb_width"] = bollinger_width(close, 20, 2)

    if macro:
        for name, series in macro.items():
            aligned = series.reindex(df.index).ffill().bfill()  # 先頭がわずかに欠けても切り捨てないための保険
            df[f"macro_{name}"] = aligned
            df[f"macro_{name}_chg20d"] = aligned.pct_change(20)

    if fundamentals:
        for name, value in fundamentals.items():
            df[f"fund_{name}"] = value

    return df, close
