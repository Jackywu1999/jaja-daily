#!/usr/bin/env python3
"""
JaJa Daily 资讯抓取脚本
两大板块：
  - 餐饮 & 零售：餐饮动态、零售动态、商业洞察、电商
  - AI & 科技：大模型、AI产品、AI Agent、AIGC、AI算力、AI投融资

来源策略（每个来源最多贡献 MAX_PER_SOURCE 条，防止单一来源占满）：
  餐饮零售专属来源：36氪、钛媒体、虎嗅、界面新闻、华尔街见闻
  AI科技专属来源：机器之心、少数派、IT之家
  通用来源（两个板块都可用）：36氪、钛媒体、虎嗅

可选增强：
  - 有 OPENAI_API_KEY 时，用 LLM 重写摘要
输出：data/YYYY-MM-DD.json
"""

import html as html_module
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from typing import Optional

# -- 配置 ----------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 每个来源最多贡献的条数（防止单一来源占满）
MAX_PER_SOURCE = 3

# -- 两大板块关键词 -------------------------------------------------------------

# 餐饮 & 零售板块关键词
FNB_KEYWORDS = [
    "餐饮", "餐厅", "饭店", "外卖", "堂食", "连锁", "加盟", "开店",
    "零售", "商超", "便利店", "超市", "卖场", "门店",
    "茶饮", "咖啡", "奶茶", "烘焙", "快餐", "火锅",
    "麦当劳", "肯德基", "星巴克", "瑞幸", "蜜雪", "海底捞",
    "元气森林", "泡泡玛特", "名创优品", "名创", "优衣库", "无印良品",
    "沃尔玛", "塔吉特", "山姆", "Costco", "好市多",
    "消费品牌", "消费赛道", "消费市场", "消费趋势", "消费复苏",
    "选址", "坪效", "翻台", "客单价",
    "新零售", "即时零售", "到家", "到店",
    "食品", "饮料", "酒水", "生鲜", "预制菜", "团餐",
    "商业地产", "购物中心", "商场", "街区", "社区商业",
    "消费升级", "消费降级", "下沉市场", "县城", "乡镇",
    "电商", "电子商务", "直播带货", "直播电商", "淘宝", "京东", "拼多多",
    "抖音电商", "快手电商", "小红书", "种草",
    "快消", "快消品", "FMCG", "消费品",
]

# AI & 科技板块关键词
AI_KEYWORDS = [
    "AI", "人工智能", "大模型", "ChatGPT", "GPT", "Claude",
    "Gemini", "DeepSeek", "智能体", "AIGC", "Agent", "LLM",
    "模型", "生成式", "机器人", "具身", "算力", "多模态",
    "自动驾驶", "数字人", "AI眼镜", "开源模型",
]

# 排除关键词（命中则丢弃）
EXCLUDE_KEYWORDS = [
    # 硬件外设
    "键盘", "耳机", "鼠标", "显示器", "手机壳", "充电器", "数据线",
    # 财务报告
    "年度报告", "净亏", "净利润", "营业收入",
    # 非相关领域
    "基因芯片", "小麦", "镉", "农业", "卫星", "火箭", "航天",
    "游戏外设", "机械键盘", "矮轴",
    # 汽车
    "SUV", "轿车", "续航", "纯电", "新能源汽车",
    "别克", "比亚迪", "特斯拉", "小鹏", "理想", "蔚来", "问界", "极氪",
    "CLTC", "WLTC", "充电桩", "车型", "经销商",
    # 汇总帖
    "IT早报", "派早报",
    # 投影/音响/智能家居硬件（避免误判为消费品牌）
    "投影仪", "投影机", "激光电视", "智能音箱", "扫地机器人",
    # 金融/证券
    "国债", "收益率", "基点", "A股", "限售股", "解禁", "券商",
    "指数", "期货", "期权", "外汇", "汇率",
    # 医药
    "司美格鲁肽", "处方", "药物", "临床", "制药",
    # 能源
    "碳酸锂", "可再生能源", "光伏", "风电", "储能",
]

