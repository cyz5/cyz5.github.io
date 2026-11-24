# -*- coding: utf-8 -*-
"""生成站点页面：首页、能力地图、章节/小节索引、课程页、待撰写页、学习路线。"""
from __future__ import annotations

import html
import json
import posixpath
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

from vault import Chapter, Lesson, Point, Section, Vault

WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
CN_TZ = ZoneInfo("Asia/Shanghai")

CHAPTER_ICONS = {
    1: "🧩", 2: "🧱", 3: "🔌", 4: "⏱️", 5: "🐧", 6: "🏗️", 7: "⚙️",
    8: "🌐", 9: "🎛️", 10: "🛡️", 11: "🔬", 12: "🤝", 13: "🤖", 14: "🧭",
}

CHAPTER_TAGLINES = {
    1: "指针、内存、预处理器与编译链接",
    2: "类与对象、RAII、constexpr 与 C/C++ 混编",
    3: "Cortex-M 内核、外设驱动、DMA 与低功耗",
    4: "任务、同步、内存管理、移植与系统调试",
    5: "驱动开发、设备树、构建系统与实时性",
    6: "分层架构、模块化、状态机与中间件",
    7: "构建、CI/CD、测试体系与代码质量",
    8: "CAN、EtherCAT、TCP/IP 与工业以太网",
    9: "电机控制、电源管理、传感器融合与 HMI",
    10: "功能安全、信息安全与合规标准",
    11: "实时性分析、DSP、OTA 与故障诊断",
    12: "项目管理、文档、沟通与问题解决",
    13: "TinyML、推理框架与边缘部署",
    14: "需求建模、业务状态机、容错与可维护性",
}


def fmt_words(n: int) -> str:
    """客观字数，不用「阅读时长」这种估算。"""
    if n >= 10000:
        return f"{n / 10000:.1f} 万字"
    return f"{n:,} 字"


def fmt_date(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, CN_TZ).strftime("%Y-%m-%d")
    except Exception:
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- 基础
def esc(v) -> str:
    return html.escape(str(v), quote=True)


def url_of(doc: str) -> str:
    if doc == "index.md":
        return ""
    if doc.endswith("/index.md"):
        return doc[: -len("index.md")]
    return doc[:-3] + "/"


def href(from_doc: str, to_doc: str) -> str:
    base = url_of(from_doc).rstrip("/") or "."
    target = url_of(to_doc)
    if not target:
        rel = posixpath.relpath(".", base)
        return "./" if rel == "." else rel + "/"
    rel = posixpath.relpath(target.rstrip("/"), base)
    return rel + "/"


