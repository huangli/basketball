# video clean 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `video clean` 子命令：清空 output/ 内容 + work/ 内容 + 源视频目录（列清单 + yes 精确确认 + dry-run + 守卫）；spec = `docs/video-clean/spec.md`（唯一契约）。

**Architecture:** 只改 `scripts/video.py`（新增 _dir_stats/_collect_srcdir_targets/_fmt_gb/_cmd_clean + argparse 注册）；stdlib shutil 新导入；无其他脚本改动。

**Tech Stack:** Python 3.14，pytest（monkeypatch input/stdin.isatty，tmp_path 造目录树）。

## Global Constraints

- 提交信息中文 conventional；只 commit 不 push；git add 点名文件（**有并行会话在同 repo 工作**，严禁 `git add -A`/`.`）
- 质量门（提交前）：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py` 全绿
- 只动 output/、work/、源视频目录三类目标；output/work 目录本身保留；无 --yes 开关
- 测试不得真删仓库任何文件——全部在 tmp_path 内造树（chdir 既有 fixture 模式）
- video.py 现有可复用：`WORK_ROOT = Path("work")`、`REPO_ROOT`、`STATE_NAME`、`read_json`（pipe_common，已导入）、`BasketballPipelineError`（已导入）

---

### Task 1: clean 子命令

**Files:**
- Modify: `scripts/video.py`（导入 shutil；新增 4 个函数；_build_parser 注册 clean）
- Test: `tests/test_video.py`（新增 TestClean 6 条）

**Interfaces:**
- Consumes: WORK_ROOT/REPO_ROOT/STATE_NAME/read_json/BasketballPipelineError、既有 argparse 子命令模式（`cl.set_defaults(func=_cmd_clean)`）
- Produces: `_dir_stats(path: Path) -> tuple[int, int]`；`_collect_srcdir_targets() -> list[Path]`；`_cmd_clean(args) -> int`；`OUTPUT_ROOT = Path("output")`

- [ ] **Step 1: 写失败测试**

tests/test_video.py 末尾追加：

```python
class TestClean:
    """clean：清单 + yes 确认 + 守卫（docs/video-clean/spec.md）。"""

    def _tree(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, *,
              with_state: bool = True, srcdir: str = "") -> pathlib.Path:
        """造工作区树：output/s1/x.mp4 + work/s1/goals_batch1.json(+state) + 素材目录。返回素材目录。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "output" / "s1").mkdir(parents=True)
        (tmp_path / "output" / "s1" / "x.mp4").write_bytes(b"0")
        sess = tmp_path / "work" / "s1"
        sess.mkdir(parents=True)
        (sess / "goals_batch1.json").write_text("{}", encoding="utf-8")
        src = tmp_path / "素材"
        src.mkdir()
        (src / "a.mp4").write_bytes(b"0")
        if with_state:
            _write_json(sess / "video_cli.json", {"srcdir": srcdir or str(src)})
        return src

    def _yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    def test_dry_run_deletes_nothing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        src = self._tree(tmp_path, monkeypatch)
        # Act
        rc = video.main(["clean", "--dry-run"])
        # Assert：零删除
        assert rc == 0
        assert (tmp_path / "output" / "s1" / "x.mp4").is_file()
        assert (tmp_path / "work" / "s1" / "goals_batch1.json").is_file()
        assert (src / "a.mp4").is_file()

    def test_confirm_yes_clears_all(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        src = self._tree(tmp_path, monkeypatch)
        self._yes(monkeypatch)
        # Act
        rc = video.main(["clean"])
        # Assert：output/work 内容清空但目录保留；源视频目录整目录消失
        assert rc == 0
        assert (tmp_path / "output").is_dir() and not list((tmp_path / "output").iterdir())
        assert (tmp_path / "work").is_dir() and not list((tmp_path / "work").iterdir())
        assert not src.exists()

    def test_non_yes_aborts(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：只输 "y"（非精确 yes）
        src = self._tree(tmp_path, monkeypatch)
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        # Act
        rc = video.main(["clean"])
        # Assert：零删除
        assert rc == 0
        assert (src / "a.mp4").is_file()
        assert (tmp_path / "output" / "s1" / "x.mp4").is_file()

    def test_no_state_skips_srcdir(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Arrange：无 video_cli.json（无 srcdir 来源）
        src = self._tree(tmp_path, monkeypatch, with_state=False)
        self._yes(monkeypatch)
        caplog.set_level(logging.WARNING)
        # Act
        rc = video.main(["clean"])
        # Assert：output/work 照常清；源视频不动；有 WARNING
        assert rc == 0
        assert not list((tmp_path / "work").iterdir())
        assert (src / "a.mp4").is_file()
        assert "不猜路径" in caplog.text or "srcdir" in caplog.text

    def test_guard_refuses_repo_root(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Arrange：srcdir 指向仓库根（恶意/配错）
        self._tree(tmp_path, monkeypatch, srcdir=str(video.REPO_ROOT))
        self._yes(monkeypatch)
        caplog.set_level(logging.WARNING)
        # Act
        rc = video.main(["clean"])
        # Assert：拒删仓库根（它还在），output/work 照常清
        assert rc == 0
        assert video.REPO_ROOT.is_dir()
        assert not list((tmp_path / "output").iterdir())
        assert "守卫拒删" in caplog.text

    def test_non_tty_refuses(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：非交互 stdin 且非 dry-run
        src = self._tree(tmp_path, monkeypatch)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        # Act
        rc = video.main(["clean"])
        # Assert：退出 1，零删除
        assert rc == 1
        assert (src / "a.mp4").is_file()
        assert (tmp_path / "output" / "s1" / "x.mp4").is_file()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_video.py::TestClean -q
```

Expected: 6 条 FAIL（argparse 无 clean 子命令 → SystemExit 2）

- [ ] **Step 3: 实现 video.py 改动**

E1 — 导入区加 `import shutil`（插在 `import shlex` 后）。

E2 — 常量区（MERGED_GOALS_NAME 后）加：

```python
# clean 清空的输出根（work/ 用既有 WORK_ROOT；两根本身保留只清内容）
OUTPUT_ROOT: Path = Path("output")
```

E3 — `_cmd_photo` 之后（`_build_parser` 之前）插入四个函数：

```python
def _dir_stats(path: Path) -> tuple[int, int]:
    """递归统计目录总字节数与文件数（os.scandir；单点失败 WARNING 按 0 计不中断）。

    Args:
        path: 目标目录。

    Returns:
        (总字节数, 文件数)。
    """
    total: int = 0
    nfiles: int = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        sub_size, sub_n = _dir_stats(Path(entry.path))
                        total += sub_size
                        nfiles += sub_n
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                        nfiles += 1
                except OSError as exc:
                    logger.warning("统计跳过 %s: %s", entry.path, exc)
    except OSError as exc:
        logger.warning("统计跳过 %s: %s", path, exc)
    return total, nfiles


def _fmt_gb(n: int) -> str:
    """字节数 → GB 两位小数字符串（清单展示用）。"""
    return f"{n / (1024 ** 3):.2f}GB"


def _collect_srcdir_targets() -> list[Path]:
    """从各场次 state 收集源视频目录（清 work 之前先读）；逐个过守卫，不合格剔除。

    守卫（拒删并 ERROR/WARNING）：srcdir = 仓库根**或是仓库根的祖先**
    （`p == REPO_ROOT or p in REPO_ROOT.parents`，防 rmtree 连仓库一起删；
    srcdir 是仓库根的子目录属合法，如素材目录就挂在仓库根下）/ 盘符根 /
    不存在或不是目录。无 state 或无 srcdir → WARNING 不猜路径。

    Returns:
        过守卫的源视频目录列表（去重，按 state 文件名序）。
    """
    targets: list[Path] = []
    for state_path in sorted(WORK_ROOT.glob(f"*/{STATE_NAME}")):
        try:
            data: Any = read_json(state_path, what=f"state {state_path.name}")
        except (BasketballPipelineError, OSError) as exc:
            logger.warning("state 读取失败，跳过其 srcdir: %s (%s)", state_path, exc)
            continue
        src: Any = data.get("srcdir") if isinstance(data, dict) else None
        if not src or not isinstance(src, str):
            continue
        p: Path = Path(src).resolve()
        if p == REPO_ROOT or p in REPO_ROOT.parents:
            logger.error("srcdir 守卫拒删（指向仓库根或其祖先）: %s", p)
            continue
        if p.parent == p:
            logger.error("srcdir 守卫拒删（盘符根）: %s", p)
            continue
        if not p.is_dir():
            logger.warning("srcdir 不存在或不是目录，跳过: %s", p)
            continue
        if p not in targets:
            targets.append(p)
    if not targets:
        logger.warning("未从任何 state 读到 srcdir——源视频目录不删（不猜路径）")
    return targets


def _cmd_clean(args: argparse.Namespace) -> int:
    """clean：清空 output/ 内容 + work/ 内容 + 源视频目录（列清单 + yes 精确确认）。

    顺序：先收集源视频目录（读 state.srcdir，在清 work 前）→ 列三分组清单
    （路径/大小/文件数）→ --dry-run 或确认词非精确 yes 则零删除。单目标删除
    失败记 ERROR 继续其余，结尾汇总，有失败退出 1。非 tty 拒绝执行（防挂起
    在确认输入）。
    """
    srcdirs: list[Path] = _collect_srcdir_targets()
    groups: list[tuple[str, list[Path]]] = [
        ("output/", sorted(OUTPUT_ROOT.iterdir()) if OUTPUT_ROOT.is_dir() else []),
        ("work/", sorted(WORK_ROOT.iterdir()) if WORK_ROOT.is_dir() else []),
        ("源视频", srcdirs),
    ]
    plan: list[Path] = []
    total_bytes: int = 0
    logger.info("=== clean 清单 ===")
    for label, paths in groups:
        logger.info("[%s] %d 项", label, len(paths))
        for p in paths:
            try:
                size, nfiles = _dir_stats(p) if p.is_dir() else (p.stat().st_size, 1)
            except OSError as exc:
                # 统计失败按 0 展示不中断（spec 口径）；目标仍进 plan 照常尝试删除
                logger.warning("统计跳过 %s: %s", p, exc)
                size, nfiles = 0, 0
            total_bytes += size
            plan.append(p)
            logger.info("  %s  %s  %d 文件", p, _fmt_gb(size), nfiles)
    logger.info("合计释放: %s", _fmt_gb(total_bytes))
    if not plan:
        logger.info("无可清理内容")
        return 0
    if args.dry_run:
        logger.info("DRY-RUN：未删除任何内容")
        return 0
    if not sys.stdin.isatty():
        logger.error("非交互环境拒绝执行 clean（防挂起在确认输入）；先看 --dry-run")
        return 1
    ans: str = input("以上全部删除（含源视频，不可恢复）。输入 yes 确认: ")
    if ans != "yes":
        logger.info("未确认（需精确输入 yes），未动任何文件")
        return 0
    failed: list[str] = []
    for p in plan:
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError as exc:
            logger.error("删除失败: %s (%s)", p, exc)
            failed.append(str(p))
    if failed:
        logger.error("clean 完成但有 %d 项删除失败: %s", len(failed), failed)
        return 1
    logger.info("clean 完成：释放 %s，工作区已恢复全新", _fmt_gb(total_bytes))
    return 0
```

E4 — `_build_parser` 注册（photo 子命令后、`return ap` 前）：

```python
    cl = sub.add_parser(
        "clean", help="清空 output/work/源视频，恢复全新工作区（列清单 + yes 确认）"
    )
    cl.add_argument("--dry-run", action="store_true", help="只列清单不删除")
    cl.set_defaults(func=_cmd_clean)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_video.py -q
```

Expected: 全绿（含既有全部用例）

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/video.py tests/test_video.py
git commit -m "feat: video clean——清空 output/work/源视频恢复全新工作区（清单+yes 确认+守卫）"
```

---

### Task 2: 文档同步 + 终审收尾

**Files:**
- Modify: `docs/video-cli/spec.md`（命令清单 + §clean 一节）、`使用手册.html`（命令表 + 一段说明）、`docs/video-clean/todo.md`
- Create: `docs/video-clean/review01.md`

- [ ] **Step 1: 全量质量门**（见 Global Constraints）
- [ ] **Step 2: docs/video-cli/spec.md**：顶部命令清单加
  `python scripts/video.py clean [--dry-run]`；新增 §clean 小节（范围/确认/守卫/
  dry-run/非 tty 拒绝，照 spec.md 已定口径缩写）
- [ ] **Step 3: 使用手册.html**：命令表加一行 clean；在第 4 步后或 FAQ 区补一段：
  "一场打完想清场：`video clean --dry-run` 先看清单 → `video clean` 输入 yes——
  output、work、源视频全清（不可恢复），下次直接 `video score <新目录>` 开新场"
  。改完过 spec-reviewer（subagent_type=plan 扮演）
- [ ] **Step 4: 立哥实测**：`video clean --dry-run` 看清单（真删由他亲自跑）
- [ ] **Step 5: todo.md 勾完 + review01.md + Commit**

```bash
git add docs/video-cli/spec.md 使用手册.html docs/video-clean/todo.md docs/video-clean/review01.md
git commit -m "docs: video clean 同步 video-cli spec 与使用手册 + 审查存档"
```

---

## Self-Review 记录

- spec 覆盖：清单/确认/dry-run/守卫/非 tty/容错汇总→Task 1；文档/实测/终审→Task 2。
- 锚点已对照当前 video.py（导入区/常量区/_build_parser 的 photo 段与
  `return ap`、_cmd_photo 尾部——均在；**实施时以当时文件为准重核，并行会话
  可能动过行数**）。
- read_json 失败路径：bad JSON → SchemaError（BasketballPipelineError 子类）、
  IO 重试耗尽 → OSError，E3 的 except 二元组覆盖两者。
- 测试无真删仓库文件：全部 tmp_path 造树；test_guard_refuses_repo_root 只验证
  拒删（REPO_ROOT.is_dir() 仍在），不会真的去 rmtree 仓库根——守卫先行。
