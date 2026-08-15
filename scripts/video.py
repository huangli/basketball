"""统一入口 CLI：score / people / build / photo 四条高频链路的 subprocess 薄封装。

输入：命令行参数（素材目录 / 场次 ID / 批次 / 过滤项）。
输出：透传调用 run_session / crop_scorers / cluster_scorers / gen_scorer_page /
    build_highlight / rank_photos / gen_photo_page 七个底层脚本；
    状态文件 work/<场次>/video_cli.json。
依赖：scripts/pipe_common.py（read_json/atomic_write_json/configure_logging/new_run_id）、
    scripts/errors.py、scripts/roster.py（validate_roster）；命令拼装契约见
    docs/video-cli/spec.md（逐字照做，不改底层脚本任何行为）。
典型调用（任意目录可运行；启动后自动 chdir 到仓库根，用户相对路径按启动目录解析）：
    python scripts/video.py score <素材目录> --session 20260722
    python scripts/video.py people --session 20260722 --batch 1
    python scripts/video.py build --session 20260722 --all
    python scripts/video.py photo --session 20260722 [--apply]
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from errors import BasketballPipelineError
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json
from roster import validate_roster

logger = logging.getLogger(__name__)

SCRIPT_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = SCRIPT_DIR.parent  # 仓库根（work/ 等相对路径基准；main 启动后 chdir 到此）
WORK_ROOT: Path = Path("work")
STATE_NAME: str = "video_cli.json"
STATE_VERSION: int = 1
# 聚类段 CLIP 权重首跑下载需走本机代理（AGENTS.md 环境节）
CLUSTER_HTTPS_PROXY: str = "http://127.0.0.1:7897"
# 聚类定稿口径（docs/scorer-cluster/；底层默认 average/0.25 是未标定起点，勿依赖）
CLUSTER_LINKAGE: str = "complete"
CLUSTER_THRESHOLD: str = "0.15"
# --max-reads 缺省换算：confirmed 球数 ×3（--best-crops 默认 3，docs/scorer-reid/spec.md）
MAX_READS_PER_GOAL: int = 3
# 输出尺寸按素材主比例换算（容差 ±1%；spec §build）
RATIO_TOLERANCE: float = 0.01
RATIO_16_9: float = 16 / 9
RATIO_4_3: float = 4 / 3
OUT_16_9: str = "1920x1080"
OUT_4_3: str = "1440x1080"
# 便服队不出分队集锦（build_highlight --team 便服 明文拒收退出 1；--all 展开时跳过）
CASUAL_TEAM: str = "便服"
# 批次 goals 文件名双轨：goals.json（旧布局批次 1）/ goals_batchK.json（现行布局）
GOALS_BATCH_RE: re.Pattern[str] = re.compile(r"^goals_batch(\d+)\.json$")


class StepFailedError(BasketballPipelineError):
    """单步子进程非零退出；携带完整命令便于打印失败现场。"""

    def __init__(self, cmd: list[str], returncode: int) -> None:
        super().__init__(f"子进程退出码 {returncode}: {shlex.join(cmd)}")
        self.cmd: list[str] = cmd
        self.returncode: int = returncode


@dataclass(frozen=True, slots=True)
class Batch:
    """单个批次的产物路径集合（命名双轨见 docs/video-cli/spec.md §批次发现）。"""

    batch: int  # 批次序号 K（旧布局 goals.json 视为批次 1）
    goals: Path
    candidates: Path
    review_dir: Path
    scorers_dir: Path

    @property
    def events_index(self) -> Path:
        """review 目录下的 events_index.json（旧布局批次 1 可能正常缺失）。"""
        return self.review_dir / "events_index.json"

    @property
    def scorer_candidates(self) -> Path:
        """crop_scorers 产出的 scorer_candidates.json。"""
        return self.scorers_dir / "scorer_candidates.json"

    @property
    def scorer_clusters(self) -> Path:
        """cluster_scorers 产出的 scorer_clusters.json（与 candidates 同目录硬约束）。"""
        return self.scorers_dir / "scorer_clusters.json"


@dataclass(frozen=True, slots=True)
class Step:
    """一个待执行步骤：标题（日志用）、子进程命令、额外环境变量。"""

    title: str
    argv: tuple[str, ...]
    env_extra: dict[str, str] | None = None


def run_step(cmd: list[str], env_extra: dict[str, str] | None = None) -> None:
    """执行单步子进程：log 完整命令，env 统一注入 PYTHONIOENCODING=utf-8。

    Args:
        cmd: 完整子进程命令（含 sys.executable 与脚本路径）。
        env_extra: 追加注入的环境变量（如聚类段的 HTTPS_PROXY），os.environ 复制后改。

    Raises:
        StepFailedError: 子进程非零退出。
    """
    logger.info("执行: %s", shlex.join(cmd))
    env: dict[str, str] = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(cmd, check=False, env=env)  # noqa: S603 命令全部由本模块内部构造
    if proc.returncode != 0:
        raise StepFailedError(cmd, proc.returncode)


def _log_dry_step(step: Step) -> None:
    """--dry-run：只打印将要执行的命令，不启动子进程。"""
    logger.info("DRY-RUN %s: %s", step.title, shlex.join(step.argv))
    if step.env_extra:
        logger.info("DRY-RUN %s: 叠加 env %s", step.title, step.env_extra)


def session_dir_or_die(session: str) -> Path:
    """定位 work/<场次>/ 目录；不存在显式失败（不猜路径）。

    Raises:
        BasketballPipelineError: 目录不存在。
    """
    session_dir: Path = WORK_ROOT / session
    if not session_dir.is_dir():
        raise BasketballPipelineError(f"场次目录不存在: {session_dir}（先跑 score）")
    return session_dir


def load_state(session: str) -> dict[str, Any]:
    """读取 work/<场次>/video_cli.json；不存在返回默认空状态，版本不符显式失败。

    Raises:
        BasketballPipelineError: state 版本不支持（不静默降级）。
        SchemaError: JSON 损坏（pipe_common.read_json 抛出）。
    """
    path: Path = WORK_ROOT / session / STATE_NAME
    if not path.is_file():
        return {"version": STATE_VERSION, "session": session, "srcdir": "", "runs": []}
    data: Any = read_json(path, what=STATE_NAME)
    if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
        raise BasketballPipelineError(f"{path}: state 版本不支持（期望 version={STATE_VERSION}）")
    if not isinstance(data.get("runs"), list):
        raise BasketballPipelineError(f"{path}: runs 必须是列表（审计口径：只追加不覆盖）")
    return data


def save_state(session: str, state: dict[str, Any]) -> None:
    """原子写 state；updated_at 刷新为当前时间。调用方保证 runs 只追加。"""
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    session_dir: Path = WORK_ROOT / session
    session_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(session_dir / STATE_NAME, state, what=STATE_NAME)


def resolve_rawdir(args_rawdir: str | None, state: dict[str, Any]) -> Path:
    """解析原片目录：显式 --rawdir 优先，其次 state.srcdir，都没有显式失败。

    Raises:
        BasketballPipelineError: 两路皆缺（不猜路径）。
    """
    if args_rawdir:
        return Path(args_rawdir)
    srcdir: Any = state.get("srcdir")
    if isinstance(srcdir, str) and srcdir:
        return Path(srcdir)
    raise BasketballPipelineError(
        "--rawdir 未给且 video_cli.json 无 srcdir（先跑 score 或显式给 --rawdir）"
    )


def _batch_from_goals(goals_path: Path) -> Batch | None:
    """由 goals 文件名推导批次配套路径（双轨）；无法识别返回 None。"""
    session_dir: Path = goals_path.parent
    name: str = goals_path.name
    if name == "goals.json":
        return Batch(
            1,
            goals_path,
            session_dir / "candidates.json",
            session_dir / "review",
            session_dir / "scorers",
        )
    m: re.Match[str] | None = GOALS_BATCH_RE.match(name)
    if m is None:
        return None
    k: int = int(m.group(1))
    if k < 1:
        return None
    return Batch(
        k,
        goals_path,
        session_dir / f"candidates_batch{k}.json",
        session_dir / f"review_batch{k}",
        session_dir / f"scorers_b{k}",
    )


def discover_batches(session_dir: Path) -> list[Batch]:
    """扫描场次目录的 goals 文件定位批次（people/build 共用），按批次号升序。

    candidates 缺失仅记 WARNING（people 执行阶段跳过该批）；events_index 缺失的
    降级 WARNING 归 people 链路（build 不引用 review 产物，不在此报噪音）；
    同 K 双布局并存显式失败（不猜）。

    Raises:
        BasketballPipelineError: 无任何 goals 文件，或同批次双布局并存。
    """
    batches: dict[int, Batch] = {}
    for goals_path in sorted(session_dir.glob("goals*.json")):
        batch: Batch | None = _batch_from_goals(goals_path)
        if batch is None:
            logger.warning("无法识别的 goals 文件，跳过: %s", goals_path.name)
            continue
        if batch.batch in batches:
            raise BasketballPipelineError(
                f"批次 {batch.batch} 双布局并存: {batches[batch.batch].goals.name} 与 "
                f"{goals_path.name}（人工改名为单一布局后重跑）"
            )
        batches[batch.batch] = batch
    if not batches:
        raise BasketballPipelineError(f"{session_dir} 下无 goals.json / goals_batchK.json")
    result: list[Batch] = [batches[k] for k in sorted(batches)]
    for b in result:
        if not b.candidates.is_file():
            logger.warning(
                "批次 %d 缺 candidates（people 执行阶段跳过该批）: %s", b.batch, b.candidates
            )
    return result


def _select_batches(batches: list[Batch], batch: int | None) -> list[Batch]:
    """--batch K 限定单批；查无此批显式失败。

    Raises:
        BasketballPipelineError: 指定批次不存在。
    """
    if batch is None:
        return batches
    selected: list[Batch] = [b for b in batches if b.batch == batch]
    if not selected:
        raise BasketballPipelineError(
            f"--batch {batch} 不存在（已发现批次: {[b.batch for b in batches]}）"
        )
    return selected


def confirmed_count(goals_path: Path) -> int:
    """数 goals.json 中 status=confirmed 的条数（--max-reads 缺省换算用）。

    Raises:
        BasketballPipelineError: 顶层结构不含 goals 列表（schema 坏不静默）。
    """
    data: Any = read_json(goals_path, what=goals_path.name)
    if not isinstance(data, dict) or not isinstance(data.get("goals"), list):
        raise BasketballPipelineError(f"{goals_path}: 顶层必须是含 goals 列表的对象")
    return sum(1 for g in data["goals"] if isinstance(g, dict) and g.get("status") == "confirmed")


def resolve_out_size(session_dir: Path) -> str:
    """读 session_facts.json 逐文件 width/height 主比例判定，换算输出尺寸。

    全部 ≈16:9（±1%）→ 1920x1080；全部 ≈4:3（±1%）→ 1440x1080；
    混比例或未知比例显式失败并列出各文件比例（混比例须分别合成，不自动选）。

    Raises:
        BasketballPipelineError: 事实表缺失/损坏/无文件/比例混杂或未知。
    """
    facts_path: Path = session_dir / "session_facts.json"
    if not facts_path.is_file():
        raise BasketballPipelineError(f"缺 session_facts.json: {facts_path}（先跑 score）")
    facts: Any = read_json(facts_path, what="session_facts.json")
    if not isinstance(facts, dict) or not isinstance(facts.get("files"), dict):
        raise BasketballPipelineError(f"{facts_path}: 顶层必须是含 files 对象的事实表")
    files: dict[str, Any] = facts["files"]
    if not files:
        raise BasketballPipelineError(f"{facts_path}: files 为空，无法判定素材比例")
    classes: set[str] = set()
    lines: list[str] = []
    for name in sorted(files):
        info: Any = files[name]
        if not isinstance(info, dict):
            raise BasketballPipelineError(f"{facts_path}: {name} 的元数据不是对象")
        try:
            width: int = int(info["width"])
            height: int = int(info["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BasketballPipelineError(
                f"{facts_path}: {name} 缺 width/height 或不可解析: {exc}"
            ) from exc
        if width <= 0 or height <= 0:
            raise BasketballPipelineError(f"{facts_path}: {name} 尺寸非法: {width}x{height}")
        ratio: float = width / height
        if abs(ratio - RATIO_16_9) / RATIO_16_9 <= RATIO_TOLERANCE:
            cls = "16:9"
        elif abs(ratio - RATIO_4_3) / RATIO_4_3 <= RATIO_TOLERANCE:
            cls = "4:3"
        else:
            cls = "未知"
        classes.add(cls)
        lines.append(f"  {name}: {width}x{height} 比例 {ratio:.4f}（{cls}）")
    if len(classes) == 1 and "16:9" in classes:
        return OUT_16_9
    if len(classes) == 1 and "4:3" in classes:
        return OUT_4_3
    detail: str = "\n".join(lines)
    raise BasketballPipelineError(
        f"素材比例混杂或未知（{sorted(classes)}），须按比例分别合成，CLI 不自动选:\n{detail}"
    )


def build_people_steps(
    args: argparse.Namespace,
    batch: Batch,
    rawdir: Path,
    session_dir: Path,
) -> list[Step]:
    """拼装单批次 people 三段链：裁图 → 聚类 → 确认页（参数契约见 spec §people）。

    --read-numbers 带上时 --max-reads 缺省 = 该批 confirmed 球数 ×3；
    --index / --roster-existing 文件存在才传；--skip-cluster 跳过聚类段且确认页
    不传 --clusters。
    """
    crop_argv: list[str] = [
        sys.executable,
        str(SCRIPT_DIR / "crop_scorers.py"),
        "--goals",
        str(batch.goals),
        "--detectdir",
        str(Path("work/detect")),
        "--framesdir",
        str(Path("work/frames")),
        "--out",
        str(batch.scorers_dir),
        "--candidates",
        str(batch.candidates),
        "--rawdir",
        str(rawdir),
    ]
    if args.read_numbers:
        crop_argv.append("--read-numbers")
        max_reads: int = (
            args.max_reads
            if args.max_reads is not None
            else confirmed_count(batch.goals) * MAX_READS_PER_GOAL
        )
        crop_argv.extend(["--max-reads", str(max_reads)])
    steps: list[Step] = [Step(f"批次{batch.batch}①裁图", tuple(crop_argv))]

    if not args.skip_cluster:
        steps.append(
            Step(
                f"批次{batch.batch}②聚类",
                (
                    sys.executable,
                    str(SCRIPT_DIR / "cluster_scorers.py"),
                    "--candidates",
                    str(batch.scorer_candidates),
                    "--out",
                    str(batch.scorer_clusters),
                    "--linkage",
                    CLUSTER_LINKAGE,
                    "--threshold",
                    CLUSTER_THRESHOLD,
                ),
                {"HTTPS_PROXY": CLUSTER_HTTPS_PROXY},
            )
        )

    page_argv: list[str] = [
        sys.executable,
        str(SCRIPT_DIR / "gen_scorer_page.py"),
        "--scorers",
        str(batch.scorer_candidates),
        "--goals",
        str(batch.goals),
        "--session",
        session_dir.name,
    ]
    if batch.events_index.is_file():
        page_argv.extend(["--index", str(batch.events_index)])
    if not args.skip_cluster:
        page_argv.extend(["--clusters", str(batch.scorer_clusters)])
    roster_path: Path = session_dir / "roster.json"
    if roster_path.is_file():
        page_argv.extend(["--roster-existing", str(roster_path)])
    if args.players_file:
        page_argv.extend(["--players-file", str(args.players_file)])
    steps.append(Step(f"批次{batch.batch}③确认页", tuple(page_argv)))
    return steps


def _cmd_score(args: argparse.Namespace) -> int:
    """score：透传 run_session.py；成功后写 state（dry-run 不写）。"""
    cmd: list[str] = [
        sys.executable,
        str(SCRIPT_DIR / "run_session.py"),
        args.srcdir,
        "--session",
        args.session,
    ]
    if args.batch_size is not None:
        cmd.extend(["--batch-size", str(args.batch_size)])
    if args.fids:
        cmd.extend(["--fids", args.fids])
    if args.force:
        cmd.append("--force")
    if args.dry_run:
        cmd.append("--dry-run")
    try:
        run_step(cmd)
    except StepFailedError as exc:
        logger.error("score 失败: %s", exc)
        return 1
    if args.dry_run:
        return 0
    state: dict[str, Any] = load_state(args.session)
    state["session"] = args.session
    state["srcdir"] = str(Path(args.srcdir).resolve())
    state["runs"].append(
        {
            "cmd": "score",
            "at": datetime.now().isoformat(timespec="seconds"),
            "argv": sys.argv[1:] if args.argv is None else args.argv,
            "exit_code": 0,
        }
    )
    save_state(args.session, state)
    logger.info("state 落盘: %s", WORK_ROOT / args.session / STATE_NAME)
    return 0


def _cmd_people(args: argparse.Namespace) -> int:
    """people：逐批次三段链（裁图 → 聚类 → 确认页），批次间独立。"""
    session_dir: Path = session_dir_or_die(args.session)
    state: dict[str, Any] = load_state(args.session)
    rawdir: Path = resolve_rawdir(args.rawdir, state)
    batches: list[Batch] = _select_batches(discover_batches(session_dir), args.batch)
    completed: list[str] = []
    dry_count: int = 0
    try:
        for batch in batches:
            if not batch.candidates.is_file():
                logger.warning("批次 %d 缺 candidates，跳过该批: %s", batch.batch, batch.candidates)
                continue
            if not batch.events_index.is_file():
                logger.warning(
                    "批次 %d 缺 events_index（确认页失兜底视频引用，降级继续）: %s",
                    batch.batch,
                    batch.events_index,
                )
            for step in build_people_steps(args, batch, rawdir, session_dir):
                if args.dry_run:
                    _log_dry_step(step)
                    dry_count += 1
                    continue
                run_step(list(step.argv), step.env_extra)
                completed.append(step.title)
    except StepFailedError as exc:
        logger.error("失败命令: %s", shlex.join(exc.cmd))
        logger.error("已完成步骤: %s", completed or "（无）")
        return 1
    if args.dry_run:
        logger.info("DRY-RUN 共 %d 步（未执行）", dry_count)
    else:
        logger.info("people 完成（%d 步）", len(completed))
    return 0


def _build_expand_all(session_dir: Path) -> list[tuple[str, str]]:
    """--all 展开：roster 逐人 --scorer tag + 逐队 --team（team 按出现序去重）。

    便服队不入分队合集（build_highlight --team 便服 明文拒收），跳过并记 WARNING；
    便服球员的个人合集仍照常出。

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
    pairs: list[tuple[str, str]] = [("--scorer", p.tag) for p in roster.players]
    teams: list[str] = []
    casual_skipped: bool = False
    for p in roster.players:
        if p.team == CASUAL_TEAM:
            casual_skipped = True
            continue
        if p.team and p.team not in teams:
            teams.append(p.team)
    if casual_skipped:
        logger.warning("--all 跳过便服分队合集（build_highlight 拒收；便服球员个人合集照常出）")
    pairs.extend(("--team", t) for t in teams)
    return pairs


