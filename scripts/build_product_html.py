#!/usr/bin/env python3
"""产品卡 HTML 生成器。

把一张产品卡 Markdown（products/<slug>.md）渲染成一张「产品卡 HTML」
（products/<slug>.html，与 md 同目录并排），版式以《产品卡_桃花晕染9款发夹.html》为模板。
配色按卡片里对颜色的描述自动推断（COLOR_WORDS/TONE_WORDS），未登记的新颜色会回落到默认主题；
也可用 frontmatter 的 theme 字段手动覆盖（预设名或 #色值）。
索引页输出为 products/index.html。

用法:
  python scripts/build_product_html.py --all             # 生成 products/ 下全部产品卡
  python scripts/build_product_html.py <slug>            # 只生成某一款（slug）
  python scripts/build_product_html.py --index           # 只重生成 index.html
  python scripts/build_product_html.py --list             # 列出可生成的产品

字段映射与主题规则见 references/product-card-html.md（本文档是"机器实现"，
那份 md 是"人读的方法说明"，两者必须保持一致）。
"""
import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_DIR = ROOT / "products"
OUTDIR = PRODUCTS_DIR  # html 与 md 放在一起（同目录）

# ---------------------------------------------------------------------------
# 主题预设：每个产品卡通过 frontmatter 的 theme 字段选择一套配色。
# 键 = theme 字段取值；默认 "pink"。配色沿用模板的 CSS 变量语义。
# ---------------------------------------------------------------------------
THEMES = {
    "pink": {  # 桃花晕染发夹：粉雾 × 青碧（默认）
        "accent": "#f6a8c0", "deep": "#e878a0", "light": "#fdeef4",
        "green": "#9fd3c0", "ink": "#4a3b44", "muted": "#9b8a93", "line": "#f0dce5",
        "head_from": "#fbdde8", "head_to": "#e9f5ee",
        "price_from": "#ffe6ef", "price_to": "#fff4f8",
        "foot": "#4a3b44", "foot_ink": "#f6e7ec", "foot_accent": "#ffd6e3",
    },
    "brown": {  # 雪纳瑞抓夹：深棕复古 × 琥珀
        "accent": "#c9a06a", "deep": "#a9783f", "light": "#f7efe2",
        "green": "#9fbfa0", "ink": "#3e342f", "muted": "#9c8d80", "line": "#eadfd0",
        "head_from": "#f0e2cf", "head_to": "#e7efe4",
        "price_from": "#f6ead6", "price_to": "#faf3e8",
        "foot": "#3e342f", "foot_ink": "#f1e8df", "foot_accent": "#e6c99a",
    },
    "cream": {  # 尼泊尔挂历：暖米复古花卉 × 陶土
        "accent": "#e0a66b", "deep": "#c8824a", "light": "#fbf1e4",
        "green": "#a9c3a0", "ink": "#54473f", "muted": "#a39386", "line": "#eee0cd",
        "head_from": "#f7e6d0", "head_to": "#eef2e4",
        "price_from": "#f8ecd9", "price_to": "#fbf4ea",
        "foot": "#54473f", "foot_ink": "#f3eae0", "foot_accent": "#eecb96",
    },
    "warm": {  # 动物台历：温柔治愈 × 暖橘
        "accent": "#f2b880", "deep": "#e0915a", "light": "#fdf2e7",
        "green": "#a9c8b8", "ink": "#524842", "muted": "#a29488", "line": "#f0e2d3",
        "head_from": "#fbe9d6", "head_to": "#eaf1e7",
        "price_from": "#fcf0e1", "price_to": "#fcf5ec",
        "foot": "#524842", "foot_ink": "#f3ebe2", "foot_accent": "#f2c894",
    },
    "blue": {  # 雾蓝系（新配色）
        "accent": "#7fb2d9", "deep": "#5c92bf", "light": "#eaf3fa",
        "green": "#9fc9b8", "ink": "#3a4a58", "muted": "#8a98a5", "line": "#dce7f0",
        "head_from": "#e3f0f8", "head_to": "#eaf2ec",
        "price_from": "#eaf3fa", "price_to": "#f4f9fc",
        "foot": "#3a4a58", "foot_ink": "#e9f2f8", "foot_accent": "#b8d8ee",
    },
    "purple": {  # 香芋紫系（新配色）
        "accent": "#b49ad1", "deep": "#9275bd", "light": "#f3eef9",
        "green": "#a9c8b8", "ink": "#463c52", "muted": "#988fa3", "line": "#e5ddf0",
        "head_from": "#ede6f7", "head_to": "#eaf2ec",
        "price_from": "#f0eaf8", "price_to": "#f7f3fb",
        "foot": "#463c52", "foot_ink": "#efe9f5", "foot_accent": "#d4c4e8",
    },
    "red": {  # 莓红/复古红系（新配色）
        "accent": "#d9888a", "deep": "#b96266", "light": "#fbecec",
        "green": "#9fc9b8", "ink": "#523a3c", "muted": "#a08a8c", "line": "#efdcdd",
        "head_from": "#f6e2e2", "head_to": "#eaf2ec",
        "price_from": "#faeaea", "price_to": "#fdf4f4",
        "foot": "#523a3c", "foot_ink": "#f5e7e8", "foot_accent": "#e8b6b8",
    },
    "yellow": {  # 鹅黄系（新配色）
        "accent": "#e0c05f", "deep": "#c09a3a", "light": "#faf3dc",
        "green": "#9fc9b8", "ink": "#524a34", "muted": "#a0987e", "line": "#efe6c8",
        "head_from": "#f7efd4", "head_to": "#eaf2ec",
        "price_from": "#faf2dc", "price_to": "#fcf7ea",
        "foot": "#524a34", "foot_ink": "#f4eeda", "foot_accent": "#ead6a0",
    },
    "green": {  # 抹茶绿系（新配色）
        "accent": "#8fbfa8", "deep": "#5f9c80", "light": "#eaf5ef",
        "green": "#c7d9cf", "ink": "#3a4a42", "muted": "#8a9a91", "line": "#d9e6de",
        "head_from": "#e3f0e9", "head_to": "#eef3ec",
        "price_from": "#eaf3ee", "price_to": "#f4f8f6",
        "foot": "#3a4a42", "foot_ink": "#e9f0ec", "foot_accent": "#c0d6cb",
    },
}
DEFAULT_THEME = "pink"

