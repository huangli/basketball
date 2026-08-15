# review03：plan/todo 第一轮审查存档（spec-reviewer，2026-08-15）

## 结论：需修订 → 已按下列清单修订 plan.md / todo.md，待复审

## 阻断（1 条，已修）

- **B1 米制换算数学漏洞**：单应下局部尺度随纵深连续变化，全局尺度中位换算
  会系统性偏估，足以翻转 Q1 结论。修订：Task 3 改为**拟合 image→court 米制
  单应，留一法误差直接在米制空间计算**，删除 px→米换算环节

## 建议改进（6 条，全部落实）

- S1 留一折内用全部 n−1 点最小二乘（method=0），RANSAC 仅作全量参考拟合 ✓
- S2 变焦档代理改 mot_cache 人框高/事件间筐锚点分布（位置漂移分不清平移与变焦）✓
- S3 顺序矛盾消除：机器开发可并行，立哥人工标注等 Q2 过关后启动（todo 顶部
  加人工门禁）✓
- S4 Task 4 报告写死项补"尺度锚定假设（FIBA 默认/非标放宽）" ✓
- S5 todo 顶部加全局 ruff+pytest 质量门 ✓
- S6 spec"镜头朝向"维度与"左右端"合并为一维并注明，防口径漂移 ✓

## 可选优化（4 条，全部落实）

- O1 球心不落任何人框 → 记未命中计入分母 ✓
- O2 Task 1 首行标"纯只读" ✓
- O3 todo Task 3 路径钉死 work/20260805_车百鼎/ ✓
- O4 find_held_box 复用方式写明（有球帧包成 Track 直接调） ✓

## 核对通过项（审查原文）

P1-P4 位置正确；load_mot_cache/find_held_box/trace_person 复用声明属实；
122 球 (fid, anchor_time) 无重复（P4 唯一性成立）；帧命名与 sec 口径一致；
test_gen_label_page 的 node --check 测试可仿；与 AGENTS.md/rules.md 无硬冲突。
