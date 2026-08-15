"""球队进球热图生成器（热图 v4：v3 框人纠偏——出手前窗口 + 队色硬守卫，docs/heatmap/spec.md v4）。

输入：work/<场次>/roster.json（已归属球，tag→team）、glob 发现的
    goals_batch*.json / candidates_batch*.json / hoops_batch*.json、
    work/detect/<fid>_mot_cache.json、work/frames/<fid>/f_*.jpg（串人守卫 + 目击拼图）、
    work/<场次>/session_facts.json 的 team_color 键（队色硬守卫映射，缺失则守卫禁用）
输出：work/<场次>/goal_landings.json（逐球落点 + 筐锚相对坐标）、
    output/<场次>/队伍_<team>_进球热图.png（每队一张）、
    work/<场次>/heatmap_audit.png（目击拼图，固定种子抽 15 球）
依赖：crop_scorers / mot_candidates / roster / release_probe / scorer_landings 只读复用；
    matplotlib 渲染（Agg 后端，已装，无新依赖）
典型调用：python scripts/goal_heatmap.py --sessiondir work/20260805_车百鼎

口径（spec v4 写死）：
    落点两路并集——主路 trace_person 回追 anchor−1.0s±0.3s 取人框底边中点
    （串人守卫 team_of_box 黑↔白相反时主路不可用、视同链断走兜底）；
    兜底 = 进球轨迹起点 ≥0.8s 前时取起点帧最近人框底边中点。
    v4 框人纠偏——持球点搜索只看 sec ≤ anchor−0.5s 的截断轨迹（v3 实测
    22/27 错球种子在入网后，球穿网落进筐下人躯干框）；队色硬守卫：落点帧
    框中人队色与 roster 队伍期望队色明确相反 → uncovered(team_mismatch)。
    坐标——原点 hoops 筐心（时刻最近采样；多覆盖取时刻最近、并列取空间最近；
    零覆盖退化全局时刻最近 + WARNING）；cx 中位切两端、归一小端、大端取反；
    尺度 = 人框高 / 1.75m；不校正旋转（同机位假设）。
"""

from __future__ import annotations

import argparse
import logging
import math
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from crop_scorers import (
    SAMPLE_FPS,
    MotCache,
    find_held_box,
    load_mot_cache,
    match_anchor_xy,
    select_goal_track,
    start_nearest_box,
    team_of_box,
    trace_person,
    track_window_dets,
)
from errors import BasketballPipelineError, SchemaError
from geom import Box
from mot_candidates import Detection, Track, run_mot
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json
from release_probe import GoalEvent, load_goals_events
from roster import format_key, validate_roster
from scorer_landings import load_merged_candidates

logger = logging.getLogger(__name__)

# ---- 判据常量（docs/heatmap/spec.md v4 写死）----
RELEASE_BEFORE_SEC: float = 1.0  # 出手时刻固定估计 = 锚点前 1.0s（球飞行 0.5~1.5s 中值）
HELD_SEARCH_BEFORE_SEC: float = (
    0.5  # v4：持球点搜索只看 sec ≤ anchor−0.5s 的轨迹点（入网后点不链种子）
)
TRACE_TOL_SEC: float = 0.3  # 追人链目标帧容差（5fps 即 ±1.5 帧）
TRACK_START_MIN_SEC: float = 0.8  # 兜底路：轨迹起点须在锚点前 ≥0.8s
PERSON_HEIGHT_M: float = 1.75  # 假设身高（像素→米尺度锚；模块常量可调）
HOOP_WINDOW_TOL_SEC: float = 1.0  # hoops 事件 window 覆盖锚点的容差
COVERAGE_MIN_RATIO: float = 0.55  # 覆盖率过关线（分母 = roster 已归属球，含便服）
AUDIT_SAMPLE_N: int = 15  # 目击拼图抽样球数
AUDIT_SEED: int = 20260815  # 目击抽样固定种子（可复现）
TEAM_CASUAL: str = "便服"  # roster 中便服队不进热图
HEAT_BIN_M: float = 0.25  # 密度网格边长（米）
HEAT_SIGMA_M: float = 0.8  # 密度高斯平滑 sigma（米）
_OPPOSITE_TEAM: dict[str, str] = {
    "黑": "白",
    "白": "黑",
}  # 队色相反映射（串人守卫 + v4 队色硬守卫；便服不触发）

# FIBA 半场模板尺寸（米，筐心为原点，y 向场内为正；模板画线用）
COURT_HALF_W: float = 7.5  # 半场宽 15m
COURT_RIM_TO_BASELINE_M: float = 1.575  # 筐心距端线
COURT_HALF_LEN_M: float = 14.0  # 半场深
PAINT_HALF_W: float = 2.45  # 禁区宽 4.9m
PAINT_LEN_M: float = 5.8  # 禁区长（端线→罚球线）
FREETHROW_R_M: float = 1.8  # 罚球弧半径
THREE_R_M: float = 6.75  # 三分半径（筐心为圆心）
THREE_CORNER_X: float = 6.6  # 三分角线 x（距边线 0.9m）


