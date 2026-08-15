# review07：plan/todo v2 第 1 轮审查（2026-08-15）

审查对象：`docs/heatmap/plan.md`、`docs/heatmap/todo.md`（v2 全文重写）
审查员：spec-reviewer 子代理 · 结论：**通过（无阻断）**，建议改进 2 条 + 可选优化 4 条

## 整体评价

plan/todo v2 与 spec v2 总体高度一致：Q1/Q2 判据口径、SKIP 落盘形态、人工门禁、
留一法米制评估、v1 证伪记档等核心口径均逐字吻合；引用的 crop_scorers 函数与常量
全部属实。

## 建议改进（已全部采纳，review08 复核落实）

1. **calib.json schema 形态与 spec 字面不一致**：spec 写分层结构，plan/todo 写扁平
   结构（每点自带 event_key/fid/frame_idx）。字段集合相同、扁平对逐点留一更直接，
   但上位契约被静默改写。修法采纳：plan Task 2 注明"扁平结构替代 spec 分层表述，
   字段集合不变——plan 细化"。
2. **"变焦档每档 ≥2 事件"是 plan 新增写死判据，spec 未载**：判据合理但属另立口径。
   修法采纳：注明"plan 细化：spec 未写死，为防止变焦档抽样不足 Q1 偏乐观新增"。

## 可选优化（已全部采纳）

3. Task 1 补"batch1/2 已有认人产物仍机器重跑"依据（认人 entry 不落
   frame_idx/box，locate 幂等重算统一落盘）。
4. 门禁并行起点消歧："Task 2 实抽样需等 Task 1 产物，Task 3 合成 fixture 可即刻
   开工"。
5. Q2 阈值补绝对球数"≥110/122"（头部门禁与 Task 4 两处）。
6. event_key 的 anchor_time 按 goals 原值原样序列化，不做格式化。

## 代码事实核对结果（全部属实）

- `locate_scorer`（crop_scorers.py:859）签名 `(cache, anchor_sec, anchor_xy=None)`，
  reason 全集 {no_track, no_track_near_anchor, no_person, start_fallback}；
  missing_cache 为 landings 新脚本自增，合理
- `load_candidates_index`（:717）、`match_anchor_xy`（:750，容差 0.3s、无匹配
  退化时间最近）属实
- 常量 TRACK_WINDOW_PRE_SEC=4.0 / TRACK_WINDOW_POST_SEC=0.5 /
  GOAL_TRACK_MAX_DIST_PX=200 / CANDIDATE_MATCH_DT_SEC=0.3 均模块级导出（:93-96），
  "全部读常量不重定义"可落地
- `_frame_path`（:1206-1208）帧命名 `f_{frame_idx+1:05d}.jpg` 属实
- goals/candidates batch{1,2,3} 六个文件均在盘，confirmed 29+49+44=122

## v1 残留检查

无矛盾残留：P1/P2/P3 判据明确废弃，release_probe.py 仅以"留档不删（复算依据）"
出现，无稳定段法口径回潮。

## 与 AGENTS.md 冲突对照表

无冲突（四件套归置、质量门、spec-reviewer 自审、work/output 目录约定均合规）。
