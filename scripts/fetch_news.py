# -*- coding: utf-8 -*-
"""
複数のRSSソースからニュースを取得し、「政治・経済・国際・社会・IT・AI・科学・論文」
に分類する。スポーツ・芸能は除外する。

国内ニュース系(NHK, JCAST)はタイトルのキーワードでジャンル判定。
IT系サイト(ITmedia, はてなブックマーク, 窓の杜, INTERNET Watch, Publickey, Qiita, wired.jp)
は「AI関連キーワードを含むか」だけ判定し、AI/ITに振り分ける。
GIGAZINEは話題が幅広いため、AI/科学/除外/ITの順で判定する。
ナゾロジー・Science Japanは科学サイトなのでそのまま科学に分類。
論文はarXivの複数分野のRSSから取得する。

各ソースは個別にtry/exceptで囲み、1つ失敗しても他のソースの取得は継続する。
"""
import os
import json
import feedparser
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(BASE_DIR, "data", "news.json")

JST = timezone(timedelta(hours=9))
MAX_ITEMS_PER_CATEGORY = 25

# ==== 除外キーワード(スポーツ・芸能) ====
EXCLUDE_KEYWORDS = [
    "野球", "サッカー", "Jリーグ", "プロ野球", "大相撲", "高校野球", "五輪", "オリンピック",
    "パラリンピック", "ワールドカップ", "W杯", "テニス", "ゴルフ", "バレー", "バスケ",
    "柔道", "駅伝", "マラソン大会", "F1", "競馬", "格闘技", "ボクシング",
    "芸能", "俳優", "女優", "タレント", "アイドル", "歌手", "ドラマ", "映画賞",
    "紅白歌合戦", "お笑い", "コンサート", "ライブ", "アニメ映画",
]

# ==== 国内ニュース(政治/経済/国際/社会)のジャンル判定キーワード ====
DOMESTIC_CATEGORY_KEYWORDS = {
    "政治": [
        "首相", "国会", "衆院", "参院", "内閣", "与党", "野党", "選挙", "法案",
        "自民党", "立憲", "公明党", "維新", "国民民主", "共産党", "外相", "官房長官",
        "防衛相", "財務相", "党首", "総裁選", "国会議員", "知事選", "政府", "閣議",
        "会談", "法改正", "デジタル庁", "省庁", "国政", "議員", "市長選",
    ],
    "経済": [
        "円安", "円高", "株価", "日経平均", "物価", "GDP", "賃上げ", "賃金",
        "決算", "貿易", "輸出", "輸入", "金利", "インフレ", "デフレ", "景気",
        "企業", "経済産業省", "財務省", "税制", "消費税", "半導体", "日銀",
        "倒産", "上場", "投資", "為替", "値上げ", "原油高", "株安", "株高",
        "補正予算", "増税", "減税", "経営", "業績", "赤字", "黒字",
    ],
    "国際": [
        "米大統領", "トランプ", "米国", "アメリカ", "中国", "ロシア", "ウクライナ",
        "EU", "欧州", "欧州連合", "韓国", "北朝鮮", "台湾", "中東", "イスラエル", "国連",
        "首脳会談", "外交", "プーチン", "ゼレンスキー", "パレスチナ", "ガザ",
        "サミット", "G7", "G20", "安保理", "NATO", "関税", "制裁", "紛争", "停戦",
        "難民", "大使館", "WTO", "IMF", "世界銀行",
    ],
    "社会": [
        "逮捕", "事件", "事故", "裁判", "災害", "地震", "台風", "大雨", "避難",
        "教育", "医療", "感染", "厚生労働省", "文部科学省",
        "火災", "死亡", "遺体", "行方不明", "詐欺", "汚職", "不祥事", "不明",
        "学校", "子ども", "高齢者", "労働", "少子化",
    ],
}

# ==== AI関連キーワード ====
AI_KEYWORDS = [
    "AI", "人工知能", "ChatGPT", "GPT", "LLM", "生成AI", "機械学習",
    "深層学習", "ディープラーニング", "OpenAI", "Anthropic", "Claude",
    "Gemini", "Copilot", "大規模言語モデル", "エージェントAI", "AIモデル",
]

# ==== 科学関連キーワード(GIGAZINEの分類用) ====
SCIENCE_KEYWORDS = [
    "宇宙", "天文", "物理学", "化学", "生物学", "考古学", "医学研究", "脳科学",
    "心理学", "進化", "恐竜", "量子", "ゲノム", "遺伝子", "天体", "惑星",
    "ブラックホール", "古生物", "人類学", "言語学", "生態系", "微生物", "NASA",
]


def fetch_feed(url, timeout=15):
    try:
        feed = feedparser.parse(url)
        return feed.entries or []
    except Exception as e:
        print(f"[warn] フィード取得失敗: {url} ({e})")
        return []


def parse_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc).astimezone(JST)
                return dt
            except Exception:
                pass
    return None


