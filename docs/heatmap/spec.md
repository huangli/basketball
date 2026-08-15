# spec：进球热区图 · 阶段 0 标定验证（v2 修订）

日期：2026-08-15 · 前置：`docs/heatmap/research.md`（预研档，路线与风险依据）
提出：立哥 · 状态：v1 review01/02 通过 → Q2 稳定段法实测 63.1% 证伪（经验教训
§8）→ **v2 修订（2026-08-15）：出手点回溯改复用认人轨迹法，Q2 重定义，Q1 不变**；
待 spec-reviewer 复审 + 立哥批准

## v2 修订记录

- 出手点口径：稳定段回溯法（v1，已证伪）→ **复用 crop_scorers.locate_scorer
  筐锚定轨迹法**（认人流程已验证先例，见下）
- Q2 重定义：轨迹法定位成功率（阈值 ≥90%）；v1 的"稳定段回溯 ≥70%"废弃
- Q1（配准精度 ≤0.5m）、calib 页/eval 工具设计、双门槛短路原则：全部沿用不变
- 修订依据：batch1+2 认人产物实测 78 球 76 真持球 = 97.4%（29/29 + 47/49），
  轨迹法不受"球在手上不停"与"闲置球假命中"两个证伪死因影响（筐锚定选轨迹）；
  90% 阈值相对 97.4% 先验留 ~7pt 余量（约 8 球），batch3 无认人先验系主要
  不确定源

## 目标

用最小成本回答两个 go/no-go 问题（Q1 沿用 v1；Q2 为 v2 重定义）：

- **Q1 配准精度**：人工点关键点的单应变换，在车百鼎素材上反投影误差中位
  是否 ≤ 0.5 米？
- **Q2 定位成功率（v2）**：122 球（`work/20260805_车百鼎/goals_batch*.json`
  confirmed 29+49+44=122）中，≥ 90% 能否经轨迹法定位到持球人框
  （`locate_scorer` OK 且非起点回退）？

**两条都过关 → 立项阶段 1；任一不过关 → 功能证伪，结论记经验教训，不纠缠。**

## 出手点口径（v2 修订，核心定义）

**热图落点 = 持球人脚部位置（persons 框底边中点），不是球心像素。**（v1 已确立，
理由不变：地面单应只映射地平面，出手瞬间球离地约 2m，球心反投影得到的是
"相机→球视线与地面的交点"，近景低机位下系统性偏差米级起步。）

- **出手时刻与持球人由认人轨迹法给出**（v2 变更点）：
  `locate_scorer(cache, anchor, anchor_xy)`——窗口 [anchor−4.0, anchor+0.5] 内
  run_mot 重链球轨迹 → 轨迹端点贴 candidates 锚点选进球轨迹（**筐锚定**，
  天然排除场边闲置球与无关球轨迹）→ 回放找最后持球点（球心严格在人框内）
  → 该帧人框即出手人框
- 落点 = 该人框底边中点（同一 mot_cache 内，无新检测）
- **reason==start_fallback 的球不计入可用落点**（起点回退框无持球语义），
  计 Q2 未命中但 goals 分母照旧（保守口径）
- 已知误差源（如实声明，不进判据）：最后持球帧可能早于真实出手 0.2~0.6s
  （球离手后下一采样帧才判非持球），人脚期间可移动；与 0.5m 门槛同量级，
  Q1 报告按事件分组附明细供研判

## 交付物

1. `scripts/scorer_landings.py`（批量落点实测器，纯只读）：
   对 122 球逐球跑 locate_scorer（复用 `load_candidates_index` +
   `match_anchor_xy` 注入 candidates_batch{1,2,3} 锚点；**不重定义 locate 窗口
   与判据**，全部从 crop_scorers 读常量）→ 输出
   `work/20260805_车百鼎/scorer_landings.json`（每球：event_key/fid/frame_idx/
   sec/person_box/landing_px/status/reason）
   + 控制台汇总（定位成功率分 reason 分层）。
   **event_key = `fid@anchor_time`（与 goals 条目一一对应；v1 plan P4 口径
   沿用不变）**；SKIP 球落盘形态写死：frame_idx=-1、sec=-1.0、
   person_box/landing_px=null，字段不省略（下游 gen_calib_page 消费此文件，
   不留实现期岔路）。
   **不改 mot_cache、不改任何现有产物；batch1/2 已有认人产物也要机器重跑
   统一落盘（认人 entry 不落 frame_idx/box，locate 幂等重算）**
   - 输入契约（rules.md §0.2）：goals/candidates 读入先过 schema 校验；
     缺缓存的球记 WARNING 且**计入分母**（保守口径）；锚点匹配超差退化为
     端点时间最近（match_anchor_xy 既有口径，与认人流程一致，不视为缺失）
