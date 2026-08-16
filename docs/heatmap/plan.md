# plan：进球热区图 · v3 → v4 框人纠偏 → v4.1 渲染 → v4.2 分区+build 集成

依据：`docs/heatmap/spec.md` v4.2（v4 经 review14/15 两轮审查通过并实跑，
立哥裁决保持 0.5s 口径；v4.1 经 review16 审查修订并提交 0e8b40c；
v4.2 经 review17 审查修订：S1 边界条同步/S2 余量带归区口径/S3 目录推导
写死 goal_heatmap 侧/S4 懒 import 更正 + J1-J5）。

## 实施顺序与理由

```
Task 1 落点+坐标（goal_heatmap.py 核心，纯机器）     [v3 已完成]
   → Task 2 渲染热图 + 目击拼图（同脚本渲染段）        [v3 已完成]
   → Task 3 实跑 + 立哥目击验收                        [v3 失败：框错人]
   → Task 5 v4 修复（种子窗口 + 队色硬守卫）+ 重跑      [已完成，18.7% 裁决接受]
   → Task 6 v4.1 渲染双风格（暗场主图 + 蜂巢副图）      [已完成 0e8b40c]
   → Task 7 v4.2 分区副图替换蜂巢 + video build 集成
   → Task 3' 目击验收 + calib-report.md（立哥暂缓）→ Task 4 文档联动
```

Task 5 改动面小（goal_heatmap.py 一个函数 + 常量 + 单测），但触及落点
口径核心，仍走 spec 更新 + 两轮审查 + 质量门全流程。

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
     大端只翻 dx 不翻 dy（flipped 落盘；实测定版：场边机位纵深一致，
     全量旋转会把大端落点镜像到端线外）→ 尺度 = 人框高/假设身高
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

- 实跑 107 球出 goal_landings.json + 2 张热图 + 目击拼图
- 立哥判拼图 15 球（判据：① 真人且投篮者本人或紧贴出手点（对照锚点帧）；
  ② 映射落点界内且距筐 ≤10m）→ ≥10 过则收
- **v3 实跑结果：目击失败**——立哥判"框到的人不是我标记的进球人"；
  机检复核（落点帧框中人 team_of_box 队色 vs roster 队伍）27/67 队色
  相反必错，18 球便服待定；可视化抽查 6 错 3 对确认判色准确。
  根因：22/27 错球种子时刻在入网瞬间/之后（球穿网落进筐下人躯干框）
  → Task 5 修复后重跑，本任务验收以 v4 重跑结果为准
- 报告写死项：覆盖率实测、两端锚点分布与翻转端、目击结论、误差声明
  （人框高尺度/无旋转校正/贴边失真）、覆盖选择性偏差（偏好静止出手）、
  team_mismatch 剔除数与便服残余噪声、广告静物风险、便服剔除数、
  可用性结论
- Verify：spec-reviewer 审报告

### Task 5：v4 框人纠偏（goal_heatmap.py 一处函数 + 常量 + 单测）

- `session_facts.json` 注入 `team_color` 键（本场：
  `{"车百鼎": "黑", "半截篮": "白"}`——roster players tag 队色实测）
- `find_landing` 两处改动（不碰 crop_scorers 对外行为）：
  1. 持球点搜索：`Track(dets=[d for d in track.dets
     if d.sec <= anchor − HELD_SEARCH_BEFORE_SEC])`（0.5s，新模块常量）
     **新建实例**，不改原轨迹对象（兜底路仍用原轨迹起点）；
     find_held_box 与 start_nearest_box **均喂截断轨迹**（S1 写死，
     堵晚起轨迹侧门）；截断为空 → 无种子，直接落兜底/no_landing
  2. 队色硬守卫：新参 `expect_color`（调用方按 team_color[team] 传入）；
     两路落点产出后统一判——落点帧框中人队色与 expect_color 明确相反
     → 返回 uncovered（reason=`team_mismatch`）；便服放行
  3. 启动校验（S2）：roster 队伍集合 ⊆ team_color 键集合，缺队伍一次性
     WARNING 且该队守卫禁用；键整体缺失 → 守卫全禁 + 启动 WARNING
- 代码内文档同步：HeatLanding.reason 枚举 docstring 补 `team_mismatch`（A4）；
  goal_landings.json 字段不变（uncovered_by_reason 新增 team_mismatch
  计数；params 记录 team_color 是否生效）
- 单测新增：持球点窗口截断（入网后轨迹点不参与种子；截断空轨迹直接
  落兜底）、队色相反剔除、便服放行、expect_color 空禁用退化；
  既有 19 测保持绿
- 重跑：落点 + 2 张热图 + 新目击拼图（固定种子不变，抽样集合随覆盖
  变化属预期）→ **机检复核（A5 载体：`work/` 下一次性脚本
  color_recheck.py，遍历 goal_landings.json covered 球重判 team_of_box
  比对 roster 队伍，相反数必须为 0，结果进 calib-report；复用
  team_of_box 存在共模盲区——判色系统性错则守卫与复核同盲，v3 已抽样
  可视化确认判色准确，报告声明此依赖）** → 立哥判新拼图
- Verify：ruff + pytest 绿 + 机检复核 + 目击验收（成功标准见 spec v4）

### Task 6：v4.1 渲染双风格（goal_heatmap.py 渲染段替换 + 单测）

- 依据：4 风格打样（work/heatmap_style_{dark,wood,hex,zones}.py 留档），
  立哥选定暗场霓虹 + 蜂巢；打样已验证的坑必须带进生产版：
  稀疏点用连续 KDE 不分箱 + gamma 压暗（dark）、自写蜂巢网格不用
  ax.hexbin（等比拉伸变形）、热力层压场地线之下/灰线压蜂巢之上
