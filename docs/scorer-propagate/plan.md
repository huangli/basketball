# Plan: 认人提效二期——轨迹传播 + 离线读号

## Overview

按 spec（docs/scorer-propagate/spec.md，已过 spec-reviewer 第 1 轮修订）
实施。**数据现实（spec-reviewer B1）**：work/ 已清场，无评估锚点数据——
所有"实跑标定/对照"任务挂起到下一个带 confirmed roster 的新场次；
本周期交付 = 实现 + 纯函数单测 + 质量门 + video people 接线。

## Architecture Decisions

- **跟踪器自写不引库**：贪心 IoU 多目标跟踪 ~100 行纯函数，可单测；
  唯一性裁决规则写死（每框至多入一轨）
- **传播与页面解耦**：propagate_scorers 只产 track_links.json，
  candidates 文件只读不改；页面按 key 反查 track_id
- **种子只消费不重算**：propagate 只读 entry 的 seed_* 字段（crop_scorers
  先跑落字段），seed 缺失 WARNING 跳过——杜绝退化重算与裁图不一致
- **传播预填的页面语义**：assign 触发、写 marks + provenance 集合、
  NOGOAL 不传播、只写"无 marks+无号码预填+未 touched"的球——
  优先级链与既有 prefill 机制不打架（spec §页面写死）
- **离线读号缓存隔离**：单独 offline_number_cache.json，K3 链路零感知

## Task List

### Phase 1: 轨迹传播

- [ ] Task 1: crop_scorers entry 落 seed_frame/seed_box/seed_team
- [ ] Task 2: propagate_scorers.py——贪心跟踪器（唯一性裁决）+ 颜色守卫
  （便服不计数）+ 进球映射 + track_links.json 落盘
- [ ] Task 3: 传播预填来源（自身不算源/冲突不预填/NOGOAL 不作源）+
  --evaluate 报表（roster-seeded / number-seeded 双指标，纯函数可测）
- [ ] Task 4: 单测 + 质量门；**提交 Phase 1a（脚本）**
- [ ] Task 5: gen_scorer_page --track-links（传播预填 + 徽标 + NOGOAL 排除 +
  acceptAll 隔离 + 兼容）+ 单测 + 实页静态目检（node --check）；
  **提交 Phase 1b（页面）**
- [ ] Task 6: video.py people 接线（裁图 → 传播 → 聚类 → 确认页，
  track_links 存在才传）+ 单测 + 质量门；**提交 Phase 1c（接线）**

### Phase 2: 离线读号（试验，可砍）

- [ ] Task 7: offline_number.py——预处理 + 连通域切字 + 模板匹配 +
  模板库自举（对齐规则：连通域数==号码位数才接收，按 x 升序 zip）+
  offline_number_cache.json 隔离缓存
- [ ] Task 8: 单测（合成数字图 + 对齐规则）+ 质量门；**提交 Phase 2**

### 挂起任务（等新场次数据就绪）

- [ ] Task 9【挂起】：新场次实跑 --evaluate 标定（准确率 ≥90%/覆盖 ≥1.5，
  守卫参数最多 3 档）；前置：该场次 roster confirmed
- [ ] Task 10【挂起】：离线读号对照实跑（K3 已读结果为真值，
  一致率 ≥70% 留 / <70% 砍）；前置：同 Task 9

### 收官

- [ ] review01 记录 spec-reviewer 第 1 轮修订；Task 9/10 实跑后补 review02；
  todo 勾选；AGENTS.md 认人流程条目更新（propagate 进 people 链）；
  过 spec-reviewer；提交

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| 俯视人群 IoU 链碎片化，覆盖率低 | 传播收益缩水 | 覆盖倍数硬指标（Task 9）；<1.2 再议放宽（不过度设计） |
| 轨迹串人致传播错填 | 误导立哥 | 颜色守卫 + 冲突不预填 + touched 覆盖 + Task 9 准确率 ≥90% 闸 |
| 锚点后轨迹物理截断（7 成球入网后 <2s） | 向后传播天然受限 | 以前向回溯为主（spec 已写死素材特性） |
| 离线读号精度不达标 | Phase 2 白做 | 砍单闸 + 模板自举零 token + 沉没成本限一个脚本 |

## Open Questions

- 守卫参数标定值（→ Task 9 / review02）
- Phase 2 去留（→ Task 10 / review02）
