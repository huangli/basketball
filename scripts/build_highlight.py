#!/usr/bin/env python3
"""个人进球合集合成（按剪辑规格）。

按 goals.json 中的记录切片：窗口 [anchor-4s, anchor+2s]，输出
1440x1080（保持 4:3）、50fps、H.264+AAC；100fps 素材入网后 2 秒
半速慢放（slowmo=true 时两段拼接）。同参数 concat 直接重封装。
产物：output/<场次>/个人_<标签>_进球合集.mp4。

输入：--goals 指定的 goals.json（status=confirmed 记录；schema 损坏抛 SchemaError）
输出：output/<场次>/个人_<标签>_进球合集.mp4
依赖：scripts/errors.py、scripts/pipe_common.py（run_ffmpeg/read_json/日志）
用法:
    python scripts/build_highlight.py --goals work/pilot/goals.json --scorer 大斌
"""

import contextlib
import logging
import os
import sys
import time
from typing import Any

from errors import BasketballPipelineError, SchemaError
from pipe_common import configure_logging, new_run_id, read_json, run_ffmpeg

logger = logging.getLogger(__name__)

RAW_DIR: str = "archive/0_raw_videos_test"  # 测试素材已归档；新场次用 --goals 内文件名对应目录
OUT_ROOT: str = "output"
OUT_W: int = 1440
OUT_H: int = 1080
OUT_FPS: int = 50
CRF: int = 20
PRESET: str = "medium"
CLIP_BEFORE_SEC: float = 4.0
CLIP_AFTER_SEC: float = 2.0

# 画面滤镜：缩放保持宽高比（force_original_aspect_ratio=decrease），不足处黑边补齐，
# 防 16:9 新素材被压扁；输出尺寸仍按 4:3 老素材写死，场次尺寸参数化是后续待办
SCALE_PAD_FILTER: str = (
    f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,"
    f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2"
)
# goals.json status 合法值（SPEC_2026-07-19 §status 流转定义）；仅 confirmed 进合成
KNOWN_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "clipped", "done", "rejected", "removed", "uncertain"}
)
# 慢放段（无现场声）配的静音轨：立体声 48kHz，与原片音轨参数一致，保证 concat 流布局一致
SILENT_AUDIO_SRC: str = "anullsrc=channel_layout=stereo:sample_rate=48000"


def parse_argv() -> tuple[str, str]:
    """解析命令行参数。

    Returns:
        (goals.json 路径, scorer 标签；空串表示全部)。
    """
    goals: str = ""
    scorer: str = ""
    args: list[str] = sys.argv[1:]
    i: int = 0
    while i < len(args):
        if args[i] == "--goals" and i + 1 < len(args):
            goals = args[i + 1]
            i += 2
        elif args[i] == "--scorer" and i + 1 < len(args):
            scorer = args[i + 1]
            i += 2
        else:
            i += 1
    return goals, scorer


def _encode_timeout_sec(duration_sec: float) -> int:
    """ffmpeg 转码超时：片段时长 ×3 + 60s 兜底，下限 120s（rules.md §4）。

    Args:
        duration_sec: 输入片段时长（秒）。

    Returns:
        超时秒数。
    """
    return max(120, int(duration_sec * 3) + 60)


