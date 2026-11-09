#!/bin/bash
# 用法: scripts/read.sh ethics/下的相对路径...   输出完整正文（不截断）
cd "$(dirname "$0")/../../../../ethics" || exit 1
for f in "$@"; do echo "=== $f"; sed -n '/^> 赞/,$p' "$f"; echo; done
