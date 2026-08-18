# -*- coding: utf-8 -*-
"""
日本国債利回り(財務省: 過去＋今月最新を結合)と国内企業物価指数(日銀API: CSV取得)を取得する。

出力:
- data/jgb_yields.json
- data/cgpi.json
"""
import csv
import json
import os
import re
import urllib.request

try:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    CURRENT_DIR = os.getcwd()

BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..")) if os.path.basename(CURRENT_DIR) == "scripts" else CURRENT_DIR
DATA_DIR = os.path.join(BASE_DIR, "data")

OUT_JGB_PATH = os.path.join(DATA_DIR, "jgb_yields.json")
OUT_CGPI_PATH = os.path.join(DATA_DIR, "cgpi.json")

MOF_JGB_ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
MOF_JGB_CURRENT_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"

# 日銀API: 確実にパースできる CSV 形式で取得 (PR01 = 物価指数, PRCG20_2200000000 = 2020年基準 総平均)
BOJ_API_CSV_URL = (
    "https://www.stat-search.boj.or.jp/api/v1/getData"
    "?format=csv&lang=jp&db=PR01&code=PRCG20_2200000000&startDate=201501"
)

JGB_TARGET_COLUMNS = {"短期(2年)": "2年", "中期(5年)": "5年", "長期(10年)": "10年"}
DAYS_TO_KEEP = 200

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
}


def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read()


def parse_wareki_date(val):
    """財務省CSVの和暦(S/H/R)や西暦を YYYY-MM-DD に変換"""
    if not val:
        return None
    val = val.strip()
    m = re.match(r"^([SHR])(\d+)\.(\d+)\.(\d+)$", val)
    if m:
        era, y, m_num, d = m.groups()
        y, m_num, d = int(y), int(m_num), int(d)
        year = 1925 + y if era == "S" else (1988 + y if era == "H" else 2018 + y)
        return f"{year:04d}-{m_num:02d}-{d:02d}"

    m2 = re.match(r"^(\d{4})[/-](\d+)[/-](\d+)$", val)
    if m2:
        year, m_num, d = map(int, m2.groups())
        return f"{year:04d}-{m_num:02d}-{d:02d}"
    return None


def parse_jgb_csv(raw_bytes, data_dict):
    """国債CSVをパースして格納"""
    text = raw_bytes.decode("cp932", errors="replace")
    lines = text.splitlines()

    header_idx = next((i for i, line in enumerate(lines) if "基準日" in line), None)
    if header_idx is None:
        return

    reader = csv.reader(lines[header_idx:])
    headers = [h.strip() for h in next(reader)]
    col_map = {lbl: headers.index(col) for lbl, col in JGB_TARGET_COLUMNS.items() if col in headers}

    for row in reader:
        if not row:
            continue
        date_str = parse_wareki_date(row[0])
        if not date_str:
            continue

        if date_str not in data_dict:
            data_dict[date_str] = {}

        for label, idx in col_map.items():
            if idx < len(row):
                val_str = row[idx].replace("-", "").strip()
                try:
                    data_dict[date_str][label] = round(float(val_str), 3)
                except ValueError:
                    pass


def fetch_jgb_yields():
    """過去CSVと今月最新CSVを結合して取得"""
    daily_records = {}

    try:
        raw_all = http_get(MOF_JGB_ALL_URL)
        parse_jgb_csv(raw_all, daily_records)
    except Exception as e:
        print(f"[warn] 過去国債CSV取得失敗: {e}")

    try:
        raw_cur = http_get(MOF_JGB_CURRENT_URL)
        parse_jgb_csv(raw_cur, daily_records)
    except Exception as e:
        print(f"[warn] 最新国債CSV取得失敗: {e}")

    if not daily_records:
        raise RuntimeError("国債データが取得できませんでした")

    sorted_dates = sorted(daily_records.keys())[-DAYS_TO_KEEP:]
    result = {label: {"dates": [], "values": []} for label in JGB_TARGET_COLUMNS}
    for d in sorted_dates:
        row_vals = daily_records[d]
        for label in JGB_TARGET_COLUMNS:
            if label in row_vals:
                result[label]["dates"].append(d)
                result[label]["values"].append(row_vals[label])

    return result


def fetch_cgpi():
    """日銀APIから国内企業物価指数(総平均)をCSVで取得してパース"""
    raw = http_get(BOJ_API_CSV_URL)
    # 日銀CSVはShift-JISまたはUTF-8で返る
    try:
        text = raw.decode("cp932")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    reader = csv.reader(text.splitlines())

    dates = []
    values = []

    for row in reader:
        if not row or len(row) < 2:
            continue

        col0 = row[0].strip().replace('"', '')
        col1 = row[1].strip().replace('"', '').replace(',', '')

        # "YYYY/MM", "YYYY-MM", "YYYYMM" の日付形式を検出
        m = re.match(r"^(\d{4})[/-]?(\d{2})", col0)
        if m:
            yyyy, mm = m.groups()
            date_str = f"{yyyy}-{mm}"

            try:
                val = round(float(col1), 2)
                dates.append(date_str)
                values.append(val)
            except ValueError:
                continue

    if not dates:
        # デバッグ用: 取れなかった場合は返ってきた内容の先頭を出力
        preview = "\n".join(text.splitlines()[:5])
        raise RuntimeError(f"日銀CSVからデータ行を抽出できませんでした。\nレスポンス先頭:\n{preview}")

    return {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("=== データ取得開始 ===")
    try:
        jgb = fetch_jgb_yields()
        with open(OUT_JGB_PATH, "w", encoding="utf-8") as f:
            json.dump(jgb, f, ensure_ascii=False, indent=2)
        dates = jgb.get("長期(10年)", {}).get("dates", [])
        print(f"◎ 国債利回り取得成功 ({len(dates)}営業日分, 最新: {dates[-1]}) -> {OUT_JGB_PATH}")
    except Exception as e:
        print(f"× 国債利回り失敗: {e}")

    try:
        cgpi = fetch_cgpi()
        with open(OUT_CGPI_PATH, "w", encoding="utf-8") as f:
            json.dump(cgpi, f, ensure_ascii=False, indent=2)
        c_dates = cgpi.get("国内企業物価指数(総平均)", {}).get("dates", [])
        c_vals = cgpi.get("国内企業物価指数(総平均)", {}).get("values", [])
        print(f"◎ 企業物価指数取得成功 ({len(c_dates)}ヶ月分, 最新: {c_dates[-1]} = {c_vals[-1]}) -> {OUT_CGPI_PATH}")
    except Exception as e:
        print(f"× 企業物価指数失敗: {e}")
    print("======================")


if __name__ == "__main__":
    main()
