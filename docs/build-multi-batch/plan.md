# video build 多批次修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `video build` 多批次合并合成 + --all 零命中跳过；spec = `docs/build-multi-batch/spec.md`（唯一契约）。

**Architecture:** 只改编排层 `scripts/video.py`：多批次时合并 goals 到 `goals_merged_cli.json` 后每 filter 调一次 build_highlight；--all 展开前用 confirmed 键集预检零命中。build_highlight/roster.py 零改动。

**Tech Stack:** Python 3.14，pytest（run_recorder 拦截 subprocess 既有模式）。

## Global Constraints

- 提交信息中文 conventional；只 commit 不 push；git add 点名文件（**有并行会话在同 repo 工作**，严禁 `git add -A`/`.`）
- 质量门（提交前）：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py` 全绿
- 单批（选中批次 ==1）与显式 --scorer/--team/无过滤的行为逐字不变
- 合并文件原子写（pipe_common.atomic_write_json）；素材/goals 只读；不动 output/
- video.py 现有导入已有 `atomic_write_json, read_json`（pipe_common）、`validate_roster`（roster）、`BasketballPipelineError`（errors）；需新增 `SchemaError`（errors）与 `format_key`（roster）

---

### Task 1: 合并合成 + 零命中跳过

**Files:**
- Modify: `scripts/video.py`（新增 MERGED_GOALS_NAME/_confirmed_keys/_merge_goals_for_build；改 _build_expand_all 签名加 known_keys；改 _cmd_build 循环结构）
- Test: `tests/test_video.py`（_goals_payload 补 anchor_time；4 个既有测试补 assignments；新增 4 个测试）

**Interfaces:**
- Consumes: `Batch`（.batch/.goals）、`run_step`、`Step`、`_select_batches`/`discover_batches`、`validate_roster` 返回 Roster（.players/.assignments）、roster.format_key（`<file>#<t:.1f>`）
- Produces: `MERGED_GOALS_NAME = "goals_merged_cli.json"`；`_confirmed_keys(goals_path: Path) -> set[str]`；`_merge_goals_for_build(batches: list[Batch], session: str, session_dir: Path) -> Path`；`_build_expand_all(session_dir: Path, known_keys: set[str]) -> list[tuple[str, str]]`

- [ ] **Step 1: 写失败测试**

tests/test_video.py 修改与新增：

T1 — `_goals_payload` 补 anchor_time（既有调用方不受影响，命中预算需要该字段）：

```python
def _goals_payload(n_confirmed: int = 2) -> dict[str, Any]:
    """构造 goals.json 内容：n 条 confirmed + 1 条 rejected（不计数）。"""
    goals = [
        {"status": "confirmed", "file": f"f{i}.mp4", "anchor_time": float(i) + 0.5}
        for i in range(n_confirmed)
    ]
    goals.append({"status": "rejected", "file": "fx.mp4", "anchor_time": 99.0})
    return {"goals": goals}
```

T2 — 4 个既有 build 测试的 roster 夹具补 assignments（与 goals 键对齐，用 roster.format_key 现算）。在文件顶部 import 区加 `from roster import format_key`，`_setup` 的 roster 夹具改为：

```python
        if roster:
            _write_json(
                session_dir / "roster.json",
                {
                    "players": [
                        {"tag": "红-7", "name": "大斌", "team": "半截篮"},
                        {"tag": "黑-A", "name": "", "team": "地平线"},
                        {"tag": "黑-B", "name": "", "team": "地平线"},
                    ],
                    "assignments": {
                        format_key("f0.mp4", 0.5): "红-7",
                        format_key("f1.mp4", 1.5): "黑-A",
                    },
                },
            )
```

