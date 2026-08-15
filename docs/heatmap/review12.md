# review12：plan/todo v3 第 1 轮审查（2026-08-15）

审查对象：`docs/heatmap/plan.md`、`docs/heatmap/todo.md`（v3 全文重写）
审查员：spec-reviewer 子代理 · 结论：**通过（无阻断）**，建议改进 3 条 + 可选优化 3 条

## 整体评价

plan/todo v3 与 spec v3 高度一致：落点两路并集、筐端归一化、队别解析、交付物、
成功标准逐项对得上，引用的 crop_scorers 函数链经逐函数核实全部属实，
v1/v2 仅以封存/留档身份出现。

## 建议改进（已全部采纳，review13 复核落实）

1. **串人守卫剔除后是否走兜底未写死**（根源在 spec 落点口径节）——两种读法
   覆盖率口径不同，涉及 ≥55% 门槛余量。修法采纳：写死"守卫剔除 → 视同链断
   走兜底"，spec/plan 同步。
2. **覆盖率分母口径（106 含便服 2 球）未在 plan/todo 重申**——实现者易从分母
   剔掉便服变 104，静默抬升覆盖率。修法采纳：todo Task 3 写明。
3. **身高 1.75m"模块常量可调"在 plan 丢失**——rules.md 禁魔法值。修法采纳：
   plan 步骤 5 补。

## 可选优化（已全部采纳）

- todo Task 1 Acceptance 字段清单补 event_key。
- plan 步骤 2"超差退化同认人"措辞改准确（锚点超差 → 退化时间最近；
  无轨迹/端点超界 → uncovered）。
- plan Task 2 目击拼图补帧图输入路径。

## 代码事实核对（全部属实）

run_mot/track_window_dets/select_goal_track/find_held_box/start_nearest_box/
trace_person/team_of_box/match_anchor_xy 逐函数签名与常量核实无误；
TRACE_WINDOW_SEC=2.0 写死（S2 上限声明属实）；GOAL_TRACK_MAX_DIST_PX=200；
帧命名 f_{frame_idx+1:05d}.jpg（0-based↔1-based）与 crop_scorers.py:1207 一致。

## 与 AGENTS.md 冲突对照表

无冲突（四件套、质量门、目录约定、素材流动、不改对外行为均合规）。
