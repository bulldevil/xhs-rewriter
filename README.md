# xhs-rewriter

小红书笔记高还原贴身仿写 skill：以「产品」为中心管理事实与固定内容（如固定 tag 组），把一条或多条对标笔记仿写成「标题×2 + 正文×2」，产出**六列 CSV** 供下游工具（排期、发布、数据统计等）直接读取。

## 它是怎么工作的

```
用户粘贴对标笔记
      │
      ▼
读取 state/current.md ──► 加载当前产品卡（事实唯一来源）
      │
      ▼
逐条笔记：标题子过程（2版） + 正文子过程（2版，收尾挂固定tag）
      │
      ▼
写入 JSON 中间产物 ──► 脚本生成六列CSV ──► 三项硬校验
      │
      ▼
output/<产品>_<日期>_批NN.csv + 批次日志 + 简短汇报
```

人工在 CSV 上修改后，把文件发回，走 `references/phase2-check.md` 终检，产出 `*_final.csv`。

## 目录结构

| 路径 | 说明 |
|---|---|
| `SKILL.md` | 总控：角色、启动协议、意图路由、全局纪律 |
| `references/product-schema.md` | 产品卡规范：字段、建档/切换/更新/查询协议 |
| `references/note-pipeline.md` | 仿写主流水线：解析→仿写→JSON→脚本校验→交付 |
| `references/shared-input-parsing.md` | 对标笔记的解析与保真规则 |
| `references/shared-rewrite-rules.md` | 高还原方法论：保留/允许/严禁清单 |
| `references/shared-xhs-style.md` | 小红书风格库：情绪词/Emoji/同义词/钩子/AI腔规避 |
| `references/title-rules.md` | 标题仿写规则（流水线子过程，2版本，≤20字） |
| `references/body-rules.md` | 正文仿写规则（流水线子过程，2版本，挂固定tag） |
| `references/phase2-check.md` | 人工改稿后的终检流程 |
| `scripts/count_chars.py` | 标题字数统计（每字符计1），超标退出码非零 |
| `scripts/check_versions.py` | 两版本差异度 + 与对标贴合度检查 |
| `scripts/validate_csv.py` | `build`：JSON→六列CSV（UTF-8-BOM，转义无忧）；`check`：六列规范校验 |
| `assets/` | 产品卡模板、六列表头模板 |
| `state/current.md` | 当前产品指针 |
| `products/` | 产品库：`_index.md` 总索引 + 一产品一卡 |
| `output/` | 六列CSV 产出、`batches.md` 批次日志、`_tmp/` 中间产物 |

## 输出格式（六列 CSV）

```
对标标题,对标正文,标题1,标题2,正文1,正文2
```

- 每行对应一条输入笔记；行数 = 输入笔记条数。
- 前两列与用户输入**逐字一致**，是下游回链对标的锚点。
- UTF-8 带 BOM，Excel / 飞书 / Google Sheets 直接打开；多行正文在单元格内带引号换行。
- 溯源信息（产品/批次）不进 CSV，见文件名与 `output/batches.md`。

## 用户侧最常用的四句话

```
新产品：<产品信息，随便粘贴，越全越好>
切换产品：<产品名或别名>
<直接粘贴一条或多条对标笔记>
我改好了，检查这批（附 CSV）
```
