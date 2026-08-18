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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JGB_PATH = os.path.join(BASE_DIR, "data", "jgb_yields.json")
OUT_CGPI_PATH = os.path.join(BASE_DIR, "data", "cgpi.json")

# 財務省 国債金利CSV（過去全期間）
MOF_JGB_CSV_ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"

# 日銀時系列統計データ検索API（正しいエンドポイント: getData）
BOJ_API_URL = "https://www.stat-search.boj.or.jp/api/v1/getData"
CGPI_SERIES_CODE = "PRCG20_2200000000"  # [国内企業物価指数] 2020年基準 総平均

JGB_TARGET_COLUMNS = {"短期(2年)": "2年", "中期(5年)": "5年", "長期(10年)": "10年"}
DAYS_TO_KEEP = 200  # 直近の営業日数

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_jgb_yields():
    """財務省の国債金利情報CSV(全期間)を取得し、直近分だけ切り出す"""
    resp = requests.get(MOF_JGB_CSV_ALL_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # Shift-JIS(CP932)でデコード
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
    
    # 日付パース（全期間CSVの過去データに元号等が含まれるため format は指定せず柔軟にパース）
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
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
    resp = requests.get(BOJ_API_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # STATUSは文字列("200")で返るため、strで比較
    if str(data.get("STATUS")) != "200":
        raise RuntimeError(f"日銀APIエラー: {data.get('MESSAGE', data)}")

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

    # '-' などの欠損記号対策
    values = []
    for v in values_raw:
        try:
            values.append(round(float(v), 2) if v is not None else None)
        except (ValueError, TypeError):
            values.append(None)

    return {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}


def main():
    os.makedirs(os.path.dirname(OUT_JGB_PATH), exist_ok=True)

    try:
        jgb = fetch_jgb_yields()
        with open(OUT_JGB_PATH, "w", encoding="utf-8") as f:
            json.dump(jgb, f, ensure_ascii=False, indent=2)
        print(f"Saved JGB yields ({len(jgb)}系列) -> {OUT_JGB_PATH}")
    except Exception as e:
        print(f"[error] 国債利回りの取得に失敗しました: {e}")

    try:
        cgpi = fetch_cgpi()
        with open(OUT_CGPI_PATH, "w", encoding="utf-8") as f:
            json.dump(cgpi, f, ensure_ascii=False, indent=2)
        print(f"Saved CGPI -> {OUT_CGPI_PATH}")
    except Exception as e:
        print(f"[error] 企業物価指数の取得に失敗しました: {e}")


if __name__ == "__main__":
    main()