def _cmd_build(args: argparse.Namespace) -> int:
    """build：尺寸按 session_facts 主比例换算，逐批调 build_highlight。"""
    session_dir: Path = session_dir_or_die(args.session)
    state: dict[str, Any] = load_state(args.session)
    rawdir: Path = resolve_rawdir(args.rawdir, state)
    out_size: str = resolve_out_size(session_dir)
    batches: list[Batch] = _select_batches(discover_batches(session_dir), args.batch)
    filters: list[tuple[str, str]]
    if args.all:
        filters = _build_expand_all(session_dir)
        if not filters:
            raise BasketballPipelineError(f"roster players 为空，--all 无合集可出: {session_dir}")
    elif args.scorer:
        filters = [("--scorer", args.scorer)]
    elif args.team:
        filters = [("--team", args.team)]
    else:
        filters = [("", "")]
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
    except StepFailedError as exc:
        logger.error("失败命令: %s", shlex.join(exc.cmd))
        logger.error("已完成步骤: %s", completed or "（无）")
        return 1
    if args.dry_run:
        logger.info("DRY-RUN 共 %d 步（未执行，--out %s）", dry_count, out_size)
    else:
        logger.info("build 完成（%d 步，--out %s）", len(completed), out_size)
    return 0


def _cmd_photo(args: argparse.Namespace) -> int:
    """photo：精彩照片链路——rank（打分→抽帧裁切）→ page（瀑布流确认页）。

    --apply 时只跑落盘段（selections 约定路径 work/<场次>/photos/photo_selections.json）；
    否则 rank + page 两步。rank 缺缓存/缺原片的文件由底层 WARNING 跳过。
    """
    session_dir_or_die(args.session)
    steps: list[Step] = []
    if args.apply:
        steps.append(
            Step(
                "照片落盘",
                (
                    sys.executable,
                    str(SCRIPT_DIR / "rank_photos.py"),
                    "--session",
                    args.session,
                    "--apply",
                ),
            )
        )
    else:
        state: dict[str, Any] = load_state(args.session)
        rawdir: Path = resolve_rawdir(args.rawdir, state)
        rank_argv: list[str] = [
            sys.executable,
            str(SCRIPT_DIR / "rank_photos.py"),
            "--session",
            args.session,
            "--rawdir",
            str(rawdir),
        ]
        if args.total is not None:
            rank_argv.extend(["--total", str(args.total)])
        steps.append(Step("照片打分抽帧", tuple(rank_argv)))
        steps.append(
            Step(
                "照片确认页",
                (
                    sys.executable,
                    str(SCRIPT_DIR / "gen_photo_page.py"),
                    "--session",
                    args.session,
                ),
            )
        )
    completed: list[str] = []
    dry_count: int = 0
    try:
        for step in steps:
            if args.dry_run:
                _log_dry_step(step)
                dry_count += 1
                continue
            run_step(list(step.argv), step.env_extra)
            completed.append(step.title)
    except StepFailedError as exc:
        logger.error("失败命令: %s", shlex.join(exc.cmd))
        logger.error("已完成步骤: %s", completed or "（无）")
        return 1
    if args.dry_run:
        logger.info("DRY-RUN 共 %d 步（未执行）", dry_count)
    else:
        logger.info("photo 完成（%d 步）", len(completed))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """构建三级 argparse：prog → 子命令 → 各自参数。"""
    ap = argparse.ArgumentParser(
        prog="video",
        description="半截篮统一入口：score（检测）→ people（认人）→ build（合集）",
    )
    sub = ap.add_subparsers(dest="command")

    sc = sub.add_parser("score", help="检测链路：透传 run_session.py 至标注页生成")
    sc.add_argument("srcdir", help="原片目录（递归扫描 .mp4）")
    sc.add_argument("--session", required=True, help="场次 ID")
    sc.add_argument("--batch-size", type=int, default=None, help="每批文件数（缺省透传底层默认）")
    sc.add_argument("--fids", default="", help="逗号分隔 fid 清单（adhoc 模式）")
    sc.add_argument("--force", action="store_true", help="忽略断点产物全部重算")
    sc.add_argument("--dry-run", action="store_true", help="只打印不执行（不写 state）")
    sc.set_defaults(func=_cmd_score)

    pp = sub.add_parser("people", help="认人链路：裁图 → 聚类 → 确认页（逐批次）")
    pp.add_argument("--session", required=True, help="场次 ID")
    pp.add_argument("--batch", type=int, default=None, help="限定单批次 K")
    pp.add_argument("--rawdir", default=None, help="原片目录（缺省读 state.srcdir）")
    pp.add_argument("--read-numbers", action="store_true", help="K3 读号（花 token，按需开）")
    pp.add_argument(
        "--max-reads",
        type=int,
        default=None,
        help="读号新调用上限（缺省 = 该批 confirmed 球数 ×3）",
    )
    pp.add_argument("--players-file", default=None, help="球员名单 JSON 文件")
    pp.add_argument(
        "--skip-cluster", action="store_true", help="跳过聚类段（确认页不传 --clusters）"
    )
    pp.add_argument("--dry-run", action="store_true", help="只打印不执行")
    pp.set_defaults(func=_cmd_people)

    bd = sub.add_parser("build", help="合成链路：build_highlight 全员/单人/单队/全量合集")
    bd.add_argument("--session", required=True, help="场次 ID")
    bd.add_argument("--batch", type=int, default=None, help="限定单批次 K")
    bd.add_argument("--rawdir", default=None, help="原片目录（缺省读 state.srcdir）")
    grp = bd.add_mutually_exclusive_group()
    grp.add_argument("--scorer", default="", help="单个人合集（tag 或姓名）")
    grp.add_argument("--team", default="", help="单队伍合集")
    grp.add_argument("--all", action="store_true", help="roster 逐人 + 逐队全量合集")
    bd.add_argument("--dry-run", action="store_true", help="只打印不执行")
    bd.set_defaults(func=_cmd_build)

    ph = sub.add_parser("photo", help="精彩照片：打分 → 抽帧裁切 → 确认页 / --apply 落盘精选")
    ph.add_argument("--session", required=True, help="场次 ID")
    ph.add_argument("--rawdir", default=None, help="原片目录（缺省读 state.srcdir）")
    ph.add_argument("--total", type=int, default=None, help="候选目标张数（缺省透传底层 200）")
    ph.add_argument(
        "--apply",
        action="store_true",
        help="落盘模式：按 work/<场次>/photos/photo_selections.json 出照片精选",
    )
    ph.add_argument("--dry-run", action="store_true", help="只打印不执行")
    ph.set_defaults(func=_cmd_photo)
    return ap


