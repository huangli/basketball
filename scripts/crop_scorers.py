"""投篮者定位裁图 + 颜色分队（spec: docs/scorer/spec.md §投篮者定位算法 / §颜色分队判据）。

输入：goals.json（status=confirmed 记录）、work/detect/<fid>_mot_cache.json（5fps
    球/人检测缓存，坐标系 1920×1080 与帧图一致）、work/frames/<fid>/f_NNNNN.jpg。
输出：<out>/ 下每个 confirmed 球一张投篮者裁图 + scorer_candidates.json
    （含 key=format_key、裁图路径、status OK/SKIP、team_guess）。
依赖：scripts/roster.py（format_key / fid_of）、scripts/geom.py（Box/iou）、
    scripts/pipe_common.py（read_json / atomic_write_json / run_id 日志）、PIL + numpy。
典型调用：
    python scripts/crop_scorers.py --goals work/20260722/goals.json \
        --detectdir work/detect --framesdir work/frames --out work/20260722/scorers

定位算法（spec B2，写死）：mot_cache 的 persons 无 track ID，先在窗口
[anchor−2.5s, anchor−0.3s] 内按相邻帧 IoU>0.3 贪心链成临时 track；逐帧取离球
最近人框计入其 track；得票最多者胜出，并列取窗口内离球平均距离更近者；
有效票 <2 帧（含 anchor<1.5s 短窗口）→ SKIP（不炸、不瞎猜）。
号码识别（--read-numbers，spec T7）本轮不做。
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from errors import BasketballPipelineError, SchemaError
from geom import Box, iou
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json
from roster import fid_of, format_key

logger = logging.getLogger(__name__)

# ---- 定位参数（spec §投篮者定位算法 B2，写死） ----
SAMPLE_FPS: int = 5  # 抽帧帧率（extract_frames 全线约定：帧 i 对应 sec = i/5）
WINDOW_PRE_SEC: float = 2.5  # 投票窗口起点 = anchor − 2.5s
WINDOW_POST_SEC: float = 0.3  # 投票窗口终点 = anchor − 0.3s（避开入网瞬间球筐重叠）
IOU_LINK_MIN: float = 0.3  # 相邻帧人框 IoU 串联阈值（跨帧断裂即新 track）
MIN_VALID_VOTES: int = 2  # 有效票（有球检测的帧数）下限，不足 → SKIP
MIN_ANCHOR_SEC: float = 1.5  # anchor 更早则窗口过短，直接 SKIP
_EPS: float = 1e-9  # 浮点窗口边界的容差

# ---- 裁图参数（spec B2 第 4 条） ----
CROP_EXPAND: float = 0.2  # 人框外扩比例（每维放大到 1.2 倍，即每侧 10%）
CROP_MIN_SHORT_SIDE: int = 400  # 短边下限（像素），不足等比放大（号码识别可读性下限）
JPEG_QUALITY: int = 95  # 裁图保存质量（认人目检用，不省这点体积）

# ---- 颜色分队阈值（spec §颜色分队判据 M4；HSV 各通道 0-255，PIL convert("HSV") 口径） ----
# 采样区 = 人框水平中 60% × 垂直 25%~60%（躯干，排除头/腿/背景边缘）。
# 标定记录（2026-08-08，批次 1 共 17 球：15 张 OK 裁图逐张目检真值 黑5/白10，2 张 SKIP 无图）：
#   黑队 frac(V<45)：真黑 0.31~0.72，真白 ≤0.19 → TH_BLACK=45、占比阈 0.25 双侧有间隔
#   白队 frac(V>170 且 S<70)：真白 0.14~0.66（取 ≥0.20 命中 8/10，余 2 张灯光暗+绿偏
#     归便服，spec 允许近阈归便服），真黑 ≤0.12 → TH_WHITE=170、TH_SAT=70、占比阈 0.20
TH_BLACK: int = 45  # 黑队：采样区 V < TH_BLACK 占比达标 → 黑
TH_WHITE: int = 170  # 白队：V > TH_WHITE 且 S < TH_SAT
TH_SAT: int = 70  # 白队的饱和度上限（彩色亮部/肤色不归白）
MIN_BLACK_FRACTION: float = 0.25  # 黑色像素占比下限，不足（含近阈混杂）归"便服"
MIN_WHITE_FRACTION: float = 0.20  # 白色像素占比下限，不足（含近阈混杂）归"便服"

STATUS_OK: str = "OK"
STATUS_SKIP: str = "SKIP"

TEAM_BLACK: str = "黑"
TEAM_WHITE: str = "白"
TEAM_CASUAL: str = "便服"


@dataclass(frozen=True, slots=True)
class BallDet:
    """mot_cache 中单个球检测（只取定位需要的字段）。"""

    conf: float
    cx: float
    cy: float
    frame_idx: int


@dataclass(frozen=True, slots=True)
class MotCache:
    """校验后的 mot_cache：balls / persons 按帧对齐，长度均为 frames。"""

    frames: int
    balls: tuple[tuple[BallDet, ...], ...]
    persons: tuple[tuple[Box, ...], ...]


@dataclass(slots=True)
class PersonTrack:
    """窗口内临时 person track（IoU 链产物，可变，仅存活于一次定位）。"""

    track_id: int
    dets: list[tuple[int, Box]] = field(default_factory=list)  # (frame_idx, box)


@dataclass(frozen=True, slots=True)
class Vote:
    """一票：某帧离球最近的人框计入其 track。"""

    frame_idx: int
    track_id: int
    dist: float
    box: Box


@dataclass(frozen=True, slots=True)
class LocateResult:
    """定位结果；status=SKIP 时 frame_idx=-1、box=None。"""

    status: str
    reason: str
    frame_idx: int
    box: Box | None
    votes: int
    total_votes: int


def load_mot_cache(path: str | Path) -> MotCache:
    """读取并校验 mot_cache（rules.md §0.2：schema 损坏显式失败，不静默容错）。

    Args:
        path: work/detect/<fid>_mot_cache.json 路径。

    Returns:
        校验后的 MotCache。

    Raises:
        SchemaError: 顶层缺 frames/balls/persons、长度不齐、检测字段类型错。
    """
    data: Any = read_json(path, what="mot_cache")
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: 顶层必须是对象，实际 {type(data).__name__}")
    frames: Any = data.get("frames")
    balls_raw: Any = data.get("balls")
    persons_raw: Any = data.get("persons")
    if not isinstance(frames, int) or frames < 0:
        raise SchemaError(f"{path}: frames 缺失或非负 int，实际 {frames!r}")
    if not isinstance(balls_raw, list) or not isinstance(persons_raw, list):
        raise SchemaError(f"{path}: balls/persons 缺失或不是列表")
    if len(balls_raw) != frames or len(persons_raw) != frames:
        raise SchemaError(
            f"{path}: 长度不齐 frames={frames} balls={len(balls_raw)} persons={len(persons_raw)}"
        )

    balls: list[tuple[BallDet, ...]] = []
    for i, frame_balls in enumerate(balls_raw):
        if not isinstance(frame_balls, list):
            raise SchemaError(f"{path}: balls[{i}] 不是列表")
        dets: list[BallDet] = []
        for j, raw in enumerate(frame_balls):
            if not isinstance(raw, dict):
                raise SchemaError(f"{path}: balls[{i}][{j}] 不是对象")
            try:
                dets.append(
                    BallDet(
                        conf=float(raw["conf"]),
                        cx=float(raw["cx"]),
                        cy=float(raw["cy"]),
                        frame_idx=int(raw["frame_idx"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SchemaError(f"{path}: balls[{i}][{j}] 字段缺失/类型错: {exc}") from exc
        balls.append(tuple(dets))

    persons: list[tuple[Box, ...]] = []
    for i, frame_persons in enumerate(persons_raw):
        if not isinstance(frame_persons, list):
            raise SchemaError(f"{path}: persons[{i}] 不是列表")
        boxes: list[Box] = []
        for j, raw in enumerate(frame_persons):
            if not (isinstance(raw, list) and len(raw) == 4):
                raise SchemaError(f"{path}: persons[{i}][{j}] 不是 [x1,y1,x2,y2]")
            try:
                boxes.append(Box(int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])))
            except (TypeError, ValueError) as exc:
                raise SchemaError(f"{path}: persons[{i}][{j}] 非法框: {exc}") from exc
        persons.append(tuple(boxes))

    return MotCache(frames=frames, balls=tuple(balls), persons=tuple(persons))


def window_frames(anchor_sec: float, total_frames: int) -> list[int]:
    """计算投票窗口内的帧索引：sec ∈ [anchor−2.5, anchor−0.3]，裁剪到 [0, total)。

    Args:
        anchor_sec: 进球锚点（秒）。
        total_frames: 缓存总帧数。

    Returns:
        升序帧索引列表（可能为空）。
    """
    lo: float = anchor_sec - WINDOW_PRE_SEC
    hi: float = anchor_sec - WINDOW_POST_SEC
    first: int = max(0, math.ceil((lo - _EPS) * SAMPLE_FPS))
    last: int = min(total_frames - 1, math.floor((hi + _EPS) * SAMPLE_FPS))
    return list(range(first, last + 1))


def link_tracks(window: list[int], persons: tuple[tuple[Box, ...], ...]) -> list[PersonTrack]:
    """把窗口内逐帧人框按相邻帧 IoU>0.3 贪心链成临时 track（spec B2 第 1 条）。

    每帧每个框在"上一帧有检测且本帧未被占用"的 track 中选 IoU 最大者串联；
    无匹配（跨帧断裂或新出现）即开新 track。

    Args:
        window: 升序帧索引。
        persons: 全量 persons 缓存（按帧索引）。

    Returns:
        临时 track 列表（长度 ≥1 的才有意义，但不过滤，由调用方计票）。
    """
    tracks: list[PersonTrack] = []
    next_id: int = 0
    for fi in window:
        prev: list[PersonTrack] = [t for t in tracks if t.dets and t.dets[-1][0] == fi - 1]
        assigned: set[int] = set()
        for box in persons[fi]:
            best: PersonTrack | None = None
            best_iou: float = IOU_LINK_MIN
            for t in prev:
                if t.track_id in assigned:
                    continue
                score: float = iou(t.dets[-1][1], box)
                if score > best_iou:
                    best = t
                    best_iou = score
            if best is None:
                best = PersonTrack(track_id=next_id)
                next_id += 1
                tracks.append(best)
            best.dets.append((fi, box))
            assigned.add(best.track_id)
    return tracks


def _point_box_dist(px: float, py: float, box: Box) -> float:
    """点到框的距离（框内为 0，框外为到最近边的欧氏距离）。"""
    dx: float = max(box.x1 - px, 0.0, px - box.x2)
    dy: float = max(box.y1 - py, 0.0, py - box.y2)
    return math.hypot(dx, dy)


def locate_scorer(cache: MotCache, anchor_sec: float) -> LocateResult:
    """按 spec B2 定位投篮者：IoU 链 → 逐帧投票 → 众数胜出（并列取平均距离更近者）。

    球无检测的帧弃票；一帧多球取 conf 最高者（盲区弱检测多为 FP，见
    mot_candidates.REJOIN_MIN_CONF 同口径）。有效票 <2 帧或 anchor<1.5s → SKIP。

    Args:
        cache: 校验后的 mot_cache。
        anchor_sec: 进球锚点（秒）。

    Returns:
        LocateResult；SKIP 时 reason ∈ {short_window, empty_window, few_votes}。
    """
    if anchor_sec < MIN_ANCHOR_SEC:
        return LocateResult(STATUS_SKIP, "short_window", -1, None, 0, 0)
    window: list[int] = window_frames(anchor_sec, cache.frames)
    if not window:
        return LocateResult(STATUS_SKIP, "empty_window", -1, None, 0, 0)

    tracks: list[PersonTrack] = link_tracks(window, cache.persons)
    box_track: dict[tuple[int, Box], int] = {
        (fi, box): t.track_id for t in tracks for fi, box in t.dets
    }

    votes: list[Vote] = []
    for fi in window:
        frame_balls: tuple[BallDet, ...] = cache.balls[fi]
        frame_persons: tuple[Box, ...] = cache.persons[fi]
        if not frame_balls or not frame_persons:
            continue  # 球无检测（或无人）该帧弃票
        ball: BallDet = max(frame_balls, key=lambda b: b.conf)
        nearest: Box = min(frame_persons, key=lambda b: _point_box_dist(ball.cx, ball.cy, b))
        votes.append(
            Vote(
                frame_idx=fi,
                track_id=box_track[(fi, nearest)],
                dist=_point_box_dist(ball.cx, ball.cy, nearest),
                box=nearest,
            )
        )

    if len(votes) < MIN_VALID_VOTES:
        return LocateResult(STATUS_SKIP, "few_votes", -1, None, 0, len(votes))

    by_track: dict[int, list[Vote]] = {}
    for v in votes:
        by_track.setdefault(v.track_id, []).append(v)

    def _rank(item: tuple[int, list[Vote]]) -> tuple[int, float]:
        """排序键：票数降序优先，并列取平均距离升序（更近者胜）。"""
        _, vs = item
        mean_dist: float = sum(v.dist for v in vs) / len(vs)
        return (-len(vs), mean_dist)

    winner_votes: list[Vote] = min(by_track.items(), key=_rank)[1]
    rep: Vote = min(winner_votes, key=lambda v: v.dist)  # 代表帧 = 离球最近帧
    return LocateResult(STATUS_OK, "", rep.frame_idx, rep.box, len(winner_votes), len(votes))


def expand_box(box: Box, ratio: float, width: int, height: int) -> tuple[int, int, int, int]:
    """人框按比例外扩并裁剪到图像边界（每维放大 1+ratio 倍，即每侧 ratio/2）。

    Args:
        box: 原人框。
        ratio: 外扩比例（0.2 = 每侧 10%）。
        width: 图像宽（像素）。
        height: 图像高（像素）。

    Returns:
        外扩并夹取后的 (x1, y1, x2, y2)。
    """
    pad_x: int = round((box.x2 - box.x1) * ratio / 2)
    pad_y: int = round((box.y2 - box.y1) * ratio / 2)
    x1: int = max(0, box.x1 - pad_x)
    y1: int = max(0, box.y1 - pad_y)
    x2: int = min(width, box.x2 + pad_x)
    y2: int = min(height, box.y2 + pad_y)
    return x1, y1, x2, y2


def crop_and_save(img_path: Path, box: Box, out_path: Path) -> None:
    """裁出投篮者：外扩 20%，短边不足 400px 等比放大到 400px，存 JPEG。

    Args:
        img_path: 代表帧图片路径。
        box: 代表帧上的胜出人框（与图片同坐标系）。
        out_path: 裁图输出路径（父目录自动创建）。
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(img_path) as im:
        rgb = im.convert("RGB")
        x1, y1, x2, y2 = expand_box(box, CROP_EXPAND, rgb.width, rgb.height)
        crop = rgb.crop((x1, y1, x2, y2))
        short: int = min(crop.size)
        if short < CROP_MIN_SHORT_SIDE:
            scale: float = CROP_MIN_SHORT_SIDE / short
            new_size: tuple[int, int] = (
                round(crop.width * scale),
                round(crop.height * scale),
            )
            crop = crop.resize(new_size, Image.Resampling.LANCZOS)
        crop.save(out_path, "JPEG", quality=JPEG_QUALITY)


