# -*- coding: utf-8 -*-
"""
data/master.csv の銘柄リストをもとに yfinance で株価を取得し、
セクターごとの「TOPIX対比の相対強度」を複数期間（1週間〜6ヶ月）で算出する。

TOPIXの代理として、NEXT FUNDS TOPIX連動型上場投信(1306.T)を使う
（TOPIX自体はyfinanceで安定して取れないため、ETF価格を代理指標とする）。
"""
import os
import time
import pandas as pd
import yfinance as yf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
MASTER_PATH = os.path.join(BASE_DIR, "data", "master.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "sector_strength.csv")
RAW_PRICES_PATH = os.path.join(BASE_DIR, "data", "prices_latest.csv")

TOPIX_PROXY_TICKER = "1306.T"  # NEXT FUNDS TOPIX連動型上場投信

# 期間定義（営業日ベースのおおよその日数）
PERIODS = {
    "1w": 5,
    "2w": 10,
    "1m": 21,
    "3m": 63,
    "6m": 126,
}

CHUNK_SIZE = 150  # yfinanceへの負荷分散のため分割ダウンロード
LOOKBACK_PERIOD = "7mo"  # 6mの計算に必要な余裕を持たせる


def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def download_close_prices(tickers):
    """複数銘柄の調整後終値をまとめて取得し、DataFrame(index=date, columns=ticker)で返す"""
    all_frames = []
    for chunk in chunked(tickers, CHUNK_SIZE):
        print(f"Downloading {len(chunk)} tickers...")
        df = yf.download(
            tickers=chunk,
            period=LOOKBACK_PERIOD,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            close = df.xs("Close", axis=1, level=1, drop_level=True)
        else:
            # 銘柄が1つしかない場合の形式対応
            close = df[["Close"]]
            close.columns = chunk
        all_frames.append(close)
        time.sleep(2)  # レート制限対策の小休止
    return pd.concat(all_frames, axis=1)


def period_return(series, days):
    """直近値と、営業日で概ねdays日前の値との変化率(%)を返す"""
    series = series.dropna()
    if len(series) < days + 1:
        return None
    latest = series.iloc[-1]
    past = series.iloc[-(days + 1)]
    if past == 0 or pd.isna(past) or pd.isna(latest):
        return None
    return (latest / past - 1.0) * 100.0


def main():
    master = pd.read_csv(MASTER_PATH, dtype=str)
    tickers = master["ticker"].tolist()
    all_tickers = tickers + [TOPIX_PROXY_TICKER]

    close_df = download_close_prices(all_tickers)
    close_df.to_csv(RAW_PRICES_PATH)  # デバッグ用に生データも保存

    # TOPIX(代理)の期間リターン
    topix_returns = {}
    if TOPIX_PROXY_TICKER in close_df.columns:
        for label, days in PERIODS.items():
            topix_returns[label] = period_return(close_df[TOPIX_PROXY_TICKER], days)
    else:
        raise RuntimeError("TOPIX代理ETF(1306.T)の価格取得に失敗しました")

    # 銘柄ごとの期間リターンを計算
    stock_returns = {}
    for t in tickers:
        if t not in close_df.columns:
            continue
        stock_returns[t] = {
            label: period_return(close_df[t], days) for label, days in PERIODS.items()
        }

    returns_df = pd.DataFrame.from_dict(stock_returns, orient="index")
    returns_df.index.name = "ticker"
    returns_df = returns_df.merge(
        master[["ticker", "sector33"]], left_index=True, right_on="ticker"
    )

    # セクターごとに単純平均（等加重）でセクターリターンを算出
    sector_returns = returns_df.groupby("sector33")[list(PERIODS.keys())].mean(numeric_only=True)

    # TOPIX対比の相対強度（ポイント差）
    relative = sector_returns.copy()
    for label in PERIODS.keys():
        relative[label] = sector_returns[label] - topix_returns[label]

    relative = relative.sort_values("1m", ascending=False)
    relative.to_csv(OUT_PATH, encoding="utf-8-sig")
    print(f"Saved sector strength -> {OUT_PATH}")
    print(relative)


if __name__ == "__main__":
    main()
