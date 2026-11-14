#!/usr/bin/env python3
"""校验 ask-ethics 的回答：正文 + 文末「引用：」列表。

用法: python3 scripts/check_links.py <答案.md> [仓库根目录，默认 ../../../..]

引用列表格式（正文最下面）:
    引用：
    - 标签：https://www.zhihu.com/question/<问题id>/answer/<回答id>   # 知乎原文链接

检查:
  [错误] 链接在库里找不到对应篇目（或与 frontmatter 的 url 不一致） / 标签不是该篇 frontmatter 的 tag 或 title / 缺引用列表 /
         正文含链接、标题、加粗
  [无出处] 正文某句话与全部引用篇目没有连续 8 字的重合（提示，需人工核对）
  [未使用] 引用了但正文一句也没用到
退出码：有 [错误] 为 1，其余为 0。
"""
import re, sys, pathlib

N = 8


def norm(s):
    return re.sub(r"[\s，。、；：！？“”‘’\"'「」『』（）()《》,.;:!?—\-…·\[\]]", "", s)


def front(body):
    d = {}
    m = re.match(r"---\n(.*?)\n---", body, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            d[k.strip()] = v.strip().strip('"')
    return d


def grams(t):
    return {t[i:i + N] for i in range(len(t) - N + 1)}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    root = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parents[4]
    errs, warns = [], []

    parts = re.split(r"\n\s*引用[：:]\s*\n", text, maxsplit=1)
    if len(parts) != 2:
        print("[错误] 找不到文末的「引用：」列表"); sys.exit(1)
    body, refs = parts

    if re.search(r"\]\(", body): errs.append("正文里有链接，链接只能放在文末引用列表")
    if re.search(r"^\s*#{1,6}\s", body, re.M): errs.append("正文里有标题")
    if "**" in body: errs.append("正文里有加粗")

    cited = {}
    for line in refs.splitlines():
        line = line.strip()
        if not line: continue
        m = re.match(r"^[-*]\s*(.+?)[：:]\s*(?:\[[^\]]*\]\(([^)]+)\)|(https?://\S+))\s*$", line)
        if not m:
            errs.append(f"引用行格式不对（应为 - 标签：知乎链接）: {line}"); continue
        label = m.group(1).strip()
        href = (m.group(2) or m.group(3)).strip()
        am = re.search(r"/answer/(\d+)", href)
        if not am:
            errs.append(f"不是知乎回答链接: {href}"); continue
        aid = am.group(1)
        hits = [x for pat in (f"*/*/{aid}-*.md", f"*/*/{aid}.md", f"*/{aid}-*.md", f"*/{aid}.md")
                for x in (root / "ethics").glob(pat)]
        if not hits:
            errs.append(f"库里找不到这个回答: {href}"); continue
        p = hits[0]
        raw = p.read_text(encoding="utf-8")
        fm = front(raw)
        if fm.get("url", "").rstrip("/") != href.rstrip("/"):
            errs.append(f"链接与该篇 frontmatter 的 url 不一致: {href} ≠ {fm.get('url')}")
        ok = {norm(fm.get("tag", "")), norm(fm.get("title", ""))} - {""}
        if norm(label) not in ok:
            errs.append(f"标签不对: 「{label}」应为「{fm.get('tag') or fm.get('title')}」 ({href})")
        key = str(p.relative_to(root))
        if key in cited:
            errs.append(f"重复引用: {href}")
        cited[key] = norm(raw.split("\n> 赞", 1)[-1])

    allg = set()
    per = {}
    for h, t in cited.items():
        g = grams(t); per[h] = g; allg |= g

    for sent in re.split(r"[。！？\n]", body):
        t = norm(sent)
        if len(t) >= N and not (grams(t) & allg):
            warns.append(f"[无出处] {sent.strip()}")
    bg = grams(norm(body))
    for h, g in per.items():
        if not (g & bg):
            warns.append(f"[未使用] {h}")

    for e in errs: print("[错误]", e)
    for w in warns: print(w)
    print(f"引用 {len(cited)} 篇，{len(errs)} 个错误，{len(warns)} 条提示")
    sys.exit(1 if errs else 0)


main()
