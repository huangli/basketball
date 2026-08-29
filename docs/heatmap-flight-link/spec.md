# spec：热图落点飞行段链接修复（heatmap-flight-link）

日期：2026-08-29 ｜ 状态：已批准（立哥 2026-08-29 口头 ok，方向 1+2）

## 背景与问题

20260822_citymonkey 场次热图覆盖率 45.7%（16/35），低于 v4 写死的 55% 过关线；
半截篮 21 球仅 8 球有落点（1 球界外），分区图只画 7 球，立哥质疑"进球不止这个数"。

调研（explore 子代理，2026-08-29，结论实测）：

- 不是素材/参数问题：检测全链参数与历史一致，球框中位 31px，有球帧占比 78.8~86.7% 正常；
- 根因 1（主）：`run_mot` 匹配门限 `MAX_MATCH_DIST=80`px/帧（`mot_candidates.py:48`）
  是为"静止/慢速球找进球候选"标定的；5fps 下 = 400px/s 限速，飞行球被切成
  1~2 点碎片 → 主路无种子、兜底轨迹起点不满足 ≥0.8s → `no_landing`。
  实测：19 个 no_landing 中 **15 个**在 250px 门限下存在 ≥3 帧连续可链飞行序列；
- 根因 2（次）：`select_goal_track` 有 anchor_xy 时纯按端点空间距离最近选轨迹，
  筐锚点把选择"吸"向网内单点碎片（实测 306.5 / 477.2 两球因此选错），
  而网内点又被 v4 的 anchor−0.5s 截断排除，自断粮道；
- 本场放大器：室外邻场入镜，53~67% 的帧有 ≥2 个球框，加剧碎片与误链（推断）。

## 目标

热图落点链路对飞行段鲁棒：citymonkey 覆盖率从 45.7% 提升到 ≥55% 过关线
（调研预估 65~80%），且不改变 mot_candidates 候选挖掘主链与 crop_scorers
认人主链的既有行为。

## 范围

**做（方向 1+2，立哥批准）：**

1. `run_mot` 增加关键字参数 `max_match_dist`（默认 = `MAX_MATCH_DIST`，行为不变）；
   `goal_heatmap.find_landing` 以放宽门限 `FLIGHT_MATCH_DIST_PX = 250` 调用
   （落点链路专用，调研标定）。
2. `select_goal_track` 增加关键字参数 `prefer_longer`（默认 False，行为不变）：
   有 anchor_xy 时，端点距离在最优 + `PREFER_LONGER_SLACK_PX`(=100px) 内的轨迹
   组成候选池，池中取最长轨迹（长度并列取端点距离更近者）；
   外层 `GOAL_TRACK_MAX_DIST_PX` 上界判定不变。`find_landing` 传 True。
3. （v4.3 增补，实场验证首轮复盘发现）prefer_longer 同步覆盖 anchor_xy=None
   分支：端点时刻距在最优 + `PREFER_LONGER_SLACK_SEC`(=1.0s) 内的轨迹组成
   候选池取最长；且 `find_landing` 在 anchor_xy 分支选择落空（端点全超
   GOAL_TRACK_MAX_DIST_PX）时回退时间域长轨选择。依据：首轮 12 个残余
   no_landing 全部存在 ≥3 点长轨迹，10 个因手工锚远离机器候选
   （anchor_xy=None）走时间分支选中网内碎片，2 个机器候选空间误导。

**不做：**

- 不动 mot_candidates 候选挖掘口径（主链 run_mot 默认门限不变）；
- 不动 crop_scorers.locate_scorer 认人链（沿用默认参数；若日后要收益另行立项）；
- 不动抽帧 5fps 采样率（治本但检测耗时翻倍，暂缓）；
- 不补 `team_color` 自动注入 session_facts.json（plan.md 历史待办，与本修复正交，
  另行立项；本场守卫空转意味着覆盖率数字可能虚高，属已知口径）；
- 不改 v4 既有的 anchor−0.5s 截断、串人守卫、队色硬守卫、RELEASE_BEFORE_SEC 等口径。

**边界注明**：父 spec `docs/heatmap/spec.md` v4 写死"不改 goal_heatmap.py 以外任何
文件的对外行为"。本次 v4.3 增量动 mot_candidates / crop_scorers 两文件，方式为
**新增关键字参数且默认值保持旧行为**（对外行为不变的形式化保证），系立哥
2026-08-29 口头批准方向 1+2，特在此显式注明对该边界条款的超越依据。

## 成功标准

1. `pytest -q` 全绿（含新增测试）；`ruff format` / `ruff check` 无新告警；
2. 重跑 `python scripts/goal_heatmap.py --sessiondir work/20260822_citymonkey`：
   覆盖率 ≥55%；参考预期 `no_landing` 19 → ≤4（首轮改造后 19→12 已达成过关线；
   增补项针对残余 12 个——全部存在 ≥3 点长轨迹，预估可再救 8~10 个）；
   放宽误链不应大量撞守卫——本场守卫禁用，以 no_landing 下降数为主指标；
3. `work/20260822_citymonkey/heatmap_audit.png` 目击拼图交立哥肉眼抽验，
   落点无系统性错人（抽查权在立哥）；
4. 既有行为不回退：run_mot 默认参数产物与改前一致（由本次新增回归用例保证——
   plan 步骤 1 测试 A 第三条：静止球默认参数链接结果不变；run_mot 默认路径此前
   零测试覆盖，本用例即新增锁）。

## 风险与对策

- **误链风险**：250px 门限在多球帧（本场 53~67% 帧 ≥2 球框）可能把邻场球链进
  飞行轨迹。防线分工要认清：串人守卫与 anchor−0.5s 截断防"错人"，界外过滤是
  渲染层，**没有任何机器闸直接防"错球"**——误链球的真实防线是锚距 200px 上界
  （GOAL_TRACK_MAX_DIST_PX）+ prefer_longer 100px 滑窗 + 目击拼图立哥肉眼终裁，
  与"机器排序+人裁判"架构定位一致。
- **长轨偏好误选**：prefer_longer 可能选中过筐的长轨迹而非网内碎片——这正是
  目标行为（网内点反正被 v4 截断排除）；候选池限 100px 滑窗内，不会拉来远端无关轨迹。
