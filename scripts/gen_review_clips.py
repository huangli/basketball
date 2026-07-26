#!/usr/bin/env python3
"""生成候选审核视频（供立哥人工标注 进球/非进球）。

读取 work/label/candidates.json，先把同一文件的候选按时间间隔聚类为
"事件"（同一进球常触发多个候选，重叠片段重复观看浪费审核时间），
每个事件只出一个片段：覆盖 [首候选-2s, 末候选+2s]，裁剪框包住事件内
全部候选位置，缩放 840x840 并烧录事件编号水印，按文件拼成一个审核 mp4。

输入：--candidates 指定的 candidates.json（schema 损坏抛 SchemaError）；
    --vlmcache 指定的 VLM 缓存 JSON（可选；损坏仅记 WARNING 并忽略判定水印）
输出：<outdir>/<fid>_events.mp4
依赖：scripts/errors.py、scripts/pipe_common.py（run_ffmpeg/read_json/日志）
用法:
    python scripts/gen_review_clips.py --candidates work/label/candidates.json
"""

import logging
import os
import sys
import time
from glob import glob
from typing import Any

from errors import BasketballPipelineError, SchemaError
from pipe_common import configure_logging, new_run_id, read_json, run_ffmpeg

logger = logging.getLogger(__name__)

CANDIDATES_JSON: str = "work/label/candidates.json"
RAW_GLOB: str = "archive/0_raw_videos_test/**/*_{fid}_D.MP4"  # 测试素材已归档；新场次处理时参数化
OUT_DIR: str = "work/review"

CLUSTER_GAP_SEC: float = 2.0  # 候选间隔 <= 该值归为同一事件（同进球触发候选实测间隔 <=1.7s）
CLIP_BEFORE_SEC: float = 2.0  # 片段起点：事件首候选前
CLIP_AFTER_SEC: float = 2.0  # 片段终点：事件末候选后
MIN_HALF_IMG: int = 420  # img 系裁剪半径
ORIG_W: int = 3840
ORIG_H: int = 2880
OUT_SIDE: int = 840
OUT_FPS: int = 30
SPEED: float = 2.0  # 审核视频加速倍率（立哥可分辨；声音用 atempo 同步保留）
FONT_PATH: str = "C\\:/Windows/Fonts/arialbd.ttf"

# candidates.json 每条记录的必需字段（本脚本实际消费的字段：聚类/裁剪/水印）
REQUIRED_STR_FIELDS: tuple[str, ...] = ("fid", "label")
REQUIRED_NUM_FIELDS: tuple[str, ...] = ("t0", "ac", "cx", "cy")


def find_source(fid: str) -> str | None:
    """按文件 ID 递归查找原片路径。

    Args:
        fid: 文件 ID（如 0011）。

    Returns:
        原片路径；找不到或找到多个返回 None。
    """
    matches: list[str] = glob(RAW_GLOB.format(fid=fid), recursive=True)
    if len(matches) != 1:
        logger.error("%s: 原片匹配数=%d，跳过", fid, len(matches))
        return None
    return matches[0]


