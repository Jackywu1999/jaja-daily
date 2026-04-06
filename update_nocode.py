#!/usr/bin/env python3
"""
update_nocode.py
每天生成新闻数据后，通过 CatDesk 浏览器自动化更新 NoCode 项目的 data.json 并重新部署。

用法：
  python3 update_nocode.py                    # 更新今天的数据
  python3 update_nocode.py 2026-04-05         # 更新指定日期的数据

依赖：catdesk browser-action CLI（已内置在 CatDesk 中）
"""

import sys
import json
import subprocess
import time
from datetime import date
from pathlib import Path

# ============================================================
# 配置
# ============================================================
NOCODE_PAGE_ID = "hn9drafk4istvd3r"          # JaJa Daily 前端项目
NOCODE_URL = f"https://nocode.sankuai.com/#/chat?pageId={NOCODE_PAGE_ID}"
CATDESK_BIN = "/Users/jacky/.catpaw/bin/catdesk"
DATA_DIR = Path(__file__).parent / "data"
# ============================================================


def browser(action_json: dict) -> dict:
    """调用 catdesk browser-action"""
    cmd = [CATDESK_BIN, "browser-action", json.dumps(action_json)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"success": False, "error": result.stdout or result.stderr}


def set_textarea(text: str) -> bool:
    """通过 evaluate 设置 textarea 内容"""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    script = (
        f'(function(){{'
        f'var el=document.querySelector("textarea");'
        f'if(!el) return "no textarea";'
        f'el.focus();'
        f'var s=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;'
        f's.call(el,"{escaped}");'
        f'el.dispatchEvent(new Event("input",{{bubbles:true}}));'
        f'return "ok";'
        f'}})()'
    )
    r = browser({"action": "evaluate", "script": script})
    return r.get("data", {}).get("result") == "ok"


def send_message() -> bool:
    """触发 Enter 发送消息"""
    script = (
        '(function(){'
        'var el=document.querySelector("textarea");'
        'if(!el) return "no textarea";'
        'el.focus();'
        'el.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",code:"Enter",keyCode:13,bubbles:true}));'
        'return "sent";'
        '})()'
    )
    r = browser({"action": "evaluate", "script": script})
    return r.get("data", {}).get("result") == "sent"


def wait_for_completion(timeout: int = 120) -> bool:
    """等待 NoCode 生成完成（输入框从 disabled 变为可用）"""
    start = time.time()
    while time.time() - start < timeout:
        r = browser({"action": "snapshot"})
        snap = r.get("data", {}).get("snapshot", "")
        if "textbox [disabled" not in snap and "textbox" in snap:
            return True
        if "生成中" not in snap and "正在生成" not in snap:
            return True
        time.sleep(3)
    return False


def click_deploy() -> bool:
    """点击部署按钮"""
    script = (
        '(function(){'
        'var all=Array.from(document.querySelectorAll("*"));'
        'var btn=all.find(el=>(el.innerText||el.textContent||"").trim()==="部署"&&el.tagName==="DIV"&&el.offsetWidth>0);'
        'if(btn){btn.click();return "clicked";}return "not found";'
        '})()'
    )
    r = browser({"action": "evaluate", "script": script})
    return r.get("data", {}).get("result") == "clicked"


def click_start_deploy() -> bool:
    """点击开始部署按钮（用 input_mouse 模拟）"""
    # 先用 mousePressed/mouseReleased 点击开始部署按钮位置
    browser({"action": "input_mouse", "type": "mousePressed", "x": 1390, "y": 317, "button": "left", "clickCount": 1})
    time.sleep(0.1)
    browser({"action": "input_mouse", "type": "mouseReleased", "x": 1390, "y": 317, "button": "left", "clickCount": 1})
    time.sleep(2)
    # 检查是否成功（弹窗消失）
    r = browser({"action": "snapshot"})
    snap = r.get("data", {}).get("snapshot", "")
    return "开始部署" not in snap


def main():
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = date.today().isoformat()

    data_file = DATA_DIR / f"{target_date}.json"
    if not data_file.exists():
        print(f"[ERROR] 数据文件不存在: {data_file}")
        sys.exit(1)

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[INFO] 更新日期: {target_date}，共 {data['total']} 条")

    # 1. 导航到 NoCode 项目
    print("[1/5] 打开 NoCode 项目...")
    r = browser({"action": "navigate", "url": NOCODE_URL})
    if not r.get("success"):
        print(f"[ERROR] 导航失败: {r}")
        sys.exit(1)
    time.sleep(3)

    # 2. 构造更新指令
    data_json_str = json.dumps(data, ensure_ascii=False)
    # 截断过长的 JSON 避免输入框溢出，用简洁版
    items_simple = []
    for item in data["items"]:
        items_simple.append({
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "summary": item["summary"],
            "tag": item["tag"],
            "id": item["id"]
        })
    payload = {
        "date": data["date"],
        "category": data["category"],
        "total": data["total"],
        "items": items_simple
    }
    payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    msg = f"请把 public/data.json 的内容完整替换为以下数据（不要修改任何代码逻辑）：{payload_str}"

    # 3. 填入消息并发送
    print("[2/5] 填入更新指令...")
    if not set_textarea(msg):
        print("[ERROR] 无法设置输入框内容")
        sys.exit(1)
    time.sleep(1)

    print("[3/5] 发送指令...")
    if not send_message():
        print("[ERROR] 发送失败")
        sys.exit(1)

    # 4. 等待生成完成
    print("[4/5] 等待 NoCode 更新完成（最多 2 分钟）...")
    if not wait_for_completion(120):
        print("[WARN] 等待超时，继续尝试部署")
    else:
        print("      更新完成！")
    time.sleep(3)

    # 5. 触发部署
    print("[5/5] 触发部署...")
    if click_deploy():
        time.sleep(2)
        click_start_deploy()
        print(f"[OK] 部署已触发！")
        print(f"     访问地址: https://newswave-daily-feed.mynocode.host")
    else:
        print("[WARN] 未找到部署按钮，请手动部署")

    print(f"\n✅ 完成！{target_date} 的数据已更新到 NoCode")


if __name__ == "__main__":
    main()
