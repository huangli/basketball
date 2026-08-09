# Plan: 认人增强——Re-ID 聚类 + 多帧读号投票 + 名单映射

## Overview

按 spec（docs/scorer-reid/spec.md）实施。Phase A 是依赖验证 spike，
失败即停工报立哥（不进入后续 Phase）。B/C/D 相互独立，A 只挡 B。

## Architecture Decisions

- **encoder 后端抽象而非替换**：CLIP 后端保留为默认，Re-ID 经 --model
  显式启用；缓存键含 model tag 天然隔离；标定对比同一份数据两条曲线
- **读号缓存键改裁图 md5**：同人不同球的裁图内容不同但同球多裁/重跑
  复用率最高；旧 goal-key 缓存迁移（goal→crops[0] md5）零新调用
- **名单走文件**（--players-file 与 roster.players 同构）：名单会随场次
  累积复用，文件比 CLI 串稳健；与 --players 互斥防双源
- **投票规则保守**：同号 ≥2 才采纳——全景裁图读号错误成本高于漏读
  （误预填误导立哥，漏读只是回到人工）

## Task List

### Phase A: torchreid 验证 spike（卡 Phase B 的入口）

- [ ] Task A1: pip install deep-person-reid（清华镜像）→ import 验证 →
  osnet_x1_0 权重下载（代理）→ 一张真裁图 CPU 推理出向量
  - 任一失败 → 停工报立哥（Boundaries 已写死）

### Phase B: Re-ID 后端（依赖 A）

- [ ] Task B1: encoder 后端抽象 + --model 参数 + osnet_x1_0 实现
- [ ] Task B2: 单测（工厂/注入假 encoder/契约不变）+ 质量门
- [ ] Task B3: 实跑标定（average + complete 双 linkage，阈值各 2~3 档，
  embedding 缓存命中零推理成本）对比 CLIP 双曲线，结果记 review01；
  **提交 Phase B**

### Phase C: 读号投票（独立于 A/B）

- [ ] Task C1: 逐张读号 + 众数投票（规则见 spec，写死）+ number_votes 落 entry
- [ ] Task C2: number_cache 键改 md5 + 旧缓存迁移（幂等、零新调用）
- [ ] Task C3: 单测（投票三态/迁移幂等/闸不变）+ 质量门；实跑 20260722
  迁移验证；**提交 Phase C**

### Phase D: 名单文件注入（独立于 A/B/C）

- [ ] Task D1: --players-file 解析/校验/互斥 + team_of_tag 映射核对
- [ ] Task D2: 单测 + 质量门；**提交 Phase D**

### Checkpoint: 收官

- [ ] review01 补实跑标定记录；todo 全勾；AGENTS.md 认人流程条目更新
  （Re-ID 后端 + 投票 + 名单文件）；过 spec-reviewer；提交

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| torchreid 不兼容 Py3.14/torch 2.13 | Phase B 全堵 | Phase A 先行验证；失败报立哥换备选（不擅自换） |
| OSNet 权重下载失败 | 同上 | 代理下载；失败留立哥手动放权重路径 |
| Re-ID 纯度仍不达标 | 增强白做 | spec 降级出口沿用；CLIP 后端保留可回退 |
| 投票后读号调用 ×3 | 额度消耗 | 缓存键改 md5 复用 + --max-reads 闸 + 旧缓存零成本迁移 |
| 远景小人裁图重缩放伤特征 | 纯度受损 | 标定时按框面积分桶观察纯度，记 review |

## Open Questions

- Re-ID 标定阈值（→ review01 记录）
- 半截篮名单到位时间（不阻塞开发，到位即灌 players.json 验证 Phase D 实链）