2. `scripts/gen_calib_page.py`（配准标注小页生成器，HTML 单页，基建仿
   gen_label_page.py：自包含、localStorage、导出 JSON）：
   从 landings **可用落点球（OK 且非 start_fallback）** 分层抽 ≥10 事件——分层
   维度：左右端 × 远近 × 不同片段 ×
   变焦档（用 landings 人框高分档粗估；位置漂移分辨不了平移与变焦故不用筐位
   漂移；spec 的"镜头朝向"维度与"左右端"由筐锚点分布共同覆盖，合并为一维）。
   每事件展示**定位帧帧图**（`work/frames/<fid>/f_%05d.jpg`，frame_idx
   0-based ↔ 文件名 1-based），立哥点 **≥5 个**场地线交点（禁区四角 +
   罚球线端点/三分弧与边线交点等，**沿纵深铺开**，勿全挤筐周——单应 8 自由度
   最少 4 点可解，留一法评估需 n−1 ≥ 4，且点位集中会让远处条件数恶化；
   **建议每事件点 6 点**：若单点 >2m 触发返工剔除，仍剩 5 点、折内 4 点满足
   留一法下限），
   导出 `calib.json`（落 `work/20260805_车百鼎/`；schema：event_key / fid /
   frame_idx / points[{px,py, landmark}] / court_spec 版本号）
3. `scripts/calib_eval.py`（精度评估）：
   calib.json → 拟合 image→court 方向单应（landmark 真实坐标即 FIBA 米制
   坐标，如禁区四角 (±2.45, 0)/(±2.45, 5.8)）→ **留一法**：折内全部 n−1 点
   最小二乘（`method=0`；RANSAC 仅用于全量点参考拟合不进留一折——折内 4~7
   点时 RANSAC 无内点集可挑或混入拟合随机性），留出点像素映射到 court 平面，
   **误差直接在米制空间计算**（不做 px→米全局换算：单应下局部尺度随纵深
   连续变化，全局换算会系统性偏估，足以翻转 Q1 结论）→ 全部留一误差点混合
   取中位 + P90，按事件分组附明细；单点误差 >2m 记 WARNING 供返工
   （`work/20260805_车百鼎/calib_eval.json`）
4. 标定报告：`docs/heatmap/calib-report.md`（独立命名；reviewNN 序列专属
   spec-reviewer 审查报告，不混用），含双门槛结论（过/不过 + 实测数字）、
   抽样偏差说明、尺度锚定假设注明（默认 FIBA；非标场地判据等比放宽口径）

## 边界（不做）

- 不画热图成品、不动 matplotlib 模板（阶段 1 的事）
- 不改 `scripts/` 现有任何文件的对外行为；新脚本全部只读现有产物
  （scorer_landings.py 只 import 复用 crop_scorers 的函数与常量）
- 不做自动关键点检测模型（阶段 3 候选，本期不碰）
- 抽样事件的人工点关键点由立哥完成（≥10 事件 × ≥5 点；先 1 事件试手
  估时，再排总量）
- 稳定段回溯法（release_probe.py）已证伪留档，不再发展、不删（复算依据）
- SKIP 球无落点不进热图事件源：热图是统计产品，≤10% 缺失不歪分布；
  不追求 122 球全落点

## 成功标准（= go/no-go 判据，预先写死，防现场改目标）

- Q1：全部留一误差点**混合取中位 ≤ 0.5 米**（P90 同时报告供参考；
  样本 = 抽样事件 × 逐点留一）
- Q2（v2）：122 球中 locate_scorer **真持球 OK ≥ 90%**（即 ≥110 球；
  start_fallback 与 SKIP 均计未命中，缺缓存计分母）
- 质量门：ruff format/check 干净、pytest 全绿（新脚本各带单测：
  landings 的轨迹法调用链合成用例、单应误差计算的已知坐标用例）

## 依赖与环境

- cv2（opencv 5.0.0 已装）findHomography + perspectiveTransform
- 页面基建仿 gen_label_page.py（自包含 HTML、localStorage、导出 JSON）
- 定位帧帧图从 `work/frames/<fid>/f_*.jpg` 现取（已在盘上，1920×1080；
  车百鼎 148 文件经 session_facts 核实全部 3840×2160/59.94fps，无 4:3，
  本期无多尺寸口径问题；他场次复用时再按 session_facts 注入）
- candidates_batch{1,2,3}.json 已在 `work/20260805_车百鼎/`（run_session 产物）

## 开放问题

1. 抽样名单由我按分层维度选出，立哥只负责点——若立哥想自己圈事件，
   calib 页支持换事件（←/→ 翻页）
2. 尺度锚定默认 FIBA 标准尺寸；车百鼎场馆若为非标场地，误差判据等比
   放宽——默认按 FIBA，报告里注明
