# TODO: video build 多批次修复

spec: docs/build-multi-batch/spec.md
plan: docs/build-multi-batch/plan.md（2 个任务）

## 已办

- [x] 问题定位（2026-08-15 立哥实测 --all 中止：零球批次 exit 1 + 逐批同名覆盖）
- [x] spec.md + plan.md 产出

## 待办

- [ ] spec/plan 过 spec-reviewer
- [ ] Task 1: video.py 合并合成 + 零命中跳过（TDD，含 4 条既有测试更新）
- [ ] Task 2: video-cli spec/手册同步 + 终审 review01.md
- [ ] 立哥实测 `video build --session 20260805_车百鼎 --all`（先 --dry-run）
