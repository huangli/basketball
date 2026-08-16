# spec：筐检测消重（mot 缓存直存 Hoop 类，detect_hoops 免重复推理）

日期：2026-08-16　状态：待审（review 由独立审查员后续产出）　提出：score 链路提速调研 P1（2026-08-16 只读分析会话）

## 背景与目标

车百鼎场次（148 文件 / 11016 帧 @5fps）`run_session.log` 实测账：

| 阶段 | 实测耗时 |
|---|---|
| ② 抽帧 | 33 min |
| ③ mot 检测 | 143 min（0.78s/帧） |
| ⑤ detect_hoops 筐补检 | **131 min（0.73s/帧 × 10832 帧）** |
| ⑥ 审核片段 | 66 min |

结构事实：⑤ 与 ③ 是**同一模型（abdullahtarek_ball.pt）在同一批抽帧上跑两遍**——
`mot_candidates.detect_frame` 只取 `classes=[0]`（球），`detect_hoops.detect_hoop_frame`
再用同一模型同一 imgsz=1280 只取 `classes=[2]`（筐）。而事件窗口
（首候选-2s ~ 末候选+dur+2s）实测覆盖 10832 帧 ≈ **全部帧的 98%**（候选密度
0.55/s，事件窗口几乎铺满全场）——"缩小补检触发范围"无油水，问题是重复推理本身。

2026-08-16 本机 benchmark（8 帧实测）：球模型@1280 `classes=[0]` = 1.139s/帧，
`classes=[0,2]` 同时出球+筐 = **1.158s/帧（+1.7%）**。即主检测顺带存筐近乎零成本。

目标：detect_hoops 阶段从 ~45 min/批降到分钟级（读 JSON + 轨迹追踪），
净省 **~2.1h/场次**（6.2h → ~4h），且行为等价（hoops.json 轨迹逐点一致）。

## 功能

1. **mot_candidates 检测顺带存筐**：
   - `detect_frame` 球模型调用 `classes=[BALL_CLS]` 改为 `classes=[BALL_CLS, HOOP_CLS]`
     （HOOP_CLS=2，与 detect_hoops 现有常量同值同源）；
   - 缓存 payload 增加 `"hoops"` 键：每帧 `[{"conf":..,"cx":..,"cy":..}, ...]`，
     按 mot 侧 `CONF_BALL=0.15` 阈值全存（⊇ detect_hoops 的 0.25 口径）；
     **量化口径复刻 `detect_hoop_frame` 语义**：cx/cy 用 `int()` 截断取整
     （不用 round），conf 存原始 float 不截断——与成功标准 1"逐点完全相等"
     对齐（review01 B1）；
   - `load_detection_cache` 对**无 hoops 键的旧缓存仍算命中**（mot 自身不消费 hoops，
     不为加键触发 2.4h 全量重跑）；帧数/结构校验语义不变。
2. **detect_hoops 缓存优先、逐帧补检回退**：
   - 逐 fid 先读 `work/detect/<fid>_mot_cache.json`：存在、可读、帧数匹配且
     含 hoops 键 → 取筐检测，按 `CONF=0.25` 过滤后走现有
     `track_hoop`/`interpolate_gaps`（一律不改）；
   - 旧缓存（无 hoops 键）/ 缓存缺失 / 结构损坏 → 回退现行逐帧 YOLO 补检，
     记 INFO/WARNING 一行说明走了哪条路；
   - YOLO 模型改为**懒加载**：全批缓存命中时 detect_hoops 不加载模型。
3. **等价性论证（写进实施注释）**：ultralytics 的 conf 过滤发生在 NMS **之前**
   （`non_max_suppression` 先按 conf_thres 筛框，再做按类分组的 batched NMS）。
   conf 过滤逐框独立，故同模型、同帧、同 imgsz 下"存 ≥0.15 再滤 ≥0.25"与
   "直接 conf=0.25"产出集合一致；NMS 按分数降序处理、低分框不可能抑制高分框，
   且按类独立，多取 Hoop 类不影响 Ball 类输出——该论断由
   成功标准 2 的候选 diff 实测兜底，不靠推理担保。

## 边界（不做）/ 非目标