def _validate_goals(data: dict[str, Any], goals_path: str) -> list[dict[str, Any]]:
    """校验 goals.json 结构，返回 status=="confirmed" 的记录列表。

    顶层必须是含 goals 列表的对象；每条记录 status 必须为 str，未知
    status 值记 WARNING（可能拼错）并跳过；confirmed 记录必须有
    file(str)、anchor_time/clip_start/clip_end(数值) 且满足
    clip_start <= anchor_time <= clip_end。

    Args:
        data: read_json 读出的 goals.json 内容。
        goals_path: 文件路径（仅用于错误信息）。

    Returns:
        校验通过的 confirmed 记录（未按 scorer 过滤）。

    Raises:
        SchemaError: 结构损坏（缺字段/类型错/时间区间错），信息含路径与记录索引。
    """
    if not isinstance(data, dict):
        raise SchemaError(f"{goals_path}: 顶层必须是对象，实际 {type(data).__name__}")
    goals: Any = data.get("goals")
    if not isinstance(goals, list):
        raise SchemaError(f"{goals_path}: 缺 goals 列表或类型错误，实际 {type(goals).__name__}")
    confirmed: list[dict[str, Any]] = []
    for i, g in enumerate(goals):
        if not isinstance(g, dict):
            raise SchemaError(f"{goals_path}: 第{i}条记录不是对象，实际 {type(g).__name__}")
        status: Any = g.get("status")
        if not isinstance(status, str):
            raise SchemaError(
                f"{goals_path}: 第{i}条 status 必须是 str，实际 {type(status).__name__}"
            )
        if status not in KNOWN_STATUSES:
            logger.warning("%s: 第%d条未知 status=%r（可能拼错），跳过", goals_path, i, status)
            continue
        if status != "confirmed":
            continue
        if not isinstance(g.get("file"), str) or not g["file"]:
            raise SchemaError(f"{goals_path}: 第{i}条(confirmed) file 缺失或不是非空 str")
        for key in ("anchor_time", "clip_start", "clip_end"):
            v: Any = g.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise SchemaError(
                    f"{goals_path}: 第{i}条(confirmed) {key} 缺失或不是数值，"
                    f"实际 {type(v).__name__}"
                )
        if not g["clip_start"] <= g["anchor_time"] <= g["clip_end"]:
            raise SchemaError(
                f"{goals_path}: 第{i}条(confirmed) 时间区间错误: "
                f"clip_start={g['clip_start']} anchor_time={g['anchor_time']} "
                f"clip_end={g['clip_end']}（要求 clip_start<=anchor_time<=clip_end）"
            )
        confirmed.append(g)
    return confirmed


def cut_normal(src: str, goal: dict[str, Any], out_path: str) -> None:
    """常速切片（50fps 素材）。

    Args:
        src: 原片路径。
        goal: 进球记录（clip_start/clip_end）。
        out_path: 输出片段路径。
    """
    run_ffmpeg(
        [
            "-ss",
            f"{goal['clip_start']:.2f}",
            "-to",
            f"{goal['clip_end']:.2f}",
            "-i",
            src,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            f"{SCALE_PAD_FILTER},fps={OUT_FPS}",
            "-c:v",
            "libx264",
            "-crf",
            str(CRF),
            "-preset",
            PRESET,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            out_path,
        ],
        timeout_sec=_encode_timeout_sec(goal["clip_end"] - goal["clip_start"]),
    )


def cut_slowmo(src: str, goal: dict[str, Any], out_path: str) -> None:
    """100fps 素材：入网前常速(降50fps)、入网后 2 秒半速慢放，两段拼接。

    part2 滤镜顺序必须是 scale/pad → setpts 拉伸时间轴 → fps 重采样
    （先 fps 会把 100fps 抽掉一半帧，输出只剩有效 25fps）；part1 保留
    现场声、part2 配 lavfi 静音轨，part1/part2/cut_normal 三者流布局
    一致（h264/yuv420p/1440x1080/50fps + aac）才能 -c copy 直接拼接。

    Args:
        src: 原片路径。
        goal: 进球记录（clip_start/anchor_time/clip_end）。
        out_path: 输出片段路径。
    """
    anchor: float = goal["anchor_time"]
    part1: str = out_path.replace(".mp4", "_p1.mp4")
    part2: str = out_path.replace(".mp4", "_p2.mp4")
    run_ffmpeg(
        [
            "-ss",
            f"{goal['clip_start']:.2f}",
            "-to",
            f"{anchor:.2f}",
            "-i",
            src,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            f"{SCALE_PAD_FILTER},fps={OUT_FPS}",
            "-c:v",
            "libx264",
            "-crf",
            str(CRF),
            "-preset",
            PRESET,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            part1,
        ],
        timeout_sec=_encode_timeout_sec(anchor - goal["clip_start"]),
    )
    run_ffmpeg(
        [
            "-ss",
            f"{anchor:.2f}",
            "-to",
            f"{goal['clip_end']:.2f}",
            "-i",
            src,
            "-f",
            "lavfi",
            "-i",
            SILENT_AUDIO_SRC,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            f"{SCALE_PAD_FILTER},setpts=PTS*2.0,fps={OUT_FPS}",
            "-c:v",
            "libx264",
            "-crf",
            str(CRF),
            "-preset",
            PRESET,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            part2,
        ],
        timeout_sec=_encode_timeout_sec(goal["clip_end"] - anchor),
    )
    list_path: str = out_path.replace(".mp4", "_concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.basename(part1)}'\nfile '{os.path.basename(part2)}'\n")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    for p in (part1, part2, list_path):
        os.remove(p)


