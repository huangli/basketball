# Implementation Plan: 进球人识别（spec: docs/scorer/spec.md v2）

## Overview

批次 1 的 17 个 confirmed 进球做试点：投篮者定位裁图（零成本）→ 颜色分队（零成本）→
认人确认页（立哥 1~2 秒/球确认）→ roster.json → build_highlight 出个人/分队合集。
号码识别（豆包）默认不开，作为可选试点最后评估。全部新文件，唯一改的老文件是
build_highlight.py（真值表范围内）；不碰 gen_review_clips.py / gen_label_page.py
（另一会话领地），与批次 2 流水线并行不撞车。

## Architecture Decisions

- **契约先行**：roster schema、键格式化（`f"{t:.1f}"` 双端同一函数）、file→fid 映射、
  scorer 解析（tag|name）收敛到 `scripts/roster.py` 共享模块，写读两端（gen_scorer_page /
  build_highlight）都 import 它，禁止各自裸拼（spec M3）。
- **投篮者定位**：persons 框无 ID → 窗口 [anchor−2.5s, −0.3s] 内 IoU>0.3 贪心链成临时
  track，逐帧取离球最近人框计入其 track，得票最多者胜出、并列取平均距离更近者；
  有效票 <2 → SKIP（spec B2）。
- **裁图规格**：代表帧（离球最近帧）人框外扩 20%，短边不足 400px 等比放大到 400px。
- **颜色分队**：采样区=框水平中 60% × 垂直 25~60%；HSV 双阈（黑 V<TH_BLACK /
  白 V>TH_WHITE 且 S<TH_SAT），近阈归便服；阈值常量放 crop_scorers.py 顶部常量区，
  按批次 1 实裁图标定并注释实测来源。
- **输出文件名用解析后的 tag**（`个人_黑21_进球合集.mp4`），不用 --scorer 原值
  （AGENTS.md 标签命名；spec 二审澄清 1）。
- **`--team 便服` → 报错退出 1**（便服不进分队合集，spec Open Q3 落定）。
- **SKIP 球**：确认页照常列出并标"无法定位、无预填"，立哥可凭视频手选；
  roster 允许未归属；build_highlight 对未归属球 WARNING 跳过不阻塞（含
  有 roster 无过滤参数的"全员"行——该行实际=全归属球，spec 二审澄清 3）。
- **号码识别**：`--read-numbers` 独立开关 + `number_cache.json` 幂等缓存；
  >20 次调用先问立哥。

## Task List

### Phase 1: 契约与零成本识别

- [ ] T1: roster.py 契约模块
- [ ] T2: crop_scorers.py 投篮者定位 + 裁图
- [ ] T3: crop_scorers.py 颜色分队 + 批次 1 实跑验收

### Checkpoint 1（人工）：T3 后

- [ ] 批次 1 的 17 球裁图与颜色分布给立哥抽查（≥3 张裁图是投篮者、颜色合理）
- [ ] ruff + pytest 全绿

### Phase 2: 确认页与合成改造

- [ ] T4: gen_scorer_page.py 认人确认页（含 --roster-existing 合并）
- [ ] T5: build_highlight.py 真值表改造（7 分支）

### Checkpoint 2（机器）：T5 后

- [ ] ruff + pytest 全绿（真值表 8 分支测试全过）
- [ ] git status 确认 gen_review_clips.py / gen_label_page.py 零改动、
      work/20260722/review_batch2/ 无写入

### Phase 3: 端到端试点

- [ ] T6: 批次 1 十七球全流程（裁图→页面→立哥确认→个人/分队合集）
- [ ] T7（可选，先问立哥）：号码识别豆包试点（≤20 次）

### Checkpoint 3（人工）：T6 后

- [ ] 立哥验收个人合集与分队合集
- [ ] spec-reviewer 审 plan/todo/最终 diff；git 提交（立哥确认后）

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 定位 SKIP 率 >30% | 高 | Checkpoint 1 实测；返工方向：扩大窗口/放宽 IoU/取球最后离开人框的帧 |
| 颜色阈值标定不足，便服桶过大 | 中 | 阈值按 17 张实裁图标定；便服只进全员/个人合集，不阻塞 |
| 投篮者=传球者选错（多人密集） | 中 | 窗口投票+确认页裁图目检兜底；错了一键改 |
| 与另一会话撞车 | 低 | 只动新文件 + build_highlight.py；Checkpoint 2 git status 验证 |
| SKIP 球归属遗漏进合集 | 低 | 未归属 WARNING 跳过 + SC4 口径覆盖 |

## Open Questions

- 球员名单（号码/特征→称呼+队别）：无名单时确认页退化为自由文本输入 + 颜色预填
- 号码识别是否启用（默认否，T7 先问）
- 批次 2 标注完成后，认人页对其 185 事件的 goals 复用同一 roster（--roster-existing）
