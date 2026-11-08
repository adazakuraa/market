# -*- coding: utf-8 -*-
"""
銘柄ユニバース(規模区分)の共通定義。

JPXの規模コードは 1=TOPIX Core30, 2=Large70, 4=Mid400, 6=Small 1, 7=Small 2 で、
番号が連続していない。コード番号に依存すると読み違えやすいため、
「規模区分」の名称から区分を判定する。
"""
import re

LARGE_MID_CLASSES = ("core30", "large70", "mid400")   # セクター強度の算出に使う(中〜大型株)
SMALL_CLASS = "small1"                                # スクリーニングにだけ加える小型株
TARGET_CLASSES = LARGE_MID_CLASSES + (SMALL_CLASS,)    # 銘柄一覧に残す区分


def size_class(size_name):
    """規模区分の名称(例: 'TOPIX Mid400', 'TOPIX Small 1')から区分キーを返す。該当なしは None"""
    s = re.sub(r"\s+", "", str(size_name)).lower()
    if "core30" in s:
        return "core30"
    if "large70" in s:
        return "large70"
    if "mid400" in s:
        return "mid400"
    if "small1" in s:
        return "small1"
    if "small2" in s:
        return "small2"
    return None


def add_size_class(master):
    """master(DataFrame)に size_class 列を付けて返す(古いmaster.csvにも対応)"""
    master = master.copy()
    master["size_class"] = master["size"].map(size_class)
    return master