def cluster_candidates(
    cands: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """把按 t0 排序的候选按 CLUSTER_GAP_SEC 间隔聚类为事件。

    Args:
        cands: 候选列表（任意顺序）。

    Returns:
        事件列表，每个事件是候选列表（按 t0 升序）。
    """
    clusters: list[list[dict[str, Any]]] = []
    for c in sorted(cands, key=lambda c: c["t0"]):
        if clusters and c["t0"] - clusters[-1][-1]["t0"] <= CLUSTER_GAP_SEC:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    return clusters


def _encode_timeout_sec(duration_sec: float) -> int:
    """ffmpeg 转码超时：片段时长 ×3 + 60s 兜底，下限 120s（rules.md §4）。

    Args:
        duration_sec: 输入片段时长（秒）。

    Returns:
        超时秒数。
    """
    return max(120, int(duration_sec * 3) + 60)


def _validate_candidates(data: Any, path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """校验 candidates.json 结构，返回候选记录列表。

    顶层必须是记录列表；每条记录必须含 fid/label(str) 与
    t0/ac/cx/cy(数值)——即聚类、裁剪、水印实际消费的字段。

    Args:
        data: read_json 读出的 candidates.json 内容。
        path: 文件路径（仅用于错误信息）。

    Returns:
        校验通过的候选记录列表。

    Raises:
        SchemaError: 结构损坏（顶层非列表/记录非对象/缺字段/类型错），
            信息含路径与记录索引。
    """
    if not isinstance(data, list):
        raise SchemaError(f"{path}: 顶层必须是记录列表，实际 {type(data).__name__}")
    for i, r in enumerate(data):
        if not isinstance(r, dict):
            raise SchemaError(f"{path}: 第{i}条记录不是对象，实际 {type(r).__name__}")
        for key in REQUIRED_STR_FIELDS:
            if not isinstance(r.get(key), str):
                raise SchemaError(
                    f"{path}: 第{i}条 {key} 缺失或不是 str，实际 {type(r.get(key)).__name__}"
                )
        for key in REQUIRED_NUM_FIELDS:
            v = r.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise SchemaError(f"{path}: 第{i}条 {key} 缺失或不是数值，实际 {type(v).__name__}")
    return data


def _load_vlm_cache(path: str) -> dict[str, Any]:
    """读取 VLM 判定缓存；未提供/缺失/损坏仅记 WARNING 并返回空（水印是可选项）。

    Args:
        path: VLM 缓存 JSON 路径；空串表示未提供。

    Returns:
        缓存 dict（键 "<fid>#N@尺度"）；不可用时空 dict。
    """
    if not path or not os.path.exists(path):
        return {}
    try:
        data = read_json(path, what="VLM 缓存")
    except (SchemaError, OSError) as exc:
        logger.warning("VLM 缓存读取失败(%s)，忽略判定水印: %s", exc, path)
        return {}
    if not isinstance(data, dict):
        logger.warning("VLM 缓存顶层不是对象，忽略判定水印: %s", path)
        return {}
    return data


def cluster_crop(members: list[dict[str, Any]]) -> tuple[int, int, int]:
    """计算事件的裁剪参数（原片系）：以 conf 最高候选为中心的正方形。

    事件内候选位置可能散布（含 FP 成员），包围盒会过度拉远画面；
    审核关注点是真球/筐区，取 conf 最高者为中心。

    Args:
        members: 事件内候选（cx/cy 为 img 系坐标）。

    Returns:
        (crop_x, crop_y, side)，均已收敛到原片范围内。
    """
    best: dict[str, Any] = max(members, key=lambda m: m["ac"])
    side: int = MIN_HALF_IMG * 4  # img 半径 -> 原片边长（坐标系 2 倍 + 双边 2 倍）
    crop_x: int = min(max(2 * best["cx"] - side // 2, 0), ORIG_W - side)
    crop_y: int = min(max(2 * best["cy"] - side // 2, 0), ORIG_H - side)
    return crop_x, crop_y, side


def cut_cluster_clip(
    src: str,
    fid: str,
    idx: int,
    members: list[dict[str, Any]],
    out_path: str,
    verdict: str = "",
) -> None:
    """裁出单个事件的审核片段（包围裁剪 + 事件编号水印）。

    Args:
        src: 原片路径。
        fid: 文件 ID。
        idx: 事件编号（1 起）。
        members: 事件内候选列表（按 t0 升序）。
        out_path: 输出片段路径。
        verdict: 可选 VLM 判定水印（如 "VLM:Y"）。
    """
    start: float = max(0.0, members[0]["t0"] - CLIP_BEFORE_SEC)
    end: float = members[-1]["t0"] + CLIP_AFTER_SEC
    crop_x, crop_y, side = cluster_crop(members)
    text: str = (
        f"#{idx} {fid} t={members[0]['t0']:.1f}-{members[-1]['t0']:.1f}s ({len(members)}cand)"
    )
    if verdict:
        text = f"{text} {verdict}"
    text = text.replace("\\", "\\\\").replace(":", "\\:")  # drawtext 选项分隔符转义
    vf: str = (
        f"crop={side}:{side}:{crop_x}:{crop_y},"
        f"scale={OUT_SIDE}:{OUT_SIDE},fps={OUT_FPS},"
        f"setpts=PTS/{SPEED},"
        f"drawtext=fontfile='{FONT_PATH}':text='{text}':"
        f"x=15:y=15:fontsize=30:fontcolor=yellow:"
        f"box=1:boxcolor=black@0.8"
    )
    run_ffmpeg(
        [
            "-ss",
            f"{start:.2f}",
            "-to",
            f"{end:.2f}",
            "-i",
            src,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            vf,
            "-af",
            f"atempo={SPEED}",
            "-c:v",
            "libx264",
            "-crf",
            "22",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            out_path,
        ],
        timeout_sec=_encode_timeout_sec(end - start),
    )


def concat_clips(clips: list[str], list_path: str, out_path: str) -> None:
    """同参数片段 concat 重封装为单文件。

    Args:
        clips: 片段路径列表（同目录）。
        list_path: concat 清单文件路径。
        out_path: 输出视频路径。
    """
    with open(list_path, "w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{os.path.basename(clip)}'\n")
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


def parse_argv() -> tuple[str, str, str]:
    """解析命令行参数。

    Returns:
        (candidates 路径, 输出目录, VLM 缓存路径；无则空串)。
    """
    candidates: str = CANDIDATES_JSON
    out_dir: str = OUT_DIR
    vlm_cache: str = ""
    args: list[str] = sys.argv[1:]
    i: int = 0
    while i < len(args):
        if args[i] == "--candidates" and i + 1 < len(args):
            candidates = args[i + 1]
            i += 2
        elif args[i] == "--outdir" and i + 1 < len(args):
            out_dir = args[i + 1]
            i += 2
        elif args[i] == "--vlmcache" and i + 1 < len(args):
            vlm_cache = args[i + 1]
            i += 2
        else:
            i += 1
    return candidates, out_dir, vlm_cache


def event_verdict(members: list[dict[str, Any]], vlm: dict[str, Any]) -> str:
    """事件的 VLM 判定：任一成员任一尺度判 YES 即 Y。

    Args:
        members: 事件内候选。
        vlm: VLM 缓存（键 "<fid>#N@尺度"）。

    Returns:
        "VLM:Y" / "VLM:N"（至少一个成员有有效判定）/ ""（全部未判）。
    """
    if not vlm:
        return ""
    n_judged: int = 0
    for m in members:
        key: str = f"{m['fid']}{m['label']}"
        for half in (420, 630):
            ans: str = vlm.get(f"{key}@{half}", {}).get("answer", "")
            if ans == "YES":
                return "VLM:Y"
            if ans == "NO":
                n_judged += 1
    return "VLM:N" if n_judged else ""


def main() -> int:
    """主入口：按文件生成事件级候选审核视频。

    Returns:
        进程退出码：0=成功；1=数据损坏/IO 失败/合成失败/有原片缺失。
    """
    run_id = new_run_id()
    configure_logging(run_id)
    candidates_path, out_dir, vlm_cache_path = parse_argv()
    try:
        os.makedirs(out_dir, exist_ok=True)
        records: list[dict[str, Any]] = _validate_candidates(
            read_json(candidates_path, what="candidates.json"), candidates_path
        )
        vlm: dict[str, Any] = _load_vlm_cache(vlm_cache_path)

        fids: list[str] = sorted({r["fid"] for r in records})
        missing: list[str] = []
        for fid in fids:
            src: str | None = find_source(fid)
            if src is None:
                logger.error("原片缺失，跳过该文件的全部事件: %s", fid)
                missing.append(fid)
                continue
            clusters: list[list[dict[str, Any]]] = cluster_candidates(
                [r for r in records if r["fid"] == fid]
            )
            t_start: float = time.time()
            clips: list[str] = []
            for idx, members in enumerate(clusters, start=1):
                clip: str = os.path.join(out_dir, f"{fid}_e{idx}.mp4")
                cut_cluster_clip(src, fid, idx, members, clip, event_verdict(members, vlm))
                clips.append(clip)
            out_path: str = os.path.join(out_dir, f"{fid}_events.mp4")
            list_path: str = os.path.join(out_dir, f"{fid}_concat.txt")
            concat_clips(clips, list_path, out_path)
            for clip in clips:
                os.remove(clip)
            os.remove(list_path)
            logger.info(
                "  %s: %d候选 -> %d事件 -> %s (%.0fs)",
                fid,
                sum(len(c) for c in clusters),
                len(clusters),
                out_path,
                time.time() - t_start,
            )

        if missing:
            logger.error("共 %d 个文件原片缺失: %s", len(missing), ", ".join(missing))
            return 1
        logger.info("完成。")
        return 0
    except BasketballPipelineError as exc:
        logger.error("管线失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1
    except OSError as exc:
        logger.error("IO 失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
