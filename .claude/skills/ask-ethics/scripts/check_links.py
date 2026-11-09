#!/usr/bin/env python3
"""校验 ask-ethics 成文里的引用链接。

用法: python3 scripts/check_links.py <答案.md> [仓库根目录，默认 ../../../..]
检查:
  1. href 指向的文件是否存在
  2. 链接文字是否逐字出现在该文件正文里（忽略空白与标点差异）
未通过的逐条列出，退出码 1。
"""
import re, sys, pathlib

def norm(s):
    return re.sub(r"[\s，。、；：！？“”‘’\"'「」『』（）()《》,.;:!?—\-…·]", "", s)

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ans = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    root = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parents[4]
    bad = 0
    links = re.findall(r"\[([^\]]+)\]\((<[^>]+>|[^)\s]+)\)", ans)
    for text, href in links:
        href = href.strip("<>")
        p = root / href
        if not p.is_file():
            print(f"[缺文件] {href}"); bad += 1; continue
        body = p.read_text(encoding="utf-8")
        body = body.split("\n> 赞", 1)[-1]
        if norm(text) not in norm(body):
            print(f"[非原文] {text}  →  {href}"); bad += 1
    print(f"共 {len(links)} 条链接，{bad} 条未通过")
    sys.exit(1 if bad else 0)

main()
