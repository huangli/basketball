# review04：plan/todo 第二轮复审存档（spec-reviewer，2026-08-15）

## 结论：通过（无阻断、无冲突），可进入实现阶段（Task 1 先行）

## 一轮修订核验（11 条全部落地）

- B1 ✓ Task 3 改米制空间直接评估（image→court 单应 + 折内最小二乘 LOO），
  px→米换算环节删除，数学上为教科书式 LOO 流程
- S1~S6 ✓ 折内 method=0 / 变焦档改人框高代理 / 门禁口径三处一致 /
  FIBA 假设入报告写死项 / todo 全局质量门 / 维度合并注记
- O1~O4 ✓ 不落人框计分母 / 纯只读标注 / 路径钉死 / find_held_box 包 Track 复用

## 复审残留（一句话级，已顺手落实）

- O1 todo Task 4 Acceptance 补"尺度锚定假设注明"（与 plan 五条写死项同步）✓
- O2 calib-report 写死项加"米制评估口径溯源一句"（与 spec 交付物 3 字面偏差说明）✓

## 冲突对照表

无冲突（四件套目录、lint/test 三连、文档自审、rules.md 输入校验与保守口径、
spec 定稿判据全部一致）。