- 改动（只动 goal_heatmap.py 渲染段 + 测试）：
  1. `render_team_heatmap` 原位替换为暗场霓虹实现（签名不变：
     pts/team/session/out——既有 smoke 测试不破）
  2. 新增 `render_team_heatmap_hex`（同签名）+
     `hex_centers`/`bin_points` 纯函数（可测）
  3. 新增 `filter_in_court(pts)` 界外过滤（余量 0.5m 模块常量），
     heat_session 渲染前统一过滤，逐球 WARNING + summary 记
     `out_of_bounds` 数；JSON 原始数据不动
  4. 全部渲染参数提为模块常量（σ=0.9/gamma=1.2/HEX_R=0.6/配色/视野）
  5. heat_session 每队出双图；中文字体 rcParams 进渲染函数内设置
  6. 蜂巢生产版固定 x∈[−8,8]（弃用打样右缘动态外扩，S1）；dy > 7.9 的
     界内点如出现 → WARNING 且不入蜂巢图（仍入暗场主图，S2）
  7. 两风格副标统一 `n=X 球（界外 Y 球未入图）`（Y=0 省略括号段，J1）
- 单测：双风格 smoke（空点集/有点集出 PNG）、filter_in_court 已知输入、
  hex 归格确定性；既有 25 测保持绿
- 重跑本场出正式双风格图 → 立哥过目（output 旧简笔图被同名覆盖，J4 已告）
- Verify：ruff + pytest 绿 + PNG 人工开图 + spec-reviewer 审 spec 修订

### Task 7：v4.2 分区副图 + build 集成（goal_heatmap.py + video.py）

- 依据：立哥看打样选定分区统计替换蜂巢（style_zones 图）；立哥指令
  热图以后在 build 阶段自动生成
- goal_heatmap.py：
  1. 删除 render_team_heatmap_hex / hex_centers / bin_points /
     HEX_* 常量（蜂巢下线），新增 `build_zones()` / `zone_of(x,y)`
     纯函数 + `render_team_heatmap_zones`（签名同主图渲染 + oob 参数）——
     打样 work/heatmap_style_zones.py 生产化：界外收拢逻辑弃用（输入已
     filter_in_court）、对手副标弃用（统一 _subtitle）、队色系调色板按
     队名字典序分配（ZONE_PALETTES 模块常量，不写死队名）
  2. heat_session 渲染循环：副图改 `队伍_XX_进球热图_分区.png`
- video.py `_cmd_build`：非 dry-run 合集全成后，成功分支内**懒 import**
  goal_heatmap 调 heat_session（S4）；**目录推导在 goal_heatmap 侧**——
  heat_session 三目录取 None 默认（推导从 main() 收进函数，video.py 只传
  session_dir，S3）；roster.json 缺失 **INFO** 跳过（J1）；异常捕获
  log ERROR 不改返回码；收尾 log 一行热图结果（出图/跳过/失败，J2/J5）；
  dry-run 只 _log_dry_step
- 单测：zone_of 10 区代表点归区（含余量带 dy<0 归就近区）、build_zones
  区数/标注位/多边形闭合、分区渲染 smoke/empty、调色板分配确定性；
  tests/test_video.py 增 build 集成 4 测（monkeypatch **goal_heatmap.
  heat_session**——懒 import 后 video 经模块属性调用，patch 模块本体即
  生效，S3 联动）：自动触发/失败不阻塞/roster 缺失跳过/dry-run 不执行；
  既有测试保持绿（hex 相关测试删除）
- 文档联动（同 Task 提交）：使用手册.html build 节、
  docs/video-cli/spec.md §build、AGENTS.md 统一入口行
- 重跑：`video build --session 20260805_车百鼎` 或单独跑 goal_heatmap
  验证双图 → 立哥过目
- Verify：ruff + pytest 全绿 + PNG 人工开图 + spec-reviewer 审文档

### Task 4：文档联动

- 验收通过：`docs/待办.md` 热图三启条目勾掉（注明产物路径）；
  经验教训 §8 补一条"v3 粗配准路线实测结论"
- 目击不过：经验教训 §8 记档收敛（三次出手全记录），待办.md 条目转
  "已证伪封存"
- 使用手册无需改（一次性产物，无 CLI 新命令）

## 风险表

| 风险 | 应对 |
|---|---|
| 追错人（种子框非投篮者） | ~~串人守卫 + 目击验收~~ **v3 实证失守**（种子与目标错成同一人时守卫放行）→ v4：持球点限出手前窗口 + 队色硬守卫双闸，目击验收仍是终裁 |
| 队色硬守卫误杀（队色判错） | team_of_box 同认人链路已实测；便服判定放行不剔除；剔除数进报告 |
| 窗口截断后持球点缺失致覆盖下降 | 出手前人持球是物理常态；跌破 55% 由立哥裁决，不硬凑 |
| session_facts 重建丢 team_color 键（S3） | run_session --force 重探测会整体重写 facts 不含该键 → 守卫退化；启动 WARNING 兜底可发现，run_session 自动写入列待办跟进 |
| 覆盖选择性偏差（突破类断链多） | 报告强制声明项；不宣称分布无偏 |
| 尺度噪声（人框高/贴边失真） | 报告误差声明；不现场调参 |
| 双端归一化切错端 | cx 双峰实测悬殊（563/1265）；报告附两端分布供核对 |
| hoops 零覆盖（实测 1 球） | 写死退化分支 + WARNING；覆盖统计如实 |
