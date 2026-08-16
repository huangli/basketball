# plan：筐检测消重（mot 缓存直存 Hoop 类，detect_hoops 免重复推理）

依据 `docs/detect-hoops-cache/spec.md`。
改动面：`scripts/mot_candidates.py`、`scripts/detect_hoops.py`、
`tests/test_detect_hoops.py`（新增用例）；无新脚本。
**不碰**：build_highlight.py / goal_heatmap.py / video.py / docs/heatmap/ /
tests/test_goal_heatmap.py（并行 session 施工中）。

## 步骤

### Step 1：mot_candidates 检测顺带存筐

- `scripts/mot_candidates.py:40` 附近加 `HOOP_CLS: int = 2`（注释对齐
  detect_hoops.HOOP_CLS，两处同源同值）。
- `detect_frame`（`scripts/mot_candidates.py:174-224`）：
  - 球模型调用（:193-199）`classes=[BALL_CLS]` → `classes=[BALL_CLS, HOOP_CLS]`；
  - 返回值增加第三项 `hoops: list[dict]`（每帧 [{"conf","cx","cy"}]，
    从同一 `rb[0].boxes` 按 cls==HOOP_CLS 筛出；Ball 筛选逻辑原样）；
    **量化口径复刻 detect_hoop_frame：cx/cy 用 `int()` 截断、conf 存原始
    float 不截断**（不用 Ball 路径的 round + 两位小数——review01 B1，
    否则成功标准 1 逐点 diff 必非零）；
  - 同步改 `run_pipeline` 检测循环（:655-673）接第三返回值并传入落盘。
- `save_detection_cache`（:227-262）：payload 加 `"hoops"` 键（增量，不动
  frames/balls/persons 结构）。
- `load_detection_cache`（:265-297）：**不校验 hoops 键**（旧缓存仍命中，
  mot 自身不消费）；docstring 注明 hoops 由 detect_hoops 自行判读。
- 关口：ruff + pytest（无 mot 专属测试文件，靠消费方测试回归）。

### Step 2：detect_hoops 缓存优先 + 回退 + 模型懒加载

- 新函数 `load_hoop_frames(fid) -> dict[float, list[tuple[int,int]]] | None`
  （detect_hoops.py 内，复用 `mot.CACHE_PATTERN`，模块已 `import mot_candidates
  as mot`，detect_hoops.py:40）：
  - 读缓存 → 缺失/损坏/帧数与帧目录不符/无 hoops 键或类型非 list → None
    （各分支记一行 INFO/WARNING 说明选路）；**元素级校验**：转换时逐条
    校验 cx/cy/conf 存在且为数，整体 try 失败或元素损坏 → 同样回退 None
    （不半路崩——review01 建议 2）；
  - 命中 → {sec: [(cx,cy),...]}（按 `CONF=0.25` 过滤，CONF 现有常量 :47 不动；
    sec 用 mot.parse_sec 同源）。
- 事件循环（:267-300）：逐 fid 进入循环前解析一次选路结果；
  命中路径跳过 `detect_hoop_frame`（:156-171，保留作回退实现，不改）；
  每帧 sec→筐中心 查表替代 YOLO 调用，下游 `track_hoop`(:75) /
  `interpolate_gaps`(:127) / 输出 schema 一律不动。
- 模型懒加载：`model = YOLO(...)`（:241）移到首个回退分支内首次使用时构造
  （模块级 `model: Any | None = None` 或局部惰性变量，取实现简洁者）。
- 关口：ruff + pytest。

### Step 3：单测（tests/test_detect_hoops.py 追加）

- 缓存命中路径：构造含 hoops 键的假缓存（tmp_path + monkeypatch
  CACHE_PATTERN/帧目录），断言不走 detect_hoop_frame（monkeypatch 计数 0 次），
  且 ≥0.25 过滤正确（0.24 被滤、0.25 保留、0.15 存而不入）。
- 旧缓存回退：无 hoops 键缓存 → 断言走逐帧分支（detect_hoop_frame 被调），
  产物与无缓存全新跑一致。
- 损坏回退：hoops 键类型错（str/dict）→ 回退不崩，WARNING 有记录；
  hoops 为 list 但元素损坏（缺 cx/cy、类型错）→ 同样回退不崩（review01 建议 2）。
- 关口：ruff + pytest。

### Step 4：子集重放验证（spec 成功标准 1/2/5）

- 从 `work/20260805_车百鼎/hoops_batch1.json` 现查选 ≥3 fid：
  ≥1 个含 detected=true 事件、≥1 个含 detected=false 事件。
  **fid 取 hoops_batch1.json `events[].fid` 原值**（完整文件名片段，
  如 `dji_mimo_20260805_185356_0001_1785944202088_video`，非短号）。
- 备份这 3 个 `work/detect/<fid>_mot_cache.json` 到 `work/detect/bak_<日期>/`，
  删除原缓存后重跑 `python scripts/mot_candidates.py <fid...>` 生成新缓存
  （~分钟级）。
- 成功标准 1：逐 fid `python scripts/detect_hoops.py --candidates
  work/20260805_车百鼎/candidates_batch1.json --fid <fid> --out
  work/diag/hoops_recheck_<fid>.json`，diff 事件条目（key/detected/track
  逐点）vs 封存 `work/20260805_车百鼎/hoops_batch1.json` —— 必须完全相等。
- 成功标准 2：`python scripts/pilot_candidates.py --out
  work/diag/candidates_recheck.json <fid...>`，diff 对应 fid 候选记录
  vs `work/20260805_车百鼎/candidates_batch1.json` —— 必须一致。
- 验证后恢复备份缓存并删除空置的 `bak_<日期>/`（车百鼎封存口径：不留下
  混合状态；work/ 为忽略区，diag 产物不入库）。
- 性能观察：记录 detect_hoops 缓存命中单 fid 墙钟，写进 review。

### Step 5：文档与提交

- **执行前先 `git status`**：确认并行 session 是否已动 AGENTS.md / 主文档，
  若已动则等其收尾后再同步这两处，避免合并冲突（review01 可选 1）。
- 回填 todo；主文档 `docs/2026-07-26-current-goal-detection-pipeline.md` §2
  脚本链一句补注（筐检测并入主检测缓存）；`AGENTS.md` 检测流水线一句同步。
- spec-reviewer 审查本目录三件套 + 实施产物，reviewNN.md 按轮次编号递增不覆盖。
- commit（只 add 本功能文件；work/diag、缓存备份不入库）。

## 依赖与顺序

Step 1 → 2 → 3 → 4 → 5 顺序执行（1 是 2 的数据前提）。每 Step 一个 commit 单元。

## 验收关口

- [ ] ruff format / check --fix / pytest -q 全绿（含 mot_cache 消费方测试回归）
- [ ] spec 成功标准 1-4 逐条过；标准 5 记录观察值
- [ ] spec-reviewer 审查通过，reviewNN.md 落盘（编号递增）
