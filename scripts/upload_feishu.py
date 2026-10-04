#!/usr/bin/env python3
"""把六列仿写 CSV 上传到飞书多维表格（Base）。

依赖本地官方飞书 CLI：`lark-cli`（@larksuite/cli）。
上传逻辑：
  1. 从 state/feishu.md 读取目标表格（url / base_token / table_id），
     或用户本次用 --url 传入新地址（自动更新状态文件）。
  2. 检查目标表格是否包含 8 列：
     标题 / 正文 / 对标标题 / 标题1 / 标题2 / 对标正文 / 正文1 / 正文2。
  3. 逐行匹配（去空格后相等）：
     - 优先用「对标标题」比对飞书「标题」列；
     - 命中多条 / 无命中，再用「对标正文」比对飞书「正文」列；
     - 仍无法唯一定位到一行 → 跳过并在结尾报告。
  4. 匹配成功的行，把六列结果写入飞书对应行的 6 个字段：
     对标标题 / 标题1 / 标题2 / 对标正文 / 正文1 / 正文2。
     （「标题」「正文」是表格里预填的锚点列，本脚本不改动。）

撞车兜底：标题/正文去空格后仍无法唯一命中时，可用 --record-id 精确写入。
record_id 必须来自脚本本次实时拉取的 _tmp/_feishu_records.ndjson（或 --dry-run 打印），
禁止复用旧快照或凭记忆硬编码（表格被人工改动后 record_id 会失效）。

用法：
  python3 scripts/upload_feishu.py <csv路径> [--url <飞书表格URL>] [--dry-run]
  python3 scripts/upload_feishu.py <csv路径> --record-id <rid1> --record-id <rid2> [--dry-run]

退出码：
  0 全部成功（含跳过但无错误）
  1 参数/状态/列检查等错误
  2 有行匹配失败被跳过
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# —— 常量 ——
SKILL_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = SKILL_ROOT / "state" / "feishu.md"

# 飞书表格必须包含的 8 列（顺序无关）
REQUIRED_COLUMNS = [
    "标题", "正文", "对标标题", "标题1", "标题2", "对标正文", "正文1", "正文2",
]

# 上传时要写入的 6 个字段（CSV 六列 ↔ 飞书字段，同名）
WRITE_COLUMNS = ["对标标题", "标题1", "标题2", "对标正文", "正文1", "正文2"]

# CSV 里用于匹配的锚点列 → 飞书里对应的预填锚点列
MATCH_PAIRS = [
    ("对标标题", "标题"),
    ("对标正文", "正文"),
]

LARK_CLI = "lark-cli"

# lark-cli 候选路径（Windows npm 全局 shim 等）
LARK_CLI_CANDIDATES = [
    LARK_CLI,
    "lark-cli.cmd",
    os.path.expandvars(r"%APPDATA%\npm\lark-cli.cmd"),
    os.path.expandvars(r"%APPDATA%\npm\lark-cli"),
]

# 直接调用 node 跑 CLI 的入口脚本（绕开 .cmd shim 与 shell 的编码/转义坑）
LARK_RUN_JS = os.path.expandvars(
    r"%APPDATA%\npm\node_modules\@larksuite\cli\scripts\run.js"
)


def find_lark():
    """返回调用 lark-cli 的命令前缀（list）。

    优先直接用 `node <run.js>`（最稳，无 shell 转义/编码问题），
    否则退回 `lark-cli`（依赖 PATH）。
    """
    if Path(LARK_RUN_JS).exists():
        node = shutil.which("node")
        if node:
            return [node, LARK_RUN_JS]
    if shutil.which(LARK_CLI):
        return [LARK_CLI]
    return [LARK_CLI]


# —— 工具 ——
def run_lark(args):
    """调用 lark-cli，返回 (returncode, stdout, stderr)。"""
    cmd = [*find_lark(), *args]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        p = subprocess.run(cmd, capture_output=True, env=env)
    except FileNotFoundError:
        print(f"❌ 找不到 lark-cli，请确认已安装飞书 CLI（@larksuite/cli）并加入 PATH")
        sys.exit(1)
    out = _decode(p.stdout)
    err = _decode(p.stderr)
    return p.returncode, out, err


def _decode(b):
    if not b:
        return ""
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def strip_ws(s):
    """去掉所有空白字符后返回（用于“去空格相等”比对）。"""
    return re.sub(r"\s+", "", s or "")


# —— 状态文件 ——
def read_state():
    if not STATE_FILE.exists():
        return {"url": None, "base_token": None, "table_id": None}
    st = {}
    for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"-\s*(\S+)\s*:\s*(.*)$", line.strip())
        if m:
            st[m.group(1)] = m.group(2).strip()
    return st


def write_state(base_token, table_id, url):
    lines = [
        "# 飞书上传状态",
        "",
        "> 由 scripts/upload_feishu.py 维护。上传目标飞书多维表格的坐标。",
        "> 更换上传目标：直接运行 `python3 scripts/upload_feishu.py <csv> --url <新URL>` 即可更新。",
        "",
        f"- url: {url}",
        f"- base_token: {base_token}",
        f"- table_id: {table_id}",
        "",
    ]
    STATE_FILE.write_text("\n".join(lines), encoding="utf-8")


def resolve_url(url):
    """URL → (base_token, table_id)。"""
    rc, out, err = run_lark(["base", "+url-resolve", "--url", url, "--as", "user"])
    if rc != 0:
        print(f"❌ 解析飞书 URL 失败：\n{err or out}")
        sys.exit(1)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(f"❌ 解析 URL 返回不是合法 JSON：\n{out}")
        sys.exit(1)
    # 真实返回：{ok, identity, data: {base_token, table_id, ...}}
    inner = data.get("data", data)
    base_token = inner.get("base_token") or inner.get("app_token")
    table_id = inner.get("table_id")
    if not base_token:
        print(f"❌ 无法从 URL 提取 base_token：\n{out}")
        sys.exit(1)
    return base_token, table_id


def ensure_target(args):
    """确定 base_token/table_id：优先 --url，否则读状态文件。"""
    url = args.url
    if url:
        base_token, table_id = resolve_url(url)
        write_state(base_token, table_id or "", url)
        print(f"✅ 已解析并记录目标表格：base_token={base_token} table_id={table_id or '(URL 未带 table，需补)'}")
        return base_token, table_id
    st = read_state()
    base_token = st.get("base_token")
    table_id = st.get("table_id")
    if not base_token:
        print("❌ 未设置飞书上传目标。请先运行：")
        print("   python3 scripts/upload_feishu.py <csv> --url <飞书表格URL>")
        sys.exit(1)
    return base_token, table_id


# —— 列检查 ——
def list_fields(base_token, table_id):
    rc, out, err = run_lark([
        "base", "+field-list", "--base-token", base_token,
        "--table-id", table_id, "--format", "json", "--as", "user",
    ])
    if rc != 0:
        print(f"❌ 读取字段列表失败：\n{err or out}")
        sys.exit(1)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(f"❌ 字段列表返回不是合法 JSON：\n{out}")
        sys.exit(1)
    # 真实返回：{ok, identity, data: {fields: [{name, ...}]}}
    inner = data.get("data", data)
    items = None
    if isinstance(inner, dict):
        items = inner.get("fields") or inner.get("items")
    if items is None and isinstance(data, list):
        items = data
    if items is None:
        print(f"❌ 无法解析字段列表结构：\n{out}")
        sys.exit(1)
    names = []
    for it in items:
        if isinstance(it, dict):
            names.append(it.get("field_name") or it.get("name") or "")
        elif isinstance(it, str):
            names.append(it)
    return names


def check_columns(names):
    missing = [c for c in REQUIRED_COLUMNS if c not in names]
    if missing:
        print(f"❌ 目标表格缺少以下列：{missing}")
        print(f"   实际列：{names}")
        sys.exit(1)
    print(f"✅ 8 列检查通过：{REQUIRED_COLUMNS}")


# —— 记录读取与匹配 ——
def fetch_records(base_token, table_id):
    """拉取全表记录，返回 {record_id: {"标题":..., "正文":...}}。"""
    tmp = SKILL_ROOT / "output" / "_tmp" / "_feishu_records.ndjson"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = run_lark([
        "base", "+record-list", "--base-token", base_token,
        "--table-id", table_id,
        "--field-id", "标题", "--field-id", "正文",
        "--format", "ndjson", "--output", str(tmp), "--overwrite", "--as", "user",
    ])
    if rc != 0:
        print(f"❌ 读取记录失败：\n{err or out}")
        sys.exit(1)
    records = {}
    if tmp.exists():
        for line in tmp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = row.get("record_id")
            if not rid:
                continue
            fields = row.get("fields", row)
            title = fields.get("标题")
            body = fields.get("正文")
            # 单元格值可能是 str、list（多值）、dict（富文本），统一成文本
            title = cell_to_text(title)
            body = cell_to_text(body)
            records[rid] = {"标题": title, "正文": body}
    return records


def cell_to_text(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "".join(cell_to_text(x) for x in v)
    if isinstance(v, dict):
        # 富文本常见 {text: "..."} 或 {value: ...}
        for k in ("text", "value", "link"):
            if k in v:
                return cell_to_text(v[k])
        return ""
    return str(v)


def match_record(records, csv_row):
    """返回匹配到的 record_id，或 None。

    优先级：对标标题↔标题，对标正文↔正文；两关都过才唯一命中。
    """
    for src_col, dst_col in MATCH_PAIRS:
        src_val = strip_ws(csv_row.get(src_col, ""))
        if not src_val:
            continue
        hits = [
            rid for rid, rec in records.items()
            if strip_ws(rec.get(dst_col, "")) == src_val
        ]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # 标题撞车 → 用正文再消歧
            continue
        # 0 命中，试下一对
    return None


# —— 上传 ——
def read_csv(path):
    p = Path(path)
    if not p.exists():
        print(f"❌ CSV 不存在：{p}")
        sys.exit(1)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def main():
    ap = argparse.ArgumentParser(description="上传六列仿写 CSV 到飞书多维表格")
    ap.add_argument("csv_path")
    ap.add_argument("--url", help="飞书多维表格 URL；提供则更新状态文件")
    ap.add_argument(
        "--record-id", action="append", default=None, metavar="RID",
        help="按 record_id 精确写入（可重复，与 CSV 行一一对应）。"
             "用于标题撞车无法唯一匹配时。RID 必须来自本次实时拉取结果，禁止硬编码旧值。",
    )
    ap.add_argument("--dry-run", action="store_true", help="只预览匹配结果，不真正写飞书")
    args = ap.parse_args()

    base_token, table_id = ensure_target(args)
    if not table_id:
        print("❌ 未取得 table_id（URL 里没有 table 参数，或状态文件里为空）")
        print("   请在 URL 中带上表格，或手动补全 state/feishu.md 的 table_id")
        sys.exit(1)

    # 1) 列检查
    names = list_fields(base_token, table_id)
    check_columns(names)

    # 2) 读 CSV
    csv_rows = read_csv(args.csv_path)
    print(f"📄 待上传 {len(csv_rows)} 行")

    # 3) 拉取飞书记录
    records = fetch_records(base_token, table_id)
    print(f"📊 飞书表格现有 {len(records)} 行记录")

    # 4) 匹配
    to_update = {}   # record_id -> 六列字段
    skipped = []     # (csv行号, 原因)
    if args.record_id:
        # --record-id 精确写入模式：RID 与 CSV 行一一对应
        if len(args.record_id) != len(csv_rows):
            print(f"❌ --record-id 数量({len(args.record_id)})与 CSV 行数({len(csv_rows)})不一致")
            sys.exit(1)
        # 校验 RID 确实存在于本次实时拉取的记录中，防止过期/失效的 RID 写脏表
        valid_rids = set(records.keys())
        for i, (rid, row) in enumerate(zip(args.record_id, csv_rows), 1):
            if rid not in valid_rids:
                skipped.append((i, f"--record-id {rid!r} 不在本次拉取的全表中（可能已删行/换行）"))
                continue
            to_update[rid] = {c: row.get(c, "") for c in WRITE_COLUMNS}
    else:
        for i, row in enumerate(csv_rows, 1):
            rid = match_record(records, row)
            if rid is None:
                anchor = strip_ws(row.get("对标标题", "")) or strip_ws(row.get("对标正文", ""))
                skipped.append((i, f"未在飞书表格中唯一定位（锚点：{anchor[:20]!r}）"))
                continue
            to_update[rid] = {c: row.get(c, "") for c in WRITE_COLUMNS}

    print(f"\n🔍 匹配结果：可写入 {len(to_update)} 行，跳过 {len(skipped)} 行")
    for i, reason in skipped:
        print(f"   ⏭️  CSV 第 {i} 行：{reason}")

    if args.dry_run:
        print("\n[--dry-run] 预览要写入的内容（不真正上传）：")
        for rid, fields in to_update.items():
            print(f"   record {rid}:")
            for k, v in fields.items():
                print(f"     {k}: {v[:40]!r}")
        return

    if not to_update:
        print("\n没有需要写入的行。")
        sys.exit(2 if skipped else 0)

    # 5) 批量更新（≤200/批，已按去重后的 record_id 分组）
    updates = list(to_update.items())
    batch_size = 200
    for start in range(0, len(updates), batch_size):
        chunk = updates[start:start + batch_size]
        payload = {"update_records": {rid: fields for rid, fields in chunk}}
        rc, out, err = run_lark([
            "base", "+record-batch-update", "--base-token", base_token,
            "--table-id", table_id, "--json", json.dumps(payload, ensure_ascii=False),
            "--as", "user",
        ])
        if rc != 0:
            print(f"❌ 写入飞书失败（第 {start + 1} 条起）：\n{err or out}")
            sys.exit(1)
        print(f"✅ 已写入 {len(chunk)} 条记录")

    # 6) 汇总
    print(f"\n✅ 上传完成：写入 {len(to_update)} 行，跳过 {len(skipped)} 行")
    if skipped:
        print("以下行未上传（请人工核对）：")
        for i, reason in skipped:
            print(f"   - CSV 第 {i} 行：{reason}")
        sys.exit(2)


if __name__ == "__main__":
    main()
