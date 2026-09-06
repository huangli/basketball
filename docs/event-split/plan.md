# Plan: event-split 审核片段合并修复

> 依据 spec.md（本目录）。

## 步骤

1. **数据摸底**：读第六人场次 `candidates_batch1.json` + `hoops_batch1.json` 结构，定位立哥目击的跨场地事件（同一事件内筐位突变的候选对），作为验收锚点
2. **单测先行**：tests/test_gen_review_clips.py 加 5 条合成用例（见 spec Testing）
3. **实现**：gen_review_clips.py `cluster_candidates` 按 spec 设计改造（三常量 + 空间约束 + 时长上限）
4. **真实数据验证**：重跑聚类出临时片段目录，前后事件清单对比（事件数、目击案例是否切开、有无误切）
5. **立哥过目** → 确认后才动正式 review_batch1

## 风险

| 风险 | 对策 |
|---|---|
| 阈值 800px 误切同回合（镜头大幅移动） | 单测覆盖 + 真实数据验证后再定稿 |
|  hoops 数据缺失/稀疏时退回球位的语义变化 | 退回路径 = 现状语义 + 新时长上限，单测锁定 |
| 上游 anchors/event_anchor 口径 | 取末成员不动；改动只在聚类合并判定 |

## Todo

- [ ] T1 数据摸底 + 单测先行 + 实现 + 真实数据对比验证（scripts/gen_review_clips.py、tests/test_gen_review_clips.py）
- [ ] T2 立哥过目确认 →（若确认）重出第六人正式 review_batch1
