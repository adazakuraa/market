# -*- coding: utf-8 -*-
"""
data/sector_strength.csv で相対的に強いセクターに属する銘柄を対象に、
- MAの並び(ゴールデンクロス/接近中)
- ADXでトレンドの強さ
- OBVが値動きに追従しているか
- RSI・MACD
- ATR(ストップ位置・ポジションサイズ計算用)
を計算し、上位(最大50銘柄)を data/screening.json / screening.csv に出力する。
"""
import os
import time
import json
import pandas as pd
import yfinance as yf

from build_sector_strength import despike
from indicators import sma, rsi, macd, atr, adx, obv

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
MASTER_PATH = os.path.join(BASE_DIR, "data", "master.csv")
SECTOR_STRENGTH_PATH = os.path.join(BASE_DIR, "data", "sector_strength.csv")
OUT_JSON_PATH = os.path.join(BASE_DIR, "data", "screening.json")
OUT_CSV_PATH = os.path.join(BASE_DIR, "data", "screening.csv")

CHUNK_SIZE = 100
LOOKBACK_PERIOD = "1y"  # MA75やADXの計算に十分な期間を確保
TOP_N_SECTORS = 15      # 強いセクター上位いくつまでを対象にするか
MAX_RESULTS = 50        # 出力する銘柄数の上限

GC_LOOKBACK_DAYS = 10       # 直近何日以内のゴールデンクロスを「済み」とみなすか
GC_APPROACH_PCT = 0.03      # MA75に対してこの割合以内に接近していたら「接近中」


def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def select_universe(master, sector_strength):
    """相対強度が高い上位セクターに属する銘柄だけに絞り込む"""
    strong_sectors = sector_strength.sort_values("1m", ascending=False).head(TOP_N_SECTORS).index.tolist()
    universe = master[master["sector33"].isin(strong_sectors)].copy()
    return universe, strong_sectors


