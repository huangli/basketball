# video.py 统一入口 CLI — plan

> 对应 spec.md。实现顺序按依赖：工具函数先行，子命令随后，测试与实现同写。

## Task 1：骨架与公用件（video.py 框架）

- `main()`：argparse 三级（prog → subcommand → 各自参数），无子命令时打印 help 退出 2
- 公用函数：
  - `run_step(cmd: list[str], env_extra: dict | None) -> None`：log 命令（shlex.join）→ subprocess.run → 非零抛 `StepFailedError(cmd)`；调用方捕获后打印已完步骤并 return 1
  - `load_state(session)` / `save_state(session, state)`：`work/<session>/video_cli.json`，read_json/atomic_write_json，version 校验
  - `resolve_rawdir(args_rawdir, state)`：显式优先 → state.srcdir → 都没有抛错
  - `discover_batches(session) -> list[Batch]`：扫 work/<S>/ 的 goals.json（旧布局批次 1）与 goals_batchK.json（现行布局）；配套命名从 goals 文件名推导（spec §批次发现对照表）；配套 candidates/review 缺失仅标注 WARNING，执行阶段跳过该批
  - `session_dir_or_die(session)`：work/<S>/ 不存在 → 报错退出
- run_step 统一注入 `PYTHONIOENCODING=utf-8`（子进程中文日志坑）；聚类段叠加 `HTTPS_PROXY`
- 全程 `from __future__ import annotations`、类型标注、docstring（rules.md 风格对齐现有脚本）

## Task 2：score 子命令

- 拼 `run_session.py <srcdir> --session <S> [--batch-size] [--fids] [--force] [--dry-run]`，原样透传
- exit 0 且非 dry-run → save_state（srcdir 转绝对路径，runs 追加一条）
- 单测：命令拼装逐字断言；state 写入/追加；dry-run 不写 state；srcdir 不存在由 run_session 自己报错（video.py 不重复校验，只透传）

## Task 3：people 子命令

- `confirmed_count(goals_path)`：读 goals.json 数 status=confirmed 条数（--max-reads 缺省 = 3×此数）
- 三段链按 spec 拼参，**逐批聚类**（clusters 落各批 scorers[_bK]/ 目录，满足 gen_scorer_page 同目录硬约束）；`--skip-cluster` 跳过第 2 段且第 3 段不传 --clusters
- 聚类段 env 注入 `HTTPS_PROXY=http://127.0.0.1:7897`（os.environ 复制后改，不污染父进程其他键）
- roster-existing：work/<S>/roster.json 存在才传
- 单测：三段子命令拼装（含定稿 --linkage complete --threshold 0.15、批次目录命名双轨：goals.json→scorers/ 与 goals_batchK.json→scorers_bK/）；--batch K 限定；--skip-cluster；max-reads 缺省换算；roster 存在与否两态

## Task 4：build 子命令

- `resolve_out_size(session) -> str`：读 session_facts.json，全部文件 width/height 主比例判定 → "1920x1080" / "1440x1080"；混比例/未知比例抛错并列出比例分布（16:9±1% / 4:3±1% 两档容差）
- `--all`：read_json roster + validate_roster 校验 → players 逐人 --scorer tag、teams 去重逐队 --team，顺序 run_step；roster 缺失/坏 → 报错退出 1 提示先跑 people
- --scorer/--team/--all 互斥（argparse mutually exclusive group）
- 单测：尺寸换算三态（16:9/4:3/混比例报错）；--all 展开命令序列（假 roster 两 player 两队）；互斥校验；roster 缺失报错

## Task 5：关口与文档

- `python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q` 全绿（--fix 后复核 diff）
- AGENTS.md 工作流约定「检测流水线」行末补一句统一入口指向（一行，不展开）
- 命令行 smoke：`python scripts/video.py --help`、`python scripts/video.py score --help` 人工过目

## 风险

| 风险 | 应对 |
|---|---|
| 透传参数与底层脚本漂移（底层加参数 CLI 不知道） | video.py 只封装已固化参数；底层新参数需要时再补，spec 边界已声明不追求全覆盖 |
| 批次命名假设（goals_batchK/scorers_bK）与未来场次不符 | discover_batches 只认此模式且 WARNING 降级不硬挂；新命名出现时改这一处即可 |
| gen_scorer_page 的参数名或约束（同目录/互斥）与 spec 示例出入 | Task 3 实现前先 `python scripts/gen_scorer_page.py --help` 实跑核对参数名与约束说明，不符以 --help 为准并回写 spec（已做：发现 --clusters 同目录硬约束，改逐批聚类） |
