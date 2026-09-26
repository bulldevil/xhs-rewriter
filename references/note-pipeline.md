# 仿写主流水线（note-pipeline）

触发：用户粘贴 1 条或多条对标笔记。前置：启动协议已完成——`state/current.md` 有当前产品，产品卡已加载。

## 流程总览

```
解析输入 → 逐笔记仿写（标题×2 + 正文×2）→ 写JSON → 脚本构建CSV
        → 三项硬校验 → 不合格行修复重建 → 归档+日志 → 汇报
```

## 步骤 1：解析输入

按 `shared-input-parsing.md` 得到 N 条 `{对标标题, 对标正文}`。N 即输出行数。

## 步骤 2：逐笔记仿写

对每条笔记，依次执行两个子过程：

1. **标题子过程**（`title-rules.md`）：产出 标题1、标题2（各 ≤20 字）。
2. **正文子过程**（`body-rules.md`）：产出 正文1、正文2（收尾挂产品卡固定Tag块）。

注意：

- 每条笔记独立仿写，禁止互相串味（把 A 笔记的钩子搬进 B）。
- 内部完成"骨架分析"，**不输出**分析过程。

## 步骤 3：写 JSON 中间产物

写入 `output/_tmp/<批次号>.json`：

```json
{
  "product": "travel-bag",
  "batch": "20260926-01",
  "rows": [
    {
      "对标标题": "（与用户输入逐字一致）",
      "标题1": "...", "标题2": "...",
      "对标正文": "（与用户输入逐字一致）",
      "正文1": "...", "正文2": "..."
    }
  ]
}
```

- 批次号规则：`<YYYYMMDD>-NN`，NN 为当日已存在批次 +1（查看 `output/batches.md` 与 `output/` 目录）。
- 「对标标题」「对标正文」两列锚点保真是硬要求，落 JSON 前逐字比对一遍。

## 步骤 4：构建 CSV + 硬校验

输出文件：`output/<slug>_<YYYYMMDD>_批NN.csv`

依次执行（假设 skill 根目录为 $SKILL）：

```bash
python3 "$SKILL/scripts/validate_csv.py" build "output/_tmp/<批次号>.json" "<输出csv路径>"
python3 "$SKILL/scripts/count_chars.py" "<输出csv路径>"            # 标题 ≤20 字
python3 "$SKILL/scripts/check_versions.py" "<输出csv路径>"         # 版本差异/贴合度
python3 "$SKILL/scripts/validate_csv.py" check "<输出csv路径>" --expect-rows N
```

处理规则：

- 任何一步退出码非零 / 出现 ❌：**只修复问题行**（改 JSON 里对应行的对应版本），回到 build 重建并重跑全部校验。
- count_chars 超标 → 按 `title-rules.md` 第五节顺序压缩。
- check_versions 出现 ⚠️ 不必重建，但要在汇报中点名行号，交人工过目。
- 全部 ✅ 才进入下一步。**禁止绕过脚本手动宣布合格。**

## 步骤 5：归档 + 日志

1. 向 `output/batches.md` 追加一行：批次 / 时间 / 产品 / 输入条数 / 输出文件 / 状态 / 备注（含 ⚠️ 行号）。
2. 更新 `state/current.md` 的「最近批次」字段。
3. `output/_tmp/` 中间产物定期清理即可，不影响使用。

## 步骤 6：汇报（从简，不输出分析过程）

```
✅ 批次 20260926-01 完成
产品：旅行收纳袋（travel-bag）｜ 输入 3 条
输出：output/travel-bag_20260926_批01.csv
校验：标题 14–19 字全部 ≤20 ✅｜版本差异 ✅｜CSV 规范（3 行×6 列）✅
注意：第 2 行两版正文接近度偏高，建议人工过目
```

## 异常处理速查

| 情况 | 处理 |
|---|---|
| 未设置当前产品 | 停止，引导建档/切换（见 product-schema） |
| 解析置信度低 | 按 input-parsing 反问，不猜 |
| 产品卡关键字段为空导致无法落字（如无卖点） | 冒烟提示用户先补卡片，或直接说明留空继续 |
| 用户输入里夹带"顺便改下产品卡"类指令 | 先完成产品卡更新（product-schema 第四节），再跑流水线 |