- **明确排除同批调研的 P2-P5**：审核片段单解码双输出/并行（P2）、抽帧 d3d11va
  硬解（P3）、imgsz 1280→960 降档（P4）、detect_hoops 事件级断点落盘（P5）。
  P5 在本功能落地后自然失效（缓存命中路径近乎即时），不做。
- 不改 `track_hoop` / `interpolate_gaps` / `select_hoop` / `CONF` / `IMGSZ` /
  事件窗口口径；不改 hoops.json schema（下游 gen_review_clips 契约不动）。
- 不改 run_session.py 编排（⑤ 阶段命令与断点判定原样）。
- **不回刷车百鼎已封存产物**：现有 148 个旧 mot_cache 不重建（无 hoops 键走
  回退路径，行为与现状完全一致）；hoops_batch1-3.json 封存只读。新场次自动受益。
- 不碰另一并行 session 的文件：`scripts/build_highlight.py`、`scripts/goal_heatmap.py`、
  `scripts/video.py` build 段、`docs/heatmap/`、`tests/test_goal_heatmap.py`。
- 不引入任何机器裁判/自动剔除语义（架构 = 机器排序 + 人裁判，不变）。

## 成功标准

1. **轨迹等价重放（机检）**：从批次 1 选 ≥3 个 fid（覆盖 detected=true 与
   detected=false 事件，按 hoops_batch1.json 现查选定），备份后重建其 mot_cache
   （新代码重跑 mot_candidates），逐 fid 跑 `detect_hoops.py --fid`，产出事件的
   key 集合、`detected`、`track` 逐点与封存 `hoops_batch1.json` 对应条目**完全相等**。
   若出现个别点 diff，判定流程：先查是否量化口径问题（review01 B1），
   再查数值漂移；确认漂移则按容差（±1px / conf ±0.005）复核并记录原因。
2. **候选侧回归（机检）**：同 subset 新缓存重跑 pilot_candidates 至临时路径，
   候选记录与封存 `candidates_batch1.json` 对应 fid 条目 diff 一致——验证
   `classes=[0,2]` 未扰动球检测输出。
3. **回退路径有测试**：单测构造"无 hoops 键的旧缓存"（monkeypatch 检测函数），
   断言走逐帧补检分支且产物与全新跑一致；缓存结构损坏（hoops 键类型错）同样回退不崩。
4. **关口**：`ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿
   （含现有 mot_cache 消费方测试：test_crop_scorers / test_scorer_landings /
   test_release_probe / test_run_session 不回归—— hoops 键为增量可选键）。
5. **性能观察值**：缓存命中时 detect_hoops 单 fid 墙钟降到秒级；全场次端到端
   省 ~2.1h 留待下一新场次实测确认（车百鼎缓存不重建，见非目标）。

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| `classes=[0,2]` 扰动球检测输出（NMS/数值漂移） | 低 | 成功标准 2 候选 diff 实测兜底；不一致即回退该改动 |
| 缓存 schema 增量破坏现有读者 | 低 | 纯增量可选键；读者均按键取用（crop_scorers 取 balls/persons，run_session._legit_zero_candidate 只读 frames）；关口含消费方测试回归 |
| 回退路径分支选错（新缓存误判为旧） | 低 | 判定条件 = "hoops 键存在且为 list"；单测覆盖三分支（新缓存/旧缓存/损坏） |
| 存 0.15 滤 0.25 与直接 0.25 不等价 | 低 | ultralytics conf 过滤发生在 NMS 之前且逐框独立，理论等价 + 成功标准 1 轨迹逐点 diff 实证 |
| detect_hoops 懒加载后 import 顺序/依赖变化 | 低 | 仅把 `YOLO(...)` 调用移到首次回退分支；torch import 保留在模块头（detect_hoops 已 import mot_candidates，本就在 torch 链上） |

## 开放问题

1. 缓存是否加显式 schema 版本字段？倾向**不加**——以 hoops 键有无作隐式版本，
   符合最小改动；若审查员认为显式版本更稳，加 `"cache_v": 2` 一处即可，不阻塞。
2. 同场次混用新旧缓存（如车百鼎后续 adhoc 补跑个别 fid）时产物可比性：
   两路径理论等价（成功标准 1 实证），逐 fid 独立选路，不强制统一。
