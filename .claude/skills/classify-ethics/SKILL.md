---
name: classify-ethics
description: 把 ethics/未归/ 里新抓取的知乎回答，由 Claude 通读全文后逐篇手动归入素问伦理树。用户说归类新文章、整理未归、给新抓的回答分类时使用。
---

# 归类新回答（第二步：通读，手动，一篇一篇）

分类靠读懂，不靠关键词、不靠脚本、不靠批量规则。**每一篇都要 `Read` 全文再定类。**

## 找出待归类的

新抓取的文章在 `ethics/未归/`，frontmatter 里带 `source_jsonl: zhihu_sync-…`：

```
grep -l '^source_jsonl: zhihu_sync' ethics/未归/*.md
```

只处理这些。`未归/` 里其它旧文章是历史遗留，除非用户明确要求整理，不要动。

## 每篇的做法

1. `Read` 该文件**全文**。长文要读完，不能只看开头、标题或 `grep` 到的片段。
2. 对照 `AGENTS.md` 的「素问伦理树」，判断他在这篇里主要处理「我与谁」的关系，选**一个**二级小类。标题和问题名只作参考，以正文为准。
3. 口径拿不准时，`Read` 目标小类下 1–2 篇已归档文章对照；两个小类难分时，选正文落脚点所在的那个。
4. 实在不属于任何小类、或读完仍拿不准的：留在 `未归/`，不要硬塞，最后汇报里列出原因。`馆务` 不作为内容归类目标。
5. 定了就移动并同步 `index.csv`（在 `ethics/` 目录下执行；小类名必须在树里，大类即该小类所属的大类）：

```
cd ethics
f='<文件名>.md'; big='<大类>'; sub='<小类>'
mkdir -p "$big/$sub" && mv "未归/$f" "$big/$sub/$f" && python3 - "未归/$f" "$big/$sub/$f" <<'PY'
import csv, sys
old, new = sys.argv[1:3]
with open('index.csv', encoding='utf-8', newline='') as fh:
    rows = list(csv.reader(fh))
hits = [r for r in rows[1:] if r and r[0] == old]
assert len(hits) == 1, f'index.csv 里 {old} 命中 {len(hits)} 行'
hits[0][0] = new
with open('index.csv', 'w', encoding='utf-8', newline='') as fh:
    csv.writer(fh).writerows(rows)
PY
```

## 规则

- 一篇读完、定完、移完，再读下一篇。不要先扫标题批量分，也不要写脚本代劳判断。
- 只移动文件和改 `index.csv` 的 path；不改文章正文和 frontmatter。已归档的文章不动。
- 全部做完，汇报：共几篇；每篇「文件 → 大类/小类」及一句理由；哪些留在未归、为什么。