def main() -> int:
    """主入口：按 goals.json 合成个人合集。

    Returns:
        进程退出码：0=全部成功；1=参数/数据/合成失败，或有进球因原片缺失被跳过。
    """
    run_id = new_run_id()
    configure_logging(run_id)
    goals_path, scorer = parse_argv()
    if not goals_path:
        logger.error("缺少 --goals 参数")
        return 1
    try:
        data: dict[str, Any] = read_json(goals_path, what="goals.json")
        goals: list[dict[str, Any]] = _validate_goals(data, goals_path)
        session: str = data.get("session", "unknown")
        goals = [g for g in goals if not scorer or g.get("scorer") == scorer]
        goals.sort(key=lambda g: (g["file"], g["anchor_time"]))
        if not goals:
            logger.error("无可合成记录 (scorer=%s)", scorer or "全部")
            return 1

        out_dir: str = os.path.join(OUT_ROOT, session)
        os.makedirs(out_dir, exist_ok=True)
        work_dir: str = os.path.join(out_dir, "_clips_tmp")
        os.makedirs(work_dir, exist_ok=True)

        t_start: float = time.time()
        clips: list[str] = []
        missing: list[str] = []
        for i, goal in enumerate(goals, 1):
            src: str = os.path.join(RAW_DIR, goal["file"])
            if not os.path.exists(src):
                logger.error("原片缺失，跳过: %s", goal["file"])
                missing.append(goal["file"])
                continue
            clip: str = os.path.join(work_dir, f"clip_{i:03d}.mp4")
            if goal.get("slowmo"):
                cut_slowmo(src, goal, clip)
            else:
                cut_normal(src, goal, clip)
            clips.append(clip)
            logger.info(
                "  片段 %d/%d: %s @%.1fs%s",
                i,
                len(goals),
                goal["file"],
                goal["anchor_time"],
                "(慢放)" if goal.get("slowmo") else "",
            )

        if not clips:
            logger.error("全部原片缺失（%d 条），无产出", len(missing))
            return 1

        list_path: str = os.path.join(work_dir, "concat.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for clip in clips:
                f.write(f"file '{os.path.basename(clip)}'\n")
        tag: str = scorer or "全员"
        out_path: str = os.path.join(out_dir, f"个人_{tag}_进球合集.mp4")
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                out_path,
            ]
        )
        for clip in clips:
            os.remove(clip)
        os.remove(list_path)
        with contextlib.suppress(OSError):
            os.rmdir(work_dir)
        logger.info(
            "合集完成: %s (%d 片段, %.0fs)",
            out_path,
            len(clips),
            time.time() - t_start,
        )
        if missing:
            logger.error(
                "合集已产出，但 %d 条进球因原片缺失被跳过: %s",
                len(missing),
                ", ".join(missing),
            )
            return 1
        return 0
    except BasketballPipelineError as exc:
        logger.error("管线失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1
    except OSError as exc:
        logger.error("IO 失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
