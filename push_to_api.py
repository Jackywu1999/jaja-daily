#!/usr/bin/env python3
"""
push_to_api.py
每天生成新闻数据后，自动推送到 NoCode 后端 API。

用法：
  python3 push_to_api.py                    # 推送今天的数据
  python3 push_to_api.py 2026-04-05         # 推送指定日期的数据
"""

import sys
import json
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

# ============================================================
# 配置：部署后填入 NoCode 后端服务的地址
# ============================================================
API_URL = "https://YOUR_NOCODE_BACKEND.mynocode.host/api/daily-news"
# ============================================================

DATA_DIR = Path(__file__).parent / "data"


def push_data(target_date: str) -> bool:
    """读取指定日期的 JSON 文件并推送到 API。"""
    data_file = DATA_DIR / f"{target_date}.json"

    if not data_file.exists():
        print(f"[ERROR] 数据文件不存在: {data_file}")
        return False

    with open(data_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "JaJaDaily-Pusher/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            resp_body = resp.read().decode("utf-8")
            print(f"[OK] 推送成功 {target_date} → HTTP {status}")
            print(f"     响应: {resp_body[:200]}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason}")
        print(f"        {e.read().decode('utf-8')[:200]}")
        return False
    except urllib.error.URLError as e:
        print(f"[ERROR] 网络错误: {e.reason}")
        return False


def main():
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = date.today().isoformat()

    print(f"[INFO] 推送日期: {target_date}")
    print(f"[INFO] 目标 API: {API_URL}")

    if API_URL.startswith("https://YOUR_NOCODE"):
        print("[WARN] 请先在脚本顶部填入真实的 API_URL！")
        sys.exit(1)

    success = push_data(target_date)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