# 每板块目标条数
FNB_TARGET   = 5   # 餐饮&零售
AI_TARGET    = 5   # AI&科技
TARGET_COUNT = FNB_TARGET + AI_TARGET  # 共 10 条

CST = timezone(timedelta(hours=8))

# -- 来源元信息 -----------------------------------------------------------------

SOURCE_META = {
    "ithome.com":       {"name": "IT之家",    "icon": "🟢"},
    "sspai.com":        {"name": "少数派",    "icon": "🔵"},
    "jiqizhixin.com":   {"name": "机器之心",  "icon": "🟣"},
    "36kr.com":         {"name": "36氪",      "icon": "🔵"},
    "tmtpost.com":      {"name": "钛媒体",    "icon": "🟠"},
    "huxiu.com":        {"name": "虎嗅",      "icon": "🟠"},
    "wallstreetcn.com": {"name": "华尔街见闻","icon": "🟡"},
    "thepaper.cn":      {"name": "澎湃新闻",  "icon": "🟣"},
    "jiemian.com":      {"name": "界面新闻",  "icon": "🟤"},
}

def get_source_meta(url: str) -> dict:
    for domain, meta in SOURCE_META.items():
        if domain in url:
            return meta
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    domain = m.group(1) if m else url
    return {"name": domain, "icon": "⚪"}


# -- 工具函数 -------------------------------------------------------------------

def fetch_raw(url: str, timeout: int = 15) -> str:
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ct)
            if m:
                charset = m.group(1)
            try:
                return raw.decode(charset, errors="replace")
            except Exception:
                return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] 抓取失败 {url}: {e}", file=sys.stderr)
        return ""


def is_excluded(text: str) -> bool:
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return True
    return False


def is_fnb(text: str) -> bool:
    """是否属于餐饮&零售板块"""
    if is_excluded(text):
        return False
    for kw in FNB_KEYWORDS:
        if kw in text:
            return True
    return False


def is_ai(text: str) -> bool:
    """是否属于 AI&科技板块"""
    if is_excluded(text):
        return False
    text_upper = text.upper()
    for kw in AI_KEYWORDS:
        if kw.upper() in text_upper:
            return True
    return False


def infer_tag(title: str) -> str:
    # 餐饮&零售 tag（优先判断）
    fnb_mapping = [
        (["餐饮", "餐厅", "饭店", "火锅", "快餐", "茶饮", "咖啡", "奶茶", "烘焙",
          "麦当劳", "肯德基", "星巴克", "瑞幸", "蜜雪", "海底捞", "堂食", "外卖连锁",
          "食品", "饮料", "酒水", "生鲜", "预制菜", "团餐"], "餐饮动态"),
        (["零售", "商超", "便利店", "超市", "卖场", "新零售", "即时零售", "到家",
          "购物中心", "商场", "街区", "社区商业", "商业地产",
          "沃尔玛", "塔吉特", "山姆", "Costco", "好市多", "优衣库", "无印良品"], "零售动态"),
        (["消费品牌", "消费赛道", "消费市场", "消费趋势", "消费复苏", "消费升级", "消费降级",
          "元气森林", "泡泡玛特", "名创优品", "名创", "快消品", "消费品",
          "选址", "坪效", "翻台", "客单价", "门店", "加盟", "连锁", "开店",
          "下沉市场", "县城", "乡镇",
          "营销", "广告", "投放", "推广", "私域", "增长", "GMV", "转化"], "商业洞察"),
        (["电商", "电子商务", "购物", "带货", "直播", "淘宝", "京东", "拼多多",
          "抖音电商", "快手电商", "小红书", "种草"], "电商"),
    ]
    for keywords, tag in fnb_mapping:
        for kw in keywords:
            if kw in title:
                return tag

    # AI&科技 tag
    ai_mapping = [
        (["大模型", "LLM", "GPT", "Claude", "Gemini", "DeepSeek", "Llama", "Qwen",
          "模型", "训练", "推理", "多模态"], "大模型"),
        (["Agent", "智能体", "扣子", "Manus", "Coze"], "AI Agent"),
        (["AIGC", "视频生成", "图像生成", "文生图", "文生视频", "Sora", "可灵", "数字人"], "AIGC"),
        (["融资", "估值", "投资", "亿美元", "亿元", "IPO", "上市", "收购"], "AI投融资"),
        (["政策", "监管", "备案", "法规", "合规", "治理", "安全"], "政策监管"),
        (["开源", "GitHub", "开放源", "开放模型"], "开源"),
        (["机器人", "人形", "具身", "Physical AI", "自动驾驶", "无人"], "机器人"),
        (["芯片", "算力", "GPU", "NPU", "英伟达", "华为昇腾"], "AI算力"),
    ]
    for keywords, tag in ai_mapping:
        for kw in keywords:
            if kw in title:
                return tag
    return "AI产品"


