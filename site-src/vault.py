# -*- coding: utf-8 -*-
"""解析 Obsidian 仓库：能力地图 -> 章节/小节/技能点，笔记 -> 课程。"""
from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from typing import Optional

SECTION_RE = re.compile(r"^###\s+📌\s*([0-9]+(?:\.[0-9]+)*)\s*(.+?)\s*$")
ROW_RE = re.compile(r"^\|\s*([0-9]+(?:\.[0-9]+)+)\s*\|")
WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")

CHAPTER_SLUGS = {
    1: "c-language", 2: "cpp", 3: "mcu", 4: "rtos", 5: "linux",
    6: "architecture", 7: "engineering", 8: "protocols", 9: "industry",
    10: "safety", 11: "specialist", 12: "soft-skills", 13: "edge-ai",
    14: "application",
}


@dataclass
class Section:
    no: str
    title: str
    chapter: "Chapter"
    points: list["Point"] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.no.replace(".", "-")

    @property
    def done(self) -> int:
        return sum(1 for p in self.points if p.lesson)

    @property
    def total(self) -> int:
        return len(self.points)


@dataclass
class Chapter:
    no: int
    title: str
    sections: list[Section] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return CHAPTER_SLUGS.get(self.no, f"ch{self.no}")

    @property
    def points(self) -> list["Point"]:
        return [p for s in self.sections for p in s.points]

    @property
    def done(self) -> int:
        return sum(1 for p in self.points if p.lesson)

    @property
    def total(self) -> int:
        return len(self.points)


@dataclass
class Point:
    no: str
    title: str
    section: Section
    note: str = ""
    marks: tuple = ("", "", "")
    link: Optional[str] = None
    lesson: Optional["Lesson"] = None

    @property
    def chapter(self) -> Chapter:
        return self.section.chapter

    @property
    def slug(self) -> str:
        return "p/" + self.no.replace(".", "-")

    @property
    def status(self) -> str:
        return "已上线" if self.lesson else "待撰写"


@dataclass
class Lesson:
    stem: str
    rel: str
    body: str
    chars: int = 0
    lines: int = 0
    code_blocks: int = 0
    minutes: int = 0
    summary: str = ""
    mtime: float = 0.0
    slug: str = ""


