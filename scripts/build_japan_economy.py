# -*- coding: utf-8 -*-
"""
日本国債利回り(財務省)と国内企業物価指数(FRED公的データ)を取得する。
GitHub Actions等の海外クラウドサーバーからでも100%ブロックされずに動作。

出力:
- data/jgb_yields.json
- data/cgpi.json
"""
import csv
import json
import os
import re
import ssl
import urllib.request

try:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    CURRENT_DIR = os.getcwd()

BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..")) if os.path.basename(CURRENT_DIR) == "scripts" else CURRENT_DIR
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUT_JGB_PATH = os.path.join(DATA_DIR, "jgb_yields.json")
OUT_CGPI_PATH = os.path.join(DATA_DIR, "cgpi.json")

# 国債URL (財務省)
MOF_JGB_ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
MOF_JGB_CURRENT_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"

# 国内企業物価指数URL (GitHub Actionsから100%取得可能な公式配信元)
CGPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=JPNPPIALLMINMEI"

JGB_TARGET_COLUMNS = {"短期(2年)": "2年", "中期(5年)": "5年", "長期(10年)": "10年"}
DAYS_TO_KEEP = 200

SSL_CONTEXT = ssl._create_unverified_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}


def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=25) as res:
        return res.read()


def parse_wareki_date(val):
    if not val:
        return None
    val = val.strip()
    m = re.match(r"^([SHR])(\d+)\.(\d+)$|^([SHR])(\d+)\.(\d+)\.(\d+)$", val)
    if m:
        parts = [p for p in m.groups() if p is not None]
        era, y, m_num = parts[0], int(parts[1]), int(parts[2])
        d = int(parts[3]) if len(parts) > 3 else 1
        year = 1925 + y if era == "S" else (1988 + y if era == "H" else 2018 + y)
        return f"{year:04d}-{m_num:02d}-{d:02d}"

    m2 = re.match(r"^(\d{4})[/-](\d+)[/-](\d+)$", val)
    if m2:
        year, m_num, d = map(int, m2.groups())
        return f"{year:04d}-{m_num:02d}-{d:02d}"
    return None


def fetch_jgb_yields():
    """過去＋最新の国債利回りを結合取得"""
    daily_records = {}

    def parse_csv(raw):
        text = raw.decode("cp932", errors="replace")
        lines = text.splitlines()
        header_idx = next((i for i, l in enumerate(lines) if "基準日" in l), None)
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
            if date_str not in daily_records:
                daily_records[date_str] = {}
            for label, idx in col_map.items():
                if idx < len(row):
                    val = row[idx].replace("-", "").strip()
                    try:
                        daily_records[date_str][label] = round(float(val), 3)
                    except ValueError:
                        pass

    parse_csv(http_get(MOF_JGB_ALL_URL))
    try:
        parse_csv(http_get(MOF_JGB_CURRENT_URL))
    except Exception:
        pass

    sorted_dates = sorted(daily_records.keys())[-DAYS_TO_KEEP:]
    result = {lbl: {"dates": [], "values": []} for lbl in JGB_TARGET_COLUMNS}
    for d in sorted_dates:
        row = daily_records[d]
        for lbl in JGB_TARGET_COLUMNS:
            if lbl in row:
                result[lbl]["dates"].append(d)
                result[lbl]["values"].append(row[lbl])
    return result


def fetch_cgpi():
    """国内企業物価指数(総平均)を取得"""
    raw = http_get(CGPI_URL)
    text = raw.decode("utf-8", errors="replace")
    dates, values = [], []
    for row in csv.reader(text.splitlines()):
        if not row or len(row) < 2:
            continue
        m = re.match(r"^(\d{4})-(\d{2})", row[0].strip())
        if m:
            yyyy, mm = m.groups()
            if int(yyyy) >= 2015:
                try:
                    val = round(float(row[1].strip()), 2)
                    dates.append(f"{yyyy}-{mm}")
                    values.append(val)
                except ValueError:
                    pass

    if not dates:
        raise RuntimeError("企業物価指数のデータが取得できませんでした")

    return {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}


def main():
    print("=== データ取得処理開始 ===")

    # 国債
    try:
        jgb = fetch_jgb_yields()
        with open(OUT_JGB_PATH, "w", encoding="utf-8") as f:
            json.dump(jgb, f, ensure_ascii=False, indent=2)
        dates = jgb.get("長期(10年)", {}).get("dates", [])
        print(f"[OK] 国債利回り取得完了 ({len(dates)}営業日分, 最新: {dates[-1]})")
    except Exception as e:
        print(f"[ERROR] 国債利回り取得失敗: {e}")

    # 企業物価指数
    try:
        cgpi = fetch_cgpi()
        with open(OUT_CGPI_PATH, "w", encoding="utf-8") as f:
            json.dump(cgpi, f, ensure_ascii=False, indent=2)
        c_dates = cgpi.get("国内企業物価指数(総平均)", {}).get("dates", [])
        c_vals = cgpi.get("国内企業物価指数(総平均)", {}).get("values", [])
        print(f"[OK] 企業物価指数取得完了 ({len(c_dates)}ヶ月分, 最新: {c_dates[-1]} = {c_vals[-1]})")
    except Exception as e:
        print(f"[ERROR] 企業物価指数取得失敗: {e}")

    print("==========================")


if __name__ == "__main__":
    main()
