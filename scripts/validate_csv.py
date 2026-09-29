#!/usr/bin/env python3
"""六列CSV的构建与校验。

子命令:
  build <json文件> <输出csv>              从JSON构建六列CSV（UTF-8-BOM，自动转义，Excel可直接打开）
  check <csv路径> [--expect-rows N]      校验表头、列数、空单元格、行数、BOM

JSON 格式:
  {
    "product": "travel-bag",
    "batch": "20260926-01",
    "rows": [
      {"对标标题": "...", "标题1": "...", "标题2": "...", "对标正文": "...",
       "正文1": "...", "正文2": "..."}
    ]
  }
  （直接传 rows 数组也可以）

check 发现问题时退出码为 1。
"""
import argparse
import csv
import json
import sys
from pathlib import Path

COLUMNS = ["对标标题", "标题1", "标题2", "对标正文", "正文1", "正文2"]


def cmd_build(args):
    src = Path(args.json_path)
    data = json.loads(src.read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) else data
    if not rows:
        print("❌ JSON 中没有任何数据行")
        sys.exit(1)

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    print(f"✅ 已生成 {out}（{len(rows)} 行数据，UTF-8-BOM，Excel/飞书可直接打开）")


def cmd_check(args):
    p = Path(args.csv_path)
    if not p.exists():
        print(f"❌ 文件不存在: {p}")
        sys.exit(2)

    raw = p.read_bytes()
    problems = []
    if raw.startswith(b"\xef\xbb\xbf"):
        print("BOM: ✅ utf-8-sig")
    else:
        print("BOM: ⚠️ 无 BOM（Excel 打开中文可能乱码，建议用 build 重新生成）")

    with p.open("r", encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.reader(f))

    no_title_rows = []

    if not all_rows:
        problems.append("文件为空")
        n_data = 0
    else:
        header = all_rows[0]
        if header != COLUMNS:
            problems.append(f"表头不符：期望 {COLUMNS}，实际 {header}")
        n_data = len(all_rows) - 1
        for i, r in enumerate(all_rows[1:], 1):
            if len(r) != 6:
                problems.append(f"第{i}行：列数={len(r)}，应为6")
                continue
            # 源笔记本身没有标题时：对标标题/标题1/标题2 三列整体留空属正常，
            # 但必须三者一致（不能只留空一部分），正文三列仍不得为空。
            bare_title = not r[0].strip()
            if bare_title:
                no_title_rows.append(i)
                if r[1].strip() or r[2].strip():
                    problems.append(
                        f"第{i}行：「对标标题」为空（源笔记无标题），但标题1/标题2有内容，应一并留空")
            for c, v in zip(COLUMNS, r):
                if v.strip():
                    continue
                if bare_title and c in ("对标标题", "标题1", "标题2"):
                    continue
                problems.append(f"第{i}行：「{c}」为空")

    if args.expect_rows is not None and n_data != args.expect_rows:
        problems.append(f"数据行数={n_data}，与输入笔记条数（{args.expect_rows}）不一致")

    if problems:
        print("❌ 校验未通过：")
        for x in problems:
            print("  -", x)
        sys.exit(1)
    hint = f"，其中 {len(no_title_rows)} 行源笔记无标题（标题列按规则留空）" if no_title_rows else ""
    print(f"✅ 校验通过：{n_data} 行 × 6 列，表头正确，无意外空单元格{hint}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="从JSON构建六列CSV")
    b.add_argument("json_path")
    b.add_argument("out_csv")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("check", help="校验六列CSV")
    c.add_argument("csv_path")
    c.add_argument("--expect-rows", type=int, default=None)
    c.set_defaults(func=cmd_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
