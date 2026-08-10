# todo：跑批提效（缩略图墙扫尾 + 一键跑批）

依据 `docs/batch-speedup/spec.md` / `plan.md`。

## Task 1：帧号映射公共函数（plan Step 0）

**Description：** `pipe_common.py` 加 `sec_to_frame_idx(sec, fps)`，显式传 fps
（避免 pipe_common ↔ mot_candidates 循环导入），docstring 注明与
parse_sec 互逆、f_00001 ↔ t=0。

**Acceptance criteria：**
- [x] 0s→1、6.1s→31、负值/越界行为有定义（钳位到 ≥1）
- [x] `tests/test_pipe_common.py` 新增映射用例全过

**Verification：** `pytest tests/test_pipe_common.py -q` 全绿
**Dependencies：** None
**Files：** `scripts/pipe_common.py`、`tests/test_pipe_common.py`
**Scope：** XS

## Task 2：F1 缩略图生成（plan Step 1）

**Description：** `gen_triage_page.py` 前半：events_index → 3 帧号
（±2 钳位）→ PIL 480px 缩略图 → `<review_dir>/thumbs/`；残次事件与
缺帧降级均 WARNING + 结尾汇总。

**Acceptance criteria：**
- [x] 帧号钳位 [1, 帧数]；缺帧降级不崩且有 WARNING
- [x] key 文件名安全化（`#`/`@` 等）
- [x] 批次 3 回放：234 事件全产，降级清单零意外（51 球 3 帧全到位或合法降级）

**Verification：** 单测全过 + 批次 3 实跑产物核对
**Dependencies：** Task 1
**Files：** `scripts/gen_triage_page.py`、`tests/test_gen_triage_page.py`
**Scope：** M

## Task 3：F1 triage.html + localStorage 联动（plan Step 2）

**Description：** 网格墙页面：3 帧横排卡片 + 事件信息 + 组标签；硬规定
落实（只能否 / 已标禁用 F / 合并写 / 不写位置键）。

**Acceptance criteria：**
- [x] raw string 模板；注入 grp 字段（复用 assign_same_rally_groups）
- [x] 已标事件 F 按钮禁用且展示既有标注（渲染读 localStorage 实时值）
- [x] save 合并写复刻；页面代码不含 POSKEY 写
- [x] 回归断言 + `node --check` 通过
- [ ] 联动实测：墙标 F → label.html 侧已标并跳过（立哥实操）

**Verification：** pytest + node --check + 立哥验收
**Dependencies：** Task 2
**Files：** `scripts/gen_triage_page.py`、`tests/test_gen_triage_page.py`
**Scope：** M

## Checkpoint：F1 完成 = 批次 3 墙可用，立哥扫尾体验验收

## Task 4：F2 run_session.py 编排器（plan Step 3）

**Description：** 阶段 ①-⑦ 编排：ffprobe 探测 + session_facts.json 落盘比对、
extract_frames（如实标注"全场抽 + 幂等跳过"，不假装按批抽）、
mot_candidates（显式 fid）、pilot_candidates（显式 --out +
fid 覆盖核对）、detect_hoops、gen_review_clips（含 --keep-clips +
--orig 注入）、双页面生成（显式 --index/--session）；切批/续跑/--force/
--dry-run/日志。**设计点：扫描探测与命令清单构建拆成两个函数**
（dry-run 单测可 monkeypatch 探测结果，tmp_path 空文件必然探测失败）。

**Acceptance criteria：**
- [x] 切批：fid 文件名排序、--batch-size 默认 50、K 从 1 递增
- [x] --fids → adhoc 固定命名，不占批次序号
- [x] 产物校验器：好 JSON 跳过 / 截断重算或终止；facts 篡改 → WARNING 终止
- [x] 混合分辨率/帧率 → WARNING 列明细并终止（spec 阶段①）
- [x] 单文件失败记 WARNING 继续，结尾汇总失败清单并非零退出（鲁棒条）
- [x] dry-run/日志如实标注 ② 为"全场抽 + 幂等跳过"
- [x] dry-run 命令含全部显式参数与 --keep-clips
- [x] 单测：切分、校验器、facts 比对、dry-run 清单（探测可注入）

**Verification：** `pytest tests/test_run_session.py -q` 全绿
**Dependencies：** Task 1（映射函数复用无依赖，但同会话顺序做）
**Files：** `scripts/run_session.py`、`tests/test_run_session.py`
**Scope：** L（编排 + 校验，注意规则：不改老脚本）

## Task 5：端到端验证（plan Step 4）

**Description：** spec 成功标准 F2 1-4 实跑。

**Acceptance criteria：**
- [x] dry-run 对 20260722 出 6 批 × 7 阶段清单，人工对照历史命令等价
- [x] 续跑断言：缓存齐单批 ②③ < 30s（日志时间戳）
- [x] --fids 3 dji 小样本端到端出 adhoc 全套
- [x] 故障注入两项（facts 篡改 / candidates 截断）行为正确

**Verification：** 上述全过
**Dependencies：** Task 4
**Files：** 无新增（work/ 下验证产物）
**Scope：** S

## Task 6：收尾

**Description：** 文档与提交。

**Acceptance criteria：**
- [x] todo 回填；spec-reviewer 实施复审写 review04.md（review03.md 为 plan/todo 第 3 轮）
- [ ] 立哥验收：批次 3 墙扫尾 + dry-run 命令等价性
- [x] commit（只 add 本功能文件）

**Verification：** 关口全绿
**Dependencies：** Task 3、5
**Scope：** XS
