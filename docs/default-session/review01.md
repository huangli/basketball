# default-session（CLI 默认场次）— review01（实现+文档一致性）

> 审查对象：docs/default-session/spec.md、plan.md、todo.md；实现 scripts/video.py、
> tests/test_video.py；同步文档 使用手册.html、AGENTS.md。
> 审查者：spec-reviewer 子代理。2026-08-29。审查时改动未 commit（工作区 diff 审查）。

## 审查范围与方法

- 逐行读 scripts/video.py 全部新增/改动函数（save/load_current_session、resolve_session、
  _resolve_score_session、四个 _cmd_* 入口、_build_parser、_cmd_clean、
  _collect_srcdir_targets、discover_batches）；
- 逐行读 tests/test_video.py 新增 TestDefaultSession（13 用例）；
- `git diff` 核对 tests/test_video.py、AGENTS.md、使用手册.html 全部改动行；
- 实跑质量关口复核实现方"全绿"声明（见末节核验记录）。

## 逐项结论

### 1. spec 成功标准 5 条 —— 全部通过

| # | 成功标准 | 结论 | 证据 |
|---|---------|------|------|
| 1 | score 不带 --session 等价于 basename，成功后指针落盘 | 通过 | video.py:260-273 `_resolve_score_session` 取 `Path(srcdir).resolve().name`；:673 成功后 `save_current_session`（dry-run :658-659 提前 return 不写）。测试 test_score_default_session_basename / test_score_writes_pointer / test_score_explicit_session_also_writes_pointer / test_score_dry_run_no_pointer 覆盖 |
| 2 | people/build/photo 不带 --session 跑通（读指针） | 通过 | 三入口第一行 `args.session = resolve_session(args)`（:688/:854/:1256）。测试 test_people_reads_pointer / test_build_reads_pointer / test_photo_apply_reads_pointer 覆盖 |
| 3 | 指针缺失报错退出 1，信息引导先跑 score 或显式 --session | 通过 | video.py:235-237 报错语含"先跑 score 或显式给 --session"，main 捕获 BasketballPipelineError 转退出 1；test_missing_pointer_exit1 断言 rc==1 且无子进程发出 |
| 4 | 显式 --session 路径与现状逐字一致（既有测试不红） | 通过 | `git diff tests/test_video.py` 删除行为零（仅 `---` 头），纯追加 TestDefaultSession；全量 pytest 实跑全绿。显式路径 `_resolve_score_session`/`resolve_session` 均原样返回 args.session，零行为变更 |
| 5 | ruff format && ruff check --fix && pytest -q 全绿 | 通过 | 本代理实跑复核（末节） |

测试覆盖度补充核对：spec 测试策略 5 类用例全部落地——basename 透传 ✓、指针写入/dry-run 不写 ✓、
三命令读指针+显式优先 ✓、缺失引导 ✓、损坏/version 不符/session 空 ✓（test_corrupt/bad_version/
empty_session_pointer_exit1）、根路径空 basename ✓（test_score_root_srcdir_empty_name，断言
run_recorder 为空即未发出子进程）。13 用例与声称数量一致。

### 2. 文档与代码一致性 —— 通过（1 处措辞建议）

逐项核对：

- 指针文件名 `current_session.json`：代码常量 :53 与手册 :85/:102/:242、AGENTS.md 一致 ✓
- 路径 `work/current_session.json`（work 根下，非场次目录内）：代码 :212/`WORK_ROOT / CURRENT_SESSION_NAME` 与文档一致 ✓
- score 缺省取素材目录 basename：手册 :102、AGENTS.md、argparse help :1461 一致 ✓
- 显式 --session 不改写指针：手册 :85"不会改动当前场次记录"；代码仅 `_cmd_score` 调
  save_current_session，people/build/photo 无写指针路径；test_explicit_session_overrides_pointer
  断言 people 显式跑后指针仍为 "other" ✓
- clean 会清掉指针：手册 FAQ :242 明说；代码 `_cmd_clean` 对 work/ iterdir 逐项，
  文件走 unlink 分支（:1436-1439）✓
- dry-run 不写指针：代码 :658-659 提前 return；测试覆盖 ✓（文档未单独强调，见建议 S3）

**AGENTS.md 措辞问题（建议 S1）**：新增句"显式 `--session` 永远优先且不改写指针"按字面读
覆盖全部四命令，但实现口径是 **score 显式 --session 同样写指针**（spec 技术方案明写"score 即
开干新场次的声明动作"，测试 test_score_explicit_session_also_writes_pointer 锁定此行为）。
"不改写"仅适用于 people/build/photo。建议改为"显式 `--session` 永远优先（score 显式同样记指针；
people/build/photo 显式只是临时覆盖，不改写指针）"。不阻断：核心口径（缺省行为、优先序、报错
不猜）均准确，且 spec/代码/测试三处对 score 显式写指针一致，仅是 AGENTS.md 单句概括失真。

