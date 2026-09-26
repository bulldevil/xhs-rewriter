#!/usr/bin/env python3
"""检查六列CSV：每条笔记的两个仿写版本是否有足够差异、与对标是否保持贴合。

判定逻辑（标题/正文 各查一次）:
  版本间相似度 >= 1.00        -> ❌ 两版本完全相同（硬伤）
  版本间相似度 >  --max-same   -> ⚠️ 两版本过于接近
  与对标最高相似度 < --min-keep -> ⚠️ 与对标偏离过大（高还原仿写下不常见）
  其他                          -> ✅

存在 ❌ 时退出码为 1（必须修）；只有 ⚠️ 时退出码为 0（人工过目即可）。

用法:
    python check_versions.py <csv路径> [--max-same 0.92] [--min-keep 0.25]
"""
import argparse
import csv
import difflib
import sys
from pathlib import Path

PAIRS = [
    ("标题", "对标标题", "标题1", "标题2"),
    ("正文", "对标正文", "正文1", "正文2"),
]


def sim(a: str, b: str) -> float:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--max-same", type=float, default=0.92,
                    help="两版本相似度上限，超过判为过于接近（默认0.92）")
    ap.add_argument("--min-keep", type=float, default=0.25,
                    help="与对标相似度下限，低于判为偏离过大（默认0.25）")
    args = ap.parse_args()

    p = Path(args.csv_path)
    if not p.exists():
        print(f"❌ 文件不存在: {p}")
        sys.exit(2)

    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    bad = 0
    warn = 0
    for i, row in enumerate(rows, 1):
        for name, ref_col, c1, c2 in PAIRS:
            inter = sim(row.get(c1), row.get(c2))
            keep = max(sim(row.get(c1), row.get(ref_col)), sim(row.get(c2), row.get(ref_col)))
            if inter >= 0.999:
                verdict = "❌ 两版本完全相同"
                bad += 1
            elif inter > args.max_same:
                verdict = "⚠️ 两版本过于接近"
                warn += 1
            elif keep < args.min_keep:
                verdict = "⚠️ 与对标偏离过大"
                warn += 1
            else:
                verdict = "✅"
            print(f"行{i:>2} {name}: 版本间={inter:.2f} 与对标最高={keep:.2f}  {verdict}")

    print(f"\n共 {len(rows)} 行：❌ 硬伤 {bad} 处（必须修复），⚠️ 提示 {warn} 处（建议人工过目）")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
