# -*- coding: utf-8 -*-
"""
data/master.csv の銘柄リストをもとに yfinance で株価を取得し、
セクターごとの「TOPIX対比の相対強度」を複数期間（1週間〜6ヶ月）で算出する。

TOPIXの代理として、NEXT FUNDS TOPIX連動型上場投信(1306.T)を使う
（TOPIX自体はyfinanceで安定して取れないため、ETF価格を代理指標とする）。
"""
import os
import time
import json
import pandas as pd
import yfinance as yf

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
MASTER_PATH = os.path.join(BASE_DIR, "data", "master.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "sector_strength.csv")
RAW_PRICES_PATH = os.path.join(BASE_DIR, "data", "prices_latest.csv")
TIMESERIES_OUT_PATH = os.path.join(BASE_DIR, "data", "sector_timeseries.json")

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

DESPIKE_THRESHOLD = 0.25  # 1日でこの割合を超える変動は異常値とみなす(25%)


def despike(df, threshold=DESPIKE_THRESHOLD):
    """
    yfinance側の誤ティック対策。1日の変化率が閾値を超える値をNaNにし、
    前日値で補完する。TOPIX代理ETFのような値が1日だけ異常だと
    全セクターの相対強度に同じ歪みが伝播するため、ここで弾いておく。
    """
    daily_ret = df.pct_change()
    bad = daily_ret.abs() > threshold
    n_bad = int(bad.sum().sum())
    if n_bad > 0:
        flagged = []
        for col in df.columns:
            bad_dates = df.index[bad[col]]
            for d in bad_dates:
                flagged.append(f"{col} @ {d.date()}")
        print(f"[despike] {n_bad}件の異常値を検出し前日値で補完します: {flagged[:20]}")
    cleaned = df.mask(bad)
    cleaned = cleaned.ffill()
    return cleaned
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


def build_timeseries(close_df, master):
    """
    各銘柄の終値を「取得期間の最初の日=0%」とした累積リターンに変換し、
    セクターごとに等加重平均→TOPIX(代理)の累積リターンとの差(ポイント)を
    日次の時系列として算出する。
    """
    df = close_df.ffill()

    # 最初の行(基準日)にすべての値が揃っている列だけを対象にする
    valid_cols = df.columns[df.iloc[0].notna()]
    df = df[valid_cols]

    cum = (df / df.iloc[0] - 1.0) * 100.0  # 累積リターン(%)

    if TOPIX_PROXY_TICKER not in cum.columns:
        raise RuntimeError("TOPIX代理ETF(1306.T)の時系列が作成できませんでした")
    topix_cum = cum[TOPIX_PROXY_TICKER]

    ticker_to_sector = dict(zip(master["ticker"], master["sector33"]))

    sector_cols = {}
    for ticker in cum.columns:
        if ticker == TOPIX_PROXY_TICKER:
            continue
        sector = ticker_to_sector.get(ticker)
        if sector is None:
            continue
        sector_cols.setdefault(sector, []).append(ticker)

    dates = [d.strftime("%Y-%m-%d") for d in cum.index]
    sectors_out = {}
    for sector, tickers_in_sector in sector_cols.items():
        sector_cum = cum[tickers_in_sector].mean(axis=1)
        relative = (sector_cum - topix_cum).round(2)
        sectors_out[sector] = relative.tolist()

    payload = {
        "dates": dates,
        "sectors": sectors_out,
    }
    with open(TIMESERIES_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"Saved timeseries -> {TIMESERIES_OUT_PATH}")


def main():
    master = pd.read_csv(MASTER_PATH, dtype=str)
    tickers = master["ticker"].tolist()
    all_tickers = tickers + [TOPIX_PROXY_TICKER]

    close_df = download_close_prices(all_tickers)
    close_df.to_csv(RAW_PRICES_PATH)  # デバッグ用に生データ(補完前)も保存
    close_df = despike(close_df)  # デバッグ用に生データも保存

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

    build_timeseries(close_df, master)


if __name__ == "__main__":
    main()
