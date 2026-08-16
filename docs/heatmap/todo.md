# todo：进球热区图 · v3 → v4 框人纠偏 → v4.1 渲染 → v4.2 分区+build 集成

依据：spec.md v4.2 + plan.md v4.2

**v1/v2 状态（均已收尾记档）**：稳定段法 63.1% < 70% 证伪、轨迹法 55.7% < 90%
证伪（经验教训 §8）；release_probe.py / scorer_landings.py 留档。
**v3 状态：Task 1/2 完成，实跑 67/107 = 62.6% 过覆盖率门槛，但目击验收
失败——立哥判"框到的人不是我标记的进球人"；机检复核 27/67 = 40% 队色
相反必错（另 18 球便服待定），根因 = 22/27 错球持球种子取在入网瞬间/之后
（球穿网落进筐下人躯干框），串人守卫对"种子目标同错"放行。**
**v4 状态：已实施并实跑（25 单测全绿）——覆盖 20/107 = 18.7%（守卫剔 12
错人 / 窗口剔 35 无种子球 / 便服 2）；阈值扫描（0.5/0.2/0.0/−0.3s）证实
放宽窗口多收的主要是错人球，立哥定：保持 0.5s 口径、覆盖率跌破 55% 裁决
接受；目击验收暂缓（立哥：先不管人，下次继续）。**
**v4.1 状态：已完成并提交 0e8b40c（暗场霓虹主图 + 蜂巢副图，界外过滤
3 球；review16 修订落实）。**
**v4.2 当前状态：立哥定副图蜂巢→分区统计替换 + 热图并入 video build
阶段；spec/plan/todo 已更新，待 spec-reviewer 两轮审查 → Task 7 实施。**

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
  - **v3 目击失败**（框错人，根因已定位）；v4 重跑 20/107 = 18.7%
    （守卫剔 12 / 窗口剔 35 / 便服 2），阈值扫描后立哥定保持 0.5s 口径、
    覆盖率跌破 55% 由立哥裁决接受；**目击验收立哥暂缓（"先不管人，
    下次继续"）**，calib-report 随目击一并后补
  - Acceptance：v4 机检队色相反数 = 0；覆盖率实测记录（跌破 55% 已裁决）；
    目击 15 球 ≥10 过（判据双条写死）；报告含全部写死声明项
    （误差/选择性偏差/team_mismatch 剔除数/便服残余噪声/静物风险/便服/
    两端分布）
  - Verify：spec-reviewer 审报告通过
- [x] Task 6：v4.1 渲染双风格（暗场霓虹主图 + 蜂巢副图）**已提交 0e8b40c**
  - 实跑：3 球界外过滤（|dx| 最大 11.9m），双风格各 2 张入 output/
  - 注：蜂巢副图上线不足一天即被 v4.2 分区统计替换（立哥看图后定）
- [ ] Task 7：v4.2 分区副图 + build 集成
  - goal_heatmap.py：蜂巢渲染器/常量/纯函数全删；build_zones/zone_of
    纯函数 + render_team_heatmap_zones（调色板按队名字典序，不写死队名；
    界外收拢与对手副标弃用，统一 _subtitle）；副图改 _分区.png
  - video.py _cmd_build：合集全成后懒 import 调 heat_session（三目录参数
    None 默认推导收进 goal_heatmap 侧，video.py 只传 session_dir）；
    roster 缺失 INFO 跳过；热图失败 log ERROR 不阻塞 + 收尾一行结果；
    dry-run 只打印
  - 单测：zone_of 归区/build_zones 几何/分区 smoke/调色板确定性 +
    test_video.py build 集成 4 测；hex 测试删除，其余保持绿
  - 文档联动同提交：使用手册.html、docs/video-cli/spec.md §build、
    AGENTS.md 统一入口行
  - 重跑验证 → 立哥过目
  - Verify：ruff + pytest 全绿 + PNG 人工开图 + spec-reviewer 审文档
  - Files：scripts/goal_heatmap.py、scripts/video.py、
    tests/test_goal_heatmap.py、tests/test_video.py、使用手册.html、
    docs/video-cli/spec.md、AGENTS.md
- [ ] Task 4：文档联动（通过→待办勾掉 + 经验教训补 v4 结论；
  不过→记档收敛 + 待办转封存）
  - Verify：联动文档过 spec-reviewer；全部提交
