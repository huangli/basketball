# todo：进球热区图 · v3 球队热图 → v4 框人纠偏

依据：spec.md v4 + plan.md v4

**v1/v2 状态（均已收尾记档）**：稳定段法 63.1% < 70% 证伪、轨迹法 55.7% < 90%
证伪（经验教训 §8）；release_probe.py / scorer_landings.py 留档。
**v3 状态：Task 1/2 完成，实跑 67/107 = 62.6% 过覆盖率门槛，但目击验收
失败——立哥判"框到的人不是我标记的进球人"；机检复核 27/67 = 40% 队色
相反必错（另 18 球便服待定），根因 = 22/27 错球持球种子取在入网瞬间/之后
（球穿网落进筐下人躯干框），串人守卫对"种子目标同错"放行。**
**v4 当前状态：spec/plan 更新（出手前窗口 + 队色硬守卫），待两轮审查
→ Task 5 实施 → 重跑验收。**

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
  - **v3 目击失败**（框错人，根因已定位）；验收以 v4 重跑结果为准
  - Acceptance：v4 机检队色相反数 = 0；覆盖率 ≥55%（跌破由立哥裁决）；
    目击 15 球 ≥10 过（判据双条写死）；报告含全部写死声明项
    （误差/选择性偏差/team_mismatch 剔除数/便服残余噪声/静物风险/便服/
    两端分布）
  - Verify：spec-reviewer 审报告通过
- [ ] Task 5：v4 框人纠偏（goal_heatmap.py + 单测 + 重跑）
  - session_facts.json 注入 team_color（车百鼎=黑、半截篮=白）
  - find_landing：截断 Track 新建实例（find_held_box 与 start_nearest_box
    均喂截断轨迹，截断空 → 无种子直接兜底/no_landing，S1）；队色硬守卫
    （expect_color 相反 → team_mismatch 剔除；便服放行）；启动校验队伍
    集合 ⊆ team_color 键（S2，缺队 WARNING 该队禁用；键缺失全禁+WARNING）；
    HeatLanding.reason docstring 同步 team_mismatch（A4）
  - 单测新增 4 类（窗口截断含空轨迹/相反剔除/便服放行/禁用退化），
    既有 19 测保持绿
  - 重跑出落点 + 热图 + 新目击拼图 → 机检复核（work/color_recheck.py
    一次性脚本，covered 球队色相反数=0，A5）→ 立哥判
  - Verify：ruff + pytest 绿 + 机检队色相反数=0 + 目击验收
  - Files：scripts/goal_heatmap.py、tests/test_goal_heatmap.py、
    work/20260805_车百鼎/session_facts.json（team_color 键）、
    work/color_recheck.py（一次性复核脚本）
- [ ] Task 4：文档联动（通过→待办勾掉 + 经验教训补 v4 结论；
  不过→记档收敛 + 待办转封存）
  - Verify：联动文档过 spec-reviewer；全部提交