@dataclass(frozen=True, slots=True)
class HoopEvent:
    """hoops_batchK.json 单事件（detect_hoops 产物归一）。

    Attributes:
        fid: 视频主键。
        window: 事件时间窗 [t0, t1]（秒）。
        anchor: 筐锚点像素 (cx, cy)。
        detected: 是否检测到筐。
        track: 筐轨迹采样点 ((sec, x, y), ...)。
    """

    fid: str
    window: tuple[float, float]
    anchor: tuple[int, int]
    detected: bool
    track: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True, slots=True)
class HeatLanding:
    """单球热图落点记录；未覆盖时落点/坐标字段取 None。

    Attributes:
        event_key: 事件主键 ``fid@anchor_time``（goals 原值序列化）。
        team: 队别（roster players.team 原值；便服/查不到为 ""）。
        covered: 是否有可用落点。
        reason: 未覆盖原因（no_team/casual_team/missing_cache/no_track/
            no_track_near_anchor/no_seed/no_landing/no_hoop/team_mismatch）；
            覆盖时为 ""。team_mismatch = v4 队色硬守卫剔除（落点框中人队色
            与 roster 队伍期望队色明确相反）。
        path: 落点路径（"trace" 主路 / "track_start" 兜底）；未覆盖为 ""。
        frame_idx: 落点帧索引（-1 未覆盖）。
        landing_px: 人框底边中点像素。
        landing_box: 落点人框 (x1,y1,x2,y2)（目击拼图矩形用；None 未覆盖）。
        box_h_px: 落点人框高（像素，坐标尺度用；0 未覆盖）。
        hoop_xy: 锚点时刻筐心像素。
        hoop_degraded: hoops 零覆盖退化标记（WARNING 已记）。
        flipped: 筐端归一化翻转标记（大端 True）。
        rel_xy_m: 筐锚相对坐标（米，归一化后）。
    """

    event_key: str
    team: str
    covered: bool
    reason: str
    path: str
    frame_idx: int
    landing_px: tuple[float, float] | None
    landing_box: tuple[int, int, int, int] | None
    box_h_px: int
    hoop_xy: tuple[float, float] | None
    hoop_degraded: bool
    flipped: bool
    rel_xy_m: tuple[float, float] | None


