#!/bin/bash
# 用法: scripts/read.sh ethics/下的相对路径...   输出完整正文（不截断），篇首印出引用用的「标签」和「链接」
cd "$(dirname "$0")/../../../../ethics" || exit 1
for f in "$@"; do
  tag=$(grep -m1 '^tag:' "$f" | sed 's/^tag: *"\{0,1\}//; s/"\{0,1\} *$//')
  title=$(grep -m1 '^title:' "$f" | sed 's/^title: *"\{0,1\}//; s/"\{0,1\} *$//')
  url=$(grep -m1 '^url:' "$f" | sed 's/^url: *"\{0,1\}//; s/"\{0,1\} *$//')
  echo "=== $f"
  echo "引用行: - ${tag:-$title}：$url"
  sed -n '/^> 赞/,$p' "$f"; echo
done
