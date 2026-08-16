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
MAX_ITEMS_PER_SOURCE_PER_CATEGORY = 6  # 1つのソースが1カテゴリを埋め尽くさないための上限

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
        "内閣府", "総務省", "法務省", "外務省", "財務省", "文部科学省", "厚生労働省",
        "農林水産省", "経済産業省", "国土交通省", "環境省", "防衛省", "憲法", "自民",
        "公明", "議会", "施行", "支持率", "給付", "抗議", "規制", "有識者検討会",
        "参院選", "衆院選", "解散", "総選挙", "議席", "過半数", "政権交代", "不信任",
        "政治改革", "本会議", "予算案", "予算委員会", "強行採決", "改憲", "都知事",
    ],
    "経済": [
        "円安", "円高", "株価", "日経平均", "物価", "GDP", "賃上げ", "賃金",
        "決算", "貿易", "輸出", "輸入", "金利", "インフレ", "デフレ", "景気",
        "企業", "経済産業省", "財務省", "税制", "消費税", "半導体", "日銀",
        "倒産", "上場", "投資", "為替", "値上げ", "原油高", "株安", "株高",
        "補正予算", "増税", "減税", "経営", "業績", "赤字", "黒字",
        "消費者", "規制", "税", "景気動向指数", "経済", "利上げ", "利下げ",
        "金融緩和", "ドル円", "NYダウ", "ナスダック", "TOPIX", "東証", "株式市場",
        "先物", "国債", "債券", "仮想通貨", "暗号資産", "ビットコイン", "ETF",
        "REIT", "バブル", "金融庁", "ベースアップ", "ベア", "春闘", "消費者物価指数",
        "好景気", "不景気", "景況感", "短観", "原油価格", "資源", "M&A",
        "買収", "合併", "提携", "自社株買い", "最高益", "リストラ", "人員削減",
        "人手不足", "操業停止", "サプライチェーン", "スタートアップ", "ユニコーン",
        "クラウドファンディング", "DX", "EV", "人工知能", "生成AI", "家計", "貯蓄",
        "ローン", "住宅", "インボイス", "補助金", "給付金", "節約", "初任給",
        "年収の壁", "時給", "キャッシュレス", "不動産", "地価", "コメ",
        "サイバー攻撃", "漏えい", "融資", "関税", "相場", "自給率", "売り上げ",
        "市場", "大企業", "経団連", "減益", "増益", "介入", "中小企業", "転嫁",
    ],
    "国際": [
        "米大統領", "トランプ", "米国", "アメリカ", "中国", "ロシア", "ウクライナ",
        "EU", "欧州", "欧州連合", "韓国", "北朝鮮", "台湾", "中東", "イスラエル", "国連",
        "首脳会談", "外交", "プーチン", "ゼレンスキー", "パレスチナ", "ガザ",
        "サミット", "G7", "G20", "安保理", "NATO", "関税", "制裁", "紛争", "停戦",
        "難民", "大使館", "WTO", "IMF", "世界銀行",
        "イラン", "イラク", "サウジアラビア", "シリア", "インド", "パキスタン",
        "フィリピン", "ベトナム", "タイ", "インドネシア", "ミャンマー", "イギリス",
        "英国", "フランス", "ドイツ", "イタリア", "カナダ", "オーストラリア",
        "豪州", "ブラジル", "メキシコ", "アフリカ", "南米", "東南アジア", "ASEAN",
        "BRICS", "国連事務総長", "FRB", "米高官", "大統領選", "米議会", "上院",
        "下院", "ホワイトハウス", "国務省", "クーデター", "亡命", "デモ", "条約",
        "協定", "地政学", "排他的経済水域", "EEZ", "領有権", "WHO", "アフガニスタン",
        "キューバ", "ホルムズ", "ヨーロッパ", "アジア", "北方領土", "IEA", "基地", "尖閣",
    ],
    "社会": [
        "事件", "事故", "裁判", "災害", "地震", "台風", "大雨", "避難",
        "教育", "医療", "感染", "厚生労働省", "文部科学省",
        "火災", "汚職", "不祥事", "不明",
        "学校", "子ども", "高齢者", "労働", "少子化",
        "大学", "給付", "消費者", "年金", "震度", "震源", "津波", "余震",
        "噴火", "土砂崩れ", "土石流", "氾濫", "浸水", "冠水", "暴風", "突風",
        "竜巻", "猛暑", "酷暑", "熱中症", "豪雪", "大雪", "線状降水帯", "気象庁",
        "特別警報", "警報", "注意報", "避難指示", "帰宅困難", "病院", "医師",
        "看護師", "患者", "救急", "手術", "臨床試験", "ワクチン", "接種",
        "インフルエンザ", "クラスター", "介護", "認知症", "国民健康保険", "処方箋",
        "薬価", "個人情報", "マイナンバー", "貧困", "格差", "豪雨", "環境省",
        "国交省", "停職", "処分",
    ]
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
    source_counts = {}  # (category, source) -> 件数
    for item in items:
        if item is None:
            continue
        if fixed_category:
            category = fixed_category
        else:
            category = category_fn(item["title"])
        if category is None:
            continue

        key = (category, item["source"])
        count = source_counts.get(key, 0)
        if count >= MAX_ITEMS_PER_SOURCE_PER_CATEGORY:
            continue  # このソースはこのカテゴリで上限に達した
        source_counts[key] = count + 1

        buckets.setdefault(category, []).append(item)


def build_domestic_sources(buckets):
    sources = {
        "NHKニュース": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "JCASTニュース": "https://www.j-cast.com/index.xml",
        "CNN.co.jp": "https://feeds.cnn.co.jp/rss/cnn/cnn.rdf",
        "朝日新聞デジタル": "http://rss.asahi.com/rss/asahi/newsheadlines.rdf",
        "毎日新聞": "https://mainichi.jp/rss/etc/mainichi-flash.rss",
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

