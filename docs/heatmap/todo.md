# todo：进球热区图 · v3 球队热图

依据：spec.md v3（review10/11 通过）+ plan.md v3

**v1/v2 状态（均已收尾记档）**：稳定段法 63.1% < 70% 证伪、轨迹法 55.7% < 90%
证伪（经验教训 §8）；release_probe.py / scorer_landings.py 留档。
**v3 当前状态：Task 1/2 完成（goal_heatmap.py + 19 单测，质量门全绿），
实跑 107 球覆盖率 67/107 = 62.6% ≥ 55% 过关；坐标修正一处（只翻 dx 不翻 dy，
实测发现大端 33 球全镜像到端线外）；热图 2 张 + 目击拼图已产出，
待立哥目击验收（Task 3）。**

**全局质量门**：每个代码 Task 提交前必过 `ruff format scripts tests &&
ruff check --fix scripts tests && pytest -q`（--fix 后复核 diff）。
并行会话 WIP 文件（photo-select 等）跑全量门时用 --ignore 排除，不碰。

- [x] Task 1：`scripts/goal_heatmap.py` 落点 + 坐标段 + 单测
  - 结果：107 已标记球覆盖 67 = 62.6% ≥55% 过关（trace 58 + track_start 9；
    no_landing 36 / no_track_near_anchor 2 / casual 2）；坐标修正：大端只翻
    dx（全量旋转实测把 33 球镜像到端线外，spec/plan 已同步修订）
  - Verify：ruff + pytest 绿（主路/兜底/双无/串人守卫/归一化取反/
    队别解析/坐标换算/覆盖统计合成用例）
  - Files：scripts/goal_heatmap.py、tests/test_goal_heatmap.py
- [x] Task 2：渲染段 + 目击拼图（同脚本）+ 单测
  - 结果：2 张热图 PNG（半截篮 36 / 车百鼎 31）+ heatmap_audit.png（15 球，
    人框矩形+十字+锚点帧并列）；密度图加低值掩膜（0 值罩灰底问题修复）
  - Verify：pytest 绿（映射纯函数/翻转一致/固定种子复现）+ PNG 人工开图
- [ ] Task 3：实跑 + 立哥目击验收 + `docs/heatmap/calib-report.md`
  - Acceptance：覆盖率 ≥55%（分母 106，含便服 2 球——便服天然不覆盖）
    实测记录；目击 15 球 ≥10 过（判据双条写死）；
    报告含全部写死声明项（误差/选择性偏差/兜底噪声/静物风险/便服/
    roster 未确认/两端分布）
  - Verify：spec-reviewer 审报告通过
- [ ] Task 4：文档联动（通过→待办勾掉 + 经验教训补 v3 结论；
  不过→记档收敛 + 待办转封存）
  - Verify：联动文档过 spec-reviewer；全部提交
