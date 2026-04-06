#!/bin/bash
# JaJa Daily 每日抓取 + 自动更新 NoCode 页面

SCRIPT_DIR="/Users/jacky/CatPaw Desk/daily-news"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 开始抓取 ===" >> "$LOG_DIR/fetch.log"

# 1. 抓取新闻数据
cd "$SCRIPT_DIR"
/usr/bin/python3 "$SCRIPT_DIR/fetch_news.py" >> "$LOG_DIR/fetch.log" 2>&1
FETCH_EXIT=$?

if [ $FETCH_EXIT -ne 0 ]; then
    echo "[ERROR] 抓取失败，退出码: $FETCH_EXIT" >> "$LOG_DIR/fetch.log"
    exit $FETCH_EXIT
fi

echo "=== 抓取完成，开始更新 NoCode ===" >> "$LOG_DIR/fetch.log"

# 2. 更新 NoCode 页面（需要 CatDesk 运行中）
/usr/bin/python3 "$SCRIPT_DIR/update_nocode.py" >> "$LOG_DIR/nocode_update.log" 2>&1
NOCODE_EXIT=$?

if [ $NOCODE_EXIT -ne 0 ]; then
    echo "[WARN] NoCode 更新失败，退出码: $NOCODE_EXIT（数据已保存到本地）" >> "$LOG_DIR/fetch.log"
else
    echo "[OK] NoCode 更新成功" >> "$LOG_DIR/fetch.log"
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 全部完成 ===" >> "$LOG_DIR/fetch.log"
