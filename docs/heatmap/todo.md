# todo：进球热区图 · v3 球队热图

依据：spec.md v3（review10/11 通过）+ plan.md v3

**v1/v2 状态（均已收尾记档）**：稳定段法 63.1% < 70% 证伪、轨迹法 55.7% < 90%
证伪（经验教训 §8）；release_probe.py / scorer_landings.py 留档。
**v3 当前状态：spec/plan 定稿（roster 驱动追人 + 筐锚粗配准，直接出图 +
目击验收），待立哥批准后开工。**

**全局质量门**：每个代码 Task 提交前必过 `ruff format scripts tests &&
ruff check --fix scripts tests && pytest -q`（--fix 后复核 diff）。
并行会话 WIP 文件（photo-select 等）跑全量门时用 --ignore 排除，不碰。

- [ ] Task 1：`scripts/goal_heatmap.py` 落点 + 坐标段 + 单测
  - Acceptance：106 已标记球全量处理；goal_landings.json 落盘（含
    event_key/team/路径/landing_px/rel_xy_m/flipped/覆盖状态）；便服剔除
    WARNING；缺缓存/两路皆无计 uncovered；控制台覆盖率汇总
  - Verify：ruff + pytest 绿（主路/兜底/双无/串人守卫/归一化取反/
    队别解析/坐标换算/覆盖统计合成用例）
  - Files：scripts/goal_heatmap.py、tests/test_goal_heatmap.py
- [ ] Task 2：渲染段 + 目击拼图（同脚本）+ 单测
  - Acceptance：每队一张热图 PNG 落 output/20260805_车百鼎/队伍_XX_进球热图.png
    （FIBA 半场模板 + 密度 + 散点）；目击拼图 heatmap_audit.png（15 球，
    落点帧+锚点帧并列，标注 event_key/rel_xy_m/flipped/模板落点）
  - Verify：pytest 绿（映射纯函数/翻转一致/固定种子复现）+ PNG 人工开图
  - Files：同上
- [ ] Task 3：实跑 + 立哥目击验收 + `docs/heatmap/calib-report.md`
  - Acceptance：覆盖率 ≥55%（分母 106，含便服 2 球——便服天然不覆盖）
    实测记录；目击 15 球 ≥10 过（判据双条写死）；
    报告含全部写死声明项（误差/选择性偏差/兜底噪声/静物风险/便服/
    roster 未确认/两端分布）
  - Verify：spec-reviewer 审报告通过
- [ ] Task 4：文档联动（通过→待办勾掉 + 经验教训补 v3 结论；
  不过→记档收敛 + 待办转封存）
  - Verify：联动文档过 spec-reviewer；全部提交
