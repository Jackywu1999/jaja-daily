# JaJa Daily

每日精选餐饮零售 & AI 科技资讯，自动抓取、自动更新。

## 部署步骤

### 第一步：创建 GitHub 仓库并上传代码

```bash
# 在 daily-news 目录下初始化 git
cd daily-news
git init
git add .
git commit -m "init: jaja daily"

# 在 GitHub 上新建一个仓库（建议命名 jaja-daily），然后：
git remote add origin https://github.com/你的用户名/jaja-daily.git
git branch -M main
git push -u origin main
```

### 第二步：开启 GitHub Pages

1. 进入仓库页面 → **Settings** → **Pages**
2. Source 选择 **Deploy from a branch**
3. Branch 选 **main**，目录选 **/ (root)**
4. 点击 **Save**

稍等 1-2 分钟，访问地址：`https://你的用户名.github.io/jaja-daily/`

### 第三步：确认 Actions 权限

1. 进入仓库 → **Settings** → **Actions** → **General**
2. 找到 **Workflow permissions**，选择 **Read and write permissions**
3. 点击 **Save**

这样 Actions 才能把每日抓取的数据自动推送回仓库。

### 第四步（可选）：配置 OpenAI Key 增强摘要

1. 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填 `OPENAI_API_KEY`，Value 填你的 Key

---

## 运行时间

每天北京时间 **08:30** 自动抓取并更新数据。

也可以在 GitHub 仓库的 **Actions** 页面手动点击 **Run workflow** 立即触发。

## 目录结构

```
daily-news/
├── index.html          # 前端页面（GitHub Pages 入口）
├── fetch_news.py       # 资讯抓取脚本
├── data/               # 每日 JSON 数据（由 Actions 自动生成）
│   └── YYYY-MM-DD.json
├── .github/
│   └── workflows/
│       └── daily-fetch.yml   # GitHub Actions 定时任务
└── .nojekyll           # 禁用 Jekyll，确保 data/ 目录可访问
```
