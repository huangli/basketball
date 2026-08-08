"""投篮者定位裁图 + 颜色分队（spec: docs/scorer/spec.md §投篮者定位算法 / §颜色分队判据）。

输入：goals.json（status=confirmed 记录）、work/detect/<fid>_mot_cache.json（5fps
    球/人检测缓存，坐标系 1920×1080 与帧图一致）、work/frames/<fid>/f_NNNNN.jpg；
    --rawdir（可选，原片目录）：给了就为每个 confirmed 球现切认人预览片段
    （窗口 [max(0, anchor−4), anchor+2]，与进球锚点严格对齐——认人页视频必须与
    裁图同球同时刻，不再引用 events_index 的事件片段，长事件开头是另一回合）。
输出：<out>/ 下每个 confirmed 球一张投篮者裁图 + scorer_candidates.json
    （含 key=format_key、裁图路径、status OK/SKIP、team_guess、clip 预览片段
    相对路径）；--rawdir 给定时另有 <out>/clips/<fid>_t<anchor:.1f>.mp4。
依赖：scripts/roster.py（format_key / fid_of）、scripts/geom.py（Box/iou）、
    scripts/pipe_common.py（read_json / atomic_write_json / run_ffmpeg / run_id 日志）、
    PIL + numpy。
典型调用：
    python scripts/crop_scorers.py --goals work/20260722/goals.json \
        --detectdir work/detect --framesdir work/frames --out work/20260722/scorers \
        --rawdir "20260722地平线/2026 年 7月22 日 地平线"

定位算法（2026-08-08 轨迹法，替换逐帧投票——逐帧取 max-conf 球会在海报球/
隔壁场球之间瞬移，逐帧规则全军覆没；轨迹是可靠的，候选本来就是轨迹挖出来的）：
窗口 [anchor−4.0, anchor+0.5] 内用 mot_candidates.run_mot 重链球轨迹
（min_length=1，短轨迹也是有效证据）；端点与候选锚点（--candidates 给的
t0/cx/cy，goals 锚点与其 dt=0 匹配）最近的轨迹 = 进球轨迹；沿该轨迹从末端
往回放找最后一个"球心严格落在某人框内"的轨迹点 → 该人框 = 投篮者（最后持球者）；
整轨无持球点 → 取轨迹起点时刻的最近人框；轨迹不存在/端点离锚点太远 → SKIP。
SKIP 球无投篮者定位但仍切预览片段（立哥凭视频手选）。
号码识别（--read-numbers，spec T7）本轮不做。
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from errors import BasketballPipelineError, SchemaError
from geom import Box
from mot_candidates import Detection, Track, euclidean, run_mot
from pipe_common import (
    atomic_write_json,
    configure_logging,
    new_run_id,
    read_json,
    run_ffmpeg,
)
from roster import fid_of, format_key

logger = logging.getLogger(__name__)

# ---- 轨迹法定位参数（2026-08-08，替换逐帧投票） ----
SAMPLE_FPS: int = 5  # 抽帧帧率（extract_frames 全线约定：帧 i 对应 sec = i/5）
TRACK_WINDOW_PRE_SEC: float = 4.0  # 轨迹重链窗口起点 = anchor − 4.0s
TRACK_WINDOW_POST_SEC: float = 0.5  # 轨迹重链窗口终点 = anchor + 0.5s
GOAL_TRACK_MAX_DIST_PX: int = 200  # 进球轨迹端点距候选锚点上界，超出 = 没链到 → SKIP
CANDIDATE_MATCH_DT_SEC: float = 0.3  # goals 锚点与 candidates t0 的匹配容差
_EPS: float = 1e-9  # 浮点窗口边界的容差

# ---- 裁图参数（spec B2 第 4 条） ----
CROP_EXPAND: float = 0.2  # 人框外扩比例（每维放大到 1.2 倍，即每侧 10%）
CROP_MIN_SHORT_SIDE: int = 400  # 短边下限（像素），不足等比放大（号码识别可读性下限）
JPEG_QUALITY: int = 95  # 裁图保存质量（认人目检用，不省这点体积）

# ---- 认人预览片段参数（--rawdir 给定时逐球现切，与进球锚点严格对齐） ----
PREVIEW_BEFORE_SEC: float = 4.0  # 窗口 = 锚点前 4s（与剪辑规格一致）
PREVIEW_AFTER_SEC: float = 2.0  # 窗口 = 锚点后 2s
PREVIEW_WIDTH: int = 1280  # 预览宽度（高自适应保持偶数；够认人即可，省体积）
PREVIEW_CRF: int = 26  # 预览码率（认人用途，比成品 20 宽松）
PREVIEW_PRESET: str = "veryfast"  # 预览求快

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
class MotCache:
    """校验后的 mot_cache：balls / persons 按帧对齐，长度均为 frames。

    balls 直接复用 mot_candidates.Detection（轨迹链接的输入类型），
    校验时从 mot_cache 原始字段构造。
    """

    frames: int
    balls: tuple[tuple[Detection, ...], ...]
    persons: tuple[tuple[Box, ...], ...]


@dataclass(frozen=True, slots=True)
class LocateResult:
    """定位结果；status=SKIP 时 frame_idx=-1、box=None。

    votes/total_votes 沿用旧字段名保持 JSON 兼容，语义改为：
    votes = 进球轨迹长度（检测数），total_votes = 窗口内轨迹总数。
    """

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

    balls: list[tuple[Detection, ...]] = []
    for i, frame_balls in enumerate(balls_raw):
        if not isinstance(frame_balls, list):
            raise SchemaError(f"{path}: balls[{i}] 不是列表")
        dets: list[Detection] = []
        for j, raw in enumerate(frame_balls):
            if not isinstance(raw, dict):
                raise SchemaError(f"{path}: balls[{i}][{j}] 不是对象")
            box_raw: Any = raw.get("box")
            if not (isinstance(box_raw, list) and len(box_raw) == 4):
                raise SchemaError(f"{path}: balls[{i}][{j}] box 不是 [x1,y1,x2,y2]")
            try:
                dets.append(
                    Detection(
                        conf=float(raw["conf"]),
                        box=[int(v) for v in box_raw],
                        cx=int(raw["cx"]),
                        cy=int(raw["cy"]),
                        sec=float(raw["sec"]),
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


def load_candidates_index(path: str | Path) -> dict[str, list[tuple[float, int, int]]]:
    """读候选 JSON（candidates.json），建 fid → [(t0, cx, cy)] 索引。

    候选锚点 (cx, cy) 是轨迹法选轨迹的空间参照（goals.json 锚点与其 t0 对应，
    批次 1 全部 17 球 dt=0.0 匹配）。

    Args:
        path: candidates.json 路径（列表，每条 {t0, dur, ac, cx, cy, src, fid, label}）。

    Returns:
        fid → [(t0, cx, cy), ...]（同 fid 多候选按文件序）。

    Raises:
        SchemaError: 顶层非列表 / 条目缺 fid/t0/cx/cy 或类型错。
    """
    data: Any = read_json(path, what="candidates.json")
    if not isinstance(data, list):
        raise SchemaError(f"{path}: 顶层必须是列表，实际 {type(data).__name__}")
    index: dict[str, list[tuple[float, int, int]]] = {}
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise SchemaError(f"{path}: 第{i}条不是对象")
        try:
            fid = str(raw["fid"])
            t0 = float(raw["t0"])
            cx = int(raw["cx"])
            cy = int(raw["cy"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaError(f"{path}: 第{i}条字段缺失/类型错: {exc}") from exc
        index.setdefault(fid, []).append((t0, cx, cy))
    return index


def match_anchor_xy(
    index: dict[str, list[tuple[float, int, int]]], fid: str, anchor_sec: float
) -> tuple[int, int] | None:
    """按 fid + |t0−anchor|≤CANDIDATE_MATCH_DT_SEC 取最近候选的 (cx, cy)；无 → None。

    Args:
        index: load_candidates_index 产物。
        fid: 视频主名。
        anchor_sec: goals.json 的进球锚点（秒）。

    Returns:
        候选锚点 (cx, cy)；无匹配返回 None（退化为端点时间最近选轨迹）。
    """
    best: tuple[int, int] | None = None
    best_dt: float = CANDIDATE_MATCH_DT_SEC
    for t0, cx, cy in index.get(fid, []):
        dt: float = abs(t0 - anchor_sec)
        if dt <= best_dt + _EPS:
            best_dt = dt
            best = (cx, cy)
    return best


def track_window_dets(cache: MotCache, anchor_sec: float) -> list[list[Detection]]:
    """取窗口 [anchor−4.0, anchor+0.5] 内逐帧球检测（保持帧序，空帧为空列表）。

    Args:
        cache: 校验后的 mot_cache。
        anchor_sec: 进球锚点（秒）。

    Returns:
        逐帧检测列表（run_mot 的输入形状）。
    """
    lo: float = anchor_sec - TRACK_WINDOW_PRE_SEC
    hi: float = anchor_sec + TRACK_WINDOW_POST_SEC
    first: int = max(0, math.ceil((lo - _EPS) * SAMPLE_FPS))
    last: int = min(cache.frames - 1, math.floor((hi + _EPS) * SAMPLE_FPS))
    return [list(cache.balls[fi]) for fi in range(first, last + 1)]


def select_goal_track(
    tracks: list[Track], anchor_sec: float, anchor_xy: tuple[int, int] | None
) -> Track | None:
    """选进球轨迹：端点（末端）与候选锚点最近的轨迹。

    有 anchor_xy（候选 cx/cy）时按端点空间距离最近，距离超 GOAL_TRACK_MAX_DIST_PX
    视为没链到（None → SKIP）；无 anchor_xy 退化为端点时间距 anchor 最近。

    Args:
        tracks: 窗口内重链的全部轨迹。
        anchor_sec: 进球锚点（秒）。
        anchor_xy: 候选锚点 (cx, cy)；None 表示无候选位置。

    Returns:
        进球轨迹；无轨迹或端点离锚点太远返回 None。
    """
    if not tracks:
        return None
    if anchor_xy is None:
        return min(tracks, key=lambda t: abs(t.last_det.sec - anchor_sec))
    best: Track = min(tracks, key=lambda t: euclidean((t.last_det.cx, t.last_det.cy), anchor_xy))
    dist: float = euclidean((best.last_det.cx, best.last_det.cy), anchor_xy)
    if dist > GOAL_TRACK_MAX_DIST_PX:
        return None
    return best


def find_held_box(
    track: Track, persons: tuple[tuple[Box, ...], ...]
) -> tuple[Detection, Box] | None:
    """沿轨迹从末端往回放，找最后一个球心严格落在某人框内（无 margin）的轨迹点。

    Args:
        track: 进球轨迹。
        persons: 全量 persons 缓存（按帧索引）。

    Returns:
        (轨迹点, 人框)；整轨无持球点返回 None。
    """
    for det in reversed(track.dets):
        for box in persons[det.frame_idx]:
            if box.x1 <= det.cx <= box.x2 and box.y1 <= det.cy <= box.y2:
                return det, box
    return None


def start_nearest_box(
    track: Track, persons: tuple[tuple[Box, ...], ...]
) -> tuple[Detection, Box] | None:
    """无持球点回退：取轨迹起点时刻离球心最近的人框（框中心距离）。

    Args:
        track: 进球轨迹。
        persons: 全量 persons 缓存（按帧索引）。

    Returns:
        (起点轨迹点, 最近人框)；起点帧无人返回 None。
    """
    first: Detection = track.dets[0]
    boxes: tuple[Box, ...] = persons[first.frame_idx]
    if not boxes:
        return None
    box: Box = min(
        boxes,
        key=lambda b: euclidean((first.cx, first.cy), ((b.x1 + b.x2) // 2, (b.y1 + b.y2) // 2)),
    )
    return first, box


def locate_scorer(
    cache: MotCache, anchor_sec: float, anchor_xy: tuple[int, int] | None = None
) -> LocateResult:
    """轨迹法定位投篮者（2026-08-08 替换逐帧投票）。

    窗口 [anchor−4.0, anchor+0.5] 内 run_mot 重链球轨迹（min_length=1）→
    端点距候选锚点最近者为进球轨迹 → 从末端回放找最后持球点（球心严格在人框内）
    → 整轨无持球点取轨迹起点最近人框。

    Args:
        cache: 校验后的 mot_cache。
        anchor_sec: 进球锚点（秒）。
        anchor_xy: 候选锚点 (cx, cy)；None 退化为端点时间最近选轨迹。

    Returns:
        LocateResult；SKIP 时 reason ∈ {no_track, no_track_near_anchor, no_person}。
    """
    tracks: list[Track] = run_mot(track_window_dets(cache, anchor_sec), min_length=1)
    if not tracks:
        return LocateResult(STATUS_SKIP, "no_track", -1, None, 0, 0)
    track: Track | None = select_goal_track(tracks, anchor_sec, anchor_xy)
    if track is None:
        return LocateResult(STATUS_SKIP, "no_track_near_anchor", -1, None, 0, len(tracks))
    held: tuple[Detection, Box] | None = find_held_box(track, cache.persons)
    if held is not None:
        det, box = held
        return LocateResult(STATUS_OK, "", det.frame_idx, box, track.length, len(tracks))
    fallback: tuple[Detection, Box] | None = start_nearest_box(track, cache.persons)
    if fallback is None:
        return LocateResult(STATUS_SKIP, "no_person", -1, None, track.length, len(tracks))
    det, box = fallback
    return LocateResult(STATUS_OK, "start_fallback", det.frame_idx, box, track.length, len(tracks))


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


def preview_window(anchor_sec: float) -> tuple[float, float]:
    """预览片段窗口：[max(0, anchor−4s), anchor+2s]（与剪辑规格一致，锚点严格对齐）。

    Args:
        anchor_sec: 进球锚点（秒）。

    Returns:
        (start_sec, end_sec)；anchor<4s 时起点夹取到 0（时长缩短，不越界）。
    """
    return max(0.0, anchor_sec - PREVIEW_BEFORE_SEC), anchor_sec + PREVIEW_AFTER_SEC


def _preview_name(fid: str, anchor_sec: float) -> str:
    """预览片段文件名：<fid>_t<anchor:.1f>.mp4（与裁图同命名口径）。"""
    return f"{fid}_t{anchor_sec:.1f}.mp4"


def cut_preview_clip(rawdir: Path, file: str, anchor_sec: float, out_path: Path) -> None:
    """从原片切认人预览片段：输入侧 -ss/-to，1280 宽、libx264、无声。

    Args:
        rawdir: 原片目录。
        file: 视频文件名（rawdir 下的 basename）。
        anchor_sec: 进球锚点（秒）。
        out_path: 输出片段路径（父目录自动创建）。

    Raises:
        BasketballPipelineError: ffmpeg 重试耗尽。
        MediaTimeoutError: ffmpeg 超时（时长×3+60s，下限 120s，同 build_highlight 口径）。
    """
    start, end = preview_window(anchor_sec)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-ss",
            f"{start:.2f}",
            "-to",
            f"{end:.2f}",
            "-i",
            str(rawdir / file),
            "-map",
            "0:v:0",
            "-vf",
            f"scale={PREVIEW_WIDTH}:-2",
            "-c:v",
            "libx264",
            "-crf",
            str(PREVIEW_CRF),
            "-preset",
            PREVIEW_PRESET,
            "-an",
            str(out_path),
        ],
        timeout_sec=max(120, int((end - start) * 3) + 60),
    )


def _try_cut_preview(
    goal: dict[str, Any], rawdir: Path | None, outdir: Path, key: str
) -> tuple[str, bool]:
    """尝试切预览片段；失败记 ERROR 继续（不炸整批，但计入缺失错误使退出码非零）。

    Args:
        goal: confirmed 记录。
        rawdir: 原片目录；None 表示未给 --rawdir（不切片）。
        outdir: 输出目录（片段落 <outdir>/clips/）。
        key: 进球键（日志用）。

    Returns:
        (clip 相对路径, 是否发生切片失败)；未切片或失败时 clip 为空串。
    """
    if rawdir is None:
        return "", False
    file: str = goal["file"]
    anchor: float = float(goal["anchor_time"])
    name: str = _preview_name(fid_of(file), anchor)
    src: Path = rawdir / file
    if not src.is_file():
        logger.error("原片缺失，预览片段跳过: %s (%s)", src, key)
        return "", True
    try:
        cut_preview_clip(rawdir, file, anchor, outdir / "clips" / name)
    except BasketballPipelineError as exc:
        logger.error("预览片段切失败，跳过: %s (%s): %s", name, key, exc)
        return "", True
    return f"clips/{name}", False


def _process_goal(
    goal: dict[str, Any],
    detectdir: Path,
    framesdir: Path,
    outdir: Path,
    rawdir: Path | None = None,
    anchor_xy: tuple[int, int] | None = None,
) -> tuple[dict[str, Any], bool]:
    """处理单个 confirmed 球：切预览片段（--rawdir 时，SKIP 球也切）→ 定位 → 裁图 → 颜色分队。

    Args:
        goal: confirmed 记录。
        detectdir: mot_cache 目录。
        framesdir: 帧图根目录。
        outdir: 输出目录。
        rawdir: 原片目录；None 表示不切预览片段。
        anchor_xy: 候选锚点 (cx, cy)（--candidates 匹配产物）；None 时轨迹选择
            退化为端点时间最近。

    Returns:
        (候选记录, 是否发生素材缺失错误)。素材缺失（cache/帧图/原片不存在、
        切片失败）记 ERROR/SKIP 并返回 True（产出型脚本口径：跳过但进程退出码非零）。
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
        "clip": "",
        "team_guess": None,
        "votes": 0,
        "total_votes": 0,
    }

    # 预览片段与定位解耦：SKIP 球也需要视频供认人手选
    clip, clip_failed = _try_cut_preview(goal, rawdir, outdir, entry["key"])
    entry["clip"] = clip

    cache_path: Path = detectdir / f"{fid}_mot_cache.json"
    if not cache_path.is_file():
        logger.error("mot_cache 缺失，跳过: %s (%s)", cache_path, entry["key"])
        entry["reason"] = "missing_cache"
        return entry, True
    cache: MotCache = load_mot_cache(cache_path)

    result: LocateResult = locate_scorer(cache, anchor, anchor_xy)
    entry["votes"] = result.votes
    entry["total_votes"] = result.total_votes
    if result.status == STATUS_SKIP:
        logger.info(
            "定位 SKIP: %s reason=%s 轨迹数=%d",
            entry["key"],
            result.reason,
            result.total_votes,
        )
        entry["reason"] = result.reason
        return entry, clip_failed
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
        "定位 OK: %s 帧=%d 轨长=%d/%d %steam=%s",
        entry["key"],
        result.frame_idx,
        result.votes,
        result.total_votes,
        "(起点回退) " if result.reason == "start_fallback" else "",
        team,
    )
    return entry, clip_failed


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """解析 CLI 参数。"""
    parser = argparse.ArgumentParser(description="投篮者定位裁图 + 颜色分队（spec B2/M4）")
    parser.add_argument("--goals", required=True, type=Path, help="goals.json 路径")
    parser.add_argument("--detectdir", required=True, type=Path, help="mot_cache 目录")
    parser.add_argument("--framesdir", required=True, type=Path, help="帧图根目录")
    parser.add_argument("--out", required=True, type=Path, help="输出目录（裁图+候选 JSON）")
    parser.add_argument(
        "--rawdir",
        type=Path,
        default=None,
        help="原片目录（可选；给了就逐球切认人预览片段到 <out>/clips/）",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=None,
        help="candidates.json（可选；提供候选锚点 cx/cy 供轨迹法选轨迹，不给则退化为端点时间最近）",
    )
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
        cand_index: dict[str, list[tuple[float, int, int]]] = {}
        if args.candidates:
            cand_index = load_candidates_index(args.candidates)
            logger.info("候选锚点索引: %d 个 fid ← %s", len(cand_index), args.candidates)
        entries: list[dict[str, Any]] = []
        missing_errors: int = 0
        for goal in confirmed:
            anchor_xy: tuple[int, int] | None = None
            if cand_index:
                anchor_xy = match_anchor_xy(
                    cand_index, fid_of(goal["file"]), float(goal["anchor_time"])
                )
                if anchor_xy is None:
                    logger.warning(
                        "候选锚点未匹配（|t0−anchor|>%.1fs），退化为端点时间最近: %s",
                        CANDIDATE_MATCH_DT_SEC,
                        format_key(goal["file"], float(goal["anchor_time"])),
                    )
            entry, had_missing = _process_goal(
                goal, args.detectdir, args.framesdir, args.out, args.rawdir, anchor_xy
            )
            entries.append(entry)
            missing_errors += int(had_missing)

        out_json: Path = args.out / "scorer_candidates.json"
        atomic_write_json(
            out_json, {"session": session, "candidates": entries}, what="scorer_candidates.json"
        )
        ok: int = sum(1 for e in entries if e["status"] == STATUS_OK)
        n_clip: int = sum(1 for e in entries if e["clip"])
        teams: dict[str, int] = {}
        for e in entries:
            if e["status"] == STATUS_OK:
                teams[e["team_guess"]] = teams.get(e["team_guess"], 0) + 1
        logger.info(
            "完成: OK=%d SKIP=%d 预览片段=%d 缺失错误=%d 颜色分布=%s → %s",
            ok,
            len(entries) - ok,
            n_clip,
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
