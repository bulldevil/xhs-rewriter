#!/usr/bin/env python3
"""统计六列CSV中标题列的字数（每个字符计1：汉字/Emoji/标点/数字/英文都算）。

用法:
    python count_chars.py <csv路径> [--limit 20]

对标标题只报告不强制；标题1/标题2 超过 limit 记为超标。
有超标时退出码为 1，全部合格为 0。
"""
import argparse
import csv
import sys
from pathlib import Path

TITLE_COLS_CHECK = ["标题1", "标题2"]
TITLE_COLS_REPORT = ["对标标题"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    p = Path(args.csv_path)
    if not p.exists():
        print(f"❌ 文件不存在: {p}")
        sys.exit(2)

    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    bad = 0
    all_cols = TITLE_COLS_CHECK + [c for c in TITLE_COLS_REPORT if c in (rows[0] if rows else {})]
    print(f"{'行':>3} {'列':<6} {'字数':>4}  内容")
    print("-" * 60)
    for i, row in enumerate(rows, 1):
        for col in all_cols:
            t = (row.get(col) or "").strip()
            n = len(t)
            flag = ""
            if col in TITLE_COLS_CHECK and n > args.limit:
                flag = f"  ❌ 超{n - args.limit}字"
                bad += 1
            short = t if len(t) <= 38 else t[:35] + "..."
            print(f"{i:>3} {col:<6} {n:>4}  {short}{flag}")
    print("-" * 60)
    print(f"共 {len(rows)} 行，标题超标 {bad} 处（上限 {args.limit} 字/条）")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