def make_item(entry, source_name):
    title = entry.get("title", "").strip()
    if not title:
        return None
    dt = parse_published(entry)
    return {
        "title": title,
        "link": entry.get("link", ""),
        "source": source_name,
        "published": dt.strftime("%Y-%m-%d %H:%M") if dt else None,
        "published_sort": dt.isoformat() if dt else "",
    }


def classify_domestic(title):
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return None
    for category, keywords in DOMESTIC_CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                return category
    return None


def classify_tech(title):
    """IT系サイト向け: AIキーワードがあればAI、なければIT"""
    for kw in AI_KEYWORDS:
        if kw in title:
            return "AI"
    return "IT"


def classify_gigazine(title):
    """GIGAZINEは話題が幅広いため、除外->AI->科学->ITの順で判定"""
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return None
    for kw in AI_KEYWORDS:
        if kw in title:
            return "AI"
    for kw in SCIENCE_KEYWORDS:
        if kw in title:
            return "科学"
    return "IT"


def add_items(buckets, items, category_fn=None, fixed_category=None):
    for item in items:
        if item is None:
            continue
        if fixed_category:
            category = fixed_category
        else:
            category = category_fn(item["title"])
        if category is None:
            continue
        buckets.setdefault(category, []).append(item)


def build_domestic_sources(buckets):
    sources = {
        "NHKニュース": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "JCASTニュース": "https://www.j-cast.com/index.xml",
        "AFPBB News": "http://feeds.afpbb.com/rss/afpbb/afpbbnews",
        "CNN.co.jp": "https://feeds.cnn.co.jp/rss/cnn/cnn.rdf",
    }
    for name, url in sources.items():
        entries = fetch_feed(url)
        print(f"{name}: {len(entries)}件取得")
        items = [make_item(e, name) for e in entries]
        add_items(buckets, items, category_fn=classify_domestic)


def build_nikkei_business(buckets):
    """日経ビジネス電子版の公式RSS。経済ニュースとしてそのまま採用"""
    entries = fetch_feed("https://business.nikkei.com/rss/sns/nb.rdf")
    print(f"日経ビジネス: {len(entries)}件取得")
    items = [make_item(e, "日経ビジネス") for e in entries]
    add_items(buckets, items, fixed_category="経済")


def build_tech_sources(buckets):
    sources = {
        "ITmedia NEWS": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
        "はてなブックマーク(テクノロジー)": "https://b.hatena.ne.jp/entrylist/it.rss",
        "窓の杜": "https://forest.watch.impress.co.jp/data/rss/1.0/wf/feed.rdf",
        "INTERNET Watch": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf",
        "Publickey": "https://www.publickey1.jp/atom.xml",
        "Qiita人気記事": "https://qiita.com/popular-items/feed",
        "WIRED.jp": "https://wired.jp/feed/rss",
    }
    for name, url in sources.items():
        entries = fetch_feed(url)
        print(f"{name}: {len(entries)}件取得")
        items = [make_item(e, name) for e in entries]
        add_items(buckets, items, category_fn=classify_tech)


def build_gigazine(buckets):
    entries = fetch_feed("https://gigazine.net/news/rss_2.0/")
    print(f"GIGAZINE: {len(entries)}件取得")
    items = [make_item(e, "GIGAZINE") for e in entries]
    add_items(buckets, items, category_fn=classify_gigazine)


def build_science_fixed_sources(buckets):
    sources = {
        "ナゾロジー": "https://nazology.kusuguru.co.jp/feed",
        "Science Japan(JST)": "https://sj.jst.go.jp/feed/rss.xml",
    }
    for name, url in sources.items():
        entries = fetch_feed(url)
        print(f"{name}: {len(entries)}件取得")
        items = [make_item(e, name) for e in entries]
        add_items(buckets, items, fixed_category="科学")


def build_arxiv_papers(buckets):
    # 分野を問わず主要カテゴリをいくつか組み合わせる
    categories = {
        "cs.AI": "AI",
        "cs.LG": "機械学習",
        "physics": "物理学",
        "q-bio": "生物学",
        "econ": "経済学",
    }
    for cat, label in categories.items():
        url = f"https://export.arxiv.org/rss/{cat}"
        entries = fetch_feed(url)
        print(f"arXiv({label}): {len(entries)}件取得")
        items = []
        for e in entries[:8]:  # 分野ごとに件数を絞って偏りを防ぐ
            item = make_item(e, f"arXiv({label})")
            items.append(item)
        add_items(buckets, items, fixed_category="論文")


def finalize(buckets):
    result = {}
    for category, items in buckets.items():
        items.sort(key=lambda x: x["published_sort"], reverse=True)
        items = items[:MAX_ITEMS_PER_CATEGORY]
        for item in items:
            item.pop("published_sort", None)
        result[category] = items
    return result


def main():
    buckets = {}
    build_domestic_sources(buckets)
    build_nikkei_business(buckets)
    build_tech_sources(buckets)
    build_gigazine(buckets)
    build_science_fixed_sources(buckets)
    build_arxiv_papers(buckets)

    news = finalize(buckets)

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