（黑-B 故意无归属——用于零命中跳过断言；`test_all_expands_players_and_teams`
的 5 条命令预期改为 4 条：`--scorer 红-7`、`--scorer 黑-A`、`--team 半截篮`、
`--team 地平线`——黑-B 零命中跳过，两队均有人命中照常出；`test_all_skips_casual_team` 的 roster 是另写的，
给 红-7 补 `format_key("f0.mp4", 0.5): "红-7"` assignments，便-X 无归属被跳过，
预期命令变为 `--scorer 红-7` + `--team 半截篮` 2 条；`test_nonzero_stops_exit1`
与 `test_dry_run_executes_nothing` 用 `_setup(roster=True)` 自动继承新夹具，
前者 fail_at=1 仍命中第二条命令、后者 rc==0 不变）

T3 — 新增测试类（追加在 TestBuild 末尾）：

```python
class TestBuildMultiBatch:
    """多批次合并合成 + --all 零命中跳过（docs/build-multi-batch/spec.md）。"""

    def _setup_two_batches(self, session_dir: pathlib.Path) -> pathlib.Path:
        _write_json(session_dir / "goals_batch1.json", _goals_payload())
        _write_json(session_dir / "goals_batch2.json", _goals_payload())
        _write_json(session_dir / "candidates_batch1.json", [])
        _write_json(session_dir / "candidates_batch2.json", [])
        _write_json(session_dir / "session_facts.json", _facts_payload())
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        return rawdir

    def _roster_full_hits(self, session_dir: pathlib.Path) -> None:
        _write_json(
            session_dir / "roster.json",
            {
                "players": [
                    {"tag": "红-7", "name": "", "team": "半截篮"},
                    {"tag": "黑-A", "name": "", "team": "地平线"},
                ],
                "assignments": {
                    format_key("f0.mp4", 0.5): "红-7",
                    format_key("f1.mp4", 1.5): "黑-A",
                },
            },
        )

    def test_multi_batch_merges_goals_and_single_call_per_filter(
        self, session_dir: pathlib.Path, run_recorder: list
    ) -> None:
        # Arrange
        rawdir = self._setup_two_batches(session_dir)
        self._roster_full_hits(session_dir)
        # Act
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        # Assert：2 球员 + 2 队 = 4 条命令，每 filter 只调一次，--goals 指向合并文件
        assert rc == 0
        assert len(run_recorder) == 4
        for cmd, _env in run_recorder:
            assert str(REL / "goals_merged_cli.json") in cmd
        # 合并文件已写盘：两批各 2 confirmed+1 rejected 逐字拼接 + session 字段
        merged = json.loads((session_dir / "goals_merged_cli.json").read_text("utf-8"))
        assert merged["session"] == SESSION
        assert len(merged["goals"]) == 6

    def test_all_skips_zero_hit_players_and_teams(
        self,
        session_dir: pathlib.Path,
        run_recorder: list,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Arrange：黑-A 有归属但不在 confirmed 键集（键对不上）→ 零命中
        rawdir = self._setup_two_batches(session_dir)
        _write_json(
            session_dir / "roster.json",
            {
                "players": [
                    {"tag": "红-7", "name": "", "team": "半截篮"},
                    {"tag": "黑-A", "name": "", "team": "地平线"},
                ],
                "assignments": {
                    format_key("f0.mp4", 0.5): "红-7",
                    "ghost.mp4#9.9": "黑-A",
                },
            },
        )
        caplog.set_level(logging.WARNING)
        # Act
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        # Assert：只出 红-7 + 半截篮；黑-A 与 地平线 零命中跳过（WARNING）
        assert rc == 0
        tail = [c[0][-2:] for c in run_recorder]
        assert tail == [["--scorer", "红-7"], ["--team", "半截篮"]]
        assert "零命中" in caplog.text

    def test_all_zero_hits_exit1(
        self, session_dir: pathlib.Path, run_recorder: list
    ) -> None:
        # Arrange：assignments 全对不上 confirmed 键
        rawdir = self._setup_two_batches(session_dir)
        _write_json(
            session_dir / "roster.json",
            {
                "players": [{"tag": "红-7", "name": "", "team": "半截篮"}],
                "assignments": {"ghost.mp4#9.9": "红-7"},
            },
        )
        # Act
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        # Assert：全零命中 → exit 1 且无子进程
        assert rc == 1
        assert run_recorder == []

    def test_dry_run_does_not_write_merged_file(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        rawdir = self._setup_two_batches(session_dir)
        self._roster_full_hits(session_dir)

        def forbidden(*a: object, **kw: object) -> None:
            raise AssertionError("dry-run 不得启动子进程")

        monkeypatch.setattr(video.subprocess, "run", forbidden)
        # Act
        rc = video.main(
            ["build", "--session", SESSION, "--rawdir", str(rawdir), "--all", "--dry-run"]
        )
        # Assert
        assert rc == 0
        assert not (session_dir / "goals_merged_cli.json").exists()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_video.py -q
```

