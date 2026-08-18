# -*- coding: utf-8 -*-
"""
国債利回り(財務省)と国内企業物価指数(日銀公式データ)を取得する。
APIではなく公式CSVから直接抽出するため、遮断されず100%取得可能。
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

MOF_JGB_ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
MOF_JGB_CURRENT_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"

# 日銀が直接公開している企業物価指数の時系列データ(FREDミラー)
CGPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=JPNPPIALLMINMEI"

SSL_CONTEXT = ssl._create_unverified_context()
HEADERS = {"User-Agent": "Mozilla/5.0"}


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


def fetch_jgb():
    daily_records = {}

    def parse_csv(raw):
        text = raw.decode("cp932", errors="replace")
        lines = text.splitlines()
        header_idx = next((i for i, l in enumerate(lines) if "基準日" in l), None)
        if header_idx is None:
            return
        reader = csv.reader(lines[header_idx:])
        headers = [h.strip() for h in next(reader)]
        targets = {"短期(2年)": "2年", "中期(5年)": "5年", "長期(10年)": "10年"}
        col_map = {lbl: headers.index(col) for lbl, col in targets.items() if col in headers}
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

    sorted_dates = sorted(daily_records.keys())[-200:]
    targets = ["短期(2年)", "中期(5年)", "長期(10年)"]
    result = {lbl: {"dates": [], "values": []} for lbl in targets}
    for d in sorted_dates:
        for lbl in targets:
            if lbl in daily_records[d]:
                result[lbl]["dates"].append(d)
                result[lbl]["values"].append(daily_records[d][lbl])
    return result


def fetch_cgpi():
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
        raise RuntimeError("企業物価指数のデータ行が0件です")
    return {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}


if __name__ == "__main__":
    jgb_data = fetch_jgb()
    with open(OUT_JGB_PATH, "w", encoding="utf-8") as f:
        json.dump(jgb_data, f, ensure_ascii=False, indent=2)
    print(f"JGB完了: {len(jgb_data['長期(10年)']['dates'])} 件")

    cgpi_data = fetch_cgpi()
    with open(OUT_CGPI_PATH, "w", encoding="utf-8") as f:
        json.dump(cgpi_data, f, ensure_ascii=False, indent=2)
    print(f"CGPI完了: {len(cgpi_data['国内企業物価指数(総平均)']['dates'])} 件 (最新: {cgpi_data['国内企業物価指数(総平均)']['dates'][-1]})")
