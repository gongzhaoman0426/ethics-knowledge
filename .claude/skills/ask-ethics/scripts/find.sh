#!/bin/bash
# 用法: scripts/find.sh 词1 词2 ...   在 ethics/ 全库按命中数排序候选篇目（每词独立计数，合并排序）
cd "$(dirname "$0")/../../../../ethics" || exit 1
for w in "$@"; do grep -rc --include=*.md -F -- "$w" . ; done \
 | awk -F: '{c[$1]+=$2} END{for(f in c) if(c[f]>0) print c[f], f}' | sort -nr | head -${TOP:-30}