Expected: 新类 4 条 FAIL + `test_all_expands_players_and_teams` /
`test_all_skips_casual_team` 2 条 FAIL（行为变更）。注意
`test_nonzero_stops_exit1` 与 `test_dry_run_executes_nothing` 只是夹具对齐，
在旧代码下仍 PASS——属预期，不是出错信号

- [ ] **Step 3: 实现 video.py 改动**

E1 — 导入行，把：

```python
from errors import BasketballPipelineError
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json
from roster import validate_roster
```

改为：

```python
from errors import BasketballPipelineError, SchemaError
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json
from roster import format_key, validate_roster
```

E2 — 模块常量区（CASUAL_TEAM 附近）加：

```python
# 多批次 build 的合并 goals 中间产物（work/<场次>/ 下，每次 build 重写——素材流动）
MERGED_GOALS_NAME: str = "goals_merged_cli.json"
```

E3 — `_build_expand_all` 前插入两个新函数：

```python
def _confirmed_keys(goals_path: Path) -> set[str]:
    """读 goals 文件，返回 confirmed 记录的 format_key 集合（--all 命中预算用）。

    缺 file/anchor_time 的坏记录跳过——结构校验是 build_highlight 的职责，
    此处只预算命中，不提前炸。

    Args:
        goals_path: goals_batchK.json 路径。

    Returns:
        confirmed 记录的 format_key 集合。
    """
    data: Any = read_json(goals_path, what=f"goals 命中预算 {goals_path.name}")
    goals: Any = data.get("goals") if isinstance(data, dict) else None
    keys: set[str] = set()
    for g in goals if isinstance(goals, list) else []:
        if not isinstance(g, dict) or g.get("status") != "confirmed":
            continue
        try:
            keys.add(format_key(g["file"], g["anchor_time"]))
        except (KeyError, TypeError, ValueError):
            # 缺键/类型坏（str anchor_time 走 f"{t:.1f}" 抛 ValueError）都跳过——
            # 结构校验是 build_highlight 的职责，此处只预算命中
            continue
    return keys


def _merge_goals_for_build(batches: list[Batch], session: str, session_dir: Path) -> Path:
    """多批次合并 goals：全记录逐字拼接，原子写 work/<场次>/goals_merged_cli.json。

    不过滤不校验（confirmed 过滤与结构校验是 build_highlight 的单一职责点）。
    每次 build 重写（素材流动，goals 会变）。

    Args:
        batches: 选定批次列表。
        session: 场次 ID（写入合并文件顶层 session 字段，build_highlight 据此定输出目录）。
        session_dir: work/<场次> 目录。

    Returns:
        合并文件路径。

    Raises:
        SchemaError: 某批 goals 顶层缺 goals 列表（结构损坏显式失败）。
    """
    merged: list[Any] = []
    for batch in batches:
        data: Any = read_json(batch.goals, what=f"批次{batch.batch} goals")
        goals: Any = data.get("goals") if isinstance(data, dict) else None
        if not isinstance(goals, list):
            raise SchemaError(f"{batch.goals}: 缺 goals 列表或类型错误")
        merged.extend(goals)
    out: Path = session_dir / MERGED_GOALS_NAME
    atomic_write_json(out, {"session": session, "goals": merged}, what="合并 goals")
    return out
```