def clean_html_text(raw: str) -> str:
    text = html_module.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# -- RSS 通用解析 ---------------------------------------------------------------

def parse_rss(rss_text: str) -> list:
    items = []
    raw_items = re.findall(r"<item[^>]*>(.*?)</item>", rss_text, re.DOTALL)
    for raw in raw_items:
        m_title = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, re.DOTALL)
        title = clean_html_text(m_title.group(1)) if m_title else ""

        m_link = re.search(r"<link[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", raw, re.DOTALL)
        if not m_link:
            m_link = re.search(r"<guid[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</guid>", raw, re.DOTALL)
        link = (m_link.group(1).strip() if m_link else "").strip()

        m_desc = re.search(r"<description[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", raw, re.DOTALL)
        if not m_desc:
            m_desc = re.search(r"<summary[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</summary>", raw, re.DOTALL)
        desc_raw = m_desc.group(1) if m_desc else ""
        description = clean_html_text(desc_raw)

        m_date = re.search(r"<pubDate[^>]*>(.*?)</pubDate>", raw, re.DOTALL)
        pub_date = m_date.group(1).strip() if m_date else ""

        if title and link and link.startswith("http"):
            items.append({
                "title":       title,
                "link":        link,
                "description": description,
                "pub_date":    pub_date,
            })
    return items


def extract_summary_from_desc(desc: str, title: str, max_len: int = 100) -> str:
    if not desc:
        return title
    desc = re.sub(r"^IT之家\s*\d+\s*月\s*\d+\s*日消息[，,]\s*", "", desc)
    desc = re.sub(r"^据[^，。]{2,15}[报道称]+[，,]\s*", "", desc)
    desc = re.sub(r"\s*IT之家注[：:].*$", "", desc, flags=re.DOTALL)
    desc = re.sub(r"\s*IT之家从[^。]{2,30}获悉[，,]?", "", desc)
    desc = re.sub(r"\s*查看全文\s*$", "", desc).strip()
    desc = re.sub(r"\s*（\s*$", "", desc).strip()
    desc = re.sub(r"\s{2,}", " ", desc).strip()
    desc = re.sub(r" ([^。！？，、]{2,20}) ", r"\1", desc)
    if desc.strip() == title.strip() or len(desc) < 10:
        return title
    if len(desc) > max_len:
        for i in range(max_len, max(max_len - 40, 20), -1):
            if i < len(desc) and desc[i] in "。！？":
                return desc[:i + 1]
        return desc[:max_len] + "…"
    return desc


# -- 通用 RSS 抓取（带来源标记）-------------------------------------------------

