# 站点生成器

这个目录把 Obsidian 仓库（纯 Markdown）构建成 GitHub Pages 站点。笔记本身不需要改格式，构建时自动处理：

- 读 `技能地图/高级嵌入式软件工程师超详细技术能力地图.md`，得到 14 章 / 93 小节 / 576 个技能点；
- 把技能点链接到对应笔记，生成课程页；
- 没写笔记的技能点生成「待撰写」占位页，保证地图没有死链；
- 技能点编号 → URL（`3.1.2` → `/p/3-1-2/`），避免中文文件名 URL 编码；
- 自动识别代码块语言（C / C++ / Bash / Python / JSON）；
- 生成导航、能力地图、学习路线、章节和小节索引。

## 本地构建

```bash
pip install -r site-src/requirements.txt
python site-src/build.py

# 预览（构建完后再起服务）
python -m mkdocs serve -f site-src/.build/mkdocs.yml
```

构建产物在 `site-src/.build/site/`，已被 `.gitignore` 排除。

## 发布

推到 `main` 分支即可，GitHub Actions 会自动构建并部署 Pages：

```bash
git add -A
git commit -m "content: 更新若干课程"
git push
```

## 目录

```text
site-src/
├── build.py           # 入口：生成 docs + 调用 mkdocs
├── vault.py           # 解析能力地图与笔记
├── pages.py           # 页面模板（首页/地图/课程/占位/路线）
├── site.yml           # 站点信息、排除的私有笔记、学习路线配置
├── mkdocs.base.yml    # MkDocs Material 配置
├── content/           # 练习库、关于页的正文
├── assets/            # 样式与交互
└── overrides/         # 首页模板（去掉自动 H1）
```

## 新增一节课

1. 在 `技能地图/<章节目录>/` 下按现有命名建 `.md`，标题用「小节名：技能点名」；
2. 在能力地图对应行把技能项改成 `[[文件名]]`；
3. 推到 `main`，1–2 分钟后上线。

没改地图链接但文件名与技能点名一致时，构建也会自动匹配。
