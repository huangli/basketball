#!/usr/bin/env python3
"""abdullahtarek 球检测 + 静止段聚类 pipeline。

用 abdullahtarek 模型替换 lumos88，跑和 batch_detect_v2.py 相同的
静止段聚类后处理逻辑，对比召回率和精确率变化。
"""

import logging
import re
import sys
import time
from glob import glob
from typing import Any

from ultralytics import YOLO

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BALL_MODEL_PATH: str = "abdullahtarek_ball.pt"
BALL_CLS: int = 0
PERSON_MODEL_PATH: str = "yolov8n.pt"
PERSON_CLS: int = 0

IMGSZ_BALL: int = 1280
IMGSZ_PERSON: int = 640
CONF_BALL: float = 0.15
CONF_PERSON: float = 0.3

SAMPLE_FPS: float = 5.0
STATIC_WINDOW: int = 4
STATIC_MAX_MOVE: int = 40
MERGE_GAP: int = 4
DEAD_BALL_SEC: float = 3.0
HELD_IOU: float = 0.3
GT_TOLERANCE: float = 3.0

FRAMES_PATTERN: str = "work/frames/{}/f_*.jpg"

GROUND_TRUTH: dict[str, float] = {
    "0011": 10.0,
    "0030": 11.0,
    "0040": 39.0,
    "0128": 11.0,
}


