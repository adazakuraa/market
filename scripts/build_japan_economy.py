# -*- coding: utf-8 -*-
"""
日本国債利回り(財務省公式CSV)と国内企業物価指数(日本銀行 時系列統計データAPI)を取得する。
どちらも登録・APIキー不要で利用できる。

出力:
- data/jgb_yields.json     : 国債利回り(2年・5年・10年、日次)
- data/cgpi.json           : 国内企業物価指数(総平均、月次)
"""
import os
import io
import json
import requests
import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_JGB_PATH = os.path.join(BASE_DIR, "data", "jgb_yields.json")
OUT_CGPI_PATH = os.path.join(BASE_DIR, "data", "cgpi.json")

MOF_JGB_CSV_ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"

BOJ_API_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
CGPI_SERIES_CODE = "PRCG20_2200000000"  # [国内企業物価指数] 総平均

JGB_TARGET_COLUMNS = {"短期(2年)": "2年", "中期(5年)": "5年", "長期(10年)": "10年"}

DAYS_TO_KEEP = 200  # 約6ヶ月ぶんの営業日を保持


def fetch_jgb_yields():
    """財務省の国債金利情報CSV(全期間)を取得し、直近分だけ切り出す"""
    resp = requests.get(MOF_JGB_CSV_ALL_URL, timeout=30)
    resp.raise_for_status()

    # Shift-JIS(CP932)でエンコードされている想定
    text = resp.content.decode("cp932", errors="replace")
    lines = text.splitlines()

    # ヘッダー行(「基準日」を含む行)を探す
    header_idx = None
    for i, line in enumerate(lines):
        if "基準日" in line:
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("財務省CSVのヘッダー行が見つかりませんでした")

    csv_text = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_text))
    df.columns = [c.strip() for c in df.columns]

    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", format="%Y/%m/%d")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    df = df.tail(DAYS_TO_KEEP)

    result = {}
    for label, col_name in JGB_TARGET_COLUMNS.items():
        if col_name not in df.columns:
            print(f"[warn] 列 '{col_name}' が見つかりませんでした。利用可能な列: {list(df.columns)}")
            continue
        series = pd.to_numeric(df[col_name], errors="coerce")
        valid = series.notna()
        result[label] = {
            "dates": [d.strftime("%Y-%m-%d") for d in df.loc[valid, date_col]],
            "values": [round(float(v), 3) for v in series[valid]],
        }
    return result


def fetch_cgpi():
    """日銀の時系列統計データAPIから国内企業物価指数(総平均)を取得する"""
    params = {
        "format": "json",
        "lang": "jp",
        "db": "PR01",
        "code": CGPI_SERIES_CODE,
        "startDate": "201501",
    }
    resp = requests.get(BOJ_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("STATUS") != 200:
        raise RuntimeError(f"日銀APIエラー: {data.get('MESSAGE')}")

    resultset = data.get("RESULTSET")
    if not resultset:
        raise RuntimeError(f"日銀APIのレスポンス構造が想定と異なります: {json.dumps(data)[:500]}")

    # RESULTSETが単一オブジェクトの場合とリストの場合の両方に対応
    entry = resultset[0] if isinstance(resultset, list) else resultset

    dates_raw = entry.get("SURVEY_DATES") or entry.get("DATES")
    values_raw = entry.get("VALUES")
    if not dates_raw or not values_raw:
        raise RuntimeError(f"日銀APIのデータ部が見つかりませんでした: {json.dumps(entry)[:500]}")

    dates = []
    for d in dates_raw:
        d = str(d)
        dates.append(f"{d[:4]}-{d[4:6]}")  # YYYYMM -> YYYY-MM

    values = [None if v is None else round(float(v), 2) for v in values_raw]

    return {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}


def main():
    os.makedirs(os.path.dirname(OUT_JGB_PATH), exist_ok=True)

    try:
        jgb = fetch_jgb_yields()
        with open(OUT_JGB_PATH, "w", encoding="utf-8") as f:
            json.dump(jgb, f, ensure_ascii=False)
        print(f"Saved JGB yields ({len(jgb)}系列) -> {OUT_JGB_PATH}")
    except Exception as e:
        print(f"[error] 国債利回りの取得に失敗しました: {e}")

    try:
        cgpi = fetch_cgpi()
        with open(OUT_CGPI_PATH, "w", encoding="utf-8") as f:
            json.dump(cgpi, f, ensure_ascii=False)
        print(f"Saved CGPI -> {OUT_CGPI_PATH}")
    except Exception as e:
        print(f"[error] 企業物価指数の取得に失敗しました: {e}")


if __name__ == "__main__":
    main()
