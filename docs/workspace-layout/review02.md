# review02：工作区文件夹结构优化（spec-reviewer 第 2 轮）

审查日期：2026-08-09。审查对象：docs/workspace-layout/ 重写后的 plan.md / todo.md（任务卡格式升级）。
审查方式：只读全文比对同目录 spec.md / review01.md（第 1 轮已审定基准）；抽查 .gitignore（全文）；Glob（include_ignored，因 work/ 为 gitignore 排除区）核实 work/frames 短名目录与 work/detect 非 dji_mimo 缓存清单。

## 结论：通过（无阻断问题）

## 核实事实

- gitignore 事实无回退：.gitignore 实测仅第 12 行 `work/`，无任何 archive/ 条目；Task 1"先加 `archive/work_legacy/` 并 git check-ignore 验证"必要且正确，明确先于批次 B-D，Task 3（批次 B）依赖 Task 1——review01 阻断问题 1 的修正保持。
- Task 5 清单与文件系统逐一吻合：work/frames/ 15 个短名目录全部存在（0007/0011/0014/0020/0022/0030/0033/0040/0048/0062/0086/0102/0120/0128/0147）；work/detect/ 非 dji_mimo mot_cache 恰 14 个（0147 无缓存，与 review01 一致）；"29 个目录/文件"计数正确。
- 批次 B 11 文件（2 探索脚本 + 7 log + 2 清单）与 review01 核定清单一一对应。
- 冻结清单贯穿：roster 相关不进任何批次；根 roster_20260722.json 处置显式延后至认人会话结束（plan Open Questions）；"权威副本为 work/20260722/roster.json"事实未回退；一期不改 scripts 代码在 plan 决策节明确。
- 依赖链正确（Task 0→1→3→4→5→6，批次 A 依赖 Task 0），每批后 pytest + 冻结清单核对 Checkpoint 可执行；无 XL 任务（Task 5 虽 29 项但为纯移动、标 S 合理）。
- 批次 D 移动前对 archive/validate_2026-07-23/ 的 ls 核对保留，与 review01 建议项一致。

## 建议项（已采纳并入 todo）

- Task 2（批次 A）把根 goals.json 移到 archive/ 根（非 work_legacy/），不在 Task 1 gitignore 防护内：验收补"git status 确认其已被跟踪（git mv）或显式接受 untracked 状态"——已修订 Task 2。

## 规范符合性

- 任务卡格式齐整，验收标准（含 git check-ignore、文件计数、冒烟抽查清单）均可检验；与 spec 边界一致（只移不删、一期不改代码、冻结清单零变动）。
- 本件通过，可按 todo 实施；实施前提仍为 Task 0 确认认人会话状态。