def _resolve_user_paths(args: argparse.Namespace, launch_cwd: Path) -> None:
    """把用户传入的相对路径参数解析为绝对路径（chdir 到仓库根之前调用）。

    支持从任意目录调用：main 启动后统一 chdir 到 REPO_ROOT（work/ 等相对路径
    基准），用户给的相对路径必须先按启动目录解析，否则会被错误地相对到仓库根。

    Args:
        args: 已解析的命令行命名空间（原地修改 srcdir/rawdir/players_file）。
        launch_cwd: 进程启动目录。
    """
    for attr in ("srcdir", "rawdir", "players_file"):
        value: str | None = getattr(args, attr, None)
        if value:
            p: Path = Path(value)
            setattr(args, attr, str(p if p.is_absolute() else (launch_cwd / p).resolve()))


def main(argv: list[str] | None = None, *, relocate: bool = False) -> int:
    """CLI 入口。返回进程退出码（0=成功；1=失败；2=无子命令）。

    Args:
        argv: 参数列表（None 取 sys.argv）。
        relocate: True 时按启动目录解析用户相对路径参数并 chdir 到 REPO_ROOT
            （真实命令行入口用）；测试与库内调用传 False 保持当前目录。
    """
    parser: argparse.ArgumentParser = _build_parser()
    args: argparse.Namespace = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    args.argv = argv
    if relocate:
        _resolve_user_paths(args, Path.cwd())
        os.chdir(REPO_ROOT)
    run_id: str = new_run_id()
    configure_logging(run_id)
    try:
        return int(args.func(args))
    except BasketballPipelineError as exc:
        logger.error("失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1
    except OSError as exc:
        logger.error("IO 失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1


if __name__ == "__main__":
    # 管道/重定向时 stdout 回落 locale 编码（cp1252/GBK），打印中文 help/日志会
    # UnicodeEncodeError（docs/经验教训.md §6）；交互控制台保持原生编码不动
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure") and not _stream.isatty():
            _stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(relocate=True))
