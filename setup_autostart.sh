#!/bin/bash
# 在系统 Terminal.app 中运行此脚本来完成开机自启配置
# bash ~/ainews/setup_autostart.sh

echo "🚀 配置每日 AI 资讯自动启动..."

# 1. 用 crontab 设置每天 8:00 自动抓取
(crontab -l 2>/dev/null | grep -v ainews; echo "0 8 * * * /bin/bash /Users/jacky/ainews/run_fetch.sh >> /Users/jacky/ainews/logs/fetch.log 2>&1") | crontab -
echo "✅ 定时抓取已设置（每天 08:00）"

# 2. 用 launchctl bootstrap 注册 server 开机自启
launchctl bootout gui/$(id -u)/com.jacky.ainews.server 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jacky.ainews.server.plist
if [ $? -eq 0 ]; then
    echo "✅ Server 开机自启已注册"
else
    echo "⚠️  launchd 注册失败，尝试备用方案..."
    # 备用：写入 ~/.zprofile 开机启动
    if ! grep -q "ainews" ~/.zprofile 2>/dev/null; then
        echo "" >> ~/.zprofile
        echo "# 每日 AI 资讯 Server 自启" >> ~/.zprofile
        echo "pgrep -f 'server.py' > /dev/null || nohup /bin/bash /Users/jacky/ainews/start_server.sh >> /Users/jacky/ainews/logs/server.log 2>&1 &" >> ~/.zprofile
        echo "✅ 已写入 ~/.zprofile（下次登录终端时自动启动）"
    fi
fi

# 3. 验证 crontab
echo ""
echo "📋 当前 crontab："
crontab -l | grep ainews

echo ""
echo "🎉 配置完成！"
echo "   页面地址: file:///Users/jacky/CatPaw%%20Desk/daily-news/index.html"
echo "   API 地址: http://localhost:8765/api/news"
