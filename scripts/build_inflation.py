# -*- coding: utf-8 -*-
"""
資金配分ページで使う「想定インフレ率」の初期値を、実際の市場データから決める。

使うデータ: 財務省が公表している 10年物の ブレーク・イーブン・インフレ率(BEI)
  BEI = 10年国債(普通の国債)の利回り − 10年物価連動国債の利回り
  = 国債市場が織り込んでいる「今後10年間の平均インフレ率」の見込み。
  過去の物価上昇率(実績)よりも、長期の資産計算に使う「これからのインフレ率」の目安として適している。
  (注: 日本のBEIは物価連動国債の取引が少ないため、実際の期待よりやや低めに出やすいと言われる)

財務省はBEIをPDF(グラフ)で公表しているため、PDFの文字情報から最新値を読み取る。
読み取れなかった場合は、前回取得できた値をそのまま使う(なければ固定の2%を使う)。

出力: data/inflation.json
"""
import io
import json
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta

import requests

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(BASE_DIR, "data", "inflation.json")
JST = timezone(timedelta(hours=9))

MOF_BEI_PDF_URL = "https://www.mof.go.jp/jgbs/topics/bond/10year_inflation-indexed/bei.pdf"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}
VALID_RANGE = (-2.0, 8.0)   # これを外れる値は読み取りミスとみなす

NUM = r"(-?\d{1,2}\.\d{1,4})"
DATE_RE = re.compile(r"(20\d{2})\s*[/年.\-]\s*(\d{1,2})\s*[/月.\-]\s*(\d{1,2})")


def load_previous():
    if not os.path.exists(OUT_PATH):
        return None
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def pdf_text(raw):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    # 全角の数字・記号(２．０７７％ など)を半角にそろえる
    return unicodedata.normalize("NFKC", text)


def parse_bei(text):
    """
    PDFの文字から最新のBEI(%)と日付を読み取る。
    「BEI」という語のすぐ後ろ(または直前)にある数値を候補にし、
    名目利回り・実質利回りも読み取れた場合は「名目 − 実質 ≒ BEI」で検算する。
    """
    flat = re.sub(r"\s+", " ", text)

    def near(label_pattern):
        vals = []
        for m in re.finditer(label_pattern + r"[^0-9\-]{0,30}" + NUM, flat, flags=re.IGNORECASE):
            vals.append(float(m.group(m.lastindex)))
        return vals

    bei_vals = near(r"(BEI|ブレーク・?イーブン・?インフレ率)")
    nominal_vals = near(r"(名目|利付国債|10年利付)")
    real_vals = near(r"(実質|物価連動)")
    bei_vals = [v for v in bei_vals if VALID_RANGE[0] <= v <= VALID_RANGE[1]]

    dates = []
    for m in DATE_RE.finditer(flat):
        try:
            dates.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date())
        except ValueError:
            pass
    latest_date = max(dates).isoformat() if dates else None

    value = None
    if bei_vals:
        # 注記の「最新値」はグラフの説明文の中で最後に出てくることが多いので、最後の候補を使う
        value = bei_vals[-1]
    elif nominal_vals and real_vals:
        value = round(nominal_vals[-1] - real_vals[-1], 3)

    check = None
    if value is not None and nominal_vals and real_vals:
        diff = nominal_vals[-1] - real_vals[-1]
        check = abs(diff - value) <= 0.05
    return value, latest_date, check, {"bei": bei_vals[-5:], "nominal": nominal_vals[-3:], "real": real_vals[-3:]}


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    previous = load_previous()
    try:
        resp = requests.get(MOF_BEI_PDF_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        text = pdf_text(resp.content)
        # 読み取りに失敗したときに原因を調べられるよう、PDFの文字の一部をログに残す
        print("---- BEI PDF text (先頭1500文字) ----")
        print(text[:1500])
        print("---- ここまで ----")
        value, date, check, debug = parse_bei(text)
        print(f"読み取り候補: {debug} / 日付: {date} / 検算: {check}")
        if value is None:
            raise ValueError("PDFからBEIの値を読み取れませんでした")
        if check is False:
            raise ValueError(f"BEI {value} が 名目−実質 と一致しません({debug})")
        payload = {
            "status": "ok",
            "value": round(value, 3),
            "date": date,
            "source": "財務省 10年ブレーク・イーブン・インフレ率(BEI)",
            "source_url": MOF_BEI_PDF_URL,
            "fetched_at": now,
        }
    except Exception as e:
        print(f"[WARN] BEIの取得に失敗: {e}")
        if previous and previous.get("value") is not None:
            payload = dict(previous)
            payload["status"] = "stale"
            payload["last_error"] = f"{now}: {e}"
            print(f"前回の値 {previous['value']}%（{previous.get('date')}）を引き続き使います")
        else:
            payload = {"status": "unavailable", "value": None, "last_error": f"{now}: {e}"}
            print("前回の値もないため、資金配分ページは固定の初期値を使います")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"Saved -> {OUT_PATH}: {payload.get('value')} ({payload['status']})")
    if payload["status"] != "ok":
        # 値は保存済み(前回値で継続)。読み取りの修正が必要なことを通知するため失敗終了する
        raise SystemExit(1)


if __name__ == "__main__":
    main()