def frontmatter(meta: dict) -> str:
    out = ["---"]

    def dump(k, v, ind=0):
        pad = "  " * ind
        if isinstance(v, dict):
            out.append(f"{pad}{k}:")
            for kk, vv in v.items():
                dump(kk, vv, ind + 1)
        elif isinstance(v, list):
            out.append(f"{pad}{k}:")
            for x in v:
                out.append(f"{pad}  - {json.dumps(x, ensure_ascii=False)}")
        elif isinstance(v, bool):
            out.append(f"{pad}{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            out.append(f"{pad}{k}: {v}")
        else:
            out.append(f"{pad}{k}: {json.dumps(str(v), ensure_ascii=False)}")

    for k, v in meta.items():
        if v is not None:
            dump(k, v)
    out.append("---")
    return "\n".join(out) + "\n"


def page(meta: dict, body: str) -> str:
    return frontmatter(meta) + "\n" + body.strip() + "\n"


def bar(done: int, total: int, cls: str = "") -> str:
    pct = 0 if not total else round(done * 100 / total)
    return (f'<div class="bar {cls}" role="progressbar" aria-valuenow="{pct}" '
            f'aria-valuemin="0" aria-valuemax="100"><i style="width:{pct}%"></i></div>')


def num(n: int) -> str:
    return f"{n:,}"


# ---------------------------------------------------------------- 代码块
CPP_RE = re.compile(r"\bstd::|class\s+\w+\s*[{:]|template\s*<|namespace\s+\w+|\w+::\w+\s*\(")
BASH_RE = re.compile(r"^\s*(?:\$ |git\s|cmake\s|make\b|pip\s|apt\s|sudo\s|export\s|"
                     r"cd\s|ls\s|mkdir\s|chmod\s|tar\s|ssh\s|openocd\b|arm-none-eabi-)", re.M)
PY_RE = re.compile(r"^\s*(?:def |import \w+|from \w+ import )", re.M)
C_SCORES = [
    r"#include\s*[<\"]",
    r"\b(?:uint\d+_t|int\d+_t|size_t|volatile|typedef|struct|union|enum)\b",
    r"\b(?:HAL|LL)_[A-Z]\w+", r"\b(?:if|for|while)\s*\(",
    r"0x[0-9A-Fa-f]{2,}", r"->", r";\s*$", r"\breturn\b",
]


def classify(block: str) -> str:
    if not block.strip():
        return "text"
    if CPP_RE.search(block):
        return "cpp"
    if BASH_RE.search(block):
        return "bash"
    if PY_RE.search(block) and not re.search(r";\s*$", block, re.M):
        return "python"
    score = sum(1 for p in C_SCORES if re.search(p, block, re.M))
    if (block.count(";") >= 2 and score >= 2) or score >= 4:
        return "c"
    if re.search(r'^\s*[{[]', block) and re.search(r'"\w+"\s*:', block):
        return "json"
    return "text"


def tag_fences(text: str) -> str:
    out, buf = [], []
    in_f = False
    info = ""
    for line in text.split("\n"):
        if line.startswith("```"):
            if not in_f:
                info = line[3:].strip()
                buf = []
                in_f = True
            else:
                lang = info or classify("\n".join(buf))
                out.append("```" + lang)
                out.extend(buf)
                out.append("```")
                in_f = False
            continue
        if in_f:
            buf.append(line)
        else:
            out.append(line)
    if in_f:
        out.append("```" + info)
        out.extend(buf)
    return "\n".join(out)


# ---------------------------------------------------------------- 站点
@dataclass
class Config:
    name: str
    tagline: str
    description: str
    author: str
    repo: str
    labs_repo: str
    branch: str
    roadmap: dict
    exclude: list


class Site:
    def __init__(self, cfg: Config, vault: Vault):
        self.cfg = cfg
        self.v = vault
        self.stats = vault.stats()
        self.order = vault.all_points()
        self.stem_to_point = {p.lesson.stem: p for p in self.order if p.lesson}

    # ---------- 路径 ----------
    @staticmethod
    def ch_doc(c: Chapter) -> str:
        return f"chapters/{c.no:02d}-{c.slug}/index.md"

    @staticmethod
    def sec_doc(s: Section) -> str:
        return f"chapters/{s.chapter.no:02d}-{s.chapter.slug}/{s.slug}/index.md"

    @staticmethod
    def pt_doc(p: Point) -> str:
        return f"{p.slug}/index.md"

    def link(self, from_doc: str, to_doc: str, text: str, cls: str = "") -> str:
        c = f' class="{cls}"' if cls else ""
        return f'<a href="{esc(href(from_doc, to_doc))}"{c}>{text}</a>'

    def point_link(self, from_doc: str, p: Point, cls: str = "") -> str:
        return self.link(from_doc, self.pt_doc(p), esc(p.title), cls)

    def nav_title(self, p: Point) -> str:
        """侧边栏去掉与所属小节重复的前缀。"""
        for sep in ("：", ":"):
            prefix = p.section.title + sep
            if p.title.startswith(prefix) and len(p.title) > len(prefix) + 2:
                return p.title[len(prefix):].strip()
        return p.title

    def github(self, path: str, action: str = "blob") -> str:
        return f"{self.cfg.repo}/{action}/{self.cfg.branch}/{quote(path)}"

    def breadcrumb(self, from_doc: str, chapter: Optional[Chapter] = None,
                   section: Optional[Section] = None) -> str:
        parts = [f'<a href="{esc(href(from_doc, "index.md"))}">首页</a>']
        if chapter:
            parts.append(f'<a href="{esc(href(from_doc, self.ch_doc(chapter)))}">'
                         f'第 {chapter.no} 章</a>')
        if section:
            parts.append(f'<a href="{esc(href(from_doc, self.sec_doc(section)))}">'
                         f'{esc(section.no)} {esc(section.title)}</a>')
        return '<nav class="crumbs" aria-label="面包屑">' + '<span>/</span>'.join(parts) + "</nav>"

    def chip(self, text: str, cls: str = "") -> str:
        c = f"chip {cls}".strip()
        return f'<span class="{c}">{text}</span>'

    # ============================================================ 首页
    def home(self) -> str:
        doc = "index.md"
        st = self.stats
        words = st["words"]
        coverage = round(st["lessons"] * 100 / st["points"])
        cards = []
        for c in self.v.chapters:
            pct = 0 if not c.total else round(c.done * 100 / c.total)
            icon = CHAPTER_ICONS.get(c.no, "📘")
            tagline = CHAPTER_TAGLINES.get(c.no, "")
            cards.append(f"""<a class="chapter-card" href="{esc(href(doc, self.ch_doc(c)))}">
  <div class="cc-top"><span class="cc-icon">{icon}</span><span class="cc-ch">CH {c.no:02d}</span><span class="cc-pct">{pct}%</span></div>
  <h3>{esc(c.title)}</h3>
  <p class="cc-tag">{esc(tagline)}</p>
  <p class="cc-meta">{len(c.sections)} 个小节 · {c.done} / {c.total} 节</p>
  {bar(c.done, c.total)}
</a>""")
        recent = sorted([p for p in self.order if p.lesson],
                        key=lambda p: p.lesson.mtime, reverse=True)[:8]
        recent_html = "\n".join(
            f'<li><a href="{esc(href(doc, self.pt_doc(p)))}"><span class="r-no">{p.no}</span>'
            f'{esc(p.title)}</a><time>{fmt_date(p.lesson.mtime)}</time></li>'
            for p in recent)
        ch = {c.no: c for c in self.v.chapters}

        body = f"""
<section class="hero">
  <div class="hero-bg" aria-hidden="true"></div>
  <div class="hero-inner">
    <div class="hero-copy">
      <p class="eyebrow">EMBEDDED SYSTEMS · 2026</p>
      <h1>嵌入式高级工程师<br><span>能力地图与课程</span></h1>
      <p class="hero-sub">{st['points']} 个技能点 · {st['lessons']} 节课程 · {num(st['codes'])} 段工程代码</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="{esc(href(doc, 'p/1-1-1/index.md'))}">从第一节开始 →</a>
        <a class="btn" href="{esc(href(doc, 'map.md'))}">打开能力地图</a>
      </div>
    </div>
    <div class="hero-code" aria-hidden="true">
      <div class="code-window">
        <div class="code-bar"><i></i><i></i><i></i><span>gpio_irq.c</span></div>
        <pre><code><span class="tok-c">/* 3.2.1 GPIO 中断 */</span>
<span class="tok-k">void</span> <span class="tok-f">EXTI0_IRQHandler</span>(<span class="tok-k">void</span>)
{{
    <span class="tok-f">exti_clear_pending</span>(<span class="tok-n">PIN_0</span>);
    <span class="tok-f">event_push</span>(<span class="tok-n">PIN_0</span>,
                 <span class="tok-f">gpio_read</span>(<span class="tok-n">GPIOA</span>, <span class="tok-n">PIN_0</span>));
}}</code></pre>
      </div>
    </div>
  </div>
</section>

<div class="stats">
  <div class="stat"><span class="stat-icon">🧭</span><strong>{st['points']}</strong><span class="stat-label">技能点</span></div>
  <div class="stat"><span class="stat-icon">📚</span><strong>{st['lessons']}</strong><span class="stat-label">已上线课程</span></div>
  <div class="stat"><span class="stat-icon">✍️</span><strong>{words / 10000:.0f}<em>万</em></strong><span class="stat-label">课程正文字数</span></div>
  <div class="stat"><span class="stat-icon">💻</span><strong>{num(st['codes'])}</strong><span class="stat-label">代码示例</span></div>
</div>

<section class="section">
  <div class="section-head">
    <h2>学习路径</h2>
    <p>从语言基础到电机控制，按依赖顺序推进；也可以直接跳到你现在的位置。</p>
  </div>
  <ol class="path">
    <li><a href="{esc(href(doc, self.ch_doc(ch[1])))}"><span class="path-no">01</span><span class="path-text"><strong>C 语言深度</strong><small>指针 · 内存 · 编译链接</small></span></a></li>
    <li><a href="{esc(href(doc, self.ch_doc(ch[3])))}"><span class="path-no">02</span><span class="path-text"><strong>MCU 硬件与底层</strong><small>内核 · 外设 · DMA</small></span></a></li>
    <li><a href="{esc(href(doc, self.ch_doc(ch[4])))}"><span class="path-no">03</span><span class="path-text"><strong>RTOS 技术栈</strong><small>任务 · 同步 · 实时性</small></span></a></li>
    <li><a href="{esc(href(doc, self.ch_doc(ch[8])))}"><span class="path-no">04</span><span class="path-text"><strong>通信协议</strong><small>CAN · EtherCAT · TCP/IP</small></span></a></li>
    <li><a href="{esc(href(doc, self.ch_doc(ch[9])))}"><span class="path-no">05</span><span class="path-text"><strong>电机控制</strong><small>FOC · SVPWM · PID</small></span></a></li>
  </ol>
</section>

<section class="section">
  <div class="section-head">
    <h2>课程章节</h2>
    <p>按能力地图的 14 个章节组织，先写 C / MCU / RTOS，再补 Linux、协议与行业应用。</p>
  </div>
  <div class="chapter-grid">
{chr(10).join(cards)}
  </div>
</section>

<section class="section">
  <div class="section-head">
    <h2>三种进入方式</h2>
    <p>不知道从哪开始，就按第 1 种走。</p>
  </div>
  <div class="entry-grid">
    <a class="entry" href="{esc(href(doc, 'map.md'))}">
      <span class="entry-icon">🗺️</span>
      <h3>按地图走</h3>
      <p>576 个技能点全量清单，标出已上线与待撰写，适合系统排查知识盲区。</p>
      <span class="entry-more">打开能力地图 →</span>
    </a>
    <a class="entry" href="{esc(href(doc, 'roadmap.md'))}">
      <span class="entry-icon">🎯</span>
      <h3>按优先级走</h3>
      <p>按职业目标筛出的三条优先级：先补决定门槛的五项，再扩展。</p>
      <span class="entry-more">查看学习路线 →</span>
    </a>
    <a class="entry" href="{esc(href(doc, 'labs.md'))}">
      <span class="entry-icon">🔧</span>
      <h3>边看边练</h3>
      <p>每节课都有梯度实战任务，配套练习仓库按章节组织，可直接跑测试。</p>
      <span class="entry-more">进入练习库 →</span>
    </a>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <h2>最近更新</h2>
    <p>按源文件修改时间排序。</p>
  </div>
  <ul class="recent">
{recent_html}
  </ul>
</section>

<section class="section note-box">
  <h2>关于内容进度</h2>
  <p>能力地图共 <strong>{st['points']}</strong> 个技能点，目前 <strong>{st['lessons']}</strong> 节有完整课程（{coverage}%），集中在 C 语言、MCU 硬件与 RTOS。
  其余章节已列入写作计划，站内以「待撰写」占位，保证地图完整可导航。</p>
</section>
"""
        return page({"title": "首页", "description": self.cfg.description,
                     "hide": ["navigation", "toc"], "template": "home.html"}, body)

    # ============================================================ 课程总览
    def courses_page(self) -> str:
        doc = "courses.md"
        st = self.stats
        rows = []
        for c in self.v.chapters:
            icon = CHAPTER_ICONS.get(c.no, "📘")
            tagline = CHAPTER_TAGLINES.get(c.no, "")
            pct = 0 if not c.total else round(c.done * 100 / c.total)
            secs = " · ".join(f"{s.no} {s.title}" for s in c.sections[:3])
            if len(c.sections) > 3:
                secs += " …"
            rows.append(f"""<a class="course-row" href="{esc(href(doc, self.ch_doc(c)))}">
  <span class="cr-icon">{icon}</span>
  <span class="cr-main">
    <span class="cr-title">第 {c.no} 章 · {esc(c.title)}</span>
    <span class="cr-desc">{esc(tagline)}</span>
    <span class="cr-secs">{esc(secs)}</span>
    {bar(c.done, c.total)}
  </span>
  <span class="cr-stat"><strong>{pct}%</strong><small>{c.done} / {c.total} 节</small></span>
</a>""")
        body = f"""
<div class="page-head">
  <p class="lead">{st['chapters']} 个章节 · {st['sections']} 个小节 · {st['points']} 个技能点，其中 {st['lessons']} 节已有完整课程。点任意章节进入小节与课程列表。</p>
</div>
<div class="course-list">
{chr(10).join(rows)}
</div>
"""
        return page({"title": "课程",
                     "description": f"按能力地图组织的 {st['chapters']} 个章节，{st['lessons']} 节课程。"},
                    body)

    # ============================================================ 能力地图
    def map_page(self) -> str:
        doc = "map.md"
        st = self.stats
        jumps = "".join(
            f'<a href="#ch{c.no}">{c.no}. {esc(c.title)}</a>' for c in self.v.chapters)
        blocks = []
        for c in self.v.chapters:
            rows = []
            for s in c.sections:
                rows.append(
                    f'<tr class="sec-row"><td colspan="4">'
                    f'<a href="{esc(href(doc, self.sec_doc(s)))}">{esc(s.no)} {esc(s.title)}</a>'
                    f'<span>{s.done} / {s.total}</span></td></tr>')
                for p in s.points:
                    status = (f'<span class="status done">{p.lesson.code_blocks} 段代码</span>'
                              if p.lesson else '<span class="status todo">待撰写</span>')
                    rows.append(f"""<tr data-point="{esc(p.no)}" data-text="{esc((p.no + p.title).lower())}">
  <td class="no">{p.no}</td>
  <td class="name">{self.point_link(doc, p, '' if p.lesson else 'todo')}</td>
  <td class="course">{status}</td>
  <td class="level"><span class="levels" data-point="{esc(p.no)}"><button type="button" class="lvl" data-l="1" aria-label="了解">🌱</button><button type="button" class="lvl" data-l="2" aria-label="熟悉">🌿</button><button type="button" class="lvl" data-l="3" aria-label="精通">🌳</button></span></td>
</tr>""")
            blocks.append(f"""<section class="map-chapter" id="ch{c.no}" data-chapter="{c.no}">
  <div class="map-chapter-head">
    <h2><span class="ch-no">{c.no:02d}</span>{esc(c.title)}</h2>
    <div class="map-chapter-stat"><span>{c.done} / {c.total} 已上线</span>
      <b class="local-pct" data-chapter="{c.no}">0%</b></div>
  </div>
  {bar(c.done, c.total)}
  <table class="map-table">
    <thead><tr><th>序号</th><th>技能点</th><th>课程</th><th>掌握度</th></tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>
</section>""")

        body = f"""
<div class="page-head">
  <p class="lead">完整技能树，共 {st['points']} 个技能点。点击课程名进入正文；点击 🌱🌿🌳 记录自己的掌握度（只存在本机浏览器）。</p>
  <div class="map-toolbar">
    <input id="map-filter" type="search" placeholder="筛选：中断 / DMA / FreeRTOS / 3.1 …" aria-label="筛选技能点">
    <span id="map-count" class="map-count">{st['points']} 个技能点</span>
    <span class="legend">🌱 了解 · 🌿 熟悉 · 🌳 精通</span>
    <button id="progress-reset" type="button" class="btn-ghost">清空我的进度</button>
  </div>
  <div class="jump">{jumps}</div>
</div>

{chr(10).join(blocks)}
"""
        return page({"title": "能力地图",
                     "description": f"{st['points']} 个嵌入式技能点的完整清单，含课程状态与掌握度记录。",
                     "hide": ["navigation"]},
                    body)

    # ============================================================ 章节页
    def chapter_page(self, c: Chapter) -> str:
        doc = self.ch_doc(c)
        cards = []
        for s in c.sections:
            pct = 0 if not s.total else round(s.done * 100 / s.total)
            cards.append(f"""<a class="sec-card" href="{esc(href(doc, self.sec_doc(s)))}">
  <div class="sc-top"><span class="sc-no">{esc(s.no)}</span><span class="sc-pct">{pct}%</span></div>
  <h3>{esc(s.title)}</h3>
  <p>{s.done} / {s.total} 节</p>
  {bar(s.done, s.total)}
</a>""")
        pct = 0 if not c.total else round(c.done * 100 / c.total)
        body = f"""
{self.breadcrumb(doc, c)}
<div class="page-head">
  <p class="lead">{c.total} 个技能点 · {len(c.sections)} 个小节 · 已上线 {c.done} 节（{pct}%）</p>
  {bar(c.done, c.total, "wide")}
</div>
<div class="card-grid">
{chr(10).join(cards)}
</div>
"""
        return page({"title": f"第 {c.no} 章 · {c.title}",
                     "description": f"{c.title}：{c.total} 个技能点，{c.done} 节课程已上线。"},
                    body)

    # ============================================================ 小节页
    def section_page(self, s: Section) -> str:
        doc = self.sec_doc(s)
        rows = []
        for p in s.points:
            if p.lesson:
                course = (f'<a href="{esc(href(doc, self.pt_doc(p)))}">阅读</a>'
                          f'<span class="muted">{fmt_words(p.lesson.body_chars)}</span>')
            else:
                course = '<span class="muted">待撰写</span>'
            rows.append(f"""<tr>
  <td class="no">{p.no}</td>
  <td class="name">{self.point_link(doc, p, '' if p.lesson else 'todo')}</td>
  <td>{course}</td>
</tr>""")
        prev_s = next_s = None
        for i, sec in enumerate(s.chapter.sections):
            if sec is s:
                prev_s = s.chapter.sections[i - 1] if i > 0 else None
                next_s = (s.chapter.sections[i + 1]
                          if i + 1 < len(s.chapter.sections) else None)
        nav = ['<nav class="prevnext">']
        nav.append(self.link(doc, self.sec_doc(prev_s),
                             "← " + esc(prev_s.no) + " " + esc(prev_s.title), "prev")
                   if prev_s else "<span></span>")
        nav.append(self.link(doc, self.sec_doc(next_s),
                             esc(next_s.no) + " " + esc(next_s.title) + " →", "next")
                   if next_s else "<span></span>")
        nav.append("</nav>")
        body = f"""
{self.breadcrumb(doc, s.chapter, s)}
<div class="page-head">
  <p class="lead">{s.total} 个技能点 · 已上线 {s.done} 节</p>
  {bar(s.done, s.total, "wide")}
</div>
<table class="point-table">
  <thead><tr><th>序号</th><th>技能点</th><th>课程</th></tr></thead>
  <tbody>
{chr(10).join(rows)}
  </tbody>
</table>
{''.join(nav)}
"""
        return page({"title": f"{s.no} {s.title}",
                     "description": f"{s.title}：{s.total} 个技能点，{s.done} 节课程。"}, body)

    # ============================================================ 课程页
    def lesson_page(self, p: Point) -> str:
        doc = self.pt_doc(p)
        L = p.lesson
        assert L is not None
        body = WIKI_RE.sub(lambda m: self._wiki(m, doc), L.body)
        body = tag_fences(body)
        chips = [self.chip(p.no, "chip-id"),
                 self.chip(fmt_words(L.body_chars)),
                 self.chip(f"{L.code_blocks} 段代码"),
                 self.chip("已上线", "chip-ok")]
        head = f"""
{self.breadcrumb(doc, p.chapter, p.section)}
<div class="lesson-meta">{''.join(chips)}</div>
"""
        prev_p, next_p = self._siblings(p)
        footer = ['<div class="lesson-end">']
        if "## 16.1" in L.body:
            footer.append('<p class="lab-hint">🔧 文末第 16 节有 4 个梯度实战任务，建议读完立刻写一版。</p>')
        footer.append('<nav class="prevnext">')
        footer.append(self.link(doc, self.pt_doc(prev_p),
                                f'<span>上一节 · {prev_p.no}</span><strong>{esc(prev_p.title)}</strong>',
                                "prev") if prev_p else "<span></span>")
        footer.append(self.link(doc, self.pt_doc(next_p),
                                f'<span>下一节 · {next_p.no}</span><strong>{esc(next_p.title)}</strong>',
                                "next") if next_p else "<span></span>")
        footer.append('</nav>')
        footer.append(f'<p class="src">源文件：<a href="{esc(self.github(L.rel))}" rel="noopener">'
                      f'{esc(L.rel)}</a> · 最后更新 {fmt_date(L.mtime)}</p>')
        footer.append('</div>')
        text = f"{head}\n{body}\n\n{''.join(footer)}"
        return page({"title": f"{p.no} {p.title}",
                     "description": (L.summary or p.title)[:120]}, text)

    def _wiki(self, m: re.Match, from_doc: str) -> str:
        target = m.group(1).strip()
        label = (m.group(2) or target).strip()
        p = self.stem_to_point.get(target)
        if p:
            return self.link(from_doc, self.pt_doc(p), esc(label))
        return esc(label)

    def _siblings(self, p: Point):
        i = self.order.index(p)
        prev_p = self.order[i - 1] if i > 0 else None
        next_p = self.order[i + 1] if i + 1 < len(self.order) else None
        return prev_p, next_p

    # ============================================================ 待撰写
    def stub_page(self, p: Point) -> str:
        doc = self.pt_doc(p)
        sibs = [x for x in p.section.points if x.lesson and x is not p][:6]
        sib_html = "".join(
            f'<li>{self.point_link(doc, x)}<span class="muted">{x.lesson.code_blocks} 段代码</span></li>'
            for x in sibs) or '<li class="muted">同小节暂无已上线课程</li>'
        prev_p, next_p = self._siblings(p)
        nav = ['<nav class="prevnext">']
        nav.append(self.link(doc, self.pt_doc(prev_p), f'<span>上一节 · {prev_p.no}</span>'
                             f'<strong>{esc(prev_p.title)}</strong>', "prev")
                   if prev_p else "<span></span>")
        nav.append(self.link(doc, self.pt_doc(next_p), f'<span>下一节 · {next_p.no}</span>'
                             f'<strong>{esc(next_p.title)}</strong>', "next")
                   if next_p else "<span></span>")
        nav.append('</nav>')
        body = f"""
{self.breadcrumb(doc, p.chapter, p.section)}
<div class="lesson-meta">{self.chip(p.no, "chip-id")}{self.chip("规划中", "chip-todo")}</div>

!!! note "这节还没有正文"
    该技能点已在能力地图中规划，课程正文正在按章节顺序补写。你可以先阅读同小节已上线的课程，或到[能力地图]({esc(href(doc, "map.md"))})查看相邻知识点。

<div class="stub-box">
  <h2>位置</h2>
  <table class="mini">
    <tr><td>所属章节</td><td>{self.link(doc, self.ch_doc(p.chapter), f"第 {p.chapter.no} 章 · " + esc(p.chapter.title))}</td></tr>
    <tr><td>所属小节</td><td>{self.link(doc, self.sec_doc(p.section), esc(p.section.no) + " " + esc(p.section.title))}</td></tr>
    <tr><td>地图序号</td><td>{p.no}（第 {self.order.index(p) + 1} / {len(self.order)} 个技能点）</td></tr>
  </table>
  <h2>同小节已上线</h2>
  <ul class="plain-list">{sib_html}</ul>
</div>

{''.join(nav)}
"""
        return page({"title": f"{p.no} {p.title}",
                     "description": f"{p.title}（规划中）：{p.section.no} {p.section.title} 的技能点。",
                     "search": {"exclude": True}}, body)

    # ============================================================ 学习路线
    def roadmap_page(self) -> str:
        doc = "roadmap.md"
        tiers = self.cfg.roadmap.get("tiers", [])
        blocks = []
        for t in tiers:
            rows = []
            for sel in t.get("points", []):
                for p in self.v.expand(sel):
                    status = ('<span class="status done">已上线</span>' if p.lesson
                              else '<span class="status todo">待撰写</span>')
                    rows.append(f'<tr><td class="no">{p.no}</td>'
                                f'<td>{self.point_link(doc, p)}</td><td>{status}</td></tr>')
            blocks.append(f"""<section class="tier" id="{esc(t.get('key', ''))}">
  <h2>{esc(t['title'])}</h2>
  <p class="tier-desc">{t.get('desc', '')}</p>
  <table class="point-table">
    <thead><tr><th>序号</th><th>技能点</th><th>状态</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>""")
        qrows = "".join(
            f'<tr><td>{esc(q["q"])}</td><td>{esc(q["focus"])}</td><td>{esc(q.get("output", ""))}</td></tr>'
            for q in self.cfg.roadmap.get("quarters", []))
        body = f"""
<div class="page-head">
  <p class="lead">{self.cfg.roadmap.get('intro', '')}</p>
</div>

<div class="tier-nav">{''.join(f'<a href="#{esc(t.get("key", ""))}">{esc(t["short"])}</a>' for t in tiers if t.get("short"))}</div>

{chr(10).join(blocks)}

<section class="tier">
  <h2>季度节奏</h2>
  <p class="tier-desc">按每周 10–12 小时的可投入时间倒排。论文期（2027.9–2028.6）只维护、不新建。</p>
  <table class="point-table">
    <thead><tr><th>季度</th><th>主攻</th><th>交付物</th></tr></thead>
    <tbody>{qrows}</tbody>
  </table>
</section>

<p class="note">说明：本页只保留技术路线与优先级，不含薪资、公司、个人履历等信息。</p>
"""
        return page({"title": "学习路线",
                     "description": "按目标岗位筛出的学习优先级：精通档五项、熟练档四项、了解档四项。",
                     "hide": ["navigation"]},
                    body)
