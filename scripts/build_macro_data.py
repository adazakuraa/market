# -*- coding: utf-8 -*-
"""
為替(米ドル/円)・米国株主要指数(S&P500, NASDAQ)・主要資源(金・原油・銀・銅)の
日次価格データをyfinanceで取得し、期間別チャート表示用のJSONを出力する。

出力:
- data/overseas.json    : 為替・米国株指数
- data/commodities.json : 主要資源
"""
import os
import json
import pandas as pd
import yfinance as yf

from build_sector_strength import despike

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_OVERSEAS_PATH = os.path.join(BASE_DIR, "data", "overseas.json")
OUT_COMMODITIES_PATH = os.path.join(BASE_DIR, "data", "commodities.json")

LOOKBACK_PERIOD = "7mo"  # 6ヶ月表示に余裕を持たせる

OVERSEAS_TICKERS = {
    "米ドル/円": "JPY=X",
    "S&P500": "^GSPC",
    "NASDAQ総合": "^IXIC",
}

COMMODITY_TICKERS = {
    "金": "GC=F",
    "原油(WTI)": "CL=F",
    "銀": "SI=F",
    "銅": "HG=F",
}


def fetch_series(label, ticker):
    df = yf.download(ticker, period=LOOKBACK_PERIOD, interval="1d", progress=False, auto_adjust=True)
    if df.empty or "Close" not in df.columns:
        print(f"[warn] {label}({ticker}) のデータが取得できませんでした")
        return None

    close_df = df[["Close"]].copy()
    close_df.columns = [ticker]  # despikeが複数銘柄DataFrameを想定しているため列名を統一
    close_df = despike(close_df, threshold=0.15, window=7)
    close = close_df[ticker].dropna()

    if close.empty:
        return None

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in close.index],
        "values": [round(float(v), 4) for v in close],
    }


def fetch_group(tickers_dict):
    result = {}
    for label, ticker in tickers_dict.items():
        print(f"Fetching {label} ({ticker})...")
        series = fetch_series(label, ticker)
        if series is not None:
            result[label] = series
    return result


def main():
    overseas = fetch_group(OVERSEAS_TICKERS)
    commodities = fetch_group(COMMODITY_TICKERS)

    os.makedirs(os.path.dirname(OUT_OVERSEAS_PATH), exist_ok=True)
    with open(OUT_OVERSEAS_PATH, "w", encoding="utf-8") as f:
        json.dump(overseas, f, ensure_ascii=False)
    with open(OUT_COMMODITIES_PATH, "w", encoding="utf-8") as f:
        json.dump(commodities, f, ensure_ascii=False)

    print(f"Saved overseas ({len(overseas)}件) -> {OUT_OVERSEAS_PATH}")
    print(f"Saved commodities ({len(commodities)}件) -> {OUT_COMMODITIES_PATH}")


if __name__ == "__main__":
    main()