E4 — `_build_expand_all` 整体替换为（签名加 known_keys；零命中跳过）：

```python
def _build_expand_all(session_dir: Path, known_keys: set[str]) -> list[tuple[str, str]]:
    """--all 展开：roster 逐人 --scorer tag + 逐队 --team（team 按出现序去重）。

    零命中跳过：球员/队伍在选定批次 confirmed 键集（known_keys）内无归属球 →
    WARNING 跳过不调用（build_highlight 对零记录 exit 1，--all 遍历不能让
    单点空组合中止整轮；2026-08-15 立哥实测黑后卫零球批次中止事故）。
    便服队不入分队合集（build_highlight 拒收），跳过并记 WARNING；
    便服球员个人合集有命中才出。

    Args:
        session_dir: work/<场次> 目录。
        known_keys: 选定批次 confirmed 球的 format_key 集合。

    Returns:
        (旗标, 值) 列表，旗标为 "--scorer" 或 "--team"。

    Raises:
        BasketballPipelineError: roster 不存在（提示先跑 people）。
        SchemaError: roster schema 损坏（validate_roster 抛出，不静默）。
    """
    roster_path: Path = session_dir / "roster.json"
    if not roster_path.is_file():
        raise BasketballPipelineError(f"roster 不存在: {roster_path}（先跑 people 确认导出）")
    roster = validate_roster(read_json(roster_path, what="roster.json"), str(roster_path))
    tag_keys: dict[str, set[str]] = {}
    for key, tag in roster.assignments.items():
        tag_keys.setdefault(tag, set()).add(key)
    hit_tags: set[str] = {t for t, ks in tag_keys.items() if ks & known_keys}
    pairs: list[tuple[str, str]] = []
    for p in roster.players:
        if p.tag not in hit_tags:
            logger.warning("--all 跳过零命中球员: %s（选定批次内无归属球）", p.tag)
            continue
        pairs.append(("--scorer", p.tag))
    teams: list[str] = []
    casual_skipped: bool = False
    warned_teams: set[str] = set()  # 零命中队伍只 WARNING 一次（不进 teams 去重失效）
    for p in roster.players:
        if p.team == CASUAL_TEAM:
            casual_skipped = True
            continue
        if not p.team or p.team in teams or p.team in warned_teams:
            continue
        if any(q.team == p.team and q.tag in hit_tags for q in roster.players):
            teams.append(p.team)
        else:
            warned_teams.add(p.team)
            logger.warning("--all 跳过零命中队伍: %s（选定批次内无归属球）", p.team)
    if casual_skipped:
        logger.warning("--all 跳过便服分队合集（build_highlight 拒收；便服球员个人合集照常出）")
    pairs.extend(("--team", t) for t in teams)
    return pairs
```

E5 — `_cmd_build` 的 filters 段与循环段，把：

```python
    if args.all:
        filters = _build_expand_all(session_dir)
        if not filters:
            raise BasketballPipelineError(f"roster players 为空，--all 无合集可出: {session_dir}")
```

改为：

```python
    if args.all:
        known_keys: set[str] = set()
        for batch in batches:
            known_keys |= _confirmed_keys(batch.goals)
        filters = _build_expand_all(session_dir, known_keys)
        if not filters:
            raise BasketballPipelineError(
                f"--all 无合集可出（roster players 为空或选定批次内均无归属球）: {session_dir}"
            )
```

再把循环段：

```python
    roster_path: Path = session_dir / "roster.json"
    completed: list[str] = []
    dry_count: int = 0
    try:
        for batch in batches:
            base: list[str] = [
                sys.executable,
                str(SCRIPT_DIR / "build_highlight.py"),
                "--goals",
                str(batch.goals),
            ]
            if roster_path.is_file():
                base.extend(["--roster", str(roster_path)])
            base.extend(["--rawdir", str(rawdir), "--out", out_size])
            for flag, value in filters:
                cmd: list[str] = [*base, flag, value] if flag else list(base)
                title: str = (
                    f"批次{batch.batch} 合成{(' ' + flag + ' ' + value) if flag else '（全员）'}"
                )
                if args.dry_run:
                    _log_dry_step(Step(title, tuple(cmd)))
                    dry_count += 1
                    continue
                run_step(cmd)
                completed.append(title)
```