# 场景类目 → 标签色。季节/日常用主色（粉），其余（穿搭/发型/特殊/风格/功能）用辅助色（绿）。
SCENARIO_PINK = {"季节", "日常"}

# 卖点判定为"辅助色（绿）"的关键词：价格 / 容量 / 功能 / 尺寸等。
GREEN_POINT_HINT = ("价格", "价", "r+", "性价比", "容量", "抓力", "功能", "两用",
                    "周期", "尺寸", "包邮", "元", "元起")


# ---------------------------------------------------------------------------
# 自动配色：根据产品卡里对颜色的描述，推断主题；未登记颜色回落到默认主题。
# COLOR_WORDS：具体颜色词 → 主题 key（取在正文里出现位置最靠前的一个）。
# TONE_WORDS：没有具体颜色时，按氛围/色调兜底。
# ---------------------------------------------------------------------------
COLOR_WORDS = {
    # 粉系
    "桃花": "pink", "桃粉": "pink", "粉雾": "pink", "粉嫩": "pink",
    "樱花": "pink", "蜜桃": "pink", "莓果": "pink", "粉色": "pink",
    # 棕系
    "深棕": "brown", "复古棕": "brown", "琥珀": "brown", "咖啡": "brown",
    "焦糖": "brown", "棕色": "brown",
    # 米/奶油系
    "暖米": "cream", "米白": "cream", "米色": "cream", "奶油": "cream",
    "奶白": "cream", "杏色": "cream",
    # 橘/橙系
    "暖橘": "warm", "暖橙": "warm", "落日": "warm", "枫叶": "warm",
    "橘色": "warm", "橙色": "warm",
    # 蓝系（新配色）
    "天蓝": "blue", "雾蓝": "blue", "靛蓝": "blue", "蓝色": "blue",
    # 紫系（新配色）
    "薰衣草": "purple", "香芋": "purple", "紫色": "purple",
    # 红系（新配色）
    "酒红": "red", "车厘子": "red", "莓红": "red", "红色": "red",
    # 黄系（新配色）
    "柠檬": "yellow", "鹅黄": "yellow", "黄色": "yellow",
    # 绿系（新配色）
    "抹茶": "green", "薄荷": "green", "青碧": "green", "绿色": "green",
}
TONE_WORDS = {
    "温柔": "warm", "治愈": "warm", "温暖": "warm",
    "清新": "cream", "清透": "cream", "清爽": "cream",
    "复古": "brown",
}


