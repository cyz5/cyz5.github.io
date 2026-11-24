## 这个站是什么

一份持续生长的嵌入式知识库：上面是 {{POINTS}} 个技能点的能力地图，下面是按技能点编号组织的课程。它不是「教程合集」，而是把「岗位需要什么」拆到可验收的粒度，再一条条写透。

目前已有 **{{LESSONS}} 节**完整课程（{{COVERAGE}}%），集中在 C 语言、MCU 硬件与底层、RTOS；其余章节按优先级陆续补写。

## 内容从哪来

所有内容先写在 Obsidian 仓库（纯 Markdown）里，构建时自动转换成网站：

- 能力地图是唯一索引：技能点编号（如 `3.1.2`）同时决定课程 URL、练习目录、地图锚点；
- 课程页保留原始 Markdown，代码块自动识别语言并高亮；
- 「待撰写」页面由构建脚本生成，保证地图永远可导航，不会出现死链接。

## 技术栈

| 层 | 选择 | 原因 |
| --- | --- | --- |
| 写作 | Obsidian + Markdown | 本地优先，纯文本可迁移 |
| 生成 | Python（解析地图、生成页面、注入导航） | 无数据库，构建可复现 |
| 渲染 | MkDocs Material | 中文检索（jieba 分词）、代码高亮、移动端友好 |
| 部署 | GitHub Actions → GitHub Pages | 零服务器成本，push 即发布 |

## 更新流程

```bash
# 本地预览
python site-src/build.py
python -m mkdocs serve -f site-src/.build/mkdocs.yml

# 发布
git add -A && git commit -m "content: 新增 3.2.1" && git push
```

CI 会在 1–2 分钟内重新构建并部署，不需要登录服务器。

## 隐私边界

站点只发布课程与技术路线。职业规划、薪资、目标公司、个人履历等内容留在本地，不进入公开仓库（见 `.gitignore` 与构建配置的 `exclude`）。

## 许可

- 课程文字：CC BY-NC-SA 4.0（署名 · 非商业 · 相同方式共享）
- 代码示例：MIT

转载或引用请保留来源链接。
