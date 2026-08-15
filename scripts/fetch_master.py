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
import sys
import requests
import pandas as pd

JPX_XLS_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(OUT_DIR, "master.csv")

# 規模コード: 1=TOPIX Core30, 2=Large70, 3=Mid400, 4=Small1, 5=Small2, 6=対象外/その他
# Small1(小型株)まで対象に含める。Small2はさらに流動性が乏しくなりがちなため除外。
# 小型株のボラティリティ条件はscreen_stocks.py側で別途フィルタする。
TARGET_SIZE_CODES = {"1", "2", "3", "4"}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Downloading {JPX_XLS_URL} ...")
    resp = requests.get(JPX_XLS_URL, timeout=60)
    resp.raise_for_status()

    df = pd.read_excel(io.BytesIO(resp.content))

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

    # 中〜大型株のみ（TOPIX Core30 + Large70 + Mid400）
    df = df[df["size_code"].isin(TARGET_SIZE_CODES)]

    # 業種コードが空（ETFやREIT等）の行を除外
    df = df[df["sector33"].notna() & (df["sector33"].astype(str).str.strip() != "-")]

    df["ticker"] = df["code"] + ".T"

    out = df[["code", "ticker", "name", "market", "sector33_code", "sector33", "size_code", "size"]]
    out = out.drop_duplicates(subset=["code"]).reset_index(drop=True)

    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved {len(out)} tickers -> {OUT_PATH}")
    print(out["sector33"].value_counts())


if __name__ == "__main__":
    main()
