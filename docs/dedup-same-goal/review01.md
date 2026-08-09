# review01：标注页同球双 J 自动识别（spec-reviewer 第 1 轮）

审查日期：2026-08-08。审查对象：docs/dedup-same-goal/ 的 spec.md / plan.md / todo.md。
审查方式：只读核对数据文件（events_index.json、goals_20260722_3.json、goals_batch3.json、goals_20260722_2.json）与代码（gen_label_page.py、gen_review_clips.py）。

## 结论：有阻断问题（2 处事实性错误，已按本轮意见修订完毕，通过）

## 已核实无误的事实

- 批次 3 原始导出 61 条 confirmed、去重后 51 条，与 JSON 计数一致。
- 同文件 8 组同球对 anchor 逐条核对全部相符（200730@3.0/6.1、200854@3.5/5.8、201604@6.2/8.6、201718@2.7/5.7、203946@1.7/5.9、204746@4.2/7.9、205942@11.5/14.9、210152@17.3/20.4），差值范围 2.3~4.2s 属实。
- 批次 2"195912 同例（37 标 → 35 球）"属实：goals_20260722_2.json 共 37 条 confirmed，195912 有 8.1/10.6 两条。
- 分组规则与数据结构兼容：events_index.json 每条事件含 fid、anchor_t0、clip、clip_wide，字段够用。
- 导出确认框兼容：导出为页面内 JS exportGoals()（gen_label_page.py:137），加 confirm() 前置检查无架构障碍；分组结果可在 Python 侧生成页面时内联进事件数据。
- todo 9 项与 plan 6 步一一对应；成功标准三条均可检验。

## 阻断问题（已修订）

1. **窗口口径引用错误（spec.md 原第 34 行）**。spec 原称审核窗口"前 4s / 后 4s+结局尾巴"。实测 gen_review_clips.py:50-53：CLIP_BEFORE_SEC = 2.0（事件首候选前）、CLIP_AFTER_SEC = 4.0（事件末候选后），即前 2s / 后 4s。"前 4s"来自 gen_label_page.py:38 的同名常量（导出剪辑窗口前 4 后 2），两模块同名常量不同值，spec 引混。→ 已修订为正确口径并注明两模块同名常量勿混。
2. **跨文件三标 anchor 与所引来源不符（spec.md 原第 11 行）**。spec 原写"203628@2.2"，但其引用的原始导出 goals_20260722_3.json 中 203628 的 anchor_time 为 3.5；2.2 是去重鉴定时人工修锚点后的值（goals_batch3.json:246；主文档 §4 去重明细："留 203628 并修锚点 3.5→2.2"）。→ 已修订为"203628@3.5（去重鉴定时帧级修锚点为 2.2）"。

## 建议项（已采纳并入 spec/plan）

- 近似口径 [anchor−CLIP_BEFORE, anchor+CLIP_AFTER] 的左界为保守子集（实际片段左界相对事件首候选更早，events_index 无事件跨度字段）——已写入 plan 步骤 1。
- 同名常量 import 写全模块路径——已写入 plan 风险节。
- "上一个/下一个"措辞改为"同组其他事件"（页面按 hoop_dist 全局排序，同 fid 事件不一定相邻）——已修订 spec 目标节。
- 回放断言口径写明"真两球（203918/203928、205204/205158）与 42 个独立球不入多事件组"——已写入 plan 步骤 5。

## 规范符合性

- 四件套目录约定（docs/dedup-same-goal/ 下 spec/plan/todo + 本 review01）符合 AGENTS.md。
- 阻断问题修订完毕，本件通过，可进入实施。