def classify_team(crop_path: Path) -> str:
    """按躯干主色分队：黑 / 白 / 便服（spec §颜色分队判据 M4）。

    采样区 = 人框水平中 60% × 垂直 25%~60%；黑：V<TH_BLACK 占比达标；
    白：V>TH_WHITE 且 S<TH_SAT 占比达标；两者均不达标（含近阈混杂）归"便服"。

    Args:
        crop_path: 投篮者裁图路径。

    Returns:
        "黑" / "白" / "便服"。
    """
    with Image.open(crop_path) as im:
        hsv = im.convert("HSV")
        x1: int = round(hsv.width * 0.2)
        x2: int = round(hsv.width * 0.8)
        y1: int = round(hsv.height * 0.25)
        y2: int = round(hsv.height * 0.6)
        arr = np.asarray(hsv.crop((x1, y1, x2, y2)), dtype=np.uint8)
    if arr.size == 0:
        return TEAM_CASUAL  # 采样区退化（极小裁图）不瞎猜
    sat = arr[..., 1].astype(np.int16)
    val = arr[..., 2].astype(np.int16)
    black_frac: float = float(np.mean(val < TH_BLACK))
    white_frac: float = float(np.mean((val > TH_WHITE) & (sat < TH_SAT)))
    if black_frac >= MIN_BLACK_FRACTION and black_frac >= white_frac:
        return TEAM_BLACK
    if white_frac >= MIN_WHITE_FRACTION:
        return TEAM_WHITE
    return TEAM_CASUAL


