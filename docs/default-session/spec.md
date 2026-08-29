# Spec: CLI 默认场次（--session 可省略）

## 背景与目标

立哥每次只开干一个场次，但 `video score/people/build/photo` 四个子命令的 `--session`
全是必填，每条命令都要重复敲场次 ID，繁琐。

目标：`--session` 全面改为可省略——

- `score` 省略时场次 ID 默认取素材目录 basename（现有约定已天然成立：
  `20260822_citymonkey/` 素材目录 ↔ `work/20260822_citymonkey/` 场次目录）；
- `score` 成功后把场次写入"当前场次"指针文件；
- `people/build/photo` 省略时读指针；指针缺失显式报错（不猜场次，鲁棒优先）；
- 显式 `--session` 永远优先，行为与现状完全一致。

用户：立哥（唯一操作者）。成功 = 日常四条命令都可以不带 `--session` 跑通。

## 技术方案要点

- 指针文件：`work/current_session.json`，内容
  `{"version": 1, "session": "<场次ID>", "updated_at": "<ISO>", "source": "score"}`，
  `atomic_write_json` 原子写（沿用 pipe_common 既有设施）。
- **写入时机**：仅 `_cmd_score` 成功后（dry-run 不写，与 state 口径一致）；
  显式 `--session` 跑 score 同样写指针（score 即"开干新场次"的声明动作）。
  people/build/photo 不写指针（显式 --session 只是临时覆盖，不搬当前场次）。
- **读取解析顺序**（people/build/photo）：显式 `--session` → 指针文件 → 报错
  （退出 1，提示"先跑 score 或显式给 --session"）。
- **指针异常**：文件缺失 → 上述报错；JSON 损坏 → SchemaError；version 不符 /
  session 字段非非空 str → BasketballPipelineError 显式失败（损坏不静默，
  rules.md §0.2）。
- **score 缺省场次**：`Path(srcdir).resolve().name`；basename 为空（如盘符根）
  显式失败（不猜；`.`/`..` 经 resolve 取实目录名，属正常使用）。
- **clean 交互**：`work/current_session.json` 在 `work/` 根下，`clean` 的
  iterdir 清扫天然覆盖（文件走 unlink 分支），无需特判；清完指针即失效，
  与"恢复全新工作区"语义一致。
- argparse 改动：四个子命令 `--session` 由 `required=True` 改可选，解析收拢到
  一个新 helper（如 `resolve_session(args) -> str`），各 `_cmd_*` 入口先解析再用。
- 只改 `scripts/video.py` 薄封装层；底层脚本（run_session / build_highlight 等）
  照常收 session，由 CLI 补全后透传，零行为变更。

## Commands

- Lint/format: `ruff format scripts tests && ruff check --fix scripts tests`
- Test: `pytest -q`
- 典型调用（改后）：
  - `video score 20260822_citymonkey`（场次 = 目录名，成功后记指针）
  - `video people` / `video build --all` / `video photo`（读指针）
  - `video build --session 20260722 --all`（显式覆盖，照旧）

## 项目结构

- 改动：`scripts/video.py`（argparse + resolve_session + score 写指针）
- 测试：`tests/test_video.py`（追加用例，不动既有断言）
- 文档：`docs/default-session/`（四件套）；`使用手册.html` 同步（AGENTS.md 强制：
  CLI 行为变更时同步更新）；`AGENTS.md` video-cli 行尾补一句默认场次口径

## 代码风格

遵守根目录 `rules.md`（鲁棒优先 ＞ 性能 ＞ 简洁）；Ruff 为唯一权威；
与 video.py 现有风格一致（类型注解、docstring 写明 Raises、中文注释）。

## 测试策略

pytest，`tests/test_video.py` 追加：

- score 省略 --session → 透传 run_session 的场次 = srcdir basename；
- score 成功后指针文件写入正确（dry-run 不写）；
- people/build/photo 省略 --session → 读指针；显式 --session 优先于指针；
- 指针缺失 → 退出 1 且错误信息含引导；指针损坏/version 不符 → SchemaError；
- srcdir basename 非法（`.`）→ 显式失败。

## 边界

- Always：显式 `--session` 语义零变更；底层脚本零改动；测试先行补失败用例
- Ask first：无（不加依赖、不动 CI、不动底层脚本接口）
- Never：不猜场次（指针缺失/多义必须报错）；不静默吞指针损坏；不改素材文件

## 成功标准

1. `video score <素材目录>`（不带 --session）等价于 `--session <目录basename>`，
   成功后指针落盘；
2. `video people` / `video build` / `video photo` 不带 --session 跑通（读指针）；
3. 指针缺失时报错退出 1，信息引导先跑 score 或显式 --session；
4. 显式 --session 路径与现状逐字一致（既有测试不红）；
5. `ruff format && ruff check --fix && pytest -q` 全绿。

## Open Questions

无（两个决策点已确认：指针方案 = score 记指针；score 缺省 = 素材目录 basename）。
