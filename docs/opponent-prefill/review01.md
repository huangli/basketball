# Review 01: opponent-prefill spec 审查（2026-09-07）

> 审查员：spec-reviewer 角色子代理（只读审查）。结论：修订后通过。

## 阻断问题与处置

- **蓝队处理未说明**（teamOfTag 蓝→OPP 与 spec 只对"黑"预填的表面张力）→ spec 设计 1 已加注：team_guess 取值空间（黑/白/便服）不含"蓝"，不冲突。
- **非候选球按钮行为未说明** → spec 设计 3 已补"非候选球'标为对手'行为不变"。

## 通过项

- 与 acceptAllPrefills 口径一致（未接受不写 marks、只写未 touched）；与 opponent-filter spec 无冲突；成功标准可测。
