---
name: sync-zhihu
description: 增量抓取知乎用户 kvxjr369f（john-hexa）的新回答，落到 ethics/未归/。用户说同步知乎、抓新回答、更新伦理库、爬一下新文章时使用。只抓取，不归类。
---

# 同步知乎新回答（第一步：抓取）

只做增量：已在库里的回答（按回答 id 比对 `index.csv` 和文件名）一律跳过。抓下来的文章写进 `ethics/未归/`，并追加 `ethics/index.csv`。**不归类**——归类是第二步，用 `classify-ethics`。

脚本：本目录 `scripts/zhihu_sync.py`，请求签名参考 MediaCrawler。

## 前提

- 本机有 `node`、`python3`、`requests`。
- 登录态：环境变量 `ZHIHU_COOKIE`，或单行文件 `.claude/skills/sync-zhihu/.zhihu_cookie`（已被同目录 `.gitignore` 忽略）（浏览器登录知乎后复制整条 Cookie，必须含 `d_c0`）。没有就让用户提供，不要自己编，也不要把 Cookie 写进别的文件或回复里。
- 首次运行会把 MediaCrawler 的 `libs/zhihu.js` 下载到本 skill 目录的 `.cache/`。

## 流程

1. 先看会抓什么：`python3 .claude/skills/sync-zhihu/scripts/zhihu_sync.py fetch --dry-run`（首次使用必做）。
2. 抓取：`python3 .claude/skills/sync-zhihu/scripts/zhihu_sync.py fetch`
   - 连续 3 页（`--patience` 可调）都已存在才停。库里新旧文章之间若可能有断档（例如某次没抓完），用 `--full` 扫完全部分页补齐，约 300 页、十来分钟；`--limit N` 限制条数。
   - 没有新回答就直接告诉用户，到此结束。
3. 汇报新增了几篇、文件名，并说明它们在 `ethics/未归/`，接下来用 `classify-ethics` 归类。用户同时要求归类的，接着做第二步。

## 规则

- 抓取间隔默认 2 秒，不要调低，不要并发。遇到 401/403 就停下，请用户更新 Cookie，别重试轰炸。
- 不改已有文章正文和 frontmatter（见 `AGENTS.md`）。