def download_ohlcv(tickers):
    """複数銘柄のOHLCVを取得し、{ticker: DataFrame(Open,High,Low,Close,Volume)}で返す"""
    result = {}
    for chunk in chunked(tickers, CHUNK_SIZE):
        print(f"Downloading OHLCV for {len(chunk)} tickers...")
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
            for t in chunk:
                if t in df.columns.get_level_values(0):
                    sub = df[t][["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
                    if not sub.empty:
                        result[t] = sub
        else:
            # 銘柄が1つしかない場合
            sub = df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
            if not sub.empty:
                result[chunk[0]] = sub
        time.sleep(2)
    return result


def golden_cross_status(ma_fast, ma_slow):
    """MAの状態から「ゴールデンクロス済み」「接近中」「-」を判定"""
    diff = ma_fast - ma_slow
    if diff.dropna().empty or len(diff.dropna()) < GC_LOOKBACK_DAYS + 1:
        return "-", False

    latest_diff = diff.iloc[-1]
    recent = diff.iloc[-(GC_LOOKBACK_DAYS + 1):]

    crossed_recently = (recent.shift(1) < 0).fillna(False) & (recent >= 0)
    if latest_diff >= 0 and crossed_recently.any():
        return "ゴールデンクロス済み", True

    if latest_diff < 0:
        latest_slow = ma_slow.iloc[-1]
        if latest_slow and abs(latest_diff) / abs(latest_slow) <= GC_APPROACH_PCT:
            rising = diff.iloc[-1] > diff.iloc[-5] if len(diff) >= 5 else False
            if rising:
                return "接近中", False

    return "-", False


def obv_confirms_trend(close, obv_series, lookback=20):
    """直近lookback日で、価格とOBVが同じ方向に動いているか(トレンド追従)を簡易判定"""
    if len(close.dropna()) < lookback + 1 or len(obv_series.dropna()) < lookback + 1:
        return False
    price_change = close.iloc[-1] - close.iloc[-lookback]
    obv_change = obv_series.iloc[-1] - obv_series.iloc[-lookback]
    return (price_change > 0 and obv_change > 0) or (price_change < 0 and obv_change < 0)


def compute_score(row):
    score = 0.0
    if row["price_above_ma25"]:
        score += 1
    if row["ma25_above_ma75"]:
        score += 1
    if row["cross_status"] == "ゴールデンクロス済み":
        score += 2
    elif row["cross_status"] == "接近中":
        score += 1
    if pd.notna(row["adx14"]):
        score += min(row["adx14"] / 50.0, 1.0) * 2
    if row["obv_confirm"]:
        score += 1
    return score


def main():
    master = pd.read_csv(MASTER_PATH, dtype=str)
    sector_strength = pd.read_csv(SECTOR_STRENGTH_PATH, index_col=0)

    universe, strong_sectors = select_universe(master, sector_strength)
    print(f"対象セクター({len(strong_sectors)}): {strong_sectors}")
    print(f"対象銘柄数: {len(universe)}")

    ohlcv = download_ohlcv(universe["ticker"].tolist())

    ticker_to_name = dict(zip(master["ticker"], master["name"]))
    ticker_to_sector = dict(zip(master["ticker"], master["sector33"]))

    records = []
    for ticker, df in ohlcv.items():
        if len(df) < 90:  # MA75等の計算に足りない銘柄は除外
            continue

        cleaned = despike(df[["Close", "High", "Low"]], threshold=0.15, window=7)
        close = cleaned["Close"]
        high = cleaned["High"]
        low = cleaned["Low"]
        volume = df["Volume"]

        ma25 = sma(close, 25)
        ma75 = sma(close, 75)
        rsi14 = rsi(close, 14)
        macd_line, macd_signal, macd_hist = macd(close)
        atr14 = atr(high, low, close, 14)
        adx14, plus_di, minus_di = adx(high, low, close, 14)
        obv_series = obv(close, volume)

        cross_status, _ = golden_cross_status(ma25, ma75)
        obv_confirm = obv_confirms_trend(close, obv_series)

        latest_price = close.iloc[-1]
        latest_ma25 = ma25.iloc[-1]
        latest_ma75 = ma75.iloc[-1]

        if pd.isna(latest_ma75):
            continue

        row = {
            "ticker": ticker,
            "name": ticker_to_name.get(ticker, ticker),
            "sector33": ticker_to_sector.get(ticker, "-"),
            "price": round(float(latest_price), 1),
            "ma25": round(float(latest_ma25), 1) if pd.notna(latest_ma25) else None,
            "ma75": round(float(latest_ma75), 1) if pd.notna(latest_ma75) else None,
            "price_above_ma25": bool(latest_price > latest_ma25) if pd.notna(latest_ma25) else False,
            "ma25_above_ma75": bool(latest_ma25 > latest_ma75) if pd.notna(latest_ma25) else False,
            "cross_status": cross_status,
            "adx14": round(float(adx14.iloc[-1]), 1) if pd.notna(adx14.iloc[-1]) else None,
            "plus_di": round(float(plus_di.iloc[-1]), 1) if pd.notna(plus_di.iloc[-1]) else None,
            "minus_di": round(float(minus_di.iloc[-1]), 1) if pd.notna(minus_di.iloc[-1]) else None,
            "obv_confirm": bool(obv_confirm),
            "rsi14": round(float(rsi14.iloc[-1]), 1) if pd.notna(rsi14.iloc[-1]) else None,
            "macd": round(float(macd_line.iloc[-1]), 2) if pd.notna(macd_line.iloc[-1]) else None,
            "macd_signal": round(float(macd_signal.iloc[-1]), 2) if pd.notna(macd_signal.iloc[-1]) else None,
            "macd_hist": round(float(macd_hist.iloc[-1]), 2) if pd.notna(macd_hist.iloc[-1]) else None,
            "atr14": round(float(atr14.iloc[-1]), 1) if pd.notna(atr14.iloc[-1]) else None,
        }
        row["score"] = round(compute_score(row), 2)
        records.append(row)

    result_df = pd.DataFrame(records)
    if result_df.empty:
        raise RuntimeError("スクリーニング結果が0件でした。データ取得に失敗している可能性があります。")

    result_df = result_df.sort_values("score", ascending=False).head(MAX_RESULTS).reset_index(drop=True)

    result_df.to_csv(OUT_CSV_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "target_sectors": strong_sectors,
        "generated_count": len(result_df),
        "stocks": result_df.to_dict(orient="records"),
    }
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Saved {len(result_df)} stocks -> {OUT_JSON_PATH}")


if __name__ == "__main__":
    main()