# --- 颜色工具（hex ↔ hsl），供 theme:#hex 自定义或未来未知颜色派生整套餐配色 ---
def _hex2rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb2hex(r, g, b):
    def c(x):
        return max(0, min(255, round(x)))
    return "#{:02x}{:02x}{:02x}".format(c(r), c(g), c(b))


def _rgb2hsl(r, g, b):
    r, g, b = r / 255, g / 255, b / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        h = s = 0.0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h *= 60
    return h, s, l


def _hsl2rgb(h, s, l):
    h = h % 360
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    rgb = ((c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x))[int(h // 60) % 6]
    return tuple((v + m) * 255 for v in rgb)


def derive_theme(base_hex: str) -> dict:
    """从基础色派生一整套配色（深/浅/辅助绿/渐变/页脚），用于新增颜色。"""
    r, g, b = _hex2rgb(base_hex)
    h, s, l = _rgb2hsl(r, g, b)

    def H(hh, ss, ll):
        return _rgb2hex(*_hsl2rgb(hh, ss, ll))

    return {
        "accent": base_hex,
        "deep": H(h, min(s + 0.1, 0.85), max(l * 0.58, 0.20)),
        "light": H(h, min(s, 0.45), 0.955),
        "green": "#9fc9b8",          # 固定柔和青绿（辅助色）
        "ink": H(h, min(s * 0.45, 0.26), 0.26),
        "muted": H(h, min(s * 0.3, 0.14), 0.55),
        "line": H(h, min(s, 0.4), 0.90),
        "head_from": H(h, min(s, 0.65), 0.94),
        "head_to": "#eaf2ec",        # 固定浅绿（头部渐变终点）
        "price_from": H(h, min(s, 0.55), 0.955),
        "price_to": H(h, min(s, 0.3), 0.985),
        "foot": H(h, min(s * 0.4, 0.26), 0.24),
        "foot_ink": H(h, min(s, 0.35), 0.93),
        "foot_accent": H(h, min(s, 0.7), 0.82),
    }


def detect_theme_key(fm: dict, body: dict):
    """在卡片里找最早出现的颜色词 → 主题 key；无具体颜色再按氛围兜底。"""
    scan = "\n".join([
        str(fm.get("name") or ""),
        str(fm.get("category") or ""),
        " ".join(fm.get("selling_points") or []),
        " ".join(fm.get("seo_keywords") or []),
        " ".join(fm.get("tags") or []),
        str(fm.get("audience") or ""),
        body.get("一句话定位") or "",
        body.get("核心卖点详述") or "",
        body.get("使用场景") or "",
        body.get("目标人群") or "",
        body.get("备注") or "",
    ])
    for words in (COLOR_WORDS, TONE_WORDS):
        best_pos, best_key = None, None
        for kw, key in words.items():
            p = scan.find(kw)
            if p != -1 and (best_pos is None or p < best_pos):
                best_pos, best_key = p, key
        if best_key:
            return best_key
    return None


def resolve_theme(fm: dict, body: dict):
    """返回 (主题 key, 主题配色 dict)。

    优先级：frontmatter 的 theme 字段（可写预设名或 #hex）＞ 颜色描述推断 ＞ 默认 pink。
    """
    explicit = (fm.get("theme") or "").strip()
    if explicit:
        if re.fullmatch(r"#[0-9a-fA-F]{6}", explicit):
            return explicit, derive_theme(explicit)
        if explicit in THEMES:
            return explicit, THEMES[explicit]
    detected = detect_theme_key(fm, body)
    if detected and detected in THEMES:
        return detected, THEMES[detected]
    return DEFAULT_THEME, THEMES[DEFAULT_THEME]


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def parse_frontmatter(fm_text: str) -> dict:
    """解析本产品库使用的简化 front matter（扁平键 + 行内 list）。"""
    data = {}
    for line in fm_text.splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            data[key] = [] if not inner else [
                x.strip().strip('"').strip("'") for x in inner.split(",")
            ]
        else:
            # 模板允许 theme 留空并带说明注释；不要把注释误当成色值。
            if key == "theme" and val.startswith("#") and not re.fullmatch(r"#[0-9a-fA-F]{6}", val):
                val = ""
            data[key] = val.strip('"').strip("'")
    return data


def parse_body(text: str) -> dict:
    """把正文按 '## 标题' 切成块，返回 {标题: 块内容}。"""
    sections, cur, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur is not None:
                sections[cur] = "\n".join(buf)
            cur, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if cur is not None:
        sections[cur] = "\n".join(buf)
    return sections


def sub_bullets(section_text: str, marker: str) -> list:
    """取某 '### ' 子标题下所有 '- ' 列表项（marker 为子标题里含的关键字）。"""
    out, on = [], False
    for line in section_text.splitlines():
        if line.startswith("### "):
            on = marker in line
            continue
        if on:
            s = line.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
    return out


def split_dun(s: str) -> list:
    """按 、，, 切分（保留 '/' 不切，用于人群）。"""
    return [x.strip() for x in re.split(r"[、，,]", s or "") if x.strip()]


def split_slash(s: str) -> list:
    """按 /、，, 切分（用于审美关键词等斜杠列表）。"""
    return [x.strip() for x in re.split(r"[/、，,]", s or "") if x.strip()]


def clean_audience(tag: str) -> str:
    """人群短语清洗：去掉『喜欢』前缀与『的人/人群』后缀。"""
    t = tag.strip()
    for pre in ("喜欢", "爱"):
        if t.startswith(pre):
            t = t[len(pre):]
            break
    for suf in ("的人群", "的人", "人群"):
        if t.endswith(suf):
            t = t[: -len(suf)]
            break
    return t.strip()


def format_price(price: str):
    """返回 (currency, main, suffix)，供模板渲染价格行。

    支持：12.9元起 / 10r+ / 9r / 9.8r包邮 等写法。
    """
    p = (price or "").strip()
    if not p:
        return "", "", ""
    suffix = ""
    if p.endswith("包邮"):
        suffix, p = "包邮", p[:-2].strip()
    elif p.endswith("起"):
        suffix, p = "起", p[:-1].strip()
    has_yuan = "元" in p
    main = p.replace("元", "").strip()
    currency = "¥" if has_yuan else ""
    return currency, main, suffix


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def esc(s) -> str:
    return html.escape(str(s), quote=False)


def render_style(t: dict) -> str:
    return f"""
  :root{{
    --pink:{t['accent']}; --pink-deep:{t['deep']}; --pink-light:{t['light']};
    --green:{t['green']}; --ink:{t['ink']}; --muted:{t['muted']}; --line:{t['line']};
    --head-from:{t['head_from']}; --head-to:{t['head_to']};
    --price-from:{t['price_from']}; --price-to:{t['price_to']};
    --foot:{t['foot']}; --foot-ink:{t['foot_ink']}; --foot-accent:{t['foot_accent']};
  }}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:"PingFang SC","Microsoft YaHei",-apple-system,sans-serif;background:#fdf8f9;color:var(--ink);line-height:1.7;}}
  .wrap{{max-width:760px;margin:0 auto;padding:32px 20px 60px;}}
  .card{{background:#fff;border-radius:20px;box-shadow:0 8px 30px rgba(120,90,100,.12);overflow:hidden;}}
  .head{{background:linear-gradient(135deg,var(--head-from) 0%,var(--head-to) 100%);padding:28px 28px 22px;text-align:center;}}
  .tagline{{display:inline-block;background:#fff;color:var(--pink-deep);font-size:12px;padding:4px 12px;border-radius:20px;letter-spacing:1px;margin-bottom:10px;}}
  .head h1{{font-size:26px;letter-spacing:2px;color:var(--ink);}}
  .head .sub{{color:var(--muted);font-size:13px;margin-top:6px;}}
  .status{{margin-top:14px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap;}}
  .pill{{font-size:11px;padding:3px 10px;border-radius:14px;background:#fff;border:1px solid var(--line);color:var(--muted);}}
  .pill.hot{{background:var(--pink-light);border-color:var(--pink);color:var(--pink-deep);font-weight:600;}}
  .body{{padding:26px 28px;}}
  .sec{{margin-bottom:26px;}}
  .sec h2{{font-size:15px;color:var(--pink-deep);letter-spacing:1px;margin-bottom:12px;display:flex;align-items:center;gap:8px;}}
  .sec h2::before{{content:"";width:4px;height:16px;background:linear-gradient(var(--pink),var(--green));border-radius:2px;}}
  .grid{{display:flex;flex-wrap:wrap;gap:8px;}}
  .tag{{background:var(--pink-light);color:var(--pink-deep);font-size:12.5px;padding:5px 12px;border-radius:16px;}}
  .tag.g{{background:#eef7f2;color:#4f9a7d;}}
  ul.clean{{list-style:none;}}
  ul.clean li{{font-size:13.5px;padding:5px 0 5px 20px;position:relative;color:var(--ink);}}
  ul.clean li::before{{content:"·";position:absolute;left:4px;color:var(--pink-deep);font-weight:bold;}}
  .kv{{border:1px solid var(--line);border-radius:14px;padding:14px 16px;background:#fffdfd;}}
  .kv .row{{display:flex;font-size:13.5px;padding:3px 0;}}
  .kv .k{{width:88px;color:var(--muted);flex-shrink:0;}}
  .kv .v{{color:var(--ink);}}
  .price{{background:linear-gradient(135deg,var(--price-from),var(--price-to));border-radius:14px;padding:14px 16px;text-align:center;}}
  .price .num{{font-size:30px;font-weight:800;color:var(--pink-deep);}}
  .price .num small{{font-size:14px;}}
  .foot{{background:var(--foot);color:var(--foot-ink);padding:18px 24px;font-size:12.5px;text-align:center;line-height:1.9;}}
  .foot .tags{{color:var(--foot-accent);margin-bottom:4px;}}
  .foot .link{{color:#fff;font-weight:700;letter-spacing:1px;}}
  .note{{font-size:12px;color:var(--muted);text-align:center;margin-top:14px;}}
"""


def render_tag_spans(items, green_flags=None):
    """渲染一组 tag <span>（不含外层 .grid）。"""
    parts = []
    for i, it in enumerate(items):
        cls = "tag g" if (green_flags and green_flags[i]) else "tag"
        parts.append(f'<span class="{cls}">{esc(it)}</span>')
    return "".join(parts)


def render_tags(items, green_flags=None):
    """渲染一个 tag 网格（外层 .grid + 一组 <span>）。"""
    return '<div class="grid">' + render_tag_spans(items, green_flags) + "</div>"


def render_grid_block(pink_items, green_items=None):
    """第一组主色 tag + 可选第二组绿色 tag（加 margin-top 隔开）。

    对应模板里的「人群关键词 / 场景关键词」双网格：第一行主色，第二行辅助色。
    """
    first = render_tags(pink_items)
    if not green_items:
        return first
    second = ('<div class="grid" style="margin-top:8px;">'
              + render_tag_spans(green_items, [True] * len(green_items))
              + "</div>")
    return first + second


def section_after_heading(section_text: str, marker: str) -> str:
    """取 '### <marker>' 标题之后的内容（到下一个 '### ' 或块尾），压成一行。"""
    out, on = [], False
    for line in (section_text or "").splitlines():
        if line.startswith("### "):
            on = marker in line
            continue
        if on:
            s = line.strip()
            if s:
                out.append(s)
    return " ".join(out)


def build_html(slug: str, fm: dict, body: dict) -> str:
    theme_key, t = resolve_theme(fm, body)

    name = fm.get("name") or slug
    category = fm.get("category") or ""
    category_primary = category.split("/")[0] if category else "好物"
    price_raw = fm.get("price") or ""

    selling_points = fm.get("selling_points") or []
    seo_keywords = fm.get("seo_keywords") or []
    tags = fm.get("tags") or []
    audience_raw = fm.get("audience") or ""

    # 一句话定位 → 标题副行（取第一个逗号/句号前的"组合"部分）
    positioning = (body.get("一句话定位") or "").strip()
    sub = re.split(r"[，。：；]", positioning)[0].strip() if positioning else \
        " × ".join(selling_points[:4])

    # 卖点详述子块
    detail = body.get("核心卖点详述") or ""
    emotion_items = sub_bullets(detail, "④")
    price_value_items = sub_bullets(detail, "⑤")

    # 使用场景 → (类目, 值) 列表
    scenarios = []
    for line in (body.get("使用场景") or "").splitlines():
        m = re.match(r"-\s*\*\*(.+?)\*\*[：:]\s*(.*)", line.strip())
        if m:
            scenarios.append((m.group(1).strip(), m.group(2).strip()))

    # 审美关键词（目标人群 → ### 审美关键词 之后的内容）
    aesthetics_text = section_after_heading(body.get("目标人群") or "", "审美关键词")
    aesthetics = split_slash(aesthetics_text)

    # 状态 pill：created==updated 视为"新建"
    created = fm.get("created") or ""
    updated = fm.get("updated") or ""
    status_text = "新建" if (created and created == updated) else "更新"

    currency, price_main, price_suffix = format_price(price_raw)
    price_line = ""
    if price_main:
        price_line = (f'<div class="num">'
                      + (f"<small>{currency}</small>" if currency else "")
                      + esc(price_main)
                      + (f" <small>{esc(price_suffix)}</small>" if price_suffix else "")
                      + "</div>")

    # 价格价值说明（最多 3 条，用 · 连接）
    price_note = " · ".join(price_value_items[:3])

    # 卖点 green 判定
    sp_green = [
        any(h in sp for h in GREEN_POINT_HINT) for sp in selling_points
    ]

    # 人群（主色）
    audience_tags = [clean_audience(x) for x in split_dun(audience_raw) if clean_audience(x)]

    # 场景拆分
    scene_pink, scene_green = [], []
    for cat, val in scenarios:
        target = scene_pink if (cat in SCENARIO_PINK) else scene_green
        target.extend(split_dun(val))

    # 情绪价值分组渲染（每 3 条一行，用 · 连接）
    emo_lines = [
        " · ".join(emotion_items[i:i + 3]) for i in range(0, len(emotion_items), 3)
    ]

    # 系列定位
    combo = " × ".join(selling_points)
    kw = "｜".join(seo_keywords)

    foot_tags = " ".join(tags)

    body_sections = []

    if selling_points:
        body_sections.append(
            f'<div class="sec"><h2>产品核心价值</h2>{render_tags(selling_points, sp_green)}</div>')

    if audience_tags or aesthetics:
        body_sections.append(
            f'<div class="sec"><h2>人群关键词</h2>{render_grid_block(audience_tags, aesthetics)}</div>')

    if scene_pink or scene_green:
        body_sections.append(
            f'<div class="sec"><h2>场景关键词</h2>{render_grid_block(scene_pink, scene_green)}</div>')

    if emo_lines:
        lis = "".join(f"<li>{esc(x)}</li>" for x in emo_lines)
        body_sections.append(
            f'<div class="sec"><h2>情绪价值关键词</h2><ul class="clean">{lis}</ul></div>')

    if price_line:
        note_div = (f'<div style="color:var(--muted);font-size:12.5px;margin-top:4px;">'
                    f"{esc(price_note)}</div>") if price_note else ""
        body_sections.append(
            f'<div class="sec"><h2>价格价值</h2><div class="price">{price_line}{note_div}</div></div>')

    if combo or kw:
        rows = []
        if combo:
            rows.append(f'<div class="row"><span class="k">组合</span><span class="v">{esc(combo)}</span></div>')
        if kw:
            rows.append(f'<div class="row"><span class="k">关键词</span><span class="v">{esc(kw)}</span></div>')
        body_sections.append(
            f'<div class="sec"><h2>系列定位</h2><div class="kv">{"".join(rows)}</div></div>')

    body_html = ("\n      ".join(body_sections) or "      <!-- 无内容 -->")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>产品卡 · {esc(name)}</title>
<style>{render_style(t)}</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="head">
      <span class="tagline">新品 · {esc(category_primary)}</span>
      <h1>{esc(name)}</h1>
      <div class="sub">{esc(sub)}</div>
      <div class="status">
        <span class="pill hot">状态：{esc(status_text)}</span>
        <span class="pill">{esc(price_raw)}</span>
        <span class="pill">{esc(category)}</span>
      </div>
    </div>

    <div class="body">
      {body_html}
    </div>

    <div class="foot">
      <div class="tags">{esc(foot_tags)}</div>
      <div class="link">— 👇👇👇 点击链接 👇👇👇 —</div>
    </div>
  </div>
  <div class="note">由 xhs-rewriter 产品库自动生成 · 产品卡 {esc(slug)} · 主题 {esc(theme_key)}</div>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def load_product(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path.name}: 未找到 front matter")
    fm = parse_frontmatter(m.group(1))
    body = parse_body(m.group(2))
    slug = fm.get("slug") or path.stem
    return slug, fm, body


def list_products():
    return sorted(p for p in PRODUCTS_DIR.glob("*.md") if p.stem != "_index")


def build_index(products):
    """生成 products/index.html，聚合全部产品卡入口。"""
    items = []
    for p in products:
        slug, fm, body = load_product(p)
        name = fm.get("name") or slug
        category = fm.get("category") or ""
        price = fm.get("price") or ""
        theme_key = fm.get("theme") or detect_theme_key(fm, body) or DEFAULT_THEME
        items.append(
            f'<li><a href="{slug}.html">{esc(name)}</a>'
            f'<span class="m">{esc(category)} · {esc(price)} · {esc(theme_key)}</span></li>'
        )
    lis = "\n".join(f"      {x}" for x in items)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>产品卡索引</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:"PingFang SC","Microsoft YaHei",-apple-system,sans-serif;background:#fdf8f9;color:#4a3b44;line-height:1.7;}}
  .wrap{{max-width:720px;margin:0 auto;padding:40px 20px 60px;}}
  h1{{font-size:22px;letter-spacing:1px;margin-bottom:6px;}}
  .sub{{color:#9b8a93;font-size:13px;margin-bottom:24px;}}
  ul{{list-style:none;}}
  li{{background:#fff;border-radius:14px;box-shadow:0 4px 16px rgba(120,90,100,.08);margin-bottom:12px;}}
  a{{display:block;padding:16px 18px;text-decoration:none;color:#e878a0;font-size:16px;font-weight:600;}}
  li .m{{display:block;color:#9b8a93;font-size:12px;font-weight:400;padding:0 18px 14px;}}
</style>
</head>
<body>
<div class="wrap">
  <h1>产品卡一览</h1>
  <div class="sub">由 xhs-rewriter 产品库自动生成 · 点击查看单张产品卡</div>
  <ul>
{lis}
  </ul>
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="产品卡 HTML 生成器")
    ap.add_argument("slugs", nargs="*", help="slug（不填则配合 --all）")
    ap.add_argument("--all", action="store_true", help="生成全部产品卡")
    ap.add_argument("--list", action="store_true", help="列出可生成的产品")
    ap.add_argument("--index", action="store_true", help="生成 index.html 索引页；可单独使用")
    args = ap.parse_args()

    products = list_products()
    if args.list:
        for p in products:
            slug, fm, body = load_product(p)
            theme_key, _ = resolve_theme(fm, body)
            src = "theme字段" if (fm.get("theme") or "").strip() else "颜色描述"
            print(f"  {p.stem:<38} {fm.get('name', '')}  [主题={theme_key}（{src}）]")
        return

    # --index 可独立使用，便于只同步索引页而不重写单张产品卡。
    if args.index and not args.all and not args.slugs:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        idx = OUTDIR / "index.html"
        idx.write_text(build_index(products), encoding="utf-8")
        print(f"✅ {idx.relative_to(ROOT)}  ← 索引页")
        return

    targets = products if args.all else None
    if not args.all:
        if not args.slugs:
            ap.error("请指定 slug 或使用 --all / --list")
        want = set(args.slugs)
        targets = [p for p in products if p.stem in want]
        missing = want - {p.stem for p in products}
        if missing:
            print(f"❌ 未找到产品卡: {', '.join(sorted(missing))}")
            sys.exit(1)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    made = []
    for p in targets:
        slug, fm, body = load_product(p)
        out = OUTDIR / f"{slug}.html"
        out.write_text(build_html(slug, fm, body), encoding="utf-8")
        made.append((slug, fm.get("name") or slug, out.name))
        print(f"✅ {out.relative_to(ROOT)}  ← {p.name}")

    if args.index or args.all:
        idx = OUTDIR / "index.html"
        idx.write_text(build_index(products), encoding="utf-8")
        print(f"✅ {idx.relative_to(ROOT)}  ← 索引页")

    print(f"\n共生成 {len(made)} 张产品卡 → {OUTDIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
