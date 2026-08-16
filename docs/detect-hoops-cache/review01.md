# review01：筐检测消重 三件套审查（spec / plan / todo）

日期：2026-08-16　审查员：独立 spec-reviewer（只读审查）
对象：`docs/detect-hoops-cache/` spec.md、plan.md、todo.md

## 整体评价

三件套结构完整、边界清晰，性能账目与源码行号引用经抽查基本全部属实，回退设计（旧缓存命中、逐帧补检兜底、懒加载）符合 rules.md 鲁棒优先与素材流动原则。但存在两处照做会直接出错的问题：坐标/conf 量化口径未钉死（与"逐点完全相等"的验收标准相冲突）、Step 4 验证命令路径不可执行。**结论：需修订。**

## 阻断问题

### B1. hoops 缓存条目的量化口径未钉死，与成功标准 1"逐点完全相等"必然冲突

- 位置：spec.md §成功标准 1（:65-68）；plan.md Step 1（:16-18）
- 事实核对：
  - 现行直检路径 `detect_hoop_frame`（`scripts/detect_hoops.py:169`）坐标用 `int(v)` **截断**取整，conf 用原始 float 在推理时以 `conf=0.25` 过滤；
  - mot 缓存路径 Ball 条目（`scripts/mot_candidates.py:210-213`）坐标用 `round(v)`（银行家舍入）、conf 用 `round(float(b.conf), 2)` 存两位小数。
- 问题：plan Step 1 只说 hoops 条目"从同一 `rb[0].boxes` 按 cls==HOOP_CLS 筛出"，未规定取整与 conf 精度。实施者沿用 Ball 路径惯例（round + 两位小数）是自然选择，但：
  - `round(10.7)=11` vs `int(10.7)=10` → cx/cy 可差 ±1px，成功标准 1 要求 track **逐点完全相等**，diff 必非零；
  - conf 存两位小数再滤 0.25：原始 0.2496 → 存 0.25 → 缓存路径放行，而直检 `conf=0.25` 会排除 → 边界帧检出集合不同，track 同样分叉。
- 修法（二选一，建议前者）：
  1. plan Step 1 明确 hoops 条目**复刻 detect_hoop_frame 语义**：cx/cy 用 `int()` 截断（不用 round），conf 存原始 float 不截断，并在 todo Task 1 验收标准中对应写明；
  2. 或成功标准 1 放宽为"±1px / conf 边界 ±0.005 容差内相等"并说明理由——但这会削弱"行为等价"的核心卖点，不推荐。

### B2. plan Step 4 的验证命令照抄不可执行

- 位置：plan.md Step 4（:59-63）
- 事实核对：`candidates_batch1.json` / `hoops_batch1.json` 实际位于 `work/20260805_车百鼎/` 下（已确认存在），仓库根下无此文件；`detect_hoops.py --candidates candidates_batch1.json ...` 在仓库根执行会因文件不存在被 `read_json` 拒掉退出。且命令缺 `python scripts/` 前缀——本工作区 shell 为 PowerShell 7+（AGENTS.md），裸写 `detect_hoops.py` / `mot_candidates.py` 无法直接运行。
- 修法：命令写全，例如：
  `python scripts/detect_hoops.py --candidates work/20260805_车百鼎/candidates_batch1.json --fid <fid> --out work/diag/hoops_recheck_<fid>.json`
  同理 `python scripts/mot_candidates.py <fid...>`、`python scripts/pilot_candidates.py --out work/diag/candidates_recheck.json <fid...>`（两者 CLI 已核对支持该用法）。

## 建议改进