def load_hoops(paths: list[Path]) -> list[HoopEvent]:
    """读取并校验 hoops_batchK.json（rules.md §0.2：schema 损坏显式失败）。

    Args:
        paths: hoops_batchK.json 路径列表（glob 发现）。

    Returns:
        全部事件（含未 detected，由使用方过滤）。

    Raises:
        SchemaError: 顶层非对象 / events 非列表 / 条目字段缺失或类型错。
    """
    events: list[HoopEvent] = []
    for path in paths:
        data: Any = read_json(path, what="hoops")
        if not isinstance(data, dict) or not isinstance(data.get("events"), list):
            raise SchemaError(f"{path}: 顶层必须是含 events 列表的对象")
        for i, raw in enumerate(data["events"]):
            if not isinstance(raw, dict):
                raise SchemaError(f"{path}: events[{i}] 不是对象")
            try:
                fid = str(raw["fid"])
                w = raw["window"]
                a = raw["anchor"]
                detected = bool(raw["detected"])
                track_raw = raw["track"]
                if not (isinstance(w, list) and len(w) == 2):
                    raise ValueError(f"window 不是 [t0,t1]: {w!r}")
                if not (isinstance(a, list) and len(a) == 2):
                    raise ValueError(f"anchor 不是 [cx,cy]: {a!r}")
                if not isinstance(track_raw, list):
                    raise ValueError(f"track 不是列表: {type(track_raw).__name__}")
                track: list[tuple[float, float, float]] = []
                for pt in track_raw:
                    if not (isinstance(pt, list) and len(pt) >= 3):
                        raise ValueError(f"track 采样点非法: {pt!r}")
                    track.append((float(pt[0]), float(pt[1]), float(pt[2])))
                events.append(
                    HoopEvent(
                        fid=fid,
                        window=(float(w[0]), float(w[1])),
                        anchor=(int(a[0]), int(a[1])),
                        detected=detected,
                        track=tuple(track),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SchemaError(f"{path}: events[{i}] 字段缺失/类型错: {exc}") from exc
    return events


def hoop_xy_at(
    hoops: list[HoopEvent],
    fid: str,
    anchor_sec: float,
    anchor_xy: tuple[int, int] | None,
) -> tuple[tuple[float, float], bool] | None:
    """取该 fid 在锚点时刻的筐心像素（spec v3 坐标口径写死）。

    优先 window 覆盖锚点 ±HOOP_WINDOW_TOL_SEC 的 detected 事件；多覆盖取
    track 采样时刻距锚点最近者，仍并列且 anchor_xy 非空时取事件锚点空间
    距离最近者；零覆盖退化为全部 detected 事件中采样时刻最近者（degraded=True）。

    Args:
        hoops: 全部 hoops 事件。
        fid: 视频主键。
        anchor_sec: 进球锚点（秒）。
        anchor_xy: candidates 锚点（并列取舍用；可为 None）。

    Returns:
        ((cx, cy), degraded)；该 fid 无任何 detected 事件返回 None。
    """
    pool_all: list[HoopEvent] = [ev for ev in hoops if ev.fid == fid and ev.detected and ev.track]
    if not pool_all:
        return None
    in_win: list[HoopEvent] = [
        ev
        for ev in pool_all
        if ev.window[0] - HOOP_WINDOW_TOL_SEC <= anchor_sec <= ev.window[1] + HOOP_WINDOW_TOL_SEC
    ]
    degraded: bool = not in_win
    pool: list[HoopEvent] = in_win or pool_all

    def _best(ev: HoopEvent) -> tuple[float, float, tuple[float, float]]:
        """(采样时刻最小差, 锚点空间距离, 时刻最近点)。"""
        pt = min(ev.track, key=lambda p: abs(p[0] - anchor_sec))
        dt = abs(pt[0] - anchor_sec)
        dist = 0.0
        if anchor_xy is not None:
            dist = math.hypot(ev.anchor[0] - anchor_xy[0], ev.anchor[1] - anchor_xy[1])
        return dt, dist, (pt[1], pt[2])

    best = min(pool, key=_best)
    return _best(best)[2], degraded


def flip_threshold(hoop_cxs: list[float]) -> float | None:
    """筐端切分阈值（cx 中位）；归一到 cx 较小端，大于阈值者 flipped=True。

    Args:
        hoop_cxs: 全部处理球的筐心 cx 列表。

    Returns:
        中位阈值；列表为空返回 None（不翻转）。
    """
    if not hoop_cxs:
        return None
    s: list[float] = sorted(hoop_cxs)
    n: int = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def to_rel_m(
    landing_px: tuple[float, float],
    hoop_xy: tuple[float, float],
    box_h_px: int,
    flipped: bool,
) -> tuple[float, float]:
    """落点像素 → 筐锚相对坐标（米；尺度 = 人框高 / PERSON_HEIGHT_M）。

    筐端归一化只镜像一个轴：场边机位下纵深方向（画面竖直轴）对两端筐
    一致（人总在筐的场内一侧），大端只需水平镜像 dx；dy 取反会把大端落点
    全部镜像到端线外（2026-08-15 实测：整组 dy∈[−4.3,−1.9] 全界外，
    不翻则 [+1.9,+4.3] 与小端组分布一致——实锤只翻 dx）。

    Args:
        landing_px: 人框底边中点像素。
        hoop_xy: 筐心像素。
        box_h_px: 人框高（像素）。
        flipped: 大端翻转标记（只翻 dx）。

    Returns:
        (dx, dy) 米制相对坐标（dy 图像向下 = 离筐向场内为正，不随翻转改变）。
    """
    scale: float = box_h_px / PERSON_HEIGHT_M
    dx: float = (landing_px[0] - hoop_xy[0]) / scale
    dy: float = (landing_px[1] - hoop_xy[1]) / scale
    if flipped:
        dx = -dx
    return dx, dy


def _team_at(frames_dir: Path, fid: str, frame_idx: int, box: Box) -> str:
    """读帧图判人框队色（串人守卫用）；帧图缺失记 WARNING 归便服（不剔除）。

    Args:
        frames_dir: 帧图根目录。
        fid: 视频主键。
        frame_idx: 帧索引（0-based；文件名 1-based）。
        box: 人框。

    Returns:
        "黑" / "白" / "便服"。

    Raises:
        OSError: 帧文件损坏（中间产物损坏显式失败，rules.md §0.2）。
    """
    img_path: Path = frames_dir / fid / f"f_{frame_idx + 1:05d}.jpg"
    if not img_path.is_file():
        logger.warning("串人守卫帧图缺失，归便服不剔除: %s", img_path)
        return "便服"
    with Image.open(img_path) as im:
        return team_of_box(im, box)


def find_landing(
    cache: MotCache,
    event: GoalEvent,
    anchor_xy: tuple[int, int] | None,
    frames_dir: Path,
    expect_color: str = "",
) -> tuple[str, str, int, Box | None]:
    """单球落点：两路并集 + v4 队色硬守卫（spec v4 落点口径写死）。

    主路 = 种子框（find_held_box / start_nearest_box，**均喂 sec ≤
    anchor−HELD_SEARCH_BEFORE_SEC 的截断轨迹**——v3 实测 22/27 错球种子在
    入网后，球穿网落进筐下人躯干框；截断为空则无种子直接落兜底）→
    trace_person 回追 → 链上最接近 anchor−RELEASE_BEFORE_SEC 帧
    （±TRACE_TOL_SEC）→ 串人守卫（黑↔白相反时主路不可用、视同链断走兜底）。
    兜底 = 原轨迹起点 ≥TRACK_START_MIN_SEC 前时取起点帧最近人框。
    队色硬守卫（v4 终闸）：两路落点产出后统一判——落点帧框中人队色与
    expect_color 明确相反 → uncovered(team_mismatch)；便服放行；
    expect_color 为空 → 守卫禁用。

    Args:
        cache: 校验后的 mot_cache。
        event: 进球事件。
        anchor_xy: candidates 锚点（None 退化端点时间最近）。
        frames_dir: 帧图根目录（串人守卫 + 队色硬守卫用）。
        expect_color: roster 队伍期望队色（"黑"/"白"；"" 守卫禁用）。

    Returns:
        (path, reason, frame_idx, box)；覆盖时 path ∈ {trace, track_start}、
        reason=""、box 非空；未覆盖时 path=""、reason 为原因、frame_idx=-1、
        box=None。
    """
    tracks = run_mot(track_window_dets(cache, event.anchor_time), min_length=1)
    if not tracks:
        return "", "no_track", -1, None
    track = select_goal_track(tracks, event.anchor_time, anchor_xy)
    if track is None:
        return "", "no_track_near_anchor", -1, None

    pre_dets: list[Detection] = [
        d for d in track.dets if d.sec <= event.anchor_time - HELD_SEARCH_BEFORE_SEC
    ]
    seed: tuple[Detection, Box] | None = None
    if pre_dets:
        pre_track = Track(dets=pre_dets)  # 新建实例不改原轨迹（兜底路仍用原起点）
        seed = find_held_box(pre_track, cache.persons)
        if seed is None:
            seed = start_nearest_box(pre_track, cache.persons)
    if seed is not None:
        seed_det, seed_box = seed
        chain: list[tuple[int, Box]] = trace_person(cache.persons, seed_det.frame_idx, seed_box)
        target_sec: float = event.anchor_time - RELEASE_BEFORE_SEC
        fi, box = min(chain, key=lambda ib: abs(ib[0] / SAMPLE_FPS - target_sec))
        if abs(fi / SAMPLE_FPS - target_sec) <= TRACE_TOL_SEC:
            seed_team: str = _team_at(frames_dir, event.fid, seed_det.frame_idx, seed_box)
            target_team: str = _team_at(frames_dir, event.fid, fi, box)
            if _OPPOSITE_TEAM.get(seed_team) != target_team:
                if _OPPOSITE_TEAM.get(target_team) == expect_color:
                    logger.info(
                        "队色硬守卫：%s 落点框色=%s 与期望=%s 相反，计 team_mismatch",
                        event.event_key,
                        target_team,
                        expect_color,
                    )
                    return "", "team_mismatch", -1, None
                return "trace", "", fi, box
            logger.info("串人守卫：%s 目标帧 %s 与种子相反，主路不可用走兜底", event.event_key, fi)

    first = track.dets[0]
    if event.anchor_time - first.sec >= TRACK_START_MIN_SEC:
        boxes: tuple[Box, ...] = cache.persons[first.frame_idx]
        if boxes:
            box = min(
                boxes,
                key=lambda b: math.hypot(first.cx - b.cx, first.cy - b.cy),
            )
            fb_team: str = _team_at(frames_dir, event.fid, first.frame_idx, box)
            if _OPPOSITE_TEAM.get(fb_team) == expect_color:
                logger.info(
                    "队色硬守卫（兜底）：%s 落点框色=%s 与期望=%s 相反，计 team_mismatch",
                    event.event_key,
                    fb_team,
                    expect_color,
                )
                return "", "team_mismatch", -1, None
            return "track_start", "", first.frame_idx, box
    return "", "no_landing", -1, None


# ---- 渲染（matplotlib Agg 后端；模板画线为纯函数便于测试）----


def court_template_lines() -> dict[str, Any]:
    """FIBA 半场模板画线参数（筐心原点，y 向场内为正；纯函数可测）。

    Returns:
        各线的坐标参数：端线/边线/中线/禁区矩形/罚球弧/三分弧与角线/筐与篮板。
    """
    baseline_y: float = -COURT_RIM_TO_BASELINE_M
    midline_y: float = COURT_HALF_LEN_M - COURT_RIM_TO_BASELINE_M
    paint_top_y: float = PAINT_LEN_M - COURT_RIM_TO_BASELINE_M
    corner_y: float = math.sqrt(THREE_R_M**2 - THREE_CORNER_X**2)
    return {
        "baseline": ((-COURT_HALF_W, baseline_y), (COURT_HALF_W, baseline_y)),
        "sidelines": (
            ((-COURT_HALF_W, baseline_y), (-COURT_HALF_W, midline_y)),
            ((COURT_HALF_W, baseline_y), (COURT_HALF_W, midline_y)),
        ),
        "midline": ((-COURT_HALF_W, midline_y), (COURT_HALF_W, midline_y)),
        "paint": (-PAINT_HALF_W, baseline_y, PAINT_HALF_W, paint_top_y),
        "freethrow_arc": ((0.0, paint_top_y), FREETHROW_R_M),
        "three_arc": ((0.0, 0.0), THREE_R_M),
        "three_corners": (
            ((-THREE_CORNER_X, baseline_y), (-THREE_CORNER_X, corner_y)),
            ((THREE_CORNER_X, baseline_y), (THREE_CORNER_X, corner_y)),
        ),
        "corner_y": corner_y,
        "rim": ((0.0, 0.0), 0.225),
        "backboard": ((-0.9, -1.2), (0.9, -1.2)),
    }


def _gaussian_blur(grid: np.ndarray, sigma_bins: float) -> np.ndarray:
    """可分离高斯平滑（手写，避免 scipy 依赖）。

    Args:
        grid: 2D 密度网格。
        sigma_bins: 平滑 sigma（格数）。

    Returns:
        平滑后的网格。
    """
    r: int = max(1, int(3 * sigma_bins))
    k: np.ndarray = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_bins) ** 2)
    k /= k.sum()
    grid = np.apply_along_axis(lambda row: np.convolve(row, k, mode="same"), 0, grid)
    return np.apply_along_axis(lambda row: np.convolve(row, k, mode="same"), 1, grid)


