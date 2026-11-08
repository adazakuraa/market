# -*- coding: utf-8 -*-
"""
JPX公式サイトが無料公開している「東証上場銘柄一覧」Excelをダウンロードし、
- プライム市場の銘柄のみ
- 規模コードが Core30 / Large70 / Mid400（≒中〜大型株、TOPIX500相当）
に絞り込んで data/master.csv を出力する。

アカウント登録不要・APIキー不要。
"""
import io
import os
import re
import sys
from urllib.parse import urljoin

import requests
import pandas as pd

from universe import TARGET_CLASSES, size_class

# 銘柄一覧Excelの掲載ページ。Excel自体のURLはJPX側で時々変わるため、
# このページからリンクを探して取得する。見つからなければ下の固定URLを試す。
JPX_LIST_PAGE_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
JPX_XLS_URL_FALLBACK = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(OUT_DIR, "master.csv")

# 規模区分は universe.py で名称から判定する(JPXの規模コードは 1,2,4,6,7 と飛び番のため)。
# 対象: TOPIX Core30 / Large70 / Mid400(中〜大型株) + Small 1(小型株)。
# Small 2はさらに流動性が乏しくなりがちなため除外。
# 小型株のボラティリティ条件はscreen_stocks.py側で別途フィルタする。


def find_xls_urls():
    """掲載ページから data_j.xls(x) へのリンクを探す。固定URLも候補に含める。"""
    urls = []
    try:
        page = requests.get(JPX_LIST_PAGE_URL, headers=HEADERS, timeout=30)
        page.raise_for_status()
        for href in re.findall(r'href="([^"]+?data_j\.xlsx?)"', page.text):
            full = urljoin(JPX_LIST_PAGE_URL, href)
            if full not in urls:
                urls.append(full)
    except Exception as e:
        print(f"[WARN] 銘柄一覧ページの取得に失敗: {e}")
    if JPX_XLS_URL_FALLBACK not in urls:
        urls.append(JPX_XLS_URL_FALLBACK)
    return urls


def download_xls():
    last_err = None
    for url in find_xls_urls():
        try:
            print(f"Downloading {url} ...")
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            return pd.read_excel(io.BytesIO(resp.content))
        except Exception as e:
            print(f"[WARN] {url} の取得に失敗: {e}")
            last_err = e
    raise RuntimeError(f"銘柄一覧Excelを取得できませんでした: {last_err}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    try:
        df = download_xls()
    except Exception as e:
        # 銘柄一覧はめったに変わらないので、取得できない日は前回の master.csv をそのまま使う
        if os.path.exists(OUT_PATH):
            print(f"[WARN] {e} -> 前回の {OUT_PATH} をそのまま使います")
            return
        raise

    # 列名はJPX側の仕様変更で微妙に変わることがあるので、部分一致で拾う
    def find_col(keyword):
        for c in df.columns:
            if keyword in str(c):
                return c
        raise KeyError(f"列が見つかりません: {keyword}")

    col_code = find_col("コード")
    col_name = find_col("銘柄名")
    col_market = find_col("市場・商品区分")
    col_sector33_code = find_col("33業種コード")
    col_sector33_name = find_col("33業種区分")
    col_size_code = find_col("規模コード")
    col_size_name = find_col("規模区分")

    df = df.rename(columns={
        col_code: "code",
        col_name: "name",
        col_market: "market",
        col_sector33_code: "sector33_code",
        col_sector33_name: "sector33",
        col_size_code: "size_code",
        col_size_name: "size",
    })

    df["code"] = df["code"].astype(str).str.strip()
    df["size_code"] = df["size_code"].astype(str).str.strip()

    # プライム市場のみ
    df = df[df["market"].astype(str).str.contains("プライム", na=False)]

    # TOPIX Core30 + Large70 + Mid400 + Small 1
    df["size_class"] = df["size"].map(size_class)
    df = df[df["size_class"].isin(TARGET_CLASSES)]

    # 業種コードが空（ETFやREIT等）の行を除外
    df = df[df["sector33"].notna() & (df["sector33"].astype(str).str.strip() != "-")]

    df["ticker"] = df["code"] + ".T"

    out = df[["code", "ticker", "name", "market", "sector33_code", "sector33", "size_code", "size", "size_class"]]
    out = out.drop_duplicates(subset=["code"]).reset_index(drop=True)

    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved {len(out)} tickers -> {OUT_PATH}")
    print(out["sector33"].value_counts())


if __name__ == "__main__":
    main()
