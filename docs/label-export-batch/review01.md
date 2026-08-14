# review01：标注页导出文件名自动带批次号（spec-reviewer 审查存档）

日期：2026-08-14 · 审查范围：docs/label-export-batch/ 四件套、使用手册.html §一第 2 步、
docs/video-cli/spec.md §批次发现，及其实现代码（gen_label_page.py / run_session.py / 两处测试）

## 结论：通过（无阻断问题）

审查代理逐项核对：导出文件名三处展示点、⑦ argv、双轨命名、payload schema、
手册口径与实现/CLI 识别行为全部一致；相关测试实测全绿（52 passed）。

## 建议改进（3 条，已全部落实）

1. todo.md 勾选反映实际进度 → 已勾选 Task 1-4
2. plan 风险表承诺的 node --check 静态检查 → 已补
   `test_gen_label_page.py::test_generated_js_syntax_node_check`
   （仿 test_gen_scorer_page.py:964 同款，node 不在 PATH 则 skip）
3. video-cli spec §批次发现补 adhoc 口径 → 已补"adhoc 补跑页面导出仍为旧名，
   同旧布局需人工改名"

## 可选优化处置记录

- `--batch` K≥1 校验（审查列可选）：已采纳并升级为防御——`build_html` 对
  `batch < 1` 直接 `raise ValueError`，附单测；防止手工调用静默产出 CLI 不认的文件名
- spec.md 行号引用外部文档（§45）→ 小节名"§批次发现"已在联动更新中采用
- plan.md 伪码 `if batch else` vs 实现 `if batch is not None`：以实现为准，仅记录

## 冲突对照表

无冲突（审查原文结论）。
