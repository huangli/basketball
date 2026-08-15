# plan：进球热区图 · v3 球队热图

依据：`docs/heatmap/spec.md` v3（review10/11 两轮审查通过，J1/K1-K3 已落实）。
v1/v2 的 plan 随双证伪封存（release_probe.py / scorer_landings.py 留档不删）。
本版无"先验证后立项"门禁——机器全链路一次做完，立哥只做最终目击验收。

## 实施顺序与理由

```
Task 1 落点+坐标（goal_heatmap.py 核心，纯机器）
   → Task 2 渲染热图 + 目击拼图（同脚本渲染段）
   → Task 3 实跑 106 球 + 立哥目击验收 + calib-report.md
   → Task 4 文档联动（经验教训 / 待办.md）
```

Task 1/2 同脚本分段开发、一次提交；Task 3 夹立哥人工（判 15 球拼图）；
目击不过则按 spec 收敛记档，三次出手到此为止。

## 任务分解

### Task 1：`scripts/goal_heatmap.py` 落点 + 坐标段 + 单测

- 输入：roster.json（assignments tag→归属、players tag→team）+
  glob 发现 `goals_batch*.json` / `candidates_batch*.json` /
  `hoops_batch*.json` + work/detect/<fid>_mot_cache.json +
  work/frames/<fid>/f_*.jpg（串人守卫用）；全部 schema 校验先行；
  缺缓存 WARNING 计 uncovered；**不改任何现有产物**
- 逐球（roster 已归属球，event_key=`fid@anchor_time` 原值序列化）：
  1. 队别：tag→players.team；便服 WARNING 剔除；tag 查不到记 uncovered
  2. 轨迹：run_mot(track_window_dets) + select_goal_track（锚点经
     match_anchor_xy，超差退化端点时间最近同认人；无轨迹/端点超界 →
     计 uncovered）→ 种子框（find_held_box / start_nearest_box）
  3. 主路：trace_person 回追 → 链上最接近 anchor−1.0s 帧（±0.3s）→
     串人守卫（team_of_box 目标帧 vs 种子帧，黑↔白明确相反时主路不可用，
     **视同链断走兜底**；便服不触发）→ 人框底边中点
  4. 兜底：主路断且轨迹起点 ≥0.8s 前 → 起点帧最近人框底边中点
  5. 坐标：hoops 锚点（时刻最近；多覆盖取采样时刻最近、并列取空间最近；
     零覆盖取全局时刻最近 detected + WARNING）→ cx 中位切两端、归一小端、
     大端 (dx,dy) 取反（flipped 落盘）→ 尺度 = 人框高/假设身高
     （1.75m 为模块常量可调，rules.md 禁魔法值）
- 输出：`work/20260805_车百鼎/goal_landings.json`（event_key/team/路径/
  landing_px/rel_xy_m/flipped/覆盖状态）+ 控制台覆盖率汇总
- 单测：合成 mot_cache/hoops/roster——主路命中、链断走兜底、两路皆无
  uncovered、串人守卫剔除→走兜底（兜底断才 uncovered）、筐端归一化取反、
  队别解析（便服剔除/查不到）、坐标换算已知输入、覆盖统计
- Verify：ruff + pytest 绿

### Task 2：渲染段 + 目击拼图（同脚本）+ 单测

- matplotlib 标准半场模板（FIBA 米制：半场 15×14m，禁区/三分线/弧顶按
  标准尺寸画线）+ 高斯密度热图 + 落点散点叠加，每队一张 PNG 落
  `output/20260805_车百鼎/队伍_XX_进球热图.png`
- 目击拼图：固定种子抽 15 覆盖球，帧图取自
  `work/frames/<fid>/f_{frame_idx+1:05d}.jpg`；每球并列落点帧
  （人框矩形+落点十字）+ 锚点帧缩略 + 文字标注
  （event_key/rel_xy_m/flipped/映射后模板落点）→
  `work/20260805_车百鼎/heatmap_audit.png`
- 单测：模板映射纯函数（rel→模板坐标）、散点/翻转一致性、拼图抽样
  确定性（固定种子复现）
- Verify：ruff + pytest 绿 + 产物 PNG 人工开图检查

### Task 3：实跑 + 目击验收 + `docs/heatmap/calib-report.md`

- 实跑 106 球出 goal_landings.json + 2 张热图 + 目击拼图
- 立哥判拼图 15 球（判据：① 真人且投篮者本人或紧贴出手点（对照锚点帧）；
  ② 映射落点界内且距筐 ≤10m）→ ≥10 过则收
- 报告写死项：覆盖率实测、两端锚点分布与翻转端、目击结论、误差声明
  （人框高尺度/无旋转校正/贴边失真）、覆盖选择性偏差（偏好静止出手）、
  兜底路噪声、广告静物风险、便服剔除数、roster 未确认风险、可用性结论
- Verify：spec-reviewer 审报告

### Task 4：文档联动

- 验收通过：`docs/待办.md` 热图三启条目勾掉（注明产物路径）；
  经验教训 §8 补一条"v3 粗配准路线实测结论"
- 目击不过：经验教训 §8 记档收敛（三次出手全记录），待办.md 条目转
  "已证伪封存"
- 使用手册无需改（一次性产物，无 CLI 新命令）

## 风险表

| 风险 | 应对 |
|---|---|
| 追错人（种子框非投篮者） | 串人守卫 + 目击验收 15 球人工终裁；不过即收敛 |
| 覆盖选择性偏差（突破类断链多） | 报告强制声明项；不宣称分布无偏 |
| 尺度噪声（人框高/贴边失真） | 报告误差声明；不现场调参 |
| 双端归一化切错端 | cx 双峰实测悬殊（563/1265）；报告附两端分布供核对 |
| hoops 零覆盖（实测 1 球） | 写死退化分支 + WARNING；覆盖统计如实 |
