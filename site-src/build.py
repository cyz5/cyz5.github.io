# -*- coding: utf-8 -*-
"""构建站点：读取 Obsidian 仓库 -> 生成 docs -> mkdocs build -> 校验。"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(HERE, ".build")
DOCS = os.path.join(BUILD, "docs")
SITE = os.path.join(BUILD, "site")

sys.path.insert(0, HERE)
import pages  # noqa: E402
import vault  # noqa: E402


def load_cfg() -> dict:
    with io.open(os.path.join(HERE, "site.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def write(doc: str, text: str) -> None:
    path = os.path.join(DOCS, doc.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def fill(text: str, ctx: dict) -> str:
    for k, v in ctx.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def git_mtimes() -> dict:
    """用 git 提交时间作为「最后更新」，CI 里需要 fetch-depth: 0。"""
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        return {}
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", ROOT, "log",
             "--format=%ct", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception:
        return {}
    if out.returncode != 0:
        return {}
    result, stamp = {}, 0
    for line in out.stdout.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.isdigit():
            stamp = int(s)
        elif stamp and s not in result:
            result[s] = stamp
    return result


def main() -> int:
    cfg = load_cfg()
    site_cfg = cfg["site"]
    owner_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not site_cfg.get("repo") and owner_repo:
        site_cfg["repo"] = f"https://github.com/{owner_repo}"
    if not site_cfg.get("repo"):
        site_cfg["repo"] = "https://github.com/YOURNAME/embedded-notes"
    if not site_cfg.get("labs_repo"):
        site_cfg["labs_repo"] = site_cfg["repo"].rsplit("/", 1)[0] + "/embedded-labs"

    cfg_obj = pages.Config(
        name=site_cfg["name"], tagline=site_cfg.get("tagline", ""),
        description=site_cfg.get("description", ""), author=site_cfg.get("author", ""),
        repo=site_cfg["repo"].rstrip("/"), labs_repo=site_cfg["labs_repo"].rstrip("/"),
        branch=site_cfg.get("branch", "main"), roadmap=cfg.get("roadmap", {}),
        exclude=site_cfg.get("exclude", []))

    v = vault.Vault(ROOT, exclude=cfg_obj.exclude)
    mtimes = git_mtimes()
    for lesson in v.lessons.values():
        if lesson.rel in mtimes:
            lesson.mtime = mtimes[lesson.rel]

    site = pages.Site(cfg_obj, v)
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(DOCS, exist_ok=True)

    # ---- 静态页 ----
    write("index.md", site.home())
    write("map.md", site.map_page())
    write("roadmap.md", site.roadmap_page())

    st = site.stats
    ctx = {
        "REPO": cfg_obj.repo, "LABS_REPO": cfg_obj.labs_repo, "AUTHOR": cfg_obj.author,
        "POINTS": st["points"], "LESSONS": st["lessons"], "CODES": f"{st['codes']:,}",
        "CHAPTERS": st["chapters"], "SECTIONS": st["sections"],
        "MINUTES": f"{st['minutes']:,}", "HOURS": round(st["minutes"] / 60),
        "COVERAGE": round(st["lessons"] * 100 / st["points"]),
    }
    for name, title in (("labs", "练习库"), ("about", "关于")):
        with io.open(os.path.join(HERE, "content", f"{name}.md"), encoding="utf-8") as f:
            body = fill(f.read(), ctx)
        write(f"{name}.md", pages.page({"title": title}, body))

    # ---- 章节 / 小节 / 课程 / 占位 ----
    n_lessons = n_stubs = 0
    for c in v.chapters:
        write(site.ch_doc(c), site.chapter_page(c))
        for s in c.sections:
            write(site.sec_doc(s), site.section_page(s))
            for p in s.points:
                if p.lesson:
                    write(site.pt_doc(p), site.lesson_page(p))
                    n_lessons += 1
                else:
                    write(site.pt_doc(p), site.stub_page(p))
                    n_stubs += 1

    # ---- 静态资源 ----
    assets = os.path.join(DOCS, "assets")
    os.makedirs(assets, exist_ok=True)
    for fn in ("base.css", "site.css", "extra.js"):
        shutil.copyfile(os.path.join(HERE, "assets", fn), os.path.join(assets, fn))

    # ---- mkdocs 配置 ----
    with io.open(os.path.join(HERE, "mkdocs.base.yml"), encoding="utf-8") as f:
        mk = yaml.safe_load(f)
    mk["site_name"] = cfg_obj.name
    mk["site_description"] = cfg_obj.description
    mk["site_author"] = cfg_obj.author
    mk["docs_dir"] = DOCS
    mk["site_dir"] = SITE
    mk["site_url"] = os.environ.get("SITE_URL", "http://127.0.0.1:8000/")
    if not mk["site_url"].endswith("/"):
        mk["site_url"] += "/"
    theme = mk.setdefault("theme", {})
    theme["custom_dir"] = os.path.join(HERE, "overrides")
    mk["copyright"] = f"© 2026 {cfg_obj.author} · 课程内容持续更新"
    mk["repo_url"] = cfg_obj.repo
    mk["repo_name"] = cfg_obj.repo.split("/")[-1]
    mk["edit_uri"] = ""
    mk["nav"] = build_nav(site, v)
    with io.open(os.path.join(BUILD, "mkdocs.yml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(mk, f, allow_unicode=True, sort_keys=False, width=120)

    # ---- 构建 ----
    os.environ.setdefault("NO_MKDOCS_2_WARNING", "1")
    from mkdocs.commands.build import build as mkdocs_build
    from mkdocs.config import load_config
    mkdocs_build(load_config(os.path.join(BUILD, "mkdocs.yml")))

    # ---- 校验 ----
    broken = check_links(SITE)
    index_path = os.path.join(SITE, "search", "search_index.json")
    idx_kb = os.path.getsize(index_path) // 1024 if os.path.exists(index_path) else 0
    html_count = sum(1 for _, _, fs in os.walk(SITE) for f in fs if f.endswith(".html"))

    print(f"  chapters={len(v.chapters)} sections={st['sections']} points={st['points']}")
    print(f"  lessons={n_lessons} stubs={n_stubs} html={html_count} search={idx_kb}KB")
    print(f"  site={SITE}")
    if broken:
        print(f"  BROKEN LINKS ({len(broken)}):")
        for b in broken[:20]:
            print("   ", b)
        return 1
    return 0


def build_nav(site: "pages.Site", v) -> list:
    nav = [
        {"首页": "index.md"},
        {"能力地图": "map.md"},
        {"学习路线": "roadmap.md"},
        {"练习库": "labs.md"},
        {"关于": "about.md"},
    ]
    chapters = []
    for c in v.chapters:
        items = [site.ch_doc(c)]
        for s in c.sections:
            sec = [site.sec_doc(s)]
            for p in s.points:
                if p.lesson:
                    sec.append({f"{p.no} {site.nav_title(p)}": site.pt_doc(p)})
            items.append({f"{s.no} {s.title}": sec})
        chapters.append({f"第 {c.no} 章 · {c.title}": items})
    nav.append({"课程": chapters})
    return nav


def check_links(site_dir: str) -> list:
    bad = []
    for dirpath, _, files in os.walk(site_dir):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dirpath, fn)
            with io.open(path, encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r'href="([^"]+)"', text):
                href_value = m.group(1)
                if href_value.startswith(("http://", "https://", "mailto:", "javascript:", "#", "//")):
                    continue
                target = urllib.parse.unquote(href_value.split("#")[0].split("?")[0])
                if not target:
                    continue
                if target.endswith(".md"):
                    bad.append(f"{os.path.relpath(path, site_dir)} -> {href_value} (未转换的 .md)")
                    continue
                resolved = os.path.normpath(os.path.join(os.path.dirname(path),
                                                         target.lstrip("/")))
                if target.endswith("/") or os.path.isdir(resolved):
                    if not os.path.exists(os.path.join(resolved, "index.html")):
                        bad.append(f"{os.path.relpath(path, site_dir)} -> {href_value}")
                elif not os.path.exists(resolved):
                    bad.append(f"{os.path.relpath(path, site_dir)} -> {href_value}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
