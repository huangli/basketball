# Plan: CLI 默认场次（--session 可省略）

依据 `docs/default-session/spec.md`（已批准）。只改 `scripts/video.py` 薄封装 +
`tests/test_video.py` 追加用例；底层脚本零改动。

## 组件与依赖

1. **指针读写**（无依赖，先做）
   - 常量：`CURRENT_SESSION_NAME = "current_session.json"`、
     `CURRENT_SESSION_VERSION = 1`。
   - `save_current_session(session)`：`WORK_ROOT / CURRENT_SESSION_NAME`，
     `atomic_write_json`；写前 `WORK_ROOT.mkdir(parents=True, exist_ok=True)`；
     内容 `{"version":1,"session":...,"updated_at":...,"source":"score"}`。
   - `load_current_session() -> str`：缺失 → `BasketballPipelineError`（引导语）；
     损坏 → `read_json` 抛 `SchemaError`；version 不符 / session 非非空 str →
     `BasketballPipelineError`。
2. **解析入口**（依赖 1）
   - `resolve_session(args) -> str`：显式 `--session` 优先，否则 `load_current_session()`。
     people/build/photo 三个 `_cmd_*` 入口第一行解析，函数体内 `args.session`
     全部换局部 `session`。
   - `_resolve_score_session(args) -> str`：显式优先；否则
     `Path(args.srcdir).resolve().name`，空串显式失败。
3. **argparse**（依赖 2）：四个子命令 `--session` 去掉 `required=True`，
   help 文案补缺省口径。
4. **score 写指针**（依赖 1、2）：`_cmd_score` 成功且非 dry-run 时，
   在 `save_state` 后追加 `save_current_session(session)`。

## 实施顺序（TDD）

1. `tests/test_video.py` 追加 `TestDefaultSession` 用例（先红）：
   - score 省略 → 透传场次 = srcdir basename；成功后写指针；dry-run 不写；
     显式 --session 也写指针；srcdir 根目录（name 为空）→ 退出 1。
   - people/build/photo 省略 → 读指针（命令正常发出）；显式优先于指针；
     指针缺失 → 退出 1 且信息含引导；损坏 / version 不符 → 退出 1。
2. 实现 video.py 上述 4 组件至全绿。
3. `ruff format scripts tests && ruff check --fix scripts tests && pytest -q`。
4. 文档同步：`使用手册.html`（命令示例去 --session、补默认场次说明）、
   `AGENTS.md` video-cli 行补默认场次口径。
5. 文档自审（spec-reviewer 子代理）+ `review01.md` 存档；分逻辑 commit。

## 风险与缓解

- **既有测试全用显式 --session** → 显式路径逐字不动，既有断言应零改动全绿；
  若红说明误伤，回查 diff。
- **指针文件被误扫** → 已核：`_collect_srcdir_targets` 只 glob
  `work/*/video_cli.json`（需子目录），`discover_batches` 只扫场次目录内
  `goals*.json`，`work/current_session.json` 不命中；clean 的 iterdir 走
  unlink 分支天然覆盖（无需特判，在 review 中复核）。
- **Windows 根路径 basename 为空** → `Path("/").resolve().name == ""` 显式失败，
  测试覆盖。

## 验证检查点

- 每组件实现后跑 `pytest tests/test_video.py -q`；
- 收尾全量 `pytest -q` + ruff 双命令；
- review 存档 + commit 前复核 `git diff` 只含预期文件。