def calc_iou(b1: list[int], b2: list[int]) -> float:
    """计算两个边界框的 IoU。

    Args:
        b1: [x1, y1, x2, y2] 边界框。
        b2: [x1, y1, x2, y2] 边界框。

    Returns:
        IoU 值，范围 [0, 1]。
    """
    x1: int = max(b1[0], b2[0])
    y1: int = max(b1[1], b2[1])
    x2: int = min(b1[2], b2[2])
    y2: int = min(b1[3], b2[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter: int = (x2 - x1) * (y2 - y1)
    a1: int = (b1[2] - b1[0]) * (b1[3] - b1[1])
    a2: int = (b2[2] - b2[0]) * (b2[3] - b2[1])
    return inter / (a1 + a2 - inter)


def detect_frame(
    ball_model: YOLO, person_model: YOLO, img_path: str
) -> dict[str, Any]:
    """单帧检测球（取最高 conf）和人物。

    Args:
        ball_model: 球检测 YOLO 模型。
        person_model: 人物检测 YOLO 模型。
        img_path: 帧图片路径。

    Returns:
        含时间、球检测、球总数、人物框列表的字典。
    """
    m = re.search(r"f_(\d+)", img_path)
    idx: int = int(m.group(1)) if m else 0
    sec: float = round((idx - 1) / SAMPLE_FPS, 1)

    rb = ball_model(
        img_path,
        conf=CONF_BALL,
        imgsz=IMGSZ_BALL,
        classes=[BALL_CLS],
        verbose=False,
    )
    rp = person_model(
        img_path,
        conf=CONF_PERSON,
        imgsz=IMGSZ_PERSON,
        classes=[PERSON_CLS],
        verbose=False,
    )

    ball: dict[str, Any] | None = None
    n_balls: int = 0
    for b in rb[0].boxes:
        n_balls += 1
        conf: float = float(b.conf)
        box: list[int] = [round(v) for v in b.xyxy[0].tolist()]
        if ball is None or conf > ball["conf"]:
            ball = {"conf": round(conf, 2), "box": box}

    persons: list[list[int]] = [
        [round(v) for v in b.xyxy[0].tolist()] for b in rp[0].boxes
    ]

    return {
        "t": sec,
        "ball": ball,
        "n_balls": n_balls,
        "persons": persons,
    }


def find_static_segments(
    dets: list[dict[str, Any]],
) -> list[int]:
    """找出连续 N 帧球位置基本不动的起始索引。

    Args:
        dets: 每帧检测结果列表。

    Returns:
        静止段起始索引列表。
    """
    raw: list[int] = []
    for i in range(len(dets) - STATIC_WINDOW + 1):
        seg: list[dict[str, Any]] = dets[i : i + STATIC_WINDOW]
        if any(d["ball"] is None for d in seg):
            continue
        cxs: list[int] = [
            (d["ball"]["box"][0] + d["ball"]["box"][2]) // 2
            for d in seg
        ]
        cys: list[int] = [
            (d["ball"]["box"][1] + d["ball"]["box"][3]) // 2
            for d in seg
        ]
        if (
            max(cxs) - min(cxs) < STATIC_MAX_MOVE
            and max(cys) - min(cys) < STATIC_MAX_MOVE
        ):
            raw.append(i)
    return raw


def merge_segments(raw: list[int]) -> list[tuple[int, int]]:
    """合并相邻（间隔 <= MERGE_GAP）的静止段。

    Args:
        raw: 静止段起始索引列表。

    Returns:
        合并后的 (start, end_exclusive) 区间列表。
    """
    if not raw:
        return []
    merged: list[tuple[int, int]] = []
    s: int = raw[0]
    p: int = raw[0]
    for idx in raw[1:]:
        if idx - p <= MERGE_GAP:
            p = idx
        else:
            merged.append((s, p + STATIC_WINDOW))
            s = idx
            p = idx
    merged.append((s, p + STATIC_WINDOW))
    return merged


def filter_and_collect(
    merged: list[tuple[int, int]],
    dets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """过滤候选段（排除死球、持球），返回候选及排除计数。

    Args:
        merged: 合并后的区间列表。
        dets: 每帧检测结果列表。

    Returns:
        (候选列表, 死球排除数, 持球排除数)。
    """
    cands: list[dict[str, Any]] = []
    rm_dead: int = 0
    rm_held: int = 0

    for ms, me in merged:
        me = min(me, len(dets))
        sd: list[dict[str, Any]] = [
            d for d in dets[ms:me] if d["ball"]
        ]
        if len(sd) < STATIC_WINDOW:
            continue
        t0: float = sd[0]["t"]
        dur: float = round(sd[-1]["t"] - t0, 1)
        if dur > DEAD_BALL_SEC:
            rm_dead += 1
            continue
        ac: float = round(
            sum(d["ball"]["conf"] for d in sd) / len(sd), 2
        )
        cx: int = sum(
            (d["ball"]["box"][0] + d["ball"]["box"][2]) // 2
            for d in sd
        ) // len(sd)
        cy: int = sum(
            (d["ball"]["box"][1] + d["ball"]["box"][3]) // 2
            for d in sd
        ) // len(sd)

        held: bool = False
        for k in range(ms, me):
            if dets[k]["ball"] is None:
                continue
            bb: list[int] = dets[k]["ball"]["box"]
            for pb in dets[k]["persons"]:
                if calc_iou(bb, pb) > HELD_IOU:
                    held = True
                    break
            if held:
                break
        if held:
            rm_held += 1
        else:
            cands.append(
                {"t0": t0, "dur": dur, "ac": ac, "cx": cx, "cy": cy}
            )

    return cands, rm_dead, rm_held


def run_pipeline(
    ball_model: YOLO, person_model: YOLO, fid: str
) -> None:
    """在单个文件上跑完整检测 pipeline 并输出结果。

    Args:
        ball_model: 球检测 YOLO 模型。
        person_model: 人物检测 YOLO 模型。
        fid: 文件 ID，如 "0030"。
    """
    frames = sorted(glob(FRAMES_PATTERN.format(fid)))
    if not frames:
        logger.warning("%s: 无帧", fid)
        return

    logger.info("\n=== %s (%d帧) ===", fid, len(frames))
    t0: float = time.time()
    dets: list[dict[str, Any]] = [
        detect_frame(ball_model, person_model, fp) for fp in frames
    ]
    elapsed: float = time.time() - t0
    avg_balls: float = round(
        sum(d["n_balls"] for d in dets) / len(dets), 1
    )
    logger.info("  检测%.1fs avg%.1f球/帧", elapsed, avg_balls)

    raw: list[int] = find_static_segments(dets)
    merged: list[tuple[int, int]] = merge_segments(raw)
    cands, rm_dead, rm_held = filter_and_collect(merged, dets)

    gt: float | None = GROUND_TRUTH.get(fid)
    logger.info(
        "  静止段%d 合并%d 排除(死球%d 持球%d) => 候选%d",
        len(raw),
        len(merged),
        rm_dead,
        rm_held,
        len(cands),
    )

    hits: int = 0
    for c in cands:
        is_hit: str = ""
        if gt is not None and abs(c["t0"] - gt) <= GT_TOLERANCE:
            hits += 1
            is_hit = " <== HIT"
        logger.info(
            "    t=%.1fs dur=%.1fs conf=%.2f @(%d,%d)%s",
            c["t0"],
            c["dur"],
            c["ac"],
            c["cx"],
            c["cy"],
            is_hit,
        )

    if gt is not None:
        status: str = "HIT" if hits > 0 else "MISS"
        logger.info(
            "  GT=%.1fs 召回=%s 候选%d 精确=%.0f%%",
            gt,
            status,
            len(cands),
            round(hits / max(len(cands), 1) * 100),
        )


def main() -> None:
    """主入口：加载模型并对各文件执行 pipeline。"""
    fids: list[str] = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else ["0011", "0030", "0040", "0128"]
    )
    ball_model = YOLO(BALL_MODEL_PATH)
    person_model = YOLO(PERSON_MODEL_PATH)

    for fid in fids:
        run_pipeline(ball_model, person_model, fid)

    logger.info("\n完成。")


if __name__ == "__main__":
    main()
