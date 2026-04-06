#!/usr/bin/env python3
"""
JaJa Daily 资讯抓取脚本
两大板块：
  - 餐饮 & 零售：餐饮动态、零售动态、商业洞察、电商
  - AI & 科技：大模型、AI产品、AI Agent、AIGC、AI算力、AI投融资
数据源（RSS）：
  - IT之家 RSS    -> 60 条/次，含正文摘要
  - 少数派 RSS    -> 10 条/次，含简短摘要
  - 机器之心 RSS  -> AI 专项
  - 36氪 RSS      -> 餐饮零售 + AI 科技
  - 钛媒体 RSS    -> 科技/商业/消费
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

# -- 两大板块关键词 -------------------------------------------------------------

# 餐饮 & 零售板块关键词
FNB_KEYWORDS = [
    "餐饮", "餐厅", "饭店", "外卖", "堂食", "连锁", "加盟", "开店",
    "零售", "商超", "便利店", "超市", "卖场", "门店",
    "茶饮", "咖啡", "奶茶", "烘焙", "快餐", "火锅",
    "麦当劳", "肯德基", "星巴克", "瑞幸", "蜜雪", "海底捞",
    "消费", "品牌", "选址", "坪效", "翻台", "客单价",
    "新零售", "即时零售", "到家", "到店",
    "食品", "饮料", "酒水", "生鲜", "预制菜", "团餐",
    "商业地产", "购物中心", "商场", "街区", "社区商业",
    "消费升级", "消费降级", "下沉市场", "县城", "乡镇",
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
    "SUV", "轿车", "续航", "纯电", "新能源汽车", "发布会", "预售",
    "别克", "比亚迪", "特斯拉", "小鹏", "理想", "蔚来", "问界", "极氪",
    "CLTC", "WLTC", "充电桩", "车型", "经销商",
    # 汇总帖
    "IT早报", "派早报",
]

# 每板块目标条数
FNB_TARGET   = 4   # 餐饮&零售
AI_TARGET    = 6   # AI&科技
TARGET_COUNT = FNB_TARGET + AI_TARGET  # 共 10 条

CST = timezone(timedelta(hours=8))

# -- 来源元信息 -----------------------------------------------------------------

SOURCE_META = {
    "ithome.com":       {"name": "IT之家",   "icon": "🟢"},
    "sspai.com":        {"name": "少数派",   "icon": "🔵"},
    "jiqizhixin.com":   {"name": "机器之心", "icon": "🟣"},
    "36kr.com":         {"name": "36氪",     "icon": "🔵"},
    "tmtpost.com":      {"name": "钛媒体",   "icon": "🟠"},
    "huxiu.com":        {"name": "虎嗅",     "icon": "🟠"},
    "wallstreetcn.com": {"name": "华尔街见闻","icon": "🟡"},
    "thepaper.cn":      {"name": "澎湃新闻", "icon": "🟣"},
    "jiemian.com":      {"name": "界面新闻", "icon": "🟤"},
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
          "购物中心", "商场", "街区", "社区商业", "商业地产"], "零售动态"),
        (["消费", "品牌", "选址", "坪效", "翻台", "客单价", "门店", "加盟", "连锁", "开店",
          "消费升级", "消费降级", "下沉市场", "县城", "乡镇",
          "营销", "广告", "投放", "推广", "私域", "增长", "GMV", "转化"], "商业洞察"),
        (["电商", "购物", "带货", "直播", "淘宝", "京东", "拼多多", "外卖"], "电商"),
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

        m_link = re.search(r"<link[^>]*>(.*?)</link>", raw, re.DOTALL)
        if not m_link:
            m_link = re.search(r"<guid[^>]*>(.*?)</guid>", raw, re.DOTALL)
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


# -- 各来源抓取 -----------------------------------------------------------------

def fetch_ithome() -> list:
    print("  [IT之家] 抓取 RSS...", file=sys.stderr)
    rss = fetch_raw("https://www.ithome.com/rss/")
    if not rss:
        return []
    items = parse_rss(rss)
    results = []
    for item in items:
        title = item["title"]
        if is_excluded(title):
            continue
        if is_fnb(title) or is_ai(title):
            summary = extract_summary_from_desc(item["description"], title)
            results.append({"title": title, "url": item["link"], "summary": summary})
    print(f"    -> {len(results)} 条匹配", file=sys.stderr)
    return results


def fetch_sspai() -> list:
    print("  [少数派] 抓取 RSS...", file=sys.stderr)
    rss = fetch_raw("https://sspai.com/feed")
    if not rss:
        return []
    items = parse_rss(rss)
    results = []
    for item in items:
        title = item["title"]
        if is_excluded(title):
            continue
        if is_fnb(title) or is_ai(title):
            summary = extract_summary_from_desc(item["description"], title)
            results.append({"title": title, "url": item["link"], "summary": summary})
    print(f"    -> {len(results)} 条匹配", file=sys.stderr)
    return results


def fetch_jiqizhixin() -> list:
    print("  [机器之心] 抓取 RSS...", file=sys.stderr)
    rss = fetch_raw("https://www.jiqizhixin.com/rss")
    if not rss:
        return []
    items = parse_rss(rss)
    results = []
    for item in items:
        title = item["title"]
        if not title or title in ("机器之心", "Synced"):
            continue
        if is_excluded(title):
            continue
        if is_ai(title):
            summary = extract_summary_from_desc(item["description"], title)
            results.append({"title": title, "url": item["link"], "summary": summary})
    print(f"    -> {len(results)} 条匹配", file=sys.stderr)
    return results


def fetch_36kr() -> list:
    """36氪 RSS — 含餐饮零售和 AI 科技内容"""
    print("  [36氪] 抓取 RSS...", file=sys.stderr)
    rss = fetch_raw("https://36kr.com/feed", timeout=15)
    if not rss:
        return []
    items = parse_rss(rss)
    results = []
    for item in items:
        title = item["title"]
        if is_excluded(title):
            continue
        if is_fnb(title) or is_ai(title):
            summary = extract_summary_from_desc(item["description"], title)
            results.append({"title": title, "url": item["link"], "summary": summary})
    print(f"    -> {len(results)} 条匹配", file=sys.stderr)
    return results


def fetch_tmtpost() -> list:
    """钛媒体 RSS — 科技/商业/消费内容"""
    print("  [钛媒体] 抓取 RSS...", file=sys.stderr)
    rss = fetch_raw("https://www.tmtpost.com/feed", timeout=15)
    if not rss:
        return []
    items = parse_rss(rss)
    results = []
    for item in items:
        title = item["title"]
        if is_excluded(title):
            continue
        if is_fnb(title) or is_ai(title):
            summary = extract_summary_from_desc(item["description"], title)
            results.append({"title": title, "url": item["link"], "summary": summary})
    print(f"    -> {len(results)} 条匹配", file=sys.stderr)
    return results


# -- LLM 摘要增强（可选）--------------------------------------------------------

def enhance_summaries_with_llm(items: list) -> list:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return items
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        need_llm = [(i, item) for i, item in enumerate(items) if item["summary"] == item["title"]]
        if not need_llm:
            return items
        titles_text = "\n".join(f"{i+1}. {item['title']}" for i, item in need_llm)
        prompt = (
            "以下是一批餐饮零售和 AI 科技行业的新闻标题，请为每条标题生成一句话摘要（30-60字）。\n"
            "要求：说清楚「谁做了什么/发生了什么/有什么意义」，语言简洁自然，不要重复标题原文。\n"
            "每条摘要单独一行，格式：序号. 摘要内容\n\n"
            f"标题列表：\n{titles_text}\n\n摘要："
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
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
        for j, (orig_idx, _) in enumerate(need_llm):
            if j < len(summaries) and summaries[j]:
                items[orig_idx]["summary"] = summaries[j]
        print(f"    -> LLM 增强了 {len(need_llm)} 条摘要", file=sys.stderr)
    except Exception as e:
        print(f"  [WARN] LLM 增强失败: {e}", file=sys.stderr)
    return items


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


# -- 主流程 --------------------------------------------------------------------

def main():
    now      = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")

    print(f"\n{'='*50}", file=sys.stderr)
    print(f"  JaJa Daily 抓取  {date_str}", file=sys.stderr)
    print(f"{'='*50}", file=sys.stderr)

    # 1. 多来源抓取
    all_raw = []
    all_raw += fetch_ithome()
    all_raw += fetch_sspai()
    all_raw += fetch_jiqizhixin()
    all_raw += fetch_36kr()
    all_raw += fetch_tmtpost()

    # 2. 去重
    candidates = merge_and_dedupe(all_raw)
    print(f"\n  去重后候选：{len(candidates)} 条", file=sys.stderr)

    # 3. 按板块分配：餐饮&零售 4 条 + AI&科技 6 条
    fnb_pool = [c for c in candidates if is_fnb(c["title"])]
    ai_pool  = [c for c in candidates if is_ai(c["title"]) and not is_fnb(c["title"])]

    fnb_items = fnb_pool[:FNB_TARGET]
    ai_items  = ai_pool[:AI_TARGET]

    # 如果某板块不足，从另一板块补充
    total = len(fnb_items) + len(ai_items)
    if total < TARGET_COUNT:
        remaining = [c for c in candidates if c not in fnb_items and c not in ai_items]
        ai_items += remaining[:TARGET_COUNT - total]

    print(f"  餐饮&零售：{len(fnb_items)} 条，AI&科技：{len(ai_items)} 条", file=sys.stderr)

    # 4. 合并：餐饮在前，AI 在后
    selected = fnb_items + ai_items

    # 5. 补充 source / tag 字段
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

    # 6. LLM 增强（可选）
    print(f"  [摘要] 处理 {len(items)} 条...", file=sys.stderr)
    items = enhance_summaries_with_llm(items)

    # 7. 加序号
    for i, item in enumerate(items, 1):
        item["id"] = i

    output = {
        "date":         date_str,
        "generated_at": now.isoformat(),
        "category":     "餐饮零售 & AI科技",
        "total":        len(items),
        "items":        items,
    }

    # 8. 保存
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
