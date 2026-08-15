# -*- coding: utf-8 -*-
"""
NHKニュース(全件RSS)と日本銀行(公式RSS)からニュースを取得し、
タイトルのキーワードで「政治・経済・国際・社会・日銀」に分類する。
スポーツ・芸能に該当するキーワードを含む記事は除外する。

出典URL:
- NHKニュース(全件): https://news.web.nhk/n-data/conf/na/rss/cat0.xml
- 日本銀行 新着情報: https://www.boj.or.jp/rss/whatsnew.xml
"""
import os
import json
import feedparser
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(BASE_DIR, "data", "news.json")

NHK_RSS_URL = "https://news.web.nhk/n-data/conf/na/rss/cat0.xml"
BOJ_RSS_URL = "https://www.boj.or.jp/rss/whatsnew.xml"

JST = timezone(timedelta(hours=9))

MAX_ITEMS_PER_CATEGORY = 20

# 除外キーワード(スポーツ・芸能)。これに1つでも該当したら分類対象から外す。
EXCLUDE_KEYWORDS = [
    "野球", "サッカー", "Jリーグ", "プロ野球", "大相撲", "高校野球", "五輪", "オリンピック",
    "パラリンピック", "ワールドカップ", "W杯", "テニス", "ゴルフ", "バレー", "バスケ",
    "柔道", "駅伝", "マラソン大会", "F1", "競馬", "格闘技", "ボクシング",
    "芸能", "俳優", "女優", "タレント", "アイドル", "歌手", "ドラマ", "映画賞",
    "紅白歌合戦", "お笑い", "コンサート", "ライブ", "アニメ映画",
]

# カテゴリ判定キーワード(優先順に判定。最初にヒットしたカテゴリを採用)
CATEGORY_KEYWORDS = {
    "政治": [
        "首相", "国会", "衆院", "参院", "内閣", "与党", "野党", "選挙", "法案",
        "自民党", "立憲", "公明党", "維新", "国民民主", "共産党", "外相", "官房長官",
        "防衛相", "財務相", "党首", "総裁選",
    ],
    "経済": [
        "円安", "円高", "株価", "日経平均", "物価", "GDP", "賃上げ", "賃金",
        "決算", "貿易", "輸出", "輸入", "金利", "インフレ", "デフレ", "景気",
        "企業", "経済産業省", "財務省", "税制", "消費税", "半導体",
    ],
    "国際": [
        "米大統領", "トランプ", "米国", "アメリカ", "中国", "ロシア", "ウクライナ",
        "EU", "欧州", "韓国", "北朝鮮", "台湾", "中東", "イスラエル", "国連",
        "首脳会談", "外交", "プーチン", "ゼレンスキー",
    ],
    "社会": [
        "逮捕", "事件", "事故", "裁判", "災害", "地震", "台風", "大雨", "避難",
        "教育", "医療", "感染", "厚生労働省", "文部科学省",
        "火災", "死亡", "遺体", "行方不明", "詐欺", "汚職", "不祥事", "不明",
    ],
}


def fetch_feed(url):
    feed = feedparser.parse(url)
    return feed.entries


def classify(title):
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return None
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                return category
    return None


def parse_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(JST)
            return dt
    return None


def build_nhk_news():
    entries = fetch_feed(NHK_RSS_URL)
    print(f"NHK RSS: {len(entries)}件取得")

    buckets = {cat: [] for cat in CATEGORY_KEYWORDS.keys()}
    for e in entries:
        title = e.get("title", "").strip()
        if not title:
            continue
        category = classify(title)
        if category is None:
            continue
        dt = parse_published(e)
        buckets[category].append({
            "title": title,
            "link": e.get("link", ""),
            "published": dt.strftime("%Y-%m-%d %H:%M") if dt else None,
            "published_sort": dt.isoformat() if dt else "",
        })

    for cat in buckets:
        buckets[cat].sort(key=lambda x: x["published_sort"], reverse=True)
        buckets[cat] = buckets[cat][:MAX_ITEMS_PER_CATEGORY]
        for item in buckets[cat]:
            item.pop("published_sort", None)

    return buckets


def build_boj_news():
    entries = fetch_feed(BOJ_RSS_URL)
    print(f"日銀 RSS: {len(entries)}件取得")

    items = []
    for e in entries:
        title = e.get("title", "").strip()
        if not title:
            continue
        dt = parse_published(e)
        items.append({
            "title": title,
            "link": e.get("link", ""),
            "published": dt.strftime("%Y-%m-%d %H:%M") if dt else None,
            "published_sort": dt.isoformat() if dt else "",
        })

    items.sort(key=lambda x: x["published_sort"], reverse=True)
    items = items[:MAX_ITEMS_PER_CATEGORY]
    for item in items:
        item.pop("published_sort", None)
    return items


def main():
    news = build_nhk_news()
    news["日銀"] = build_boj_news()

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    payload = {"generated_at": now, "categories": news}

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    for cat, items in news.items():
        print(f"{cat}: {len(items)}件")
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()

