# plan：进球热区图 · 阶段 0 标定验证（v2 修订）

依据：`docs/heatmap/spec.md` v2（review05/06 两轮审查通过）。
v1 plan（稳定段法）已随 Q2 证伪废弃——release_probe.py 留档不删（复算依据），
其 P1/P2 稳定段判据、P3 观察项不再使用；保留沿用的决策点：

- **P4 event_key 规则**：`fid@anchor_time`（与 goals 条目一一对应）——v2 沿用；
  anchor_time 按 goals 原值原样序列化，不做格式化（防对账时格式漂移）
- **门禁口径（写死）**：Task 2/3 机器开发不受人工门禁限制（Task 2 实抽样需等
  Task 1 产物，Task 3 合成 fixture 可即刻开工）；立哥人工点位必须等新 Q2
  报告出炉、确认 ≥90%（≥110/122）过关后才启动——短路原则：先跑便宜的判据，
  省人工

## 实施顺序与理由

```
Task 1 scorer_landings.py（新 Q2，纯机器）──┐
                                            ├─→ Task 4 双门槛汇总 + calib-report.md
Task 2 gen_calib_page.py（Q1 tooling）      │    → Task 5 文档联动（经验教训/research）
Task 3 calib_eval.py（Q1 评估，合成 fixture）┘
         ↑ 之间夹一次立哥人工：calib 页点 ≥10 事件（建议每事件 6 点）
```

Task 1 优先出报告：全机器无人工依赖，batch1/2 已有 97.4% 先验，batch3（44 球）是
主要不确定源。calib_eval 用合成 fixtures 先行开发，立哥点完 calib.json 即刻复用。

## 任务分解

### Task 1：`scripts/scorer_landings.py` + 单测（新 Q2，纯只读）

- 输入：`work/20260805_车百鼎/goals_batch{1,2,3}.json` +
  `candidates_batch{1,2,3}.json`（goals/candidates 均 schema 校验先行，
  file 去 .mp4 得 fid；缺缓存记 WARNING 且计入分母）；**不改任何现有产物**；
  batch1/2 已有认人产物仍机器重跑（认人 entry 不落 frame_idx/box，
  locate 幂等重算统一落盘）
- 逐球：`load_candidates_index` 建 fid→锚点索引 → `match_anchor_xy` 匹配
  （超差退化端点时间最近，与认人流程同口径）→ `locate_scorer(cache, anchor,
  anchor_xy)`（窗口/判据全部用 crop_scorers 导出常量，不重新定义）→
  落点 = 人框底边中点
- 输出：`work/20260805_车百鼎/scorer_landings.json`（每球：event_key/fid/
  frame_idx/sec/person_box/landing_px/status/reason；SKIP 写死 frame_idx=-1、
  sec=-1.0、person_box/landing_px=null 字段不省略）+ 控制台汇总（定位成功率
  分 reason 分层：真持球 / start_fallback / no_track / no_track_near_anchor /
  no_person / missing_cache）
- 单测：合成 mot_cache + candidates（真持球命中 / start_fallback 计未命中 /
  no_track_near_anchor / 缺缓存计分母 / SKIP 落盘形态 / 锚点超差退化）
- Verify：ruff format/check + pytest 绿 + 实跑 122 球出报告，
  达到/未达 90% 都如实记录

### Task 2：`scripts/gen_calib_page.py` + 单测（Q1 工具）

- 抽样：从 landings **可用落点球（OK 且非 start_fallback）** 分层抽 ≥10 事件
  （左右端 × 远近 × 不同片段 × 变焦档——变焦档用 landings **人框高**分档粗估；
  每档 ≥2 事件——plan 细化：spec 未写死，为防止变焦档抽样不足 Q1 偏乐观新增；
  抽样逻辑独立纯函数可测；分档依据写进 calib-report）