1. **spec.md §功能 3（:44-47）等价性论证的事实性错误**：ultralytics 的 conf 过滤发生在 NMS **之前**（`non_max_suppression` 先按 conf_thres 筛框再做按类分组的 batched NMS），不是"NMS 之后的结果过滤"。结论仍成立（conf 过滤逐框独立；NMS 按分数降序处理，低分框不可能抑制高分框，故 ≥0.25 集合两路径一致），建议改写论证措辞，避免给后续读者留下错误心智模型。不影响成败（文档已声明由实测兜底），不升级为阻断。
2. **hoops 元素级结构校验缺失**：spec 风险表与 plan Step 2 的判定条件均为"hoops 键存在且为 list"。若 hoops 是 list 但元素损坏（缺 cx/cy、类型错），缓存路径会在查表时 KeyError/TypeError 崩在半路，而非回退。rules.md §0.2"数据损坏必须停/可观测"。建议 `load_hoop_frames` 在转换时对元素做校验（或 try 转换整体失败即回退），并在 Step 3 单测补一条"hoops 为 list 但元素损坏"用例。
3. **Step 4 fid 形态未说明**（plan.md :55-58）：work/detect 下缓存主键是完整文件名片段（如 `dji_mimo_20260805_185356_0001_1785944202088_video`，已确认），不是早期 0001 风格短号。建议写明"fid 取 hoops_batch1.json events[].fid 原值"。
4. **成功标准 1 的复跑确定性无口径**（spec.md :65-68）：封存 hoops_batch1.json 由旧代码 `classes=[2]` 直检产出，新路径是新代码 `classes=[0,2]` 重跑的缓存。同机同版本 CPU 推理通常可复现，但若出现数值漂移导致个别点 diff，当前文档只有"不一致即回退该改动"——建议补一句判定流程（先查是否量化口径问题 B1，再查漂移，漂移则按容差复核）。
5. **todo.md Task 2 验收（:32）"逐字节同构"措辞过强**：JSON 字节级一致受浮点格式化/键序影响，实际意图是字段/schema 同构。建议改为"key/detected/track/window/anchor 字段与现行 schema 同构"。

## 可选优化

1. **AGENTS.md / 主文档不在并行 session 的"不碰"清单内**：spec §边界列了 build_highlight.py / goal_heatmap.py / video.py build 段 / docs/heatmap/ / test_goal_heatmap.py，但 plan Step 5 要改 `AGENTS.md` 与主文档 §2——heatmap session 收尾时大概率也要同步这两处。建议 Step 5 执行前先 `git status` 确认对方是否已动这两文件，避免合并冲突。
2. **Step 4 备份目录去向**：`work/detect/bak_<日期>/` 验证后恢复即空置，建议写明"恢复后删除空目录"或保留策略，避免 work/ 下遗留歧义缓存。
3. **开放问题 1（cache_v 字段）**：同意 spec 倾向——以 hoops 键有无作隐式版本符合最小改动，不加显式版本字段。
4. spec 背景表数字经核算自洽：0.73s/帧 × 10832 ≈ 132 min（报 131）、0.78 × 11016 ≈ 143 min、131 min/3 批 ≈ 44 min/批（报 ~45）、10832/11016 ≈ 98.3%（报 98%）——均对，无需改。

## 行号引用抽查（全部属实）

| 引用 | 实际 | 结果 |
|---|---|---|
| plan :15 `detect_frame` = mot_candidates.py:174-224 | :174-224 | ✓ |
| plan :16 球模型调用 = :193-199 | :193-199 `rb = ball_model(...)` | ✓ |
| plan :20 `save_detection_cache` = :227-262 / `load_detection_cache` = :265-297 | :227-262 / :265-297 | ✓ |
| plan :19 检测循环 = :655-673 | :655-673 else 分支含 `save_detection_cache` | ✓ |
| plan :30 detect_hoops.py:40 `import mot_candidates as mot` | :40 | ✓ |
| plan :33 CONF :47 / :36 `detect_hoop_frame` :156-171 / :39 `model = YOLO(...)` :241 | :47 / :156-171 / :241 | ✓ |
| plan :37-38 `track_hoop` :75 / `interpolate_gaps` :127 | :75 / :127 | ✓ |
| spec :31 detect_hoops 现有 HOOP_CLS=2 | detect_hoops.py:49 | ✓ |
| spec 成功标准 4 消费方测试 test_crop_scorers / test_scorer_landings / test_release_probe / test_run_session | tests/ 下均存在 | ✓ |

## 与 AGENTS.md 冲突对照表

无冲突。已逐条核对：四件套同放 `docs/<功能名>/`（✓ 本目录）、review 按轮次编号不覆盖（✓ review01 起排）、commit 不 push 且只 add 本功能文件（✓ plan Step 5）、关口三连（✓ spec 成功标准 4 与 rules.md §10 一致）、机器排序+人裁判架构不变（✓ spec §边界明示）、素材流动/容忍缺失（✓ 旧缓存与缺文件均走回退）、文档自审要求（✓ 本审查即执行）。

## 结论

**需修订**（存在阻断问题 B1、B2）。修订量小：B1 钉死量化口径（建议复刻 `int()` 截断 + conf 存原始 float），B2 补全命令路径与前缀；建议改进 5 条可同轮一并吸收。
