#!/usr/bin/env python3
"""三模型球检测头对头对比验证。

在已知 ground truth 的帧上，对比三个 YO 球检测模型的
检测密度（假阳性指标）和 GT 帧召回率。
"""

import logging
import re
import time
from glob import glob
from typing import Any

from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

IMGSZ: int = 1280
CONF: float = 0.01
SAMPLE_FPS: float = 5.0
GT_HALF_WINDOW: float = 1.5
MAX_MINUTES: int = 90
FRAMES_PATTERN: str = "work/frames/{}/f_*.jpg"

GROUND_TRUTH: dict[str, float] = {
    "0011": 10.0,
    "0030": 11.0,
    "0040": 39.0,
    "0128": 11.0,
}

MODELS: dict[str, tuple[str, int]] = {
    "lumos88_nano": ("basketball_yolo11.pt", 32),
    "446f_yolo11m": ("446f6e6e79_yolo11m.pt", 0),
    "abdullahtarek": ("abdullahtarek_ball.pt", 0),
}


def parse_idx(path: str) -> int:
    """从帧路径解析帧序号。

    Args:
        path: 帧文件路径，如 work/frames/0030/f_056.jpg。

    Returns:
        帧序号整数，如 56。
    """
    m = re.search(r"f_(\d+)", path)
    return int(m.group(1)) if m else 0


def idx_to_sec(idx: int) -> float:
    """帧序号转时间秒数。

    Args:
        idx: 帧序号（1-based）。

    Returns:
        对应的秒数，保留 1 位小数。
    """
    return round((idx - 1) / SAMPLE_FPS, 1)


def detect_balls(
    model: YOLO, img_path: str, ball_cls: int
) -> list[dict[str, Any]]:
    """用指定模型检测单帧中的所有球。

    Args:
        model: 已加载的 YOLO 模型实例。
        img_path: 帧图片路径。
        ball_cls: 球类别 ID。

    Returns:
        检测列表，每项含 conf 和 box。
    """
    result = model(
        img_path, conf=CONF, imgsz=IMGSZ, classes=[ball_cls], verbose=False
    )
    return [
        {
            "conf": round(float(b.conf), 3),
            "box": [round(v) for v in b.xyxy[0].tolist()],
        }
        for b in result[0].boxes
    ]


def run_on_file(
    model: YOLO, ball_cls: int, fid: str
) -> dict[str, Any]:
    """在单个文件的所有帧上运行模型，返回统计结果。

    Args:
        model: 已加载的 YOLO 模型实例。
        ball_cls: 球类别 ID。
        fid: 文件 ID，如 "0030"。

    Returns:
        包含检测统计和 GT 窗口检测详情的字典。
    """
    frames = sorted(glob(FRAMES_PATTERN.format(fid)))
    if not frames:
        logger.warning("  %s: 无帧", fid)
        return {}

    total_dets: int = 0
    frames_hit: int = 0
    gt_sec: float | None = GROUND_TRUTH.get(fid)
    gt_window: list[dict[str, Any]] = []
    t0: float = time.time()

    for fp in frames:
        idx: int = parse_idx(fp)
        sec: float = idx_to_sec(idx)
        dets = detect_balls(model, fp, ball_cls)
        total_dets += len(dets)
        if dets:
            frames_hit += 1
        if gt_sec is not None and abs(sec - gt_sec) <= GT_HALF_WINDOW:
            gt_window.append({"sec": sec, "idx": idx, "dets": dets})

    elapsed: float = time.time() - t0
    n: int = len(frames)
    return {
        "fid": fid,
        "n_frames": n,
        "total_dets": total_dets,
        "avg_per_frame": round(total_dets / n, 1),
        "detection_rate": round(frames_hit / n * 100, 1),
        "elapsed": round(elapsed, 1),
        "sec_per_frame": round(elapsed / n, 2),
        "gt_window": gt_window,
    }


def print_model_result(
    name: str, results: list[dict[str, Any]]
) -> None:
    """打印单个模型在所有文件上的检测结果。

    Args:
        name: 模型名称。
        results: 每个文件的统计结果列表。
    """
    logger.info("\n=== %s ===", name)
    for r in results:
        logger.info(
            "  %s: %d帧 %d检出(avg %.1f/帧 覆盖%.0f%%) %.1fs(%.2fs/帧)",
            r["fid"],
            r["n_frames"],
            r["total_dets"],
            r["avg_per_frame"],
            r["detection_rate"],
            r["elapsed"],
            r["sec_per_frame"],
        )
        for g in r["gt_window"]:
            if g["dets"]:
                best = max(g["dets"], key=lambda d: d["conf"])
                logger.info(
                    "    GT %.1fs: %d检出 最高conf=%.3f @%s",
                    g["sec"],
                    len(g["dets"]),
                    best["conf"],
                    best["box"],
                )
            else:
                logger.info("    GT %.1fs: MISS", g["sec"])


def main() -> None:
    """主入口：速度测试 + 头对头球检测对比。"""
    fids: list[str] = ["0011", "0030", "0040", "0128"]

    logger.info("速度测试 (imgsz=%d)...", IMGSZ)
    test_frame = sorted(glob(FRAMES_PATTERN.format("0030")))[0]
    speeds: dict[str, float] = {}
    for name, (path, cls) in MODELS.items():
        model = YOLO(path)
        t0 = time.time()
        model(
            test_frame,
            conf=CONF,
            imgsz=IMGSZ,
            classes=[cls],
            verbose=False,
        )
        dt = time.time() - t0
        speeds[name] = dt
        logger.info("  %-16s: %.1fs/帧", name, dt)

    total_frames = sum(
        len(glob(FRAMES_PATTERN.format(f))) for f in fids
    )
    est = sum(total_frames * speeds[n] for n in MODELS)
    logger.info("总帧数=%d 预估=%.0f分钟", total_frames, est / 60)

    if est / 60 > MAX_MINUTES:
        logger.info("预估>%d分钟，只跑 0030", MAX_MINUTES)
        fids = ["0030"]

    for name, (path, cls) in MODELS.items():
        model = YOLO(path)
        results = [run_on_file(model, cls, fid) for fid in fids]
        print_model_result(name, results)

    logger.info("\n完成。")


if __name__ == "__main__":
    main()
