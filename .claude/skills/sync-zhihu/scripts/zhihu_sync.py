#!/usr/bin/env python3
"""增量抓取知乎用户的全部回答，写入 ethics/未归/ 并追加 index.csv。只抓取，不归类。

归类是另一个 skill（classify-ethics）：由 Claude 通读每篇后手动归位。
请求签名和接口参考 NanmiCoder/MediaCrawler 的 media_platform/zhihu（签名脚本 libs/zhihu.js
首次运行时从其仓库下载到 skill 目录的 .cache/，不随本库分发）。仅供个人学习，请控制频率。

用法：zhihu_sync.py fetch [--token kvxjr369f] [--full] [--limit N] [--dry-run]

登录态：浏览器登录知乎后复制整条 Cookie（必须含 d_c0），放进环境变量 ZHIHU_COOKIE，
或写入 skill 目录下的 .zhihu_cookie（单行）。需要本机有 node。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 脚本在 <repo>/.claude/skills/sync-zhihu/scripts/；ETHICS_DIR 仅供测试时指向别处的 ethics/
ETHICS = Path(os.environ["ETHICS_DIR"]) if os.environ.get("ETHICS_DIR") else HERE.parents[3] / "ethics"
ROOT = ETHICS.parent
INDEX = ETHICS / "index.csv"
SKILL_DIR = HERE.parent  # 缓存、Cookie 都放在本 skill 目录下
CACHE = SKILL_DIR / ".cache"
COOKIE_FILE = SKILL_DIR / ".zhihu_cookie"
SIGN_JS_URL = "https://raw.githubusercontent.com/NanmiCoder/MediaCrawler/main/libs/zhihu.js"
UNSORTED = "未归"
TZ = timezone(timedelta(hours=8))
BASE = "https://www.zhihu.com"
INCLUDE = (
    "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,"
    "collapse_reason,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,"
    "voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,excerpt,paid_info,"
    "reaction_instruction,is_labeled,label_info,relationship.is_authorized,voting,is_author,is_thanked,is_nothelp;"
    "data[*].vessay_info;data[*].author.badge[?(type=best_answerer)].topics;data[*].author.vip_info;"
    "data[*].question.has_publishing_draft,relationship"
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

NODE_RUNNER = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^﻿/, '');
const getSign = new Function('require', src + '\nreturn get_sign;')(require);
process.stdout.write(JSON.stringify(getSign(process.argv[3], process.argv[4])));
"""


# ───────────────────────── 去重 ─────────────────────────
def known_ids() -> set[str]:
    ids: set[str] = set()
    if INDEX.is_file():
        for r in csv.DictReader(INDEX.open(encoding="utf-8")):
            m = re.search(r"/answer/(\d+)", r.get("url", ""))
            if m:
                ids.add(m.group(1))
    for p in ETHICS.rglob("*.md"):
        m = re.match(r"(\d+)(?:-|\.md$)", p.name)
        if m:
            ids.add(m.group(1))
    return ids


# ───────────────────────── 请求 ─────────────────────────
def load_cookie() -> str:
    c = os.environ.get("ZHIHU_COOKIE", "").strip()
    if not c and COOKIE_FILE.is_file():
        c = COOKIE_FILE.read_text(encoding="utf-8").strip()
    if "d_c0" not in c:
        sys.exit("缺少登录态：请设置 ZHIHU_COOKIE 或写入 .claude/skills/sync-zhihu/.zhihu_cookie（需含 d_c0）")
    return c


def sign_js() -> Path:
    CACHE.mkdir(exist_ok=True)
    js = CACHE / "zhihu.js"
    if not js.is_file():
        import requests

        r = requests.get(SIGN_JS_URL, timeout=30)
        r.raise_for_status()
        js.write_bytes(r.content)
    return js


def sign(uri: str, cookie: str) -> dict:
    js = sign_js()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(NODE_RUNNER)
        runner = f.name
    try:
        out = subprocess.run(
            ["node", runner, str(js), uri, cookie], capture_output=True, text=True, timeout=20, check=True
        ).stdout
    finally:
        os.unlink(runner)
    return json.loads(out)