def read_text(path: str) -> str:
    with io.open(path, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def plain(text: str, limit: int = 0) -> str:
    """粗略去 markdown，用于摘要/描述。"""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_#>|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit] if limit else t


class Vault:
    def __init__(self, root: str, exclude: list[str] | None = None):
        self.root = root
        self.map_path = os.path.join(
            root, "技能地图", "高级嵌入式软件工程师超详细技术能力地图.md")
        self.exclude = set(exclude or [])
        self.chapters: list[Chapter] = []
        self.lessons: dict[str, Lesson] = {}
        self.warnings: list[str] = []
        self.load_notes()
        self.parse_map()
        self.bind()

    # ---------- 笔记 ----------
    def load_notes(self) -> None:
        skip_dirs = {".obsidian", ".git", ".github", "_tools", "site-src",
                     "node_modules", "labs", "build"}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames
                           if d not in skip_dirs and not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, self.root).replace("\\", "/")
                if rel in self.exclude:
                    continue
                text = strip_frontmatter(read_text(path))
                stem = fn[:-3]
                if stem in self.lessons:
                    self.warnings.append(f"文件名重复：{stem}（{rel}）")
                    continue
                code = text.count("\n```") // 2
                body_chars = len(plain(text))
                minutes = max(4, round(body_chars / 420 + code * 0.35))
                para = ""
                for block in re.split(r"\n\s*\n", text):
                    b = block.strip()
                    if b and not b.startswith(("#", "|", ">", "-", "*", "```")):
                        para = plain(b, 120)
                        if len(para) > 20:
                            break
                lesson = Lesson(
                    stem=stem, rel=rel, body=text, chars=len(text),
                    lines=text.count("\n") + 1, code_blocks=code,
                    minutes=minutes, summary=para, mtime=os.path.getmtime(path))
                self.lessons[stem] = lesson

    # ---------- 能力地图 ----------
    def parse_map(self) -> None:
        text = read_text(self.map_path)
        titles = []
        for line in text.split("\n"):
            if line.startswith("## "):
                t = re.sub(r"^[^A-Za-z\u4e00-\u9fff]+", "", line[3:].strip())
                if t and t not in ("使用说明", "完整目录"):
                    titles.append(t)

        chapter = None
        section = None
        for line in text.split("\n"):
            if line.startswith("## "):
                chapter = None
                section = None
                continue
            if line.startswith("### ") and "📌" in line:
                m = SECTION_RE.match(line)
                if not m:
                    self.warnings.append(f"小节标题无法解析：{line[:50]}")
                    continue
                no, title = m.group(1), m.group(2).strip()
                cno = int(no.split(".")[0])
                if chapter is None or chapter.no != cno:
                    ctitle = titles[cno - 1] if 0 < cno <= len(titles) else f"第 {cno} 章"
                    chapter = Chapter(no=cno, title=ctitle)
                    self.chapters.append(chapter)
                section = Section(no=no, title=title, chapter=chapter)
                chapter.sections.append(section)
                continue
            if line.startswith("|") and section is not None:
                m = ROW_RE.match(line)
                if not m:
                    continue
                cells = line.strip().strip("|").split("|")
                if len(cells) < 4:
                    continue
                no = cells[0].strip()
                name = cells[1].strip()
                marks = tuple(c.strip() for c in cells[2:5]) if len(cells) >= 5 else ("", "", "")
                note = cells[5].strip() if len(cells) >= 6 else ""
                link = None
                wm = WIKI_RE.search(name)
                if wm:
                    link = wm.group(1).strip()
                    title = (wm.group(2) or wm.group(1)).strip()
                else:
                    title = name
                title = re.sub(r"\*\*", "", title).strip()
                if not title:
                    continue
                section.points.append(Point(
                    no=no, title=title, section=section, note=note,
                    marks=marks, link=link))

    # ---------- 绑定 ----------
    def bind(self) -> None:
        used = set()
        for ch in self.chapters:
            for sec in ch.sections:
                for p in sec.points:
                    lesson = None
                    if p.link:
                        lesson = self.lessons.get(p.link)
                        if lesson is None:
                            self.warnings.append(f"地图链接找不到笔记：{p.link}")
                    if lesson is None:
                        for stem, cand in self.lessons.items():
                            if stem in used:
                                continue
                            if stem == p.title or stem.endswith("：" + p.title) \
                                    or stem.endswith(":" + p.title):
                                lesson = cand
                                break
                    if lesson:
                        p.lesson = lesson
                        used.add(lesson.stem)
                        lesson.slug = p.slug

    # ---------- 查询 ----------
    def all_points(self) -> list[Point]:
        return [p for c in self.chapters for p in c.points]

    def point(self, no: str) -> Optional[Point]:
        for c in self.chapters:
            for s in c.sections:
                for p in s.points:
                    if p.no == no:
                        return p
        return None

    def expand(self, selector: str) -> list[Point]:
        selector = selector.strip()
        if selector.endswith(".x"):
            prefix = selector[:-2] + "."
            return [p for p in self.all_points() if p.no.startswith(prefix)]
        if selector.count(".") == 1:
            prefix = selector + "."
            return [p for p in self.all_points() if p.no.startswith(prefix)]
        p = self.point(selector)
        return [p] if p else []

    def stats(self) -> dict:
        points = self.all_points()
        return dict(
            points=len(points),
            lessons=sum(1 for p in points if p.lesson),
            codes=sum(l.code_blocks for p in points if p.lesson for l in [p.lesson]),
            chars=sum(l.chars for p in points if p.lesson for l in [p.lesson]),
            minutes=sum(p.lesson.minutes for p in points if p.lesson),
            chapters=len(self.chapters),
            sections=sum(len(c.sections) for c in self.chapters),
        )
