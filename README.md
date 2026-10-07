# xhs-rewriter

小红书笔记高还原仿写工作区：围绕当前产品，把一条或多条对标笔记改写成「标题×2 + 正文×2」，由脚本生成六列 CSV。

## 常用入口

```text
新产品：<产品信息>
切换产品：<产品名或别名>
<直接粘贴一条或多条对标笔记>
我改好了，检查这批（附 CSV）
```

可选操作：产品卡 HTML 生成、飞书多维表格回填。详细路由和约束见 [SKILL.md](SKILL.md)，具体规则按需读取 `references/` 下对应文件。

## 输出

```text
对标标题,标题1,标题2,对标正文,正文1,正文2
```

每行对应一条输入笔记；标题1/标题2由脚本检查上限，CSV由 `scripts/validate_csv.py` 生成和校验。产品、批次和终检信息保存在工作区的 `products/`、`output/` 与 `state/` 中。

## 主要参考

- `references/note-pipeline.md`：仿写、构建、校验和交付
- `references/product-schema.md`：产品卡建档、切换、更新和查询
- `references/phase2-check.md`：人工改稿后的终检
- `references/product-card-html.md`：产品卡 HTML 生成
- `scripts/upload_feishu.py`：明确要求上传时的统一入口
