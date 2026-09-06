# Plan: opponent-filter 对手过滤

> 依据 spec.md + review01.md（本目录）。

## 步骤

1. **T1 roster 伪球员 + build 过滤**：roster.py 伪球员常量（tag="对手"，team=有效对手名）；video.py `_build_expand_all` 显式跳过对手（个人+分队）；build_highlight 侧实证 --team 我方/--team 对手 行为（若要改动则最小）。单测先行。
2. **T2 确认页"标为对手"**：gen_scorer_page.py 逐球 + 整簇"标为对手"按钮、对手分组展示、tag=对手 特判（不走 teamOfTag）、导出含伪球员。单测 + 浏览器冒烟。
3. **T3 GUI 出合集步**：app.js 默认按钮"出我方合集"（--team=team_config.team_name）；app.py 如需参数透传最小改动。浏览器冒烟。
4. **端到端验证**：第六人场次实跑——认人页标几个对手 → 导出 → 出我方合集（零对手球）+ --all（无对手产物）。

## 依赖与验证点

- T1 先行（schema/过滤契约是 T2/T3 的基础）；T2/T3 可连做但各自独立 commit
- 每 T 过：pytest/ruff 全绿 + 任务审查
- T3 后端到端实证（立哥第六人场次真实数据）

## 风险

| 风险 | 对策 |
|---|---|
| roster.py validate_roster 拦截伪球员 | T1 先实证，需要放行则最小改动 + 单测锁定 |
| teamOfTag 特判遗漏其他调用点 | T2 先全量 grep teamOfTag 使用点 |
| O2 黑白阵营与伪球员并存混乱 | T2 摸清现状后只加不碰，报告中写清口径 |
