# review05：spec.md v2 第 1 轮审查（2026-08-15）

审查对象：`docs/heatmap/spec.md`（v2 修订版，全文重审）
审查员：spec-reviewer 子代理 · 结论：**通过（无阻断）**，建议改进 3 条 + 可选优化 3 条

## 整体评价

v2 修订事实基础扎实：所有引用的代码事实（locate_scorer 签名、SKIP reason 集合、
窗口常量、match_anchor_xy 退化口径、帧命名映射）经逐条核对全部属实；修订依据的
97.4%（29/29 + 47/49）从落盘产物复算确认无误；122 = 29+49+44 分母核实。判据闭合、
可判定、无歧义性硬伤，与经验教训 §8 的证伪结论兼容且正是按 §8"未来重启"建议落地。

## 逐项核验记录（备查）

- `locate_scorer(cache, anchor_sec, anchor_xy=None)` 签名与 spec 一致
  （`scripts/crop_scorers.py:859`）；SKIP reason ∈ {no_track, no_track_near_anchor,
  no_person}（:878/:881/:888），OK 时 reason 为 `""` 或 `"start_fallback"`
  （:885/:890）。
- 窗口常量是导出的：`TRACK_WINDOW_PRE_SEC=4.0` / `TRACK_WINDOW_POST_SEC=0.5`
  （crop_scorers.py:93-94），`GOAL_TRACK_MAX_DIST_PX`、`CANDIDATE_MATCH_DT_SEC`
  同样导出——spec"全部从 crop_scorers 读常量"可行。
- `load_candidates_index`（:717）与 `match_anchor_xy`（:750）存在，无匹配/超差
  返回 None → 退化为端点时间最近（`select_goal_track` :808-809）。
- `candidates_batch{1,2,3}.json` 三个文件均真实存在于 `work/20260805_车百鼎/`。
- 认人产物复算：b1 29 球全 OK 真持球；b2 47 OK 真持球 + 2 SKIP
  （no_track_near_anchor）→ 76/78 = 97.4%。entry 键集合确无 frame_idx/person_box，
  交付物 1"机器重跑统一落盘"的必要性属实。
- 帧命名：`_frame_path` = `f_{frame_idx+1:05d}.jpg`（crop_scorers.py:1206-1208），
  frame_idx 0-based ↔ 文件名 1-based；抽查 3 个 fid 帧图均为 1920×1080。
- 分母换算：≥110/122 = 90.16% ≥ 90%，109/122 = 89.3% 不过关——"即 ≥110 球"正确。

## 建议改进（已全部采纳，review06 复核落实）

1. **"landings OK 球"口径缝隙**（交付物 2）：status==OK 包含 start_fallback，
   字面读法会抽进无持球语义的球。修法：改为"可用落点球（OK 且非 start_fallback）"。
2. **SKIP 球落盘形态未写死**（交付物 1）：SKIP 时 frame_idx=-1、box=None 的落盘
   形态（-1/null 还是省略字段）未声明，下游 gen_calib_page 消费会留实现期岔路。
   修法：补"SKIP 时 frame_idx=-1、person_box/landing_px=null，字段不省略"。
3. **"P4" 引用悬空**（交付物 1）：P4 定义在 plan.md（v1），spec 前置只列
   research.md。修法：spec 内自包含写死 `event_key = fid@anchor_time`。
   另提醒：plan/todo 的 v2 修订里需同步删掉 release_probe 的 P1/P2 稳定段判据，
   避免两份文档并存两套 Q2 口径。

## 可选优化（已全部采纳）

1. 跨产物字段命名统一：calib.json 的 `frame` 改 `frame_idx`。
2. 修订记录补阈值依据："90% 阈值相对 97.4% 先验留 ~7pt 余量（约 8 球），
   batch3 无先验系主要不确定源"。
3. 抽样点位缓冲：建议每事件点 6 点（≥5 判据不变），单点 >2m 返工剔除后
   折内仍满足留一下限。

## 与 AGENTS.md 冲突对照表

无冲突。四件套位置、work/ 中间产物落盘、rules.md §0.2 输入校验、只读复用
不改对外行为、reviewNN 与 calib-report 命名隔离等约定均合规；与经验教训 §8
兼容（未推翻 v1 真结论，Q2 新口径正是 §8 建议的筐锚定方案）。
