# plan：进球热区图 · 阶段 0 标定验证

依据：`docs/heatmap/spec.md`（review01/02 已过两轮审查）。
四个实现决策点（review02 收口项，写死不再讨论）：

- **P1 多稳定段取段规则**：出手时刻 = 窗口内**最后一段稳定段的末帧**
  （球离手即出手），人框取该帧持球人框
- **P2 稳定段判据**：段内**相邻**有球帧位移均 ≤60px（非首尾，更严同价）
- **P3 可信度观察项**：报告附"人框贴帧边 / 与相邻人框重叠"统计
  （不改判据，只做可信度分层）
- **P4 event_key 规则**：`fid@anchor_time`（与 goals 条目一一对应）

## 实施顺序与理由

```
Task 1 release_probe.py（Q2，纯机器）──┐
                                      ├─→ Task 4 双门槛汇总 + calib-report.md
Task 2 gen_calib_page.py（Q1  tooling）│    → Task 5 文档联动（经验教训/手册）
Task 3 calib_eval.py（Q1 评估）────────┘
         ↑ 之间夹一次立哥人工：calib 页点 ≥10 事件
```

Task 1 先行：全机器无人工依赖，Q2 若先证伪（<70%）可省下立哥点点的工
（短路原则：先跑便宜的判据）。**门禁口径（写死）：Task 2/3 的机器开发可在
Task 1 出结果后并行推进（只费机器时间）；立哥人工标注必须等 Q2 报告出炉、
确认过关后再启动**——这才真正兑现短路原则。calib_eval 用合成 fixtures
先行开发，立哥点完 calib.json 即刻复用。

## 任务分解

### Task 1：`scripts/release_probe.py` + 单测（Q2，纯只读）

- 输入：`work/20260805_车百鼎/goals_batch{1,2,3}.json`（schema 校验先行，
  file 去 .mp4 得 fid；缺缓存/缺帧记 WARNING 且计入分母）；**不改
  mot_cache、不改任何现有产物**
- 逐球：mot_cache（复用 crop_scorers.load_mot_cache 的校验实现）→
  锚点前 0.4~2.5s 窗口（帧间隔 0.2s，`sec=(idx-1)/5`）→ 稳定段检测
  （间隔 ≤2 帧分段；段内 ≥2 有球帧且相邻位移均 ≤60px）→ P1 取最后稳定段
  末帧 → 球心落人框定持球人（窗口内有球帧包成 Track 直接复用
  crop_scorers.find_held_box；球心不落任何人框 → 记未命中、计入分母，
  与缺缓存同口径）→ 人框底边中点落点；P3 观察项标记
- 输出：`work/20260805_车百鼎/release_probe.json`
  （每球：event_key/命中与否/稳定段数/落点/观察项）+ 控制台汇总
  （覆盖率 = 命中数/122、断帧分布、P3 分层）
- 一致性抽查：同球 ±0.4s 平移窗口两次回溯，落点像素距离 ≤100px 判一致；
  抽 10 球计入报告
- 单测：合成 mot_cache（稳定段/瞬移段/断帧段/多稳定段取末段/缺缓存计分母）
- Verify：ruff format/check + pytest 绿 + 实跑 122 球出报告，
  覆盖率达到/未达 70% 都如实记录

### Task 2：`scripts/gen_calib_page.py` + 单测（Q1 工具）

- 抽样：从 122 球分层抽 ≥10 事件（左右端 × 远近 × 不同片段 × 变焦档——
  变焦档用 mot_cache **人框高**（同片段/相邻事件间人框高变化）粗估分档，
  位置漂移分辨不了平移与变焦故不用筐位漂移；spec 的"镜头朝向"维度与
  "左右端"由筐锚点分布共同覆盖，合并为一维，此处注明防口径漂移）；
  抽样逻辑独立纯函数可测；分档依据写进 calib-report
- 页面：仿 gen_label_page 自包含 HTML——展示出手术帧（release_probe 命中球
  的出手帧；未命中球用锚点帧兜底并标注）、按序点 ≥5 个线交点（页面给出
  建议点位清单：禁区四角 → 罚球线端点 → 三分弧/边线交点，沿纵深铺开）、
  localStorage 进度、←/→ 换事件、导出 calib.json
- 导出 schema（P4）：`{court_spec: "fiba-v1", points: [{event_key, fid,
  frame, px, py, landmark}]}`（立哥下载后移入 work/20260805_车百鼎/）
- 单测：抽样分层覆盖断言、页面含 landmark 清单与导出函数、node --check
  JS 语法（仿 test_gen_label_page 同款）
- Verify：ruff format/check + pytest 绿 + 生成页面浏览器实测点 1 事件
  （我先试手估时）

### Task 3：`scripts/calib_eval.py` + 单测（Q1 评估）

- 输入 calib.json（schema 校验）→ **拟合 image→court 方向单应**（landmark 的
  真实坐标即 FIBA 米制 court 坐标，如禁区四角 (±2.45, 0)/(±2.45, 5.8)）→
  留一法：折内用**全部 n−1 点最小二乘**（`method=0`；RANSAC 仅用于全量点
  参考拟合不进留一折——折内 4~7 点时 RANSAC 无内点集可挑或混入拟合随机性），
  留出点像素映射到 court 平面，**误差直接在米制空间计算**（删除 px→米换算
  环节：单应下局部尺度随纵深连续变化，全局尺度中位换算会系统性偏估，
  足以翻转 Q1 结论——一轮审查 B1 驱动）
- 统计口径（写死）：全部留一误差点混合取中位 + P90，按事件分组附明细；
  单点误差 >2m 记 WARNING 供返工
- 输出：`work/20260805_车百鼎/calib_eval.json` + 控制台汇总
- 单测：已知合成单应 + 已知 landmark 坐标 → 误差应≈0；扰动 1 点误差上升
- Verify：ruff format/check + pytest 绿 + 合成 fixture 端到端跑通（不等立哥数据）

### Task 4：双门槛汇总 + `docs/heatmap/calib-report.md`

- 立哥点完 calib.json 后跑 calib_eval 出 Q1 实测；合并 Q2 报告
- 报告写死格式：双判据实测值 vs 阈值、P3 可信度分层、抽样偏差说明、
  **尺度锚定假设注明（默认 FIBA；非标场地判据等比放宽口径）**、
  单应评估口径溯源一句（米制空间直接评估，与 spec 交付物 3 字面
  "px→米换算"的偏差说明）、明确结论（立项阶段 1 / 证伪）
- Verify：报告含全部写死项；spec-reviewer 审报告

### Task 5：文档联动

- 立项：research.md 状态更新 + 阶段 1 spec 另起（新四件套）
- 证伪：`docs/经验教训.md` 记一条（含实测数字与出处）
- 使用手册无需改（阶段 0 无立哥 CLI 新命令；calib 页为一次性工具）

## 风险表

| 风险 | 应对 |
|---|---|
| Q2 先证伪，立哥点点白费劲 | 门禁写死：立哥人工标注等 Q2 报告过关后才启动（机器开发可先行） |
| 抽样事件人脚被挡（P3 高发） | 观察项如实报告；若 P3 比例 >30% 在报告中单独提示口径风险 |
| 变焦档抽样不足导致 Q1 偏乐观 | 抽样强制覆盖每档 ≥2 事件；档位划分写进报告 |
| 立哥点位点错（线交点认错） | 页面给建议点位清单 + 示意图；calib_eval 对单点误差 >2m 的事件记 WARNING 供返工 |