def render_team_heatmap(
    rel_points: list[tuple[float, float]], team: str, session: str, out_path: Path
) -> None:
    """渲染单队热图 PNG：FIBA 半场模板 + 高斯密度 + 落点散点。

    Args:
        rel_points: 该队全部落点的相对坐标（米）。
        team: 队名（标题与文件名用）。
        session: 场次 ID。
        out_path: 输出 PNG 路径。
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import patches

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(9, 8))
    lines = court_template_lines()
    if rel_points:
        xs = np.array([p[0] for p in rel_points])
        ys = np.array([p[1] for p in rel_points])
        x_edges = np.arange(-COURT_HALF_W, COURT_HALF_W + HEAT_BIN_M, HEAT_BIN_M)
        y_edges = np.arange(
            -COURT_RIM_TO_BASELINE_M, COURT_HALF_LEN_M - COURT_RIM_TO_BASELINE_M, HEAT_BIN_M
        )
        grid, _, _ = np.histogram2d(ys, xs, bins=[y_edges, x_edges])
        grid = _gaussian_blur(grid, HEAT_SIGMA_M / HEAT_BIN_M)
        # 低密度区掩掉（hot 色图 0 值发黑，不掩会全场罩灰底）
        masked = np.ma.masked_where(grid < 0.05 * grid.max(), grid)
        ax.imshow(
            masked,
            extent=[-COURT_HALF_W, COURT_HALF_W, y_edges[0], y_edges[-1]],
            origin="lower",
            cmap="hot",
            alpha=0.65,
            aspect="auto",
        )
        ax.scatter(xs, ys, s=42, facecolors="none", edgecolors="white", linewidths=1.2)
    for seg in (
        lines["baseline"],
        lines["midline"],
        *lines["sidelines"],
        *lines["three_corners"],
        lines["backboard"],
    ):
        ax.plot([seg[0][0], seg[1][0]], [seg[0][1], seg[1][1]], color="black", lw=1.5)
    px1, py1, px2, py2 = lines["paint"]
    ax.add_patch(patches.Rectangle((px1, py1), px2 - px1, py2 - py1, fill=False, lw=1.5))
    arc_c, arc_r = lines["freethrow_arc"]
    ax.add_patch(patches.Arc(arc_c, arc_r * 2, arc_r * 2, theta1=0, theta2=180, lw=1.5))
    theta = np.linspace(
        math.degrees(math.acos(THREE_CORNER_X / THREE_R_M)),
        180 - math.degrees(math.acos(THREE_CORNER_X / THREE_R_M)),
        60,
    )
    ax.plot(
        THREE_R_M * np.cos(np.radians(theta)),
        THREE_R_M * np.sin(np.radians(theta)),
        color="black",
        lw=1.5,
    )
    rim_c, rim_r = lines["rim"]
    ax.add_patch(patches.Circle(rim_c, rim_r, fill=False, color="red", lw=2))
    ax.set_xlim(-COURT_HALF_W - 0.4, COURT_HALF_W + 0.4)
    ax.set_ylim(-COURT_RIM_TO_BASELINE_M - 1.0, COURT_HALF_LEN_M - COURT_RIM_TO_BASELINE_M + 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"{session} 队伍_{team}_进球热图（n={len(rel_points)}）")
    ax.set_xlabel("米（筐心为原点）")
    ax.set_ylabel("米（离筐向场内）")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _audit_font(size: int) -> ImageFont.ImageFont:
    """取中文字体（微软雅黑），失败退回默认字体。"""
    for cand in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _audit_cell(
    frames_dir: Path,
    rec: HeatLanding,
    anchor_sec: float,
    fid: str,
    font: ImageFont.ImageFont,
) -> Image.Image:
    """拼单球目击单元：落点帧（人框+十字）与锚点帧并列 + 文字标注。"""
    cell_w, cell_h = 1280, 400
    cell = Image.new("RGB", (cell_w, cell_h), "white")

    def _load(frame_idx: int) -> Image.Image:
        p = frames_dir / fid / f"f_{frame_idx + 1:05d}.jpg"
        if not p.is_file():
            logger.warning("目击拼图帧图缺失，占位: %s", p)
            return Image.new("RGB", (640, 360), "gray")
        return Image.open(p).convert("RGB").resize((640, 360))

    landing_img = _load(rec.frame_idx)
    d = ImageDraw.Draw(landing_img)
    if rec.landing_px is not None:
        sx, sy = 640 / 1920, 360 / 1080
        if rec.landing_box is not None:
            bx1, by1, bx2, by2 = rec.landing_box
            d.rectangle([bx1 * sx, by1 * sy, bx2 * sx, by2 * sy], outline="yellow", width=3)
        cx, cy = rec.landing_px[0] * sx, rec.landing_px[1] * sy
        d.line([(cx - 12, cy), (cx + 12, cy)], fill="red", width=3)
        d.line([(cx, cy - 12), (cx, cy + 12)], fill="red", width=3)
    anchor_idx: int = round(anchor_sec * SAMPLE_FPS)
    anchor_img = _load(anchor_idx)
    cell.paste(landing_img, (0, 30))
    cell.paste(anchor_img, (640, 30))
    d = ImageDraw.Draw(cell)
    rel = rec.rel_xy_m
    rel_txt = f"({rel[0]:.1f},{rel[1]:.1f})m" if rel else "N/A"
    short_fid = fid.removeprefix("dji_mimo_")
    txt = (
        f"{short_fid}@{anchor_sec}  team={rec.team} path={rec.path} "
        f"rel={rel_txt} flipped={rec.flipped}"
    )
    d.text((6, 6), txt, fill="black", font=font)
    d.text((6, 374), "落点帧", fill="red", font=font)
    d.text((646, 374), "锚点帧", fill="blue", font=font)
    return cell


def build_audit_grid(
    records: list[HeatLanding],
    events: dict[str, GoalEvent],
    frames_dir: Path,
    out_path: Path,
) -> list[str]:
    """固定种子抽 15 个覆盖球拼目击图（供立哥肉眼验收）。

    Args:
        records: 全部落点记录（内部筛 covered）。
        events: event_key → 事件（取 anchor/fid）。
        frames_dir: 帧图根目录。
        out_path: 输出 PNG 路径。

    Returns:
        被抽中的 event_key 列表（报告用）。
    """
    covered: list[HeatLanding] = [r for r in records if r.covered]
    rng = random.Random(AUDIT_SEED)  # noqa: S311 非加密用途，固定种子仅为可复现抽样
    sample: list[HeatLanding] = rng.sample(covered, min(AUDIT_SAMPLE_N, len(covered)))
    font = _audit_font(20)
    cols = 3
    rows: int = math.ceil(len(sample) / cols) or 1
    grid = Image.new("RGB", (cols * 1280, rows * 400), "white")
    for i, rec in enumerate(sample):
        ev = events[rec.event_key]
        cell = _audit_cell(frames_dir, rec, ev.anchor_time, ev.fid, font)
        grid.paste(cell, ((i % cols) * 1280, (i // cols) * 400))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path)
    return [r.event_key for r in sample]


# ---- 主流程 ----


def _uncovered(event_key: str, team: str, reason: str) -> HeatLanding:
    """构造未覆盖记录（写死形态：-1/0/None，字段不省略）。"""
    return HeatLanding(
        event_key=event_key,
        team=team,
        covered=False,
        reason=reason,
        path="",
        frame_idx=-1,
        landing_px=None,
        landing_box=None,
        box_h_px=0,
        hoop_xy=None,
        hoop_degraded=False,
        flipped=False,
        rel_xy_m=None,
    )


def heat_session(
    session_dir: Path, detect_dir: Path, frames_dir: Path, out_dir: Path
) -> dict[str, Any]:
    """全量热图流程：落点两路并集 → 筐端归一化坐标 → JSON + 热图 + 目击拼图。

    Args:
        session_dir: work/<场次> 目录（roster/goals/candidates/hoops）。
        detect_dir: mot_cache 目录。
        frames_dir: 帧图根目录。
        out_dir: 热图 PNG 输出目录（output/<场次>）。

    Returns:
        报告字典（summary / landings），已原子写入 goal_landings.json。

    Raises:
        BasketballPipelineError: roster.json 缺失 / 无 goals / 无 candidates / 无 hoops。
        SchemaError: 任一输入 schema 损坏。
    """
    roster_path: Path = session_dir / "roster.json"
    if not roster_path.is_file():
        raise BasketballPipelineError(f"roster.json 不存在: {roster_path}（先完成认人导出）")
    roster = validate_roster(read_json(roster_path, what="roster.json"), str(roster_path))
    tag2team: dict[str, str] = {p.tag: p.team for p in roster.players}
    # v4 队色硬守卫映射（按场次注入；缺失 → 守卫禁用 + WARNING，不静默）
    team_color: dict[str, str] = {}
    facts_path: Path = session_dir / "session_facts.json"
    if facts_path.is_file():
        facts: Any = read_json(facts_path, what="session_facts.json")
        if isinstance(facts, dict) and isinstance(facts.get("team_color"), dict):
            team_color = {str(k): str(v) for k, v in facts["team_color"].items()}
    if not team_color:
        logger.warning("session_facts.json 无 team_color 键，队色硬守卫禁用（退化 v3 行为）")
    else:
        roster_teams: set[str] = {p.team for p in roster.players if p.team != TEAM_CASUAL}
        for t in sorted(roster_teams - set(team_color)):
            logger.warning("team_color 缺队伍映射，该队队色硬守卫禁用: %s", t)
    goals_files: list[Path] = sorted(session_dir.glob("goals_batch*.json"))
    cand_files: list[Path] = sorted(session_dir.glob("candidates_batch*.json"))
    hoops_files: list[Path] = sorted(session_dir.glob("hoops_batch*.json"))
    if not goals_files:
        raise BasketballPipelineError(f"{session_dir} 下无 goals_batch*.json")
    if not cand_files:
        raise BasketballPipelineError(f"{session_dir} 下无 candidates_batch*.json")
    if not hoops_files:
        raise BasketballPipelineError(f"{session_dir} 下无 hoops_batch*.json（先跑 score）")
    events: dict[str, GoalEvent] = {}
    for gf in goals_files:
        for e in load_goals_events(gf):
            if e.event_key in events:
                raise SchemaError(f"跨批次事件重复: {e.event_key}")
            events[e.event_key] = e
    cand_index = load_merged_candidates(cand_files)
    hoops: list[HoopEvent] = load_hoops(hoops_files)
    logger.info(
        "goals %d 事件 / roster 已归属 %d 球 / hoops %d 事件",
        len(events),
        len(roster.assignments),
        len(hoops),
    )

    caches: dict[str, MotCache] = {}
    records: list[HeatLanding] = []
    hoop_cxs: list[float] = []
    for e in events.values():
        rkey: str = format_key(f"{e.fid}.mp4", e.anchor_time)
        tag: str | None = roster.assignments.get(rkey)
        if tag is None:
            continue  # 未标记的球不管（立哥原话）
        team: str = tag2team.get(tag, "")
        if not team:
            logger.warning("tag 查不到 team，计 uncovered: %s tag=%s", e.event_key, tag)
            records.append(_uncovered(e.event_key, "", "no_team"))
            continue
        if team == TEAM_CASUAL:
            logger.warning("便服归属不进热图（计分母）: %s tag=%s", e.event_key, tag)
            records.append(_uncovered(e.event_key, team, "casual_team"))
            continue
        cache_path: Path = detect_dir / f"{e.fid}_mot_cache.json"
        if not cache_path.exists():
            logger.warning("缺 mot_cache，计 uncovered: %s", e.event_key)
            records.append(_uncovered(e.event_key, team, "missing_cache"))
            continue
        if e.fid not in caches:
            caches[e.fid] = load_mot_cache(cache_path)
        anchor_xy = match_anchor_xy(cand_index, e.fid, e.anchor_time)
        path, reason, fi, box = find_landing(
            caches[e.fid], e, anchor_xy, frames_dir, expect_color=team_color.get(team, "")
        )
        if box is None:
            records.append(_uncovered(e.event_key, team, reason))
            continue
        hoop = hoop_xy_at(hoops, e.fid, e.anchor_time, anchor_xy)
        if hoop is None:
            logger.warning("该 fid 无 detected hoops 事件，计 uncovered: %s", e.event_key)
            records.append(_uncovered(e.event_key, team, "no_hoop"))
            continue
        (hx, hy), degraded = hoop
        if degraded:
            logger.warning("hoops 零覆盖退化（window 不含锚点）: %s", e.event_key)
        landing_px: tuple[float, float] = ((box.x1 + box.x2) / 2.0, float(box.y2))
        records.append(
            HeatLanding(
                event_key=e.event_key,
                team=team,
                covered=True,
                reason="",
                path=path,
                frame_idx=fi,
                landing_px=landing_px,
                landing_box=(box.x1, box.y1, box.x2, box.y2),
                box_h_px=box.y2 - box.y1,
                hoop_xy=(hx, hy),
                hoop_degraded=degraded,
                flipped=False,  # 第二遍统一填
                rel_xy_m=None,
            )
        )
        hoop_cxs.append(hx)

    # 第二遍：筐端归一化（cx 中位切两端，归一小端，大端取反）+ 相对坐标
    threshold: float | None = flip_threshold(hoop_cxs)
    final: list[HeatLanding] = []
    for r in records:
        if not r.covered or r.landing_px is None or r.hoop_xy is None:
            final.append(r)
            continue
        flipped: bool = threshold is not None and r.hoop_xy[0] > threshold
        rel: tuple[float, float] = to_rel_m(r.landing_px, r.hoop_xy, r.box_h_px, flipped)
        final.append(
            HeatLanding(
                event_key=r.event_key,
                team=r.team,
                covered=True,
                reason="",
                path=r.path,
                frame_idx=r.frame_idx,
                landing_px=r.landing_px,
                landing_box=r.landing_box,
                box_h_px=r.box_h_px,
                hoop_xy=r.hoop_xy,
                hoop_degraded=r.hoop_degraded,
                flipped=flipped,
                rel_xy_m=rel,
            )
        )

    total: int = len(final)
    n_covered: int = sum(1 for r in final if r.covered)
    coverage: float = n_covered / total if total else 0.0
    by_path: dict[str, int] = {}
    uncovered_by_reason: dict[str, int] = {}
    teams_dist: dict[str, int] = {}
    for r in final:
        if r.covered:
            by_path[r.path] = by_path.get(r.path, 0) + 1
            teams_dist[r.team] = teams_dist.get(r.team, 0) + 1
        else:
            uncovered_by_reason[r.reason] = uncovered_by_reason.get(r.reason, 0) + 1
    report: dict[str, Any] = {
        "session": session_dir.name,
        "generated_at": datetime.now(UTC).isoformat(),
        "params": {
            "release_before_sec": RELEASE_BEFORE_SEC,
            "held_search_before_sec": HELD_SEARCH_BEFORE_SEC,
            "trace_tol_sec": TRACE_TOL_SEC,
            "track_start_min_sec": TRACK_START_MIN_SEC,
            "person_height_m": PERSON_HEIGHT_M,
            "coverage_min_ratio": COVERAGE_MIN_RATIO,
            "flip_threshold_cx": threshold,
            "team_color_guard": bool(team_color),
        },
        "summary": {
            "total_marked": total,
            "covered": n_covered,
            "coverage": round(coverage, 4),
            "coverage_pass": coverage >= COVERAGE_MIN_RATIO,
            "by_path": by_path,
            "uncovered_by_reason": uncovered_by_reason,
            "teams": teams_dist,
            "casual_excluded": uncovered_by_reason.get("casual_team", 0),
            "hoop_degraded": sum(1 for r in final if r.hoop_degraded),
        },
        "landings": [asdict(r) for r in final],
    }
    out_json: Path = session_dir / "goal_landings.json"
    atomic_write_json(out_json, report, what="goal_landings.json")

    for team in sorted(teams_dist):
        pts: list[tuple[float, float]] = [
            r.rel_xy_m for r in final if r.covered and r.team == team and r.rel_xy_m is not None
        ]
        png: Path = out_dir / f"队伍_{team}_进球热图.png"
        render_team_heatmap(pts, team, session_dir.name, png)
        logger.info("热图已出: %s（n=%d）", png, len(pts))
    audit_keys: list[str] = build_audit_grid(
        final, events, frames_dir, session_dir / "heatmap_audit.png"
    )
    logger.info("目击拼图已出（%d 球）: %s", len(audit_keys), session_dir / "heatmap_audit.png")

    logger.info("==== 热图 v4 覆盖率汇总 ====")
    logger.info(
        "覆盖率: %d/%d = %.1f%%（阈值 %.0f%%）→ %s",
        n_covered,
        total,
        coverage * 100,
        COVERAGE_MIN_RATIO * 100,
        "过关" if report["summary"]["coverage_pass"] else "未过关",
    )
    logger.info("路径分布: %s；未覆盖原因: %s", by_path, uncovered_by_reason)
    logger.info(
        "分队: %s；筐端阈值 cx=%s；hoops 退化 %d",
        teams_dist,
        threshold,
        report["summary"]["hoop_degraded"],
    )
    logger.info("报告已落盘: %s", out_json)
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """解析 CLI 参数。"""
    parser = argparse.ArgumentParser(description="球队进球热图生成（热图 v4）")
    parser.add_argument("--sessiondir", required=True, type=Path, help="work/<场次> 目录")
    parser.add_argument(
        "--detectdir", type=Path, default=None, help="mot_cache 目录（默认 <sessiondir>/../detect）"
    )
    parser.add_argument(
        "--framesdir", type=Path, default=None, help="帧图根目录（默认 <sessiondir>/../frames）"
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="热图 PNG 输出目录（默认 <repo>/output/<场次>）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。返回进程退出码（0=完成，非 0=失败；覆盖率未过关不算失败）。"""
    args = _parse_args(argv)
    run_id: str = new_run_id()
    configure_logging(run_id)
    session_dir: Path = args.sessiondir
    detect_dir: Path = args.detectdir or session_dir.parent / "detect"
    frames_dir: Path = args.framesdir or session_dir.parent / "frames"
    out_dir: Path = args.outdir or session_dir.parent.parent / "output" / session_dir.name
    try:
        heat_session(session_dir, detect_dir, frames_dir, out_dir)
    except BasketballPipelineError as e:
        logger.error("热图生成失败 run_id=%s: %s", run_id, e, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
