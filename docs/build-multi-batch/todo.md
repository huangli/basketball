# TODO: video build 多批次修复

spec: docs/build-multi-batch/spec.md
plan: docs/build-multi-batch/plan.md（2 个任务）

## 已办

- [x] 问题定位（2026-08-15 立哥实测 --all 中止：零球批次 exit 1 + 逐批同名覆盖）
- [x] spec.md + plan.md 产出（spec 预审吸收 B1-B3 + 建议）
- [x] Task 1: video.py 合并合成 + 零命中跳过（ed7df83；改名 93865e6；except 补括号 0c330ae；审查 Approved）
- [x] Task 2: video-cli spec + 使用手册同步（spec-reviewer PASS-WITH-WARNINGS 建议已吸收）+ 存档 review01.md

## 待办

- [ ] 立哥实测 `video build --session 20260805_车百鼎 --all`（先 --dry-run 看展开）+ 抽查跨批球员合集片段数
