# -*- coding: utf-8 -*-
"""
日本国債利回り(財務省公式CSV)と国内企業物価指数(日本銀行API)を取得する。

出力:
- data/jgb_yields.json
- data/cgpi.json
"""
import csv
import json
import os
import re
import urllib.request

# スマホ環境でも安定してプロジェクト直下を特定するパス設定
try:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    CURRENT_DIR = os.getcwd()

BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..")) if os.path.basename(CURRENT_DIR) == "scripts" else CURRENT_DIR
DATA_DIR = os.path.join(BASE_DIR, "data")

OUT_JGB_PATH = os.path.join(DATA_DIR, "jgb_yields.json")
OUT_CGPI_PATH = os.path.join(DATA_DIR, "cgpi.json")

MOF_JGB_CSV_ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
BOJ_API_URL = "https://www.stat-search.boj.or.jp/api/v1/getData?format=json&lang=jp&code=PRCG20_2200000000&startDate=201501"

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
    """財務省CSVの和暦(S49.9.24 / H1.1.8 / R6.1.4)を西暦 YYYY-MM-DD に変換"""
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


def fetch_jgb_yields():
    """財務省の国債金利情報CSV(全期間)を取得"""
    raw = http_get(MOF_JGB_CSV_ALL_URL)
    text = raw.decode("cp932", errors="replace")
    lines = text.splitlines()

    header_idx = next((i for i, line in enumerate(lines) if "基準日" in line), None)
    if header_idx is None:
        raise RuntimeError("財務省CSVのヘッダー行が見つかりませんでした")

    reader = csv.reader(lines[header_idx:])
    headers = [h.strip() for h in next(reader)]

    col_map = {lbl: headers.index(col) for lbl, col in JGB_TARGET_COLUMNS.items() if col in headers}
    result = {k: {"dates": [], "values": []} for k in col_map}

    for row in list(reader)[-DAYS_TO_KEEP:]:
        if not row:
            continue
        date_str = parse_wareki_date(row[0])
        if not date_str:
            continue
        for label, idx in col_map.items():
            if idx < len(row):
                val_str = row[idx].replace("-", "").strip()
                try:
                    val = round(float(val_str), 3)
                    result[label]["dates"].append(date_str)
                    result[label]["values"].append(val)
                except ValueError:
                    pass
    return result


def fetch_cgpi():
    """日銀APIから国内企業物価指数(総平均)を取得"""
    raw = http_get(BOJ_API_URL)
    data = json.loads(raw.decode("utf-8"))

    if str(data.get("STATUS")) != "200":
        raise RuntimeError(f"日銀APIエラー: {data.get('MESSAGE', data)}")

    resultset = data.get("RESULTSET", [])
    entry = resultset[0] if isinstance(resultset, list) else resultset
    dates_raw = entry.get("SURVEY_DATES") or entry.get("DATES", [])
    values_raw = entry.get("VALUES", [])

    dates = [f"{str(d)[:4]}-{str(d)[4:6]}" for d in dates_raw]
    values = []
    for v in values_raw:
        try:
            values.append(round(float(v), 2) if v is not None else None)
        except (ValueError, TypeError):
            values.append(None)

    return {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

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