def fetch_source(name: str, url: str, fnb_only: bool = False, ai_only: bool = False) -> list:
    """
    通用 RSS 抓取函数。
    fnb_only=True  → 只抓餐饮零售
    ai_only=True   → 只抓 AI 科技
    两者都 False   → 两个板块都抓
    返回的每条记录带 _source_name 字段，用于后续限流。
    """
    print(f"  [{name}] 抓取 RSS...", file=sys.stderr)
    rss = fetch_raw(url, timeout=15)
    if not rss:
        return []
    items = parse_rss(rss)
    results = []
    for item in items:
        title = item["title"]
        # 机器之心 RSS 有时会有空标题或来源名作标题
        if not title or title in ("机器之心", "Synced"):
            continue
        if is_excluded(title):
            continue
        match = False
        if fnb_only and is_fnb(title):
            match = True
        elif ai_only and is_ai(title):
            match = True
        elif not fnb_only and not ai_only and (is_fnb(title) or is_ai(title)):
            match = True
        if match:
            summary = extract_summary_from_desc(item["description"], title)
            results.append({
                "title":        title,
                "url":          item["link"],
                "summary":      summary,
                "_source_name": name,   # 用于来源限流
            })
    print(f"    -> {len(results)} 条匹配", file=sys.stderr)
    return results


# -- LLM 摘要增强（可选）--------------------------------------------------------