def get_page(token: str, offset: int, limit: int, cookie: str) -> dict:
    import requests
    from urllib.parse import urlencode

    uri = f"/api/v4/members/{token}/answers?" + urlencode(
        {"include": INCLUDE, "offset": offset, "limit": limit, "order_by": "created"}
    )
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "cookie": cookie,
        "referer": f"{BASE}/people/{token}/answers",
        "user-agent": UA,
        "x-api-version": "3.0.91",
        "x-app-za": "OS=Web",
        "x-requested-with": "fetch",
        "x-zse-93": "101_3_3.0",
        **sign(uri, cookie),
    }
    for attempt in range(3):
        r = requests.get(BASE + uri, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (401, 403):
            sys.exit(f"HTTP {r.status_code}：登录态失效或触发风控，请重新复制 Cookie 后再试\n{r.text[:200]}")
        time.sleep(2 * (attempt + 1))
    sys.exit(f"请求失败 HTTP {r.status_code}: {r.text[:200]}")


# ───────────────────────── HTML → 文本 ─────────────────────────
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "blockquote", "h1", "h2", "h3", "h4", "pre", "figure", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
            if tag == "li":
                self.out.append("- ")
            elif tag == "blockquote":
                self.out.append("> ")
        elif tag == "span" and a.get("data-tex"):
            self.out.append(f"${a['data-tex']}$")
            self._skip += 1
        elif tag == "img" and not a.get("eq"):
            self.out.append("[图片]")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html or "")
    text = "".join(p.out).replace("​", "")
    lines = [ln.rstrip() for ln in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ───────────────────────── 写入 ─────────────────────────
def safe_name(s: str, limit: int = 40) -> str:
    s = re.sub(r'[\\/:*?"<>|\s#%&{}$!\'`@+=^~;,\[\]()（）]+', "", s or "")
    return s[:limit]


def fmt_date(ts: int | None) -> str:
    return datetime.fromtimestamp(ts or 0, TZ).strftime("%Y-%m-%d")


def render(ans: dict, author: str, source: str) -> tuple[str, str, dict]:
    aid = str(ans["id"])
    q = ans.get("question") or {}
    qid = str(q.get("id") or "")
    qtitle = (q.get("title") or "").strip()
    title = qtitle or f"answer-{aid}"
    url = f"{BASE}/question/{qid}/answer/{aid}"
    text = html_to_text(ans.get("content", ""))
    votes, comments = ans.get("voteup_count", 0), ans.get("comment_count", 0)
    created, updated = fmt_date(ans.get("created_time")), fmt_date(ans.get("updated_time"))
    qt = title.replace('"', "'")
    md = (
        f'---\ntitle: "{qt}"\ncontent_id: "{aid}"\nquestion_id: "{qid}"\ntag: ""\n'
        f"voteup_count: {votes}\ncomment_count: {comments}\ncreated: {created}\nupdated: {updated}\n"
        f'url: "{url}"\nauthor: {author}\nsource_jsonl: {source}\n---\n\n'
        f"# {title}\n\n> 原文：[{url}]({url})  \n> 赞 {votes} · 评论 {comments} · {created}\n\n{text}\n"
    )
    stem = f"{aid}-{safe_name(qtitle)}" if safe_name(qtitle) else aid
    row = {"title": title, "votes": votes, "created": created, "chars": len(text), "url": url}
    return stem + ".md", md, row


def append_index(rel: str, row: dict) -> None:
    new = not INDEX.is_file()
    with INDEX.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["path", "title", "votes", "created", "chars", "url"])
        w.writerow([rel, row["title"], row["votes"], row["created"], row["chars"], row["url"]])


# ───────────────────────── 抓取 ─────────────────────────
def cmd_fetch(a) -> None:
    known = known_ids()
    cookie = "" if a.fixture else load_cookie()
    source = f"zhihu_sync-{datetime.now(TZ):%Y-%m-%d}"
    new: list[dict] = []
    offset, limit, scanned, known_streak, pages = a.offset, 20, 0, 0, 0
    fixtures = json.loads(Path(a.fixture).read_text(encoding="utf-8")) if a.fixture else None
    while True:
        if fixtures is not None:
            page = fixtures.pop(0) if fixtures else {"data": [], "paging": {"is_end": True}}
        else:
            page = get_page(a.token, offset, limit, cookie)
        data = page.get("data") or []
        fresh = [x for x in data if str(x.get("id")) not in known]
        scanned += len(data)
        for ans in fresh:
            new.append(ans)
            known.add(str(ans["id"]))
        print(f"offset={offset} 本页{len(data)}篇，新增{len(fresh)}篇", file=sys.stderr)
        if (page.get("paging") or {}).get("is_end") or not data:
            break
        known_streak = 0 if fresh else known_streak + 1
        if known_streak >= a.patience and not a.full:  # 连续多页都已存在才停；中间若有断档，用 --full 补
            break
        if a.limit and len(new) >= a.limit:
            break
        offset += limit
        pages += 1
        if a.max_pages and pages >= a.max_pages:
            print(f"已扫 {pages} 页，到此为止；下一段用 --offset {offset}", file=sys.stderr)
            break
        time.sleep(a.interval)
    if not new:
        print(f"没有新回答（已扫描 {scanned} 篇）")
        return

    out_dir = ETHICS / UNSORTED
    out_dir.mkdir(exist_ok=True)
    items = []
    for ans in new:
        name, md, row = render(ans, a.author, source)
        rel = f"{UNSORTED}/{name}"
        if not a.dry_run:
            (ETHICS / rel).write_text(md, encoding="utf-8")
            append_index(rel, row)
        items.append({"file": rel, "id": str(ans["id"]), "title": row["title"], "chars": row["chars"]})
    print(f"新增 {len(items)} 篇" + ("（dry-run，未写盘）" if a.dry_run else f"，已落到 ethics/{UNSORTED}/"))
    for it in items:
        print(f"  {it['file']}  [{it['chars']}字]")
    if not a.dry_run:
        print("下一步：用 classify-ethics 通读并手动归类。")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fetch")
    f.add_argument("--token", default="kvxjr369f", help="知乎 url_token（people/ 后面那段）")
    f.add_argument("--author", default="john-hexa", help="写入 frontmatter 的 author")
    f.add_argument("--full", action="store_true", help="不做早停，扫完全部分页")
    f.add_argument("--offset", type=int, default=0, help="从第几条开始扫（分段补抓用）")
    f.add_argument("--max-pages", type=int, default=0, help="最多扫几页（0 不限），分段补抓用")
    f.add_argument("--patience", type=int, default=3, help="连续几页全部已存在就停（默认 3）")
    f.add_argument("--limit", type=int, default=0, help="最多抓多少篇新回答（0 不限）")
    f.add_argument("--interval", type=float, default=2.0, help="分页间隔秒数")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--fixture", help="测试用：从本地 JSON（分页响应数组）读取，不联网")
    f.set_defaults(fn=cmd_fetch)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
