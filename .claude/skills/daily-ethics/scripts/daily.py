#!/usr/bin/env python3
"""今日一问：从 ethics/ 抽一篇原文作种子。记录写入本 skill 目录下的 daily-log.csv。"""

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

# 脚本在 <repo>/.claude/skills/daily-ethics/scripts/，数据在 <repo>/ethics/
ETHICS = Path(__file__).resolve().parents[4] / "ethics"
INDEX = ETHICS / "index.csv"
LOG = Path(__file__).resolve().parents[1] / "daily-log.csv"  # 与 SKILL.md 同目录
SKIP_L1 = {"未归"}
SKIP_L2 = {"馆务"}
MIN_CHARS = 600
EPOCH = date(2026, 1, 1)


def load_rows():
    rows = []
    for r in csv.DictReader(INDEX.open(encoding="utf-8")):
        parts = r["path"].split("/")
        r["l1"] = parts[0]
        r["l2"] = parts[1] if len(parts) == 3 else parts[0]
        if r["l1"] in SKIP_L1 or r["l2"] in SKIP_L2:
            continue
        try:
            if int(r["chars"]) < MIN_CHARS:
                continue
        except ValueError:
            continue
        if not any("一" <= c <= "鿿" for c in r["title"]):
            continue
        rows.append(r)
    return rows


def load_log():
    if not LOG.is_file():
        return []
    return list(csv.DictReader(LOG.open(encoding="utf-8")))


def current_pick(log, day):
    cur = None
    for r in log:
        if r["date"] != day:
            continue
        if r["action"] == "picked":
            cur = r["path"]
        elif r["action"] == "skipped" and r["path"] == cur:
            cur = None
    return cur


def pick_one(rows, used, day, l1, l2, salt):
    pairs = sorted({(r["l1"], r["l2"]) for r in rows})
    if l1:
        pairs = [p for p in pairs if p[0] == l1]
    if l2:
        pairs = [p for p in pairs if p[1] == l2]
    if not l1 and not l2 and pairs:
        extra = int(hashlib.sha256(salt.encode()).hexdigest(), 16) % len(pairs) if salt else 0
        start = ((date.fromisoformat(day) - EPOCH).days + extra) % len(pairs)
        pairs = pairs[start:] + pairs[:start]
    for pair in pairs:
        cand = [r for r in rows if (r["l1"], r["l2"]) == pair and r["path"] not in used]
        if cand:
            return min(
                cand,
                key=lambda r: hashlib.sha256(f"{day}:{salt}:{r['path']}".encode()).hexdigest(),
            )
    return None


def append_log(day, path, action):
    new = not LOG.is_file()
    with LOG.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "path", "action"])
        w.writerow([day, path, action])


def show(r, day):
    print(json.dumps({
        "date": day,
        "path": "ethics/" + r["path"],
        "title": r["title"],
        "l1": r["l1"],
        "l2": r["l2"],
        "chars": r["chars"],
        "votes": r["votes"],
    }, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="抽今日一问种子篇")
    p.add_argument("--date", default="", help="YYYY-MM-DD，默认今天")
    p.add_argument("--l1", default="", help="只抽这一大类")
    p.add_argument("--l2", default="", help="只抽这一小类")
    p.add_argument("--skip", action="store_true", help="作废今日已抽，另抽一篇")
    p.add_argument("--no-log", action="store_true", help="只打印，不写日志")
    a = p.parse_args()

    day = a.date or date.today().isoformat()
    rows = load_rows()
    by_path = {r["path"]: r for r in rows}
    log = load_log()
    used = {r["path"] for r in log if r["action"] in ("picked", "skipped")}
    cur = current_pick(log, day)
    salt = ""

    if a.skip:
        if cur:
            if not a.no_log:
                append_log(day, cur, "skipped")
            used.add(cur)
        salt = f"skip:{sum(1 for r in log if r['date'] == day)}"
    elif cur in by_path:
        show(by_path[cur], day)
        return

    pick = pick_one(rows, used, day, a.l1, a.l2, salt)
    if not pick:
        raise SystemExit("这个范围内没有未抽过的篇目了")
    if not a.no_log:
        append_log(day, pick["path"], "picked")
    show(pick, day)


if __name__ == "__main__":
    main()
