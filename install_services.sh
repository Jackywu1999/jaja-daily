#!/bin/bash
# 安装每日 AI 资讯服务（开机自启 + 每日定时抓取）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "📦 安装每日 AI 资讯服务..."

# 创建日志目录
mkdir -p "$SCRIPT_DIR/logs"

# 复制 plist 到 LaunchAgents
cp "$SCRIPT_DIR/com.jacky.ainews.server.plist" "$LAUNCH_AGENTS/"
cp "$SCRIPT_DIR/com.jacky.ainews.fetch.plist"  "$LAUNCH_AGENTS/"

# 加载服务
launchctl load "$LAUNCH_AGENTS/com.jacky.ainews.server.plist"
launchctl load "$LAUNCH_AGENTS/com.jacky.ainews.fetch.plist"

echo ""
echo "✅ 安装完成！"
echo ""
echo "  🖥️  API Server  → 已启动，开机自动运行"
echo "  ⏰  每日抓取    → 每天早上 08:00 自动执行"
echo "  🌐  访问页面    → file:///Users/jacky/CatPaw%%20Desk/daily-news/index.html"
echo ""
echo "管理命令："
echo "  停止 server:  launchctl unload ~/Library/LaunchAgents/com.jacky.ainews.server.plist"
echo "  停止定时任务: launchctl unload ~/Library/LaunchAgents/com.jacky.ainews.fetch.plist"
echo "  查看日志:     tail -f '$SCRIPT_DIR/logs/server.log'"