- 页面：仿 gen_label_page 自包含 HTML——展示定位帧帧图
  （`f_{frame_idx+1:05d}.jpg`）并**叠加人框矩形与落点标记**（供立哥判断
  该球落点可信度）、按序点 ≥5 个线交点（建议 6 点；页面给建议点位清单：
  禁区四角 → 罚球线端点 → 三分弧/边线交点，沿纵深铺开）、localStorage 进度、
  ←/→ 换事件、导出 calib.json
- 导出 schema（扁平结构，替代 spec 的分层表述，字段集合不变——plan 细化，
  扁平结构对 calib_eval 逐点留一评估更直接）：
  `{court_spec: "fiba-v1", points: [{event_key, fid, frame_idx,
  px, py, landmark}]}`（立哥下载后移入 work/20260805_车百鼎/）
- 单测：抽样分层覆盖断言（可用落点球过滤 start_fallback）、页面含 landmark
  清单与导出函数、node --check JS 语法（仿 test_gen_label_page 同款）
- Verify：ruff format/check + pytest 绿 + 生成页面浏览器实测点 1 事件
  （我先试手估时）

### Task 3：`scripts/calib_eval.py` + 单测（Q1 评估）

- 输入 calib.json（schema 校验）→ **拟合 image→court 方向单应**（landmark 的
  真实坐标即 FIBA 米制 court 坐标，如禁区四角 (±2.45, 0)/(±2.45, 5.8)）→
  留一法：折内用**全部 n−1 点最小二乘**（`method=0`；RANSAC 仅用于全量点
  参考拟合不进留一折），留出点像素映射到 court 平面，**误差直接在米制空间
  计算**（不做 px→米全局换算：单应下局部尺度随纵深连续变化，全局尺度中位
  换算会系统性偏估，足以翻转 Q1 结论——v1 一轮审查 B1 驱动，v2 沿用）
- 统计口径（写死）：全部留一误差点混合取中位 + P90，按事件分组附明细；
  单点误差 >2m 记 WARNING 供返工
- 输出：`work/20260805_车百鼎/calib_eval.json` + 控制台汇总
- 单测：已知合成单应 + 已知 landmark 坐标 → 误差应≈0；扰动 1 点误差上升
- Verify：ruff format/check + pytest 绿 + 合成 fixture 端到端跑通（不等立哥数据）

### Task 4：双门槛汇总 + `docs/heatmap/calib-report.md`

- 立哥点完 calib.json 后跑 calib_eval 出 Q1 实测；合并新 Q2 报告
- 报告写死格式：双判据实测值 vs 阈值（Q1 中位 ≤0.5m；Q2 ≥90% 即 ≥110/122）、
  抽样偏差
  说明、**尺度锚定假设注明（默认 FIBA；非标场地判据等比放宽口径）**、
  米制评估口径溯源一句、最后持球帧≈出手帧的 0.2~0.6s 人体位移误差声明、
  明确结论（立项阶段 1 / 证伪）
- Verify：报告含全部写死项；spec-reviewer 审报告

### Task 5：文档联动

- 立项：research.md 状态更新 + 阶段 1 spec 另起（新四件套）
- 证伪：`docs/经验教训.md` §8 追加一条（含实测数字与出处；
  v1 稳定段法证伪条目保留不删）
- 使用手册无需改（阶段 0 无立哥 CLI 新命令；calib 页为一次性工具）

## 风险表

| 风险 | 应对 |
|---|---|
| batch3 拖低 Q2（无认人先验） | 阈值 90% 已留 ~7pt 余量；真挂了短路，省立哥点位工 |
| 人框底边中点 ≠ 真实脚位（框截脚/贴边） | calib 页叠加人框与落点标记，立哥点位时同步研判；报告按事件附明细 |
| 最后持球帧早于真实出手 0.2~0.6s | spec 已声明为已知误差源；Q1 单点 >2m WARNING 触发返工复核 |
| 变焦档抽样不足导致 Q1 偏乐观 | 抽样强制覆盖每档 ≥2 事件；档位划分写进报告 |
| 立哥点位点错（线交点认错） | 页面给建议点位清单 + 人框叠加参照；>2m WARNING 返工机制 |
