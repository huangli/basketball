# todo：筐检测消重（mot 缓存直存 Hoop 类，detect_hoops 免重复推理）

依据 `docs/detect-hoops-cache/spec.md` / `plan.md`。

## Task 1：mot_candidates 顺带存筐（plan Step 1）

**Description：** `detect_frame` 球模型 `classes=[BALL_CLS, HOOP_CLS]`（新增
HOOP_CLS=2 常量，注释与 detect_hoops 同源对齐），返回值加 hoops 列表；
`run_pipeline` 检测循环接续；`save_detection_cache` payload 加 `"hoops"` 键；
`load_detection_cache` 不校验该键（旧缓存仍命中，不触发全量重跑）。

**Acceptance criteria：**
- [ ] 新缓存含 hoops 键，条目为 {"conf","cx","cy"}，阈值口径 CONF_BALL=0.15；
      cx/cy 用 int() 截断、conf 存原始 float（复刻 detect_hoop_frame，review01 B1）
- [ ] Ball/Person 检测逻辑与缓存既有三键（frames/balls/persons）零改动
- [ ] 旧缓存（无 hoops 键）跑 mot_candidates 仍命中不重演（日志为证）

**Verification：** `ruff check scripts/mot_candidates.py` + `pytest -q` 全绿
**Dependencies：** None
**Files：** `scripts/mot_candidates.py`
**Scope：** S

## Task 2：detect_hoops 缓存优先 + 回退 + 懒加载（plan Step 2）

**Description：** 新增 `load_hoop_frames(fid)`（复用 mot.CACHE_PATTERN 与
mot.parse_sec，CONF=0.25 过滤）；事件循环逐 fid 选路：缓存命中走查表，
缺失/损坏/无 hoops 键回退逐帧 YOLO（detect_hoop_frame 原样保留）；
YOLO 模型改懒加载。track_hoop/interpolate_gaps/输出 schema 不动。

**Acceptance criteria：**
- [ ] 三分支选路各有一行日志（命中/回退原因）
- [ ] 全批缓存命中时不加载 YOLO 模型
- [ ] hoops.json 与现行 schema 同构（key/detected/track/window/anchor 字段不变）
- [ ] load_hoop_frames 元素级校验：元素损坏（缺 cx/cy、类型错）回退 None
      不半路崩

**Verification：** `ruff check scripts/detect_hoops.py` + `pytest -q` 全绿
**Dependencies：** Task 1
**Files：** `scripts/detect_hoops.py`
**Scope：** M

## Task 3：单测四用例（plan Step 3）

**Description：** tests/test_detect_hoops.py 追加：缓存命中（检测函数 0 调用 +
0.25 过滤边界 0.24/0.25/0.15）、旧缓存回退（走逐帧且产物一致）、
hoops 键损坏回退（不崩 + WARNING）、hoops 为 list 但元素损坏回退。

**Acceptance criteria：**
- [ ] 四个用例全过；现有 test_detect_hoops 用例不回归
- [ ] mot_cache 消费方测试不回归：test_crop_scorers / test_scorer_landings /
  test_release_probe / test_run_session（不改其代码，只验证）

**Verification：** `pytest tests/test_detect_hoops.py -q` 与 `pytest -q` 全绿
**Dependencies：** Task 2
**Files：** `tests/test_detect_hoops.py`
**Scope：** S

## Task 4：子集重放验证（plan Step 4，spec 成功标准 1/2/5）

**Description：** 选 ≥3 fid（detected true/false 均覆盖），备份→重建缓存→
逐 fid detect_hoops + pilot_candidates 至 work/diag/，diff 封存产物。

**Acceptance criteria：**
- [ ] hoops 轨迹 diff：key 集合、detected、track 逐点与 hoops_batch1.json 完全相等
- [ ] candidates diff：对应 fid 记录与 candidates_batch1.json 一致
- [ ] detect_hoops 缓存命中单 fid 墙钟记录（秒级），写入 review
- [ ] 验证后备份缓存恢复原位，work/diag 产物不入库

**Verification：** diff 结果为零差异 + 日志存档
**Dependencies：** Task 3
**Files：** 无新增（work/ 下验证产物）
**Scope：** S

## Checkpoint：功能完成 = diff 全零 + 关口全绿，提请审查

## Task 5：文档与收尾（plan Step 5）

**Description：** 主文档 §2 与 AGENTS.md 检测流水线各一句同步；todo 回填；
spec-reviewer 审查产出 review01.md；按逻辑单元 commit（只 add 本功能文件）。

**Acceptance criteria：**
- [ ] 文档同步两句落盘（不碰 docs/heatmap/）
- [ ] spec-reviewer 审查通过，reviewNN.md 落 docs/detect-hoops-cache/（编号递增）
- [ ] commit 完成，不 push；立哥知悉性能观察值

**Verification：** 关口全绿 + 审查意见闭环
**Dependencies：** Task 4
**Scope：** XS
