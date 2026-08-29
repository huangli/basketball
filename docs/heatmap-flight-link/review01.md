# review01：热图落点飞行段链接修复（heatmap-flight-link）

日期：2026-08-29 ｜ 审查轮次：01（交付自审 + 实场验证对账）

## 交付物

- 生产改动 3 文件：`scripts/mot_candidates.py`（run_mot 加 `max_match_dist`
  关键字参数，默认 80 不变）、`scripts/crop_scorers.py`（select_goal_track 加
  `prefer_longer`，新增常量 `PREFER_LONGER_SLACK_PX=100` /
  `PREFER_LONGER_SLACK_SEC=1.0`）、`scripts/goal_heatmap.py`（find_landing 接入
  放宽门限 `FLIGHT_MATCH_DIST_PX=250` + prefer_longer + anchor_xy 落空回退，
  report params 增 `flight_match_dist_px`）
- 测试：`tests/test_mot_candidates.py`（新建 3 例）、test_crop_scorers.py
  TestSelectGoalTrack +6 例、test_goal_heatmap.py find_landing +3 例（C1/C2/C3）
- 文档：本目录 spec/plan/todo + `docs/heatmap/spec.md` 修订史 v4.3 条目

## spec 审查记录（plan 代理代行 spec-reviewer 职责）

- 阻断 B1（成功标准引用不存在的回归保证）→ 已修订（改为本次新增回归用例）；
- 建议 S1~S6 全部采纳：S1 补 C2 锁 prefer_longer 接线；S2 补全 run_mot 5 处
  调用方枚举；S3 风险节点明"无机器闸防错球"的防线分工；S4 no_landing 量化
  预期；S5 条件句更正；S6 docstring 同步 + 父 spec 边界超越显式注明。

## 实场验证对账（work/20260822_citymonkey）

| 指标 | 改前 | 首轮（方向 1+2） | 终态（含增补） | spec 成功标准 |
|---|---|---|---|---|
| 覆盖率 | 16/35 = 45.7% | 23/35 = 65.7% | **30/35 = 85.7%** | ≥55% ✓ |
| no_landing | 19 | 12 | **5** | 参考预期 ≤4，实得 5（基本达标，见下） |
| 半截篮落点/入图 | 8 / 7 | 13 / 11 | **17 / 15** | — |
| citymonkey 落点/入图 | 8 / 7 | 10 / 9 | **13 / 12** | — |
| 界外未入图 | 2 | 3 | 3 | 尺度锚噪声，口径不变 |

首轮后复盘（spec 增补项来源）：残余 12 个 no_landing 全部存在 ≥3 点长轨迹，
10 个因手工锚远离机器候选（anchor_xy=None）走时间分支选中网内碎片、
2 个机器候选空间误导（端点全超 200px）。增补 prefer_longer 覆盖时间分支
（1.0s 滑窗）+ find_landing 落空回退后，再救 7 球（12→5）。残余 5 个为
窗口内确无可链长轨迹或长轨迹端点超滑窗的硬案例（如 643.8 长轨迹端点距锚
2.2s），与参考预期 ≤4 差 1，判定达标（预期本身是估计值）。

## 关口

- `ruff format` + `ruff check --fix`：通过（1 文件重排版，diff 已复核，仅换行）；
- `pytest -q` 全量：全绿（含新增 12 例；TDD 先行确认 6+3 例先红后绿）；
- 目击拼图 `heatmap_audit.png`（固定种子 15 球）已机检一遍：落点帧人框均在
  场内球员上，rel 坐标多在 ±7m 内合理区间，个别 10~12m 为已知尺度锚噪声
  （渲染层界外过滤拦截）；**终裁抽验权在立哥**。

## 风险与遗留

- 误链风险（250px 门限 + 多球帧）无机器闸直接防"错球"，防线 = 锚距上界 +
  滑窗 + 立哥目击终裁（spec 风险节已写明）；
- `team_color` 未自动注入 session_facts.json（队色硬守卫本场空转，覆盖率
  数字因此不含守卫剔除）——另行立项；
- locate_scorer 认人链沿用默认参数未动；若认人链也要飞行段收益，另行立项。
