#!/usr/bin/env python3
"""abdullahtarek 模型 Ball+Hoop 检测 + 空间过滤验证。

测试 abdullahtarek 模型的 Ball 和 Hoop（篮筐）检测能力，
验证"只认筐附近的球"空间过滤方案的有效性。
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
CONF: float = 0.15
SAMPLE_FPS: float = 5.0
GT_HALF_WINDOW: float = 1.5
HOOP_PROXIMITY: int = 250
FRAMES_PATTERN: str = "work/frames/{}/f_*.jpg"

GROUND_TRUTH: dict[str, float] = {
    "0011": 10.0,
    "0030": 11.0,
    "0040": 39.0,
    "0128": 11.0,
}

MODEL_PATH: str = "abdullahtarek_ball.pt"
BALL_CLS: int = 0
HOOP_CLS: int = 2


def parse_idx(path: str) -> int:
    """从帧路径解析帧序号。

    Args:
        path: 帧文件路径。

    Returns:
        帧序号整数。
    """
    m = re.search(r"f_(\d+)", path)
    return int(m.group(1)) if m else 0


def idx_to_sec(idx: int) -> float:
    """帧序号转秒数。

    Args:
        idx: 帧序号（1-based）。

    Returns:
        对应秒数。
    """
    return round((idx - 1) / SAMPLE_FPS, 1)


def box_center(box: list[int]) -> tuple[int, int]:
    """计算检测框中心点。

    Args:
        box: [x1, y1, x2, y2] 坐标列表。

    Returns:
        (cx, cy) 中心坐标。
    """
    return (box[0] + box[2]) // 2, (box[1] + box[3]) // 2


def euclidean_dist(
    p1: tuple[int, int], p2: tuple[int, int]
) -> float:
    """计算两点欧氏距离。

    Args:
        p1: 第一个点 (x, y)。
        p2: 第二个点 (x, y)。

    Returns:
        欧氏距离。
    """
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def run_on_file(model: YOLO, fid: str) -> dict[str, Any]:
    """在单个文件所有帧上检测 Ball+Hoop，统计空间过滤效果。

    Args:
        model: 已加载的 YOLO 模型。
        fid: 文件 ID。

    Returns:
        统计结果字典。
    """
    frames = sorted(glob(FRAMES_PATTERN.format(fid)))
    if not frames:
        logger.warning("  %s: 无帧", fid)
        return {}

    total_balls: int = 0
    total_hoops: int = 0
    balls_near_hoop: int = 0
    frames_with_hoop: int = 0
    gt_sec: float | None = GROUND_TRUTH.get(fid)
    gt_details: list[dict[str, Any]] = []
    t0: float = time.time()

    for fp in frames:
        idx: int = parse_idx(fp)
        sec: float = idx_to_sec(idx)
        result = model(fp, conf=CONF, imgsz=IMGSZ, verbose=False)

        balls: list[dict[str, Any]] = []
        hoops: list[dict[str, Any]] = []
        for b in result[0].boxes:
            cls: int = int(b.cls)
            conf_val: float = round(float(b.conf), 3)
            box: list[int] = [round(v) for v in b.xyxy[0].tolist()]
            if cls == BALL_CLS:
                balls.append({"conf": conf_val, "box": box})
            elif cls == HOOP_CLS:
                hoops.append({"conf": conf_val, "box": box})

        total_balls += len(balls)
        total_hoops += len(hoops)
        if hoops:
            frames_with_hoop += 1

        near: int = 0
        if hoops:
            hoop_centers: list[tuple[int, int]] = [
                box_center(h["box"]) for h in hoops
            ]
            for ball in balls:
                bc: tuple[int, int] = box_center(ball["box"])
                if any(
                    euclidean_dist(bc, hc) < HOOP_PROXIMITY
                    for hc in hoop_centers
                ):
                    near += 1
        balls_near_hoop += near

        if gt_sec is not None and abs(sec - gt_sec) <= GT_HALF_WINDOW:
            gt_details.append(
                {
                    "sec": sec,
                    "idx": idx,
                    "balls": balls,
                    "hoops": hoops,
                    "near": near,
                }
            )

    elapsed: float = time.time() - t0
    n: int = len(frames)
    return {
        "fid": fid,
        "n_frames": n,
        "total_balls": total_balls,
        "total_hoops": total_hoops,
        "avg_balls": round(total_balls / n, 1),
        "avg_hoops": round(total_hoops / n, 1),
        "hoop_coverage": round(frames_with_hoop / n * 100, 1),
        "balls_near_hoop": balls_near_hoop,
        "filtered_rate": round(
            (1 - balls_near_hoop / max(total_balls, 1)) * 100, 1
        ),
        "elapsed": round(elapsed, 1),
        "gt_details": gt_details,
    }


def main() -> None:
    """主入口：Ball+Hoop 检测 + 空间过滤效果验证。"""
    fids: list[str] = ["0011", "0030", "0040", "0128"]
    logger.info(
        "abdullahtarek Ball+Hoop (imgsz=%d conf=%.2f)", IMGSZ, CONF
    )
    logger.info("空间过滤: 只保留 Hoop %dpx 内 Ball\n", HOOP_PROXIMITY)

    model = YOLO(MODEL_PATH)

    for fid in fids:
        r = run_on_file(model, fid)
        if not r:
            continue
        logger.info("=== %s ===", fid)
        logger.info(
            "  %d帧 Ball=%d(%.1f/帧) Hoop=%d(%.1f/帧 覆盖%.0f%%)",
            r["n_frames"],
            r["total_balls"],
            r["avg_balls"],
            r["total_hoops"],
            r["avg_hoops"],
            r["hoop_coverage"],
        )
        logger.info(
            "  过滤: %d->%d球(砍%.0f%%) %.1fs",
            r["total_balls"],
            r["balls_near_hoop"],
            r["filtered_rate"],
            r["elapsed"],
        )
        for g in r["gt_details"]:
            hoop_str: str = (
                "; ".join(
                    f"c={h['conf']}@{h['box']}" for h in g["hoops"]
                )
                or "MISS"
            )
            ball_str: str = (
                "; ".join(
                    f"c={b['conf']}@{b['box']}" for b in g["balls"]
                )
                or "MISS"
            )
            logger.info(
                "  GT %.1fs: H[%s] B[%s] near=%d",
                g["sec"],
                hoop_str,
                ball_str,
                g["near"],
            )
        logger.info("")

    logger.info("完成。")


if __name__ == "__main__":
    main()
