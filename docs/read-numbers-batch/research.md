# research：认人链路提效调研依据（2026-08-16 只读分析会话）

本文件归档 `docs/read-numbers-batch/spec.md` 引用的调研实测数据，供复核。

## 1. 读号通路闲置现状（车百鼎实证）

- `video people` 的 `--read-numbers` 默认关（`scripts/video.py:755`）；
  车百鼎三批均未启用：`work/20260805_车百鼎/scorers_b1/` 无 `number_cache.json`，
  `scorer_candidates.json` 中 `number_votes` 全 None。
- 该场 roster 中带号 tag（黑24/对7/白1/黑9）覆盖 26/107 归属——若读号开启，
  这部分基本免看。
- K3 读号忠实度实测 5/5 无幻觉：`docs/scorer/spec.md` Open Questions 2
  （2026-08-08 批次 1 实测）。

## 2. 跨批聚类继承预填 —— 已证伪（勿再提议）

方法：复用车百鼎三批 `clip_cache.json` 的 CLIP embedding（281 条），
以批 1 聚类结果为基准，对 b2/b3 做跨批 complete linkage 聚类并把一致簇的
roster 归属继承为预填，与该场 roster 真值对账：

| 口径 | 结果 |
|---|---|
| 跨批 complete@0.15 簇纯度 | 49.5% |
| 一致簇继承与真值符合率 b2 | 2/29 |
| 一致簇继承与真值符合率 b3 | 1/25 |
| 阈值收紧到 0.06 后 | b2 2/6、b3 0/1 |

结论：CLIP 全身外观跨批次（不同天/不同球衣）不可迁移，强上等于批量误填。
本数据应同步补记 `docs/经验教训.md`（AGENTS.md 约定证伪集中索引）。

## 3. 批内聚类纯度现状（簇级选人不敢点的根因）

以 roster 真值回测批内聚类（complete@0.15）多球簇纯:混 = b1 0:6 / b2 1:8 /
b3 2:9，批内纯度 55~59%——批内多球簇几乎全是混合簇，簇级一键选人大部分
簇不敢用，实际退化为逐球点选（122 球 ≈ 122 次看图+点击）。
配套改进方向 = 簇代表图按簇内多样性取样（本次非目标，另行立项）。
