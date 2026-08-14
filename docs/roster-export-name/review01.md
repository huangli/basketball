# review01：认人确认页导出文件名即 roster.json（spec-reviewer 审查存档）

日期：2026-08-14 · 审查范围：docs/roster-export-name/ 四件套、使用手册.html
第 117/187 行，及其实现代码（gen_scorer_page.py / test_gen_scorer_page.py）

## 结论：通过（无阻断、无冲突）

审查代理逐条核对：下载名常量、按钮文案、alert、docstring、测试断言、roster
schema 与 confirmed 判定、video.py 下游读取路径（people 预填链 / build 拒收）
全部一致；多批导出同名 ` (1)` 后缀、旧导出物兼容两条边界在 spec/plan/手册
三处一致覆盖。

## 建议改进（3 条，已全部落实）

1. todo 勾选反映实际进度 → 已勾选 Task 1-3
2. 审查报告存档 → 本文件
3. spec/plan 漏记 FAQ 联动改动（手册第 187 行）→ spec「联动更新」与
   plan 步骤 3 已补记

## 可选优化处置记录

- plan.md「按键提示行」措辞 → 已改「页头提示行」（对应 gen_scorer_page.py:120
  的 `<small>` 提示行，非按键说明行）

## 冲突对照表

无冲突（审查原文结论，9 项逐条比对全部一致）。