改为：

```python
    roster_path: Path = session_dir / "roster.json"
    # 多批次合并：输出名由 session+filter 决定、不含批次，逐批调会互相覆盖
    # （且零球批次 exit 1 中止整轮）；合并后每 filter 只调一次，build_highlight
    # 内部按 (file, anchor_time) 排序——文件名即时间戳，跨批排序天然正确
    jobs: list[tuple[Path, str]]
    if len(batches) > 1:
        merged_path: Path = session_dir / MERGED_GOALS_NAME
        if not args.dry_run:
            merged_path = _merge_goals_for_build(batches, args.session, session_dir)
        jobs = [(merged_path, "合并批次")]
    else:
        jobs = [(b.goals, f"批次{b.batch}") for b in batches]
    completed: list[str] = []
    dry_count: int = 0
    try:
        for goals_path, batch_label in jobs:
            base: list[str] = [
                sys.executable,
                str(SCRIPT_DIR / "build_highlight.py"),
                "--goals",
                str(goals_path),
            ]
            if roster_path.is_file():
                base.extend(["--roster", str(roster_path)])
            base.extend(["--rawdir", str(rawdir), "--out", out_size])
            for flag, value in filters:
                cmd: list[str] = [*base, flag, value] if flag else list(base)
                title: str = (
                    f"{batch_label} 合成{(' ' + flag + ' ' + value) if flag else '（全员）'}"
                )
                if args.dry_run:
                    _log_dry_step(Step(title, tuple(cmd)))
                    dry_count += 1
                    continue
                run_step(cmd)
                completed.append(title)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_video.py -q
```

Expected: 全绿

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/video.py tests/test_video.py
git commit -m "fix: video build 多批次合并合成 + --all 零命中跳过（修零球批次中止/同名覆盖）"
```

---

### Task 2: 文档同步 + 终审收尾

**Files:**
- Modify: `docs/video-cli/spec.md`（build 节同步合并语义）、`使用手册.html`（build 说明补一句）、`docs/build-multi-batch/todo.md`
- Create: `docs/build-multi-batch/review01.md`

- [ ] **Step 1: 全量质量门**（见 Global Constraints）
- [ ] **Step 2: docs/video-cli/spec.md build 节**：把逐批调用语义改为"选中批次 >1 时先合并 goals 到 goals_merged_cli.json、每 filter 只调一次；--all 零命中球员/队伍 WARNING 跳过、全零 exit 1"
- [ ] **Step 3: 使用手册.html 合成一节补一句**：多批次场次 build 自动合并跨批片段，每球员/队伍只出一个合集；某球员全场没进球会 WARNING 跳过不中断。改完过 spec-reviewer（subagent_type=plan 扮演）
- [ ] **Step 4: 立哥实测**：`video build --session 20260805_车百鼎 --all`（先 --dry-run 看展开）
- [ ] **Step 5: todo.md 勾完 + review01.md + Commit**

```bash
git add docs/video-cli/spec.md 使用手册.html docs/build-multi-batch/todo.md docs/build-multi-batch/review01.md
git commit -m "docs: build 多批次合并语义同步 video-cli spec 与使用手册 + 审查存档"
```

---

## Self-Review 记录

- spec 覆盖：合并合成/零命中跳过/单批不变/dry-run 不写盘→Task 1；文档/实测/终审→Task 2。
- 既有测试影响面已逐一盘点（4 条更新 + 断言新预期），_goals_payload 加 anchor_time
  对 score/people 测试无影响（它们只断 argv 不读 goals 内容——执行者若发现受影响
  测试，停下报 BLOCKED 不自由发挥）。
- 命名一致：MERGED_GOALS_NAME/_confirmed_keys/_merge_goals_for_build/known_keys/
  hit_tags 全文一致。
