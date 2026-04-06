#!/usr/bin/env python3
"""
每日资讯 HTTP API Server
- GET /api/news          → 返回今日资讯 JSON
- GET /api/news?date=YYYY-MM-DD  → 返回指定日期资讯
- GET /api/refresh       → 触发重新抓取（后台执行）
- GET /health            → 健康检查
"""

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import urlparse, parse_qs

PORT = 8765
CST = timezone(timedelta(hours=8))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# ── 数据读取 ──────────────────────────────────────────────────────────────────

def load_news(date_str: str) -> Optional[dict]:
    path = os.path.join(DATA_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取 {path} 失败: {e}", file=sys.stderr)
        return None


def get_today_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


def trigger_fetch(date_str: str):
    """后台触发抓取脚本"""
    script = os.path.join(SCRIPT_DIR, "fetch_news.py")
    print(f"[INFO] 触发抓取 {date_str}...", file=sys.stderr)
    try:
        env = os.environ.copy()
        subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.DEVNULL,
            stderr=sys.stderr,
            env=env,
        )
    except Exception as e:
        print(f"[ERROR] 触发抓取失败: {e}", file=sys.stderr)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class NewsHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{datetime.now(CST).strftime('%H:%M:%S')}] {format % args}", file=sys.stderr)

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # 允许跨域（前端页面调用）
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # ── GET /health ──────────────────────────────────────────────────────
        if path == "/health":
            self.send_json({"status": "ok", "time": datetime.now(CST).isoformat()})
            return

        # ── GET /api/news ────────────────────────────────────────────────────
        if path == "/api/news":
            date_str = params.get("date", [get_today_str()])[0]

            # 校验日期格式
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                self.send_json({"error": "日期格式错误，请使用 YYYY-MM-DD"}, 400)
                return

            data = load_news(date_str)

            if data is None:
                # 数据不存在，触发抓取并返回提示
                today = get_today_str()
                if date_str == today:
                    threading.Thread(target=trigger_fetch, args=(date_str,), daemon=True).start()
                    self.send_json({
                        "date": date_str,
                        "status": "fetching",
                        "message": "数据正在抓取中，请 30 秒后重试",
                        "total": 0,
                        "items": [],
                    }, 202)
                else:
                    self.send_json({
                        "error": f"没有找到 {date_str} 的数据",
                        "date": date_str,
                    }, 404)
                return

            self.send_json(data)
            return

        # ── GET /api/refresh ─────────────────────────────────────────────────
        if path == "/api/refresh":
            today = get_today_str()
            threading.Thread(target=trigger_fetch, args=(today,), daemon=True).start()
            self.send_json({
                "status": "triggered",
                "message": f"已触发 {today} 数据重新抓取，约 1-2 分钟后完成",
                "date": today,
            })
            return

        # ── 静态文件 ─────────────────────────────────────────────────────────
        # / 或 /index.html → 返回 index.html
        static_map = {
            "":            "index.html",
            "/index.html": "index.html",
        }
        static_file = static_map.get(path)
        if static_file:
            file_path = os.path.join(SCRIPT_DIR, static_file)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        # ── 404 ──────────────────────────────────────────────────────────────
        self.send_json({"error": "Not Found", "path": path}, 404)


# ── 启动 ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    server = HTTPServer(("0.0.0.0", PORT), NewsHandler)
    print(f"""
╔══════════════════════════════════════════╗
║       每日资讯 API Server 已启动          ║
╠══════════════════════════════════════════╣
║  http://localhost:{PORT}/api/news          ║
║  http://localhost:{PORT}/api/news?date=... ║
║  http://localhost:{PORT}/api/refresh       ║
║  http://localhost:{PORT}/health            ║
╚══════════════════════════════════════════╝
""", file=sys.stderr)

    # 启动时检查今日数据，没有则自动触发抓取
    today = get_today_str()
    if not os.path.exists(os.path.join(DATA_DIR, f"{today}.json")):
        print(f"[INFO] 今日数据不存在，自动触发抓取...", file=sys.stderr)
        threading.Thread(target=trigger_fetch, args=(today,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server 已停止", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()