def enhance_summaries_with_llm(items: list) -> list:
    """为所有条目生成/补全摘要（40-80字，两行以内）。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return items
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        all_items_text = "\n".join(
            f"{i+1}. 标题：{item['title']}\n   原摘要：{item['summary'] if item['summary'] != item['title'] else '（无）'}"
            for i, item in enumerate(items)
        )
        prompt = (
            "以下是一批餐饮零售和 AI 科技行业的新闻，请为每条新闻生成一段摘要（40-80字）。\n"
            "要求：\n"
            "1. 说清楚「谁做了什么/发生了什么/有什么意义」\n"
            "2. 语言简洁自然，不要重复标题原文\n"
            "3. 如果原摘要已经足够好，可以在其基础上润色扩充\n"
            "4. 每条摘要控制在40-80字，对应约两行显示\n"
            "5. 每条摘要单独一行，格式：序号. 摘要内容\n\n"
            f"新闻列表：\n{all_items_text}\n\n摘要："
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        summaries = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^\d+[\.、。]\s*", "", line).strip()
            if cleaned:
                summaries.append(cleaned)
        for i, item in enumerate(items):
            if i < len(summaries) and summaries[i]:
                items[i]["summary"] = summaries[i]
        print(f"    -> LLM 增强了 {len(items)} 条摘要", file=sys.stderr)
    except Exception as e:
        print(f"  [WARN] LLM 增强失败: {e}", file=sys.stderr)
    return items


def generate_editor_note(items: list) -> str:
    """用 LLM 生成碎碎念总结，无 API Key 时降级为简单拼接。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    fnb_items = [i for i in items if i.get("tag") in ['餐饮动态','零售动态','商业洞察','电商']]
    ai_items  = [i for i in items if i.get("tag") not in ['餐饮动态','零售动态','商业洞察','电商']]

    if not api_key:
        sentence = f"今天共精选 {len(items)} 条。"
        if fnb_items:
            sentence += f"餐饮零售板块：{fnb_items[0]['title'][:20]}等话题值得关注；"
        if ai_items:
            sentence += f"AI科技板块：{ai_items[0]['title'][:20]}等动态持续发酵。"
        return sentence

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        titles = "\n".join(f"- [{item['tag']}] {item['title']}" for item in items)
        prompt = (
            f"以下是今日精选的 {len(items)} 条餐饮零售和AI科技资讯标题：\n{titles}\n\n"
            "请以'小ja'的口吻，写一段今日资讯的总结性点评（80-120字）。\n"
            "要求：\n"
            "1. 提炼今日最值得关注的1-2个餐饮零售趋势和1-2个AI科技动态\n"
            "2. 语气轻松自然，像朋友间的分享，不要太正式\n"
            "3. 不要用'今天共精选X条'这种模板句式开头\n"
            "4. 控制在80-120字"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        note = resp.choices[0].message.content.strip()
        print(f"    -> LLM 生成碎碎念完成", file=sys.stderr)
        return note
    except Exception as e:
        print(f"  [WARN] 碎碎念生成失败: {e}", file=sys.stderr)
        sentence = f"今天共精选 {len(items)} 条。"
        if fnb_items:
            sentence += f"餐饮零售：{fnb_items[0]['title'][:20]}等话题值得关注；"
        if ai_items:
            sentence += f"AI科技：{ai_items[0]['title'][:20]}等动态持续发酵。"
        return sentence


# -- 去重合并 -------------------------------------------------------------------

def merge_and_dedupe(sources: list) -> list:
    seen_titles = set()
    seen_urls   = set()
    merged = []
    for item in sources:
        title = item.get("title", "").strip()
        url   = item.get("url", "").strip()
        key   = title[:20]
        if key in seen_titles or url in seen_urls:
            continue
        seen_titles.add(key)
        seen_urls.add(url)
        merged.append(item)
    return merged


def pick_with_source_limit(pool: list, target: int, max_per_source: int = MAX_PER_SOURCE) -> list:
    """
    从 pool 中按顺序选取 target 条，每个来源最多贡献 max_per_source 条。
    """
    source_count: dict = {}
    selected = []
    for item in pool:
        src = item.get("_source_name", "unknown")
        if source_count.get(src, 0) >= max_per_source:
            continue
        source_count[src] = source_count.get(src, 0) + 1
        selected.append(item)
        if len(selected) >= target:
            break
    return selected


# -- 主流程 --------------------------------------------------------------------

def main():
    now      = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")

    print(f"\n{'='*50}", file=sys.stderr)
    print(f"  JaJa Daily 抓取  {date_str}", file=sys.stderr)
    print(f"{'='*50}", file=sys.stderr)

    # ----------------------------------------------------------------
    # 1. 分池抓取
    #    餐饮零售专属来源：36氪、钛媒体、虎嗅、界面新闻、华尔街见闻
    #    AI科技专属来源：机器之心、少数派、IT之家
    #    通用来源（两个板块都可用）：36氪、钛媒体、虎嗅（已在餐饮池中，AI 池也加入）
    # ----------------------------------------------------------------

    print("\n[餐饮零售] 专属来源抓取...", file=sys.stderr)
    fnb_raw = []
    fnb_raw += fetch_source("36氪",      "https://36kr.com/feed",                    fnb_only=True)
    fnb_raw += fetch_source("钛媒体",    "https://www.tmtpost.com/feed",              fnb_only=True)
    fnb_raw += fetch_source("虎嗅",      "https://www.huxiu.com/rss/0.xml",           fnb_only=True)
    fnb_raw += fetch_source("界面新闻",  "https://www.jiemian.com/lists/rss.html",    fnb_only=True)
    fnb_raw += fetch_source("华尔街见闻","https://wallstreetcn.com/feed",             fnb_only=True)

    print("\n[AI科技] 专属来源抓取...", file=sys.stderr)
    ai_raw = []
    ai_raw += fetch_source("机器之心",  "https://www.jiqizhixin.com/rss",             ai_only=True)
    ai_raw += fetch_source("少数派",    "https://sspai.com/feed",                     ai_only=True)
    ai_raw += fetch_source("IT之家",    "https://www.ithome.com/rss/",                ai_only=True)
    # 通用来源也补充 AI 内容（36氪/钛媒体/虎嗅 AI 报道也很多）
    ai_raw += fetch_source("36氪",      "https://36kr.com/feed",                      ai_only=True)
    ai_raw += fetch_source("钛媒体",    "https://www.tmtpost.com/feed",               ai_only=True)
    ai_raw += fetch_source("虎嗅",      "https://www.huxiu.com/rss/0.xml",            ai_only=True)

    # 2. 各自去重
    fnb_candidates = merge_and_dedupe(fnb_raw)
    ai_candidates  = merge_and_dedupe(ai_raw)

    print(f"\n  餐饮候选：{len(fnb_candidates)} 条，AI候选：{len(ai_candidates)} 条", file=sys.stderr)

    # 3. 每个来源限流，各取目标条数
    fnb_items = pick_with_source_limit(fnb_candidates, FNB_TARGET)
    ai_items  = pick_with_source_limit(ai_candidates,  AI_TARGET)

    # 4. 餐饮不足时：放宽关键词，从餐饮候选中再捞（不限来源）
    if len(fnb_items) < FNB_TARGET:
        already_urls = {i["url"] for i in fnb_items}
        extra_pool = [
            c for c in fnb_candidates
            if c["url"] not in already_urls
            and any(kw in c["title"] for kw in [
                "消费", "品牌", "门店", "市场", "商业", "零售",
                "食品", "饮品", "外卖", "电商", "购物", "连锁",
            ])
        ]
        need = FNB_TARGET - len(fnb_items)
        fnb_items += pick_with_source_limit(extra_pool, need)
        print(f"  [补充] 餐饮放宽关键词后：{len(fnb_items)} 条", file=sys.stderr)

    # 5. 仍不足时，两个板块互补（保证总数达标）
    total = len(fnb_items) + len(ai_items)
    if total < TARGET_COUNT:
        # 把 AI 候选中未被选中的拿来补餐饮（或反之）
        all_used_urls = {i["url"] for i in fnb_items + ai_items}
        remaining_ai  = [c for c in ai_candidates  if c["url"] not in all_used_urls]
        remaining_fnb = [c for c in fnb_candidates if c["url"] not in all_used_urls]
        if len(fnb_items) < len(ai_items):
            fnb_items += pick_with_source_limit(remaining_ai + remaining_fnb, TARGET_COUNT - total)
        else:
            ai_items  += pick_with_source_limit(remaining_fnb + remaining_ai, TARGET_COUNT - total)

    print(f"\n  最终：餐饮&零售 {len(fnb_items)} 条，AI&科技 {len(ai_items)} 条", file=sys.stderr)

    # 来源分布统计
    def source_dist(items):
        dist: dict = {}
        for i in items:
            s = i.get("_source_name", "?")
            dist[s] = dist.get(s, 0) + 1
        return dist
    print(f"  餐饮来源分布：{source_dist(fnb_items)}", file=sys.stderr)
    print(f"  AI来源分布：{source_dist(ai_items)}",   file=sys.stderr)

    # 6. 合并：餐饮在前，AI 在后
    selected = fnb_items + ai_items

    # 7. 补充 source / tag 字段（去掉内部用的 _source_name）
    items = []
    for item in selected:
        source_meta = get_source_meta(item["url"])
        items.append({
            "title":       item["title"],
            "url":         item["url"],
            "source":      source_meta["name"],
            "source_icon": source_meta["icon"],
            "summary":     item.get("summary", item["title"]),
            "tag":         infer_tag(item["title"]),
        })

    # 8. LLM 增强摘要（所有条目）
    print(f"\n  [摘要] 处理 {len(items)} 条...", file=sys.stderr)
    items = enhance_summaries_with_llm(items)

    # 9. 生成碎碎念
    print(f"  [碎碎念] 生成总结...", file=sys.stderr)
    editor_note = generate_editor_note(items)

    # 10. 加序号
    for i, item in enumerate(items, 1):
        item["id"] = i

    output = {
        "date":         date_str,
        "generated_at": now.isoformat(),
        "category":     "餐饮零售 & AI科技",
        "total":        len(items),
        "editor_note":  editor_note,
        "items":        items,
    }

    # 11. 保存
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir   = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    out_path   = os.path.join(data_dir, f"{date_str}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！共 {len(items)} 条（餐饮{len(fnb_items)}+AI{len(ai_items)}），已保存到 {out_path}", file=sys.stderr)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
