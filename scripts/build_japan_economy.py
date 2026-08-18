# -*- coding: utf-8 -*-
import csv
import io
import json
import os
import re
import sys
import urllib.request

# 保存先ディレクトリ設定（スマホ環境で __file__ が無い場合にも対応）
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUT_JGB_PATH = os.path.join(DATA_DIR, "jgb_yields.json")
OUT_CGPI_PATH = os.path.join(DATA_DIR, "cgpi.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
}


def http_get(url):
    """requestsが無くても動くHTTPリクエスト関数"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.read()


def parse_wareki_date(val):
    """和暦(S49.9.24 / H1.1.8 / R6.1.4)を西暦 YYYY-MM-DD に変換"""
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


def fetch_jgb():
    print("\n[1/2] 財務省から国債利回りを取得中...")
    url = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
    raw_bytes = http_get(url)
    text = raw_bytes.decode("cp932", errors="replace")

    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if "基準日" in line:
            header_idx = i
            break

    if header_idx is None:
        raise Exception("CSV内に『基準日』のヘッダーが見つかりませんでした。")

    reader = csv.reader(lines[header_idx:])
    headers = [h.strip() for h in next(reader)]

    # 必要な列のインデックスを取得 (2年, 5年, 10年)
    targets = {"短期(2年)": "2年", "中期(5年)": "5年", "長期(10年)": "10年"}
    col_map = {}
    for label, col_name in targets.items():
        if col_name in headers:
            col_map[label] = headers.index(col_name)

    result = {k: {"dates": [], "values": []} for k in col_map}

    # 直近200件を保持
    rows = list(reader)[-200:]
    for row in rows:
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

    with open(OUT_JGB_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    latest_date = result["長期(10年)"]["dates"][-1]
    latest_val = result["長期(10年)"]["values"][-1]
    print(f"  -> 国債利回り取得成功！ (最新: {latest_date} 10年債={latest_val}%)")
    print(f"  -> 保存先: {OUT_JGB_PATH}")


def fetch_cgpi():
    print("\n[2/2] 日銀APIから企業物価指数を取得中...")
    url = "https://www.stat-search.boj.or.jp/api/v1/getData?format=json&lang=jp&code=PRCG20_2200000000&startDate=202001"
    raw_bytes = http_get(url)
    data = json.loads(raw_bytes.decode("utf-8"))

    # 日銀のステータスコード判定
    status = str(data.get("STATUS", ""))
    if status != "200":
        raise Exception(f"日銀APIエラーレスポンス: {data.get('MESSAGE', data)}")

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

    result = {"国内企業物価指数(総平均)": {"dates": dates, "values": values}}

    with open(OUT_CGPI_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  -> 企業物価指数取得成功！ (最新: {dates[-1]} = {values[-1]})")
    print(f"  -> 保存先: {OUT_CGPI_PATH}")


if __name__ == "__main__":
    print("=== データ取得テスト開始 ===")
    try:
        fetch_jgb()
    except Exception as e:
        print(f"  [!] 国債取得エラー: {e}")

    try:
        fetch_cgpi()
    except Exception as e:
        print(f"  [!] 企業物価指数取得エラー: {e}")
    print("===========================")