### 3. 风险点复核 —— 全部通过

- **指针被 `_collect_srcdir_targets` 误扫**：不命中。video.py:1364 glob 模式
  `*/video_cli.json` 要求一层子目录，`work/current_session.json` 在 work 根下不匹配 ✓
- **指针被 `discover_batches` 误扫**：不命中。video.py:330 只扫传入的 session_dir 内
  `goals*.json`，指针不在任何场次目录内、文件名也不以 goals 开头 ✓
- **`_cmd_clean` 清指针**：走通。work/ iterdir 含文件项；统计分支
  `_dir_stats(p) if p.is_dir() else (p.stat().st_size, 1)`（:1411）对文件取 stat；
  删除分支 `p.is_dir() and not p.is_symlink()` 为假 → `p.unlink()`（:1436-1439）✓
  （既有 TestClean 已覆盖 work 下文件删除路径，本次实跑全绿）
- **既有测试零改动**：`git diff tests/test_video.py` 无任何有效删除行，纯追加 211 行
  TestDefaultSession ✓

### 4. 四件套完整性 —— 通过（todo 勾选待收尾）

- docs/default-session/ 下 spec.md / plan.md / todo.md 齐全，本 review01.md 补齐第四件 ✓
- plan.md 与实现逐条一致（常量名、写入时机、异常类型、解析顺序、TDD 顺序）✓
- spec.md 两处措辞滞后于 plan/实现（建议 S2，见下）；成功标准本身全部达成，不影响通过
- **todo.md 全部 6 项仍是 `[ ]` 未勾选**，而 1-4 实际已完成、5 以本 review 收尾、6 待 commit。
  需在交付前按实际勾选（这是流程要求，非代码问题）

**spec.md 与实现的两处口径差（建议 S2）**：
a) spec §指针异常写"version 不符 / session 字段非非空 str → **SchemaError**"，实现抛的是
**BasketballPipelineError**（video.py:239-245），仅 JSON 损坏由 read_json 抛 SchemaError。
plan.md 口径与实现一致。行为层面无差异（SchemaError 是 BasketballPipelineError 子类，
main 统一捕获转退出 1，测试也只断言 rc==1），建议回改 spec 一句以 plan/实现为准；
b) spec §score 缺省写"basename 为空或 `.`/`..` 显式失败"，实现对 `.`/`..` 经 resolve 后取
的是启动目录/父目录名（非空，不失败），plan 已收窄为"根路径 basename 为空"并有测试锁定。
实际 `.` 解析为启动目录名语义合理，建议 spec 改述为"basename 为空（如盘符根）显式失败"。

### 5. AGENTS.md 同步 —— 通过（措辞见 S1）

改动位置正确（统一入口 CLI 行内追加）、要素齐全（日期、四命令可省、basename 缺省、指针路径、
优先序、报错不猜、四件套指引），符合"CLI 行为变更时同步更新"约定。仅 S1 那句"不改写指针"
的适用范围表述需收窄。模块 docstring（video.py:15-18 典型调用段）同步准确 ✓。

## 阻断问题

无。

## 建议

- S1（AGENTS.md 措辞）："显式 --session 永远优先且不改写指针"改为标明 score 显式同样记指针、
  不改写仅限 people/build/photo（依据：video.py:673 + test_score_explicit_session_also_writes_pointer）。
- S2（spec.md 回改两句）：a) 指针异常类型以 plan/实现为准（version 不符/session 空 →
  BasketballPipelineError，仅 JSON 损坏 → SchemaError）；b) score 缺省失败条件改述为
  "basename 为空（如盘符根）显式失败"，去掉 `.`/`..`（实现经 resolve 取实目录名）。
- S3（手册可选补强）：速查表 score 行 `--dry-run` 备注现写"只打印"，可顺手补"（不写 state/
  不记当前场次）"，与 argparse help :1466 口径对齐。
- S4（收尾流程）：todo.md 按实际勾选 1-5，6 在 commit 后勾；本 review 归档后按
  AGENTS.md 自动提交约定分逻辑 commit（只 commit 不 push）。

## 核验记录（本代理实跑）

- `python -m pytest -q`：全绿（100%，0 失败）✓
- `python -m ruff format --check scripts tests`：54 files already formatted ✓
- `python -m ruff check scripts tests`：All checks passed ✓
- `git diff tests/test_video.py`：仅追加，零删除行 ✓
- TestDefaultSession 用例数：13，与声称一致 ✓

## 最终结论

**通过**（建议 S1/S2 为文档措辞收尾，不阻断；可随 todo 勾选与 commit 一并处理）。
