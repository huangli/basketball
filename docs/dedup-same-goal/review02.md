# review02：标注页同球双 J 自动识别（spec-reviewer 第 2 轮）

审查日期：2026-08-09。审查对象：docs/dedup-same-goal/ 重写后的 plan.md / todo.md（任务卡格式升级）。
审查方式：只读全文比对同目录 spec.md / review01.md（第 1 轮已审定基准）；抽查 scripts/gen_label_page.py（全文）、tests/test_gen_label_page.py（全文）、scripts/gen_review_clips.py:40-59；核实回放输入文件存在性。

## 结论：通过（无阻断问题）

## 核实事实

- 窗口口径无回退：todo Task 1 取 `[anchor_t0 − CLIP_BEFORE_SEC, anchor_t0 + CLIP_AFTER_SEC]`，常量引自 gen_review_clips 并要求写全模块路径。实测 gen_review_clips.py:50-53 为 2.0/4.0（前 2 后 4），gen_label_page.py:38-39 确有同名不同值常量（4.0/2.0）——review01 阻断问题 1 的修正在 plan 决策节/风险表与 todo 中保持。
- 实现落点存在：分组数据内联可行（gen_label_page.py:78 `const EVENTS = __EVENTS__`，build_html :191-206 以 json.dumps 内联）；exportGoals JS 在 :137（绑定 :169），confirm() 前置检查落点真实；todo Task 4 所列导出 schema（file/anchor_time/clip_start/clip_end/status/scorer）与 :142-149 逐字段一致。
- 测试映射可行：tests/test_gen_label_page.py 现有 import 纯函数 + _event() fixture（含 fid/anchor_t0）的结构可承载 Task 1 新增 5 用例。
- 依赖正确：Task 2 依赖 Task 1；Task 3/4 明确 Checkpoint 通过后开工、可并行；Task 5 依赖 2/3/4；无 XL 任务（最大 M、2 文件）。
- 数字与基准一致：8 组同球对清单、anchor 差 2.3~4.2s、"42 个独立球"、跨文件反例 203918/203928 与 205204/205158 均与 review01 核定口径一致；203628 修锚点事实未回退。
- 回放输入 work/20260722/review_batch3/events_index.json 与 20260722地平线/goals_20260722_3.json 均存在。

## 建议项（已采纳并入 todo）

- Task 3 色框/标签落点：现行标注页为单事件翻页器（show(i) 一次一事件，无卡片网格），落点以实现时页面结构为准，验收口径写为"同组可一眼识别"——已修订 Task 3。
- Task 2 回放脚本注释注明：跨文件反例在仅同 fid 规则下由构造保证不并，0 误分组真正考验是同文件 42 个独立球——已修订 Task 2 Description。

## 规范符合性

- 任务卡格式（Description/Acceptance criteria/Verification/Dependencies/Files/Scope）齐整，验收标准均可检验；与 spec 边界一致（仅同文件、机器不自动删、不动上游）。
- 本件通过，可按 todo 实施。
