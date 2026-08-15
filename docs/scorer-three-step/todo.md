# TODO: 认人页三步引导流程

spec: docs/scorer-three-step/spec.md（已过 spec-reviewer，Ready=Yes）
plan: docs/scorer-three-step/plan.md（6 个任务，TDD 逐任务提交）

## 已办

- [x] 立哥需求对齐（三步流程 + 删簇，2026-08-15）
- [x] demo 页迭代验证（布局/悬停放大/簇6剔除 hack，scorer_demo.html）
- [x] spec.md 定稿（含删簇数据契约）+ spec-reviewer 审查 Ready=Yes
- [x] plan.md 产出（Self-Review + spec-reviewer Ready=Yes）
- [x] Task 1: 三步引导标题条（814a70f，审查通过）
- [x] Task 2: 删簇（clState deleted 墓碑子键）（56af412，审查通过）
- [x] Task 3: 页内改真名（_names 键）（1c27c4e，审查通过）
- [x] Task 4: 按人核对（_review 键 + 可见集）（cf37282，审查通过）
- [x] Task 5: 逐球区定高不定宽布局 + 悬停放大（e4c56be，审查通过）
- [x] Task 6: 质量门 576 passed；实数据重生成 b1（29球/16人/13簇）/b2（49球/16人/22簇）
      + demo 副本刷新 + 使用手册认人节改三步流程（spec-reviewer PASS）
- [x] 终审整支：Ready=Yes（review02.md），Minor 留档 6 条均不阻断

## 待办

- [ ] 立哥手工验证清单全过（plan.md Task 6 Step 3：三步条/改名/按人核对/删簇含簇6实测/布局/悬停放大/导出 diff）