def _confirmed_goals(data: Any, goals_path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """从 goals.json 数据中取 confirmed 记录（缺 file/anchor_time 显式失败）。

    Args:
        data: read_json 读出的原始 JSON。
        goals_path: 文件路径（仅用于错误信息）。

    Returns:
        confirmed 记录列表（保留原始 dict）。

    Raises:
        SchemaError: 顶层非对象 / goals 非列表 / confirmed 记录缺字段或类型错。
    """
    if not isinstance(data, dict):
        raise SchemaError(f"{goals_path}: 顶层必须是对象，实际 {type(data).__name__}")
    goals: Any = data.get("goals")
    if not isinstance(goals, list):
        raise SchemaError(f"{goals_path}: 缺 goals 列表或类型错误")
    confirmed: list[dict[str, Any]] = []
    for i, g in enumerate(goals):
        if not isinstance(g, dict):
            raise SchemaError(f"{goals_path}: 第{i}条记录不是对象")
        if g.get("status") != "confirmed":
            continue
        if not isinstance(g.get("file"), str) or not g["file"]:
            raise SchemaError(f"{goals_path}: 第{i}条(confirmed) file 缺失或不是非空 str")
        anchor: Any = g.get("anchor_time")
        if not isinstance(anchor, (int, float)):
            raise SchemaError(f"{goals_path}: 第{i}条(confirmed) anchor_time 缺失或非数值")
        confirmed.append(g)
    return confirmed


def _frame_path(framesdir: Path, fid: str, frame_idx: int) -> Path:
    """帧映射：fid + frame_idx → work/frames/<fid>/f_{frame_idx+1:05d}.jpg。"""
    return framesdir / fid / f"f_{frame_idx + 1:05d}.jpg"


def _crop_name(fid: str, anchor_sec: float) -> str:
    """裁图文件名：<fid>_t<anchor:.1f>.jpg（同 fid 多球靠锚点区分）。"""
    return f"{fid}_t{anchor_sec:.1f}.jpg"


def _process_goal(
    goal: dict[str, Any],
    detectdir: Path,
    framesdir: Path,
    outdir: Path,
) -> tuple[dict[str, Any], bool]:
    """处理单个 confirmed 球：定位 → 裁图 → 颜色分队。

    Args:
        goal: confirmed 记录。
        detectdir: mot_cache 目录。
        framesdir: 帧图根目录。
        outdir: 输出目录。

    Returns:
        (候选记录, 是否发生素材缺失错误)。素材缺失（cache/帧图不存在）记
        SKIP + reason 并返回 True（产出型脚本口径：跳过但进程退出码非零）。
    """
    file: str = goal["file"]
    anchor: float = float(goal["anchor_time"])
    fid: str = fid_of(file)
    entry: dict[str, Any] = {
        "key": format_key(file, anchor),
        "file": file,
        "anchor_time": anchor,
        "status": STATUS_SKIP,
        "reason": "",
        "crop": "",
        "team_guess": None,
        "votes": 0,
        "total_votes": 0,
    }

    cache_path: Path = detectdir / f"{fid}_mot_cache.json"
    if not cache_path.is_file():
        logger.error("mot_cache 缺失，跳过: %s (%s)", cache_path, entry["key"])
        entry["reason"] = "missing_cache"
        return entry, True
    cache: MotCache = load_mot_cache(cache_path)

    result: LocateResult = locate_scorer(cache, anchor)
    entry["votes"] = result.votes
    entry["total_votes"] = result.total_votes
    if result.status == STATUS_SKIP:
        logger.info(
            "定位 SKIP: %s reason=%s total_votes=%d",
            entry["key"],
            result.reason,
            result.total_votes,
        )
        entry["reason"] = result.reason
        return entry, False
    if result.box is None:  # 防御：OK 必有 box，逻辑错误显式失败而非静默
        raise BasketballPipelineError(f"定位 OK 但 box 为空: {entry['key']}")

    frame_path: Path = _frame_path(framesdir, fid, result.frame_idx)
    if not frame_path.is_file():
        logger.error("代表帧缺失，跳过: %s (%s)", frame_path, entry["key"])
        entry["reason"] = "missing_frame"
        return entry, True

    crop_name: str = _crop_name(fid, anchor)
    crop_and_save(frame_path, result.box, outdir / crop_name)
    team: str = classify_team(outdir / crop_name)
    entry["status"] = STATUS_OK
    entry["crop"] = crop_name
    entry["team_guess"] = team
    logger.info(
        "定位 OK: %s 帧=%d 票=%d/%d team=%s",
        entry["key"],
        result.frame_idx,
        result.votes,
        result.total_votes,
        team,
    )
    return entry, False


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """解析 CLI 参数。"""
    parser = argparse.ArgumentParser(description="投篮者定位裁图 + 颜色分队（spec B2/M4）")
    parser.add_argument("--goals", required=True, type=Path, help="goals.json 路径")
    parser.add_argument("--detectdir", required=True, type=Path, help="mot_cache 目录")
    parser.add_argument("--framesdir", required=True, type=Path, help="帧图根目录")
    parser.add_argument("--out", required=True, type=Path, help="输出目录（裁图+候选 JSON）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。返回进程退出码（0=全部处理无素材缺失，1=失败或有素材缺失）。"""
    args = _parse_args(argv)
    run_id: str = new_run_id()
    configure_logging(run_id)
    try:
        goals_path: Path = args.goals
        data: Any = read_json(goals_path, what="goals.json")
        confirmed: list[dict[str, Any]] = _confirmed_goals(data, str(goals_path))
        session: str = data.get("session", "") if isinstance(data, dict) else ""
        logger.info("confirmed 球 %d 个，开始定位", len(confirmed))

        args.out.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, Any]] = []
        missing_errors: int = 0
        for goal in confirmed:
            entry, had_missing = _process_goal(goal, args.detectdir, args.framesdir, args.out)
            entries.append(entry)
            missing_errors += int(had_missing)

        out_json: Path = args.out / "scorer_candidates.json"
        atomic_write_json(
            out_json, {"session": session, "candidates": entries}, what="scorer_candidates.json"
        )
        ok: int = sum(1 for e in entries if e["status"] == STATUS_OK)
        teams: dict[str, int] = {}
        for e in entries:
            if e["status"] == STATUS_OK:
                teams[e["team_guess"]] = teams.get(e["team_guess"], 0) + 1
        logger.info(
            "完成: OK=%d SKIP=%d 缺失错误=%d 颜色分布=%s → %s",
            ok,
            len(entries) - ok,
            missing_errors,
            teams,
            out_json,
        )
        if missing_errors:
            logger.error("有 %d 条素材缺失（详见上条 ERROR），退出码非零", missing_errors)
            return 1
        return 0
    except BasketballPipelineError as e:
        logger.error("管线失败 run_id=%s: %s", run_id, e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
