#!/usr/bin/env python3
"""事件级 VLM 判定（P0 实验：K3 逐事件 1 次调用，替代逐候选精筛）。

对 review_v3 事件索引中的每个事件取 anchor_t0 前后 [-1.5, -0.5, 0.5, 1.5]s
四帧、逐帧筐居中裁剪（half=420），一次调用 K3 判 YES/NO/UNCLEAR；
与 goals.json 人工真值对齐评估召回与压缩力，验证"召回不降且 token 大降"。

用法:
    python scripts/vlm_judge_events.py [--index PATH] [--goals PATH] [--hoops PATH]
                                       [--cache PATH] [--rounds N] [--model NAME]
    python scripts/vlm_judge_events.py --evaluate     # 只评估不调 API
    python scripts/vlm_judge_events.py --renormalize  # 离线重放降级规则（不调 API）

- 判定规则沿用 vlm_filter.PROMPT 原文，仅帧数表述改为四帧；
- 缓存键 = 事件 key（"fid#eN"），协议指纹（MODEL|IMG_SIZE|PROMPT|offsets|half|
  "event-v1" 的 sha1 前 12 位）变更即整包作废重来；JUDGED 终态不重判，ERR 下轮重试；
- 分批：--rounds 限本轮新调用数（OAuth token 仅 900s，轮间由 CLI 活动刷新）；
- 凭证复用本机 Kimi Code 托管订阅，每次调用前重读（见 vlm_filter.load_token）；
- 召回护栏：裸 YES/NO 一律降级 UNCLEAR（见 vlm_filter.normalize_verdict）；
  无筐轨迹回退帧中心裁剪的事件，其 NO 同样降级 UNCLEAR（裁剪里可能没有筐，
  规则1"看不到筐判 NO"此时不是证据而是我们的取景失败）；
  --renormalize 对已缓存判定离线重放上述两条规则（用存储的 raw，不调 API）。
"""

import concurrent.futures as cf
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import traceback
from collections import Counter
from typing import Any

import httpx
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_label_sheet as gls
import vlm_filter as tvf
from errors import SchemaError
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json

logger = logging.getLogger(__name__)

INDEX_JSON: str = "work/20260722/review_v3/events_index.json"
GOALS_JSON: str = "work/20260722/goals.json"
HOOPS_JSON: str = "work/20260722/hoops.json"
CACHE_JSON: str = "work/20260722/vlm_events_cache.json"

MODEL: str = "k3"
IMG_SIZE: int = tvf.IMG_SIZE  # 840，协议指纹计入
EVENT_HALF: int = 420  # 单尺度裁剪半径（v2 协议实测有效尺度）
EVENT_OFFSETS: tuple[float, ...] = (-1.5, -0.5, 0.5, 1.5)  # 四帧偏移（秒，围绕 anchor_t0）
CROP_MODE: str = "event-v1"  # 事件级裁剪协议标记（计入指纹）
WORKERS: int = tvf.WORKERS  # 6 并发
MAX_NEW_PER_RUN: int = 75  # 每轮最多新调用数（--rounds 可覆盖）
MATCH_TOL_SEC: float = 2.0  # 真值对齐：|anchor_time - anchor_t0| 上限
JUDGED_ANSWERS: frozenset[str] = tvf.JUDGED_ANSWERS  # YES/NO/UNCLEAR 终态不重判
PENDING: str = "PENDING"  # 缓存未命中（尚未判定），评估单列

EVENT_REQUIRED_FIELDS: tuple[str, ...] = ("key", "fid", "src_file", "anchor_t0")
GOAL_REQUIRED_FIELDS: tuple[str, ...] = ("file", "anchor_time", "status")

# 判定规则与 vlm_filter.PROMPT 逐字一致，仅帧数表述三帧→四帧（约隔0.5~1秒）
PROMPT: str = tvf.PROMPT.replace(
    "这三张图是同一位置相隔约1秒的连续三帧（室内篮球场）。",
    "这四张图是同一位置相隔约0.5~1秒的连续四帧（室内篮球场）。",
)
if PROMPT == tvf.PROMPT:
    raise SchemaError("PROMPT 帧数表述替换未生效：vlm_filter.PROMPT 原文已变更，需同步本模块")


def protocol_fp(model: str) -> str:
    """计算事件级缓存协议指纹（sha1 前 12 位）。

    MODEL/IMG_SIZE/PROMPT/四帧偏移/裁剪半径/协议标记 任一变更即作废旧缓存。

    Args:
        model: VLM 模型名。

    Returns:
        12 位十六进制指纹。
    """
    s: str = f"{model}|{IMG_SIZE}|{PROMPT}|{list(EVENT_OFFSETS)}|{EVENT_HALF}|{CROP_MODE}"
    return hashlib.sha1(s.encode(), usedforsecurity=False).hexdigest()[:12]


def load_events(path: str) -> list[dict[str, Any]]:
    """读取事件索引并做 schema 校验（rules.md §0.2：数据损坏必须停）。

    Args:
        path: events_index.json 路径。

    Returns:
        事件列表（含 key/fid/src_file/anchor_t0）。

    Raises:
        SchemaError: 顶层结构或必填字段缺失/类型错误。
    """
    payload: Any = read_json(path, what="events_index.json")
    events: Any = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise SchemaError(f"events_index.json 缺 events 列表: {path}")
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            raise SchemaError(f"events[{i}] 不是对象: {path}")
        for f in EVENT_REQUIRED_FIELDS:
            if f not in ev:
                raise SchemaError(f"events[{i}] 缺字段 {f}: {path}")
    return events


def load_goals(path: str) -> list[dict[str, Any]]:
    """读取 goals.json 人工真值并做 schema 校验（rules.md §0.2）。

    Args:
        path: goals.json 路径。

    Returns:
        真值列表（含 file/anchor_time/status）。

    Raises:
        SchemaError: 顶层结构或必填字段缺失。
    """
    payload: Any = read_json(path, what="goals.json")
    goals: Any = payload.get("goals") if isinstance(payload, dict) else None
    if not isinstance(goals, list):
        raise SchemaError(f"goals.json 缺 goals 列表: {path}")
    for i, g in enumerate(goals):
        if not isinstance(g, dict):
            raise SchemaError(f"goals[{i}] 不是对象: {path}")
        for f in GOAL_REQUIRED_FIELDS:
            if f not in g:
                raise SchemaError(f"goals[{i}] 缺字段 {f}: {path}")
    return goals


def match_goals_to_events(
    events: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    tol: float = MATCH_TOL_SEC,
) -> tuple[dict[str, int], list[int]]:
    """真值对齐：每条 goal 匹配同 src_file 且 |anchor_time-anchor_t0|<=tol 的最近事件。

    Args:
        events: 事件列表。
        goals: 真值列表。
        tol: 时间容差（秒，含边界）。

    Returns:
        (正例映射 {事件key: goal下标}, 未匹配 goal 下标列表)。
    """
    pos_map: dict[str, int] = {}
    unmatched: list[int] = []
    for gi, g in enumerate(goals):
        best_key: str | None = None
        best_dt: float = tol
        for ev in events:
            if ev["src_file"] != g["file"]:
                continue
            dt: float = abs(float(g["anchor_time"]) - float(ev["anchor_t0"]))
            if dt <= best_dt:
                best_dt = dt
                best_key = ev["key"]
        if best_key is None:
            unmatched.append(gi)
        else:
            pos_map[best_key] = gi
    return pos_map, unmatched


def answer_of(cache: dict[str, Any], key: str) -> str:
    """取事件的缓存判定态；未判定归 PENDING。

    Args:
        cache: answers 字典。
        key: 事件 key。

    Returns:
        "YES"/"NO"/"UNCLEAR"/"ERR"/"PENDING"。
    """
    res: Any = cache.get(key)
    if not isinstance(res, dict):
        return PENDING
    ans: Any = res.get("answer")
    if ans in JUDGED_ANSWERS or ans == "ERR":
        return str(ans)
    return PENDING


def evaluate(
    events: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    cache: dict[str, Any],
    tol: float = MATCH_TOL_SEC,
) -> dict[str, Any]:
    """聚合评估：正/负例判定分布、两种人工判读策略估算、token 用量。

    策略 a：YES 自动收 + NO 自动弃，人只看 UNCLEAR；
    策略 b：人看 YES+UNCLEAR，NO 自动弃。

    Args:
        events: 事件列表。
        goals: 真值列表。
        cache: answers 字典。
        tol: 真值对齐时间容差（秒）。

    Returns:
        评估结果字典（分布/策略/token/正例判NO清单/未匹配真值）。
    """
    pos_map, unmatched = match_goals_to_events(events, goals, tol)
    pos: Counter[str] = Counter()
    neg: Counter[str] = Counter()
    confirmed: Counter[str] = Counter()
    pos_no: list[str] = []
    in_tokens: int = 0
    out_tokens: int = 0
    for ev in events:
        key: str = ev["key"]
        ans: str = answer_of(cache, key)
        res: Any = cache.get(key)
        if isinstance(res, dict) and res.get("usage"):
            in_tokens += int(res["usage"].get("prompt_tokens", 0))
            out_tokens += int(res["usage"].get("completion_tokens", 0))
        gi: int | None = pos_map.get(key)
        if gi is None:
            neg[ans] += 1
            continue
        pos[ans] += 1
        if goals[gi].get("status") == "confirmed":
            confirmed[ans] += 1
        if ans == "NO":
            pos_no.append(key)
    all_dist: Counter[str] = pos + neg
    return {
        "n_events": len(events),
        "n_pos": len(pos_map),
        "n_neg": len(events) - len(pos_map),
        "pos": pos,
        "neg": neg,
        "confirmed": confirmed,
        "pos_no": pos_no,
        "unmatched_goals": [goals[gi] for gi in unmatched],
        "strategy_a_human": all_dist["UNCLEAR"],
        "strategy_b_human": all_dist["YES"] + all_dist["UNCLEAR"],
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
    }


def _dist_line(c: Counter[str]) -> str:
    """格式化判定分布为固定顺序文本。

    Args:
        c: 判定计数器。

    Returns:
        形如 "YES=3 UNCLEAR=1 NO=10 ERR=0 PENDING=0" 的字符串。
    """
    return " ".join(f"{k}={c.get(k, 0)}" for k in ("YES", "UNCLEAR", "NO", "ERR", PENDING))


def print_report(result: dict[str, Any]) -> None:
    """输出评估报告（正/负例分布、confirmed 单列、策略估算、token、召回事故清单）。

    Args:
        result: evaluate 返回的评估结果。
    """
    logger.info("=== 事件级 VLM 评估 ===")
    logger.info(
        "事件 %d：正例 %d，负例 %d",
        result["n_events"],
        result["n_pos"],
        result["n_neg"],
    )
    logger.info("正例分布: %s", _dist_line(result["pos"]))
    logger.info("  其中 confirmed: %s", _dist_line(result["confirmed"]))
    logger.info("负例分布: %s", _dist_line(result["neg"]))
    logger.info(
        "人工判读量估算: 策略a(只看UNCLEAR)=%d 事件, 策略b(看YES+UNCLEAR)=%d 事件",
        result["strategy_a_human"],
        result["strategy_b_human"],
    )
    logger.info(
        "token 用量: 输入 %d, 输出 %d",
        result["in_tokens"],
        result["out_tokens"],
    )
    for g in result["unmatched_goals"]:
        logger.warning(
            "真值未匹配到事件: %s t=%.1fs (%s)",
            g.get("file"),
            g.get("anchor_time"),
            g.get("status"),
        )
    if result["pos_no"]:
        logger.warning("召回事故：正例判 NO 共 %d 条", len(result["pos_no"]))
        for key in result["pos_no"]:
            logger.warning("  正例判NO: %s", key)
    else:
        logger.info("正例判 NO: 0 条（召回无事故）")


def demote_fallback_no(res: dict[str, Any], is_fallback: bool) -> dict[str, Any]:
    """无筐轨迹回退裁剪事件的 NO 降级为 UNCLEAR（其余判定原样返回）。

    回退裁剪的画面里可能没有筐，规则1"看不到筐判 NO"此时不是证据，
    而是取景失败的产物，不允许成为终态。

    Args:
        res: 判定结果 {"answer", "raw", ...}。
        is_fallback: 该事件是否无筐轨迹（回退帧中心/锚点裁剪）。

    Returns:
        判定结果（必要时 answer 已由 NO 改为 UNCLEAR）。
    """
    if is_fallback and res.get("answer") == "NO":
        return {**res, "answer": "UNCLEAR"}
    return res


def fallback_keys(
    events: list[dict[str, Any]], hoops_by_key: dict[str, dict[str, Any]]
) -> set[str]:
    """无有效筐轨迹（track 为空）的事件 key 集：裁剪中心不可信，其 NO 须降级。

    track 为空时 event_centers 回退到静态 anchor 或帧中心——anchor 来自
    detected=False 的筐事件本身不可靠（实测 anchor 偏移导致四帧无筐），
    与"完全无筐数据"同等对待。

    Args:
        events: 事件列表（含 key 字段）。
        hoops_by_key: hoops.json 按事件 key 索引的筐事件。

    Returns:
        无有效筐轨迹的事件 key 集。
    """
    return {ev["key"] for ev in events if not (hoops_by_key.get(ev["key"]) or {}).get("track")}


def renormalize_cache(cache: dict[str, Any], fallback_keys: set[str]) -> tuple[dict[str, Any], int]:
    """离线重放降级规则：裸 YES/NO 降级 + 无筐回退 NO 降级（用存储的 raw，不调 API）。

    Args:
        cache: 事件级判定缓存（key -> {"answer", "raw", ...}）。
        fallback_keys: 无筐轨迹回退裁剪的事件 key 集。

    Returns:
        (重放后的新缓存, 发生降级的条数)。
    """
    out: dict[str, Any] = {}
    n: int = 0
    for key, res in cache.items():
        r: dict[str, Any] = demote_fallback_no(tvf.normalize_verdict(res), key in fallback_keys)
        if r.get("answer") != res.get("answer"):
            n += 1
        out[key] = r
    return out, n


def event_centers(ev: dict[str, Any] | None, t0: float) -> list[tuple[int, int]] | None:
    """取四帧时刻（t0+各 EVENT_OFFSETS）对应的筐位（track 内 sec 最近点）。

    Args:
        ev: hoops.json 中按 key 命中的事件；None 表示无筐数据。
        t0: 事件锚点时间（秒）。

    Returns:
        与 EVENT_OFFSETS 对齐的 (cx, cy) 列表；无 track 回退锚点（四点同位）；
        二者皆无返回 None（调用方回退帧中心）。
    """
    if not ev:
        return None
    track: Any = ev.get("track")
    if track:
        centers: list[tuple[int, int]] = []
        for off in EVENT_OFFSETS:
            target: float = t0 + off
            _, hx, hy, *_ = min(track, key=lambda p: abs(p[0] - target))
            centers.append((int(hx), int(hy)))
        return centers
    anchor: Any = ev.get("anchor")
    if isinstance(anchor, list) and len(anchor) >= 2:
        return [(int(anchor[0]), int(anchor[1]))] * len(EVENT_OFFSETS)
    return None


def event_crops(
    event: dict[str, Any],
    centers: list[tuple[int, int]] | None,
) -> list[Image.Image]:
    """取事件四帧裁剪图（缺帧用可用帧补齐；无筐位回退帧中心）。

    Args:
        event: 事件（fid/anchor_t0/key）。
        centers: 逐帧裁剪中心（与 EVENT_OFFSETS 对齐）；None 回退帧中心。

    Returns:
        四张裁剪图（2*EVENT_HALF 见方）。

    Raises:
        FileNotFoundError: 四帧全缺。
    """
    imgs: list[Image.Image | None] = []
    for off in EVENT_OFFSETS:
        path: str = gls.frame_path(event["fid"], float(event["anchor_t0"]) + off)
        try:
            imgs.append(Image.open(path).convert("RGB"))
        except FileNotFoundError:
            imgs.append(None)
    avail: Image.Image | None = next((im for im in imgs if im is not None), None)
    if avail is None:
        raise FileNotFoundError(f"{event['key']} 四帧全缺")
    crops: list[Image.Image] = []
    for i, im in enumerate(imgs):
        real: Image.Image = im if im is not None else avail
        if centers:
            cx, cy = centers[i]
        else:
            cx, cy = real.width // 2, real.height // 2
        crops.append(gls.crop_around(real, cx, cy, EVENT_HALF))
    return crops


def ask_vlm_event(
    client: httpx.Client,
    event: dict[str, Any],
    model: str,
    centers: list[tuple[int, int]] | None,
) -> dict[str, Any]:
    """对单个事件以四帧调用一次 VLM（失败归 ERR，不抛出炸整批）。

    Args:
        client: httpx 客户端。
        event: 事件。
        model: VLM 模型名。
        centers: 逐帧裁剪中心；None 回退帧中心。

    Returns:
        {"answer": "YES"|"NO"|"UNCLEAR"|"ERR", "usage": dict|None, "raw": str}。
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    try:
        for crop in event_crops(event, centers):
            b64: str = tvf.crop_to_b64(crop)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )
    except FileNotFoundError as exc:
        return {"answer": "ERR", "usage": None, "raw": str(exc)}

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }
    last_err: str = ""
    for _ in range(tvf.HTTP_RETRY + 1):
        try:
            auth: dict[str, str] = {"Authorization": f"Bearer {tvf.load_token()}"}
            resp = client.post(
                tvf.API_URL,
                json=payload,
                headers=auth,
                timeout=tvf.HTTP_TIMEOUT_SEC,
            )
        except httpx.HTTPError as exc:
            last_err = f"网络错误: {exc}"
            continue
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            raw: str = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"answer": tvf.parse_answer(raw), "usage": data.get("usage"), "raw": raw[-300:]}
        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 401:
            logger.warning("401，等待后强制重载 token 重试")
            time.sleep(8)
            tvf.load_token(force=True)
            continue
        if resp.status_code in (400, 403):
            break
    return {"answer": "ERR", "usage": None, "raw": last_err}


def load_cache(path: str, protocol: str) -> dict[str, Any]:
    """读取事件级 VLM 缓存；协议指纹不符或损坏即整包作废（缓存可再生，只 WARNING）。

    Args:
        path: 缓存文件路径。
        protocol: 当前协议指纹（见 protocol_fp）。

    Returns:
        answers 字典（键 = 事件 key）。
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            payload: Any = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("缓存损坏(%s)，重新开始", exc)
        return {}
    if not isinstance(payload, dict) or payload.get("_protocol") != protocol:
        logger.warning("缓存协议变更或结构异常，作废重开")
        return {}
    answers: Any = payload.get("answers")
    if not isinstance(answers, dict):
        logger.warning("缓存 answers 结构异常，重新开始")
        return {}
    return answers


def save_cache(path: str, cache: dict[str, Any], protocol: str) -> None:
    """以 {"_protocol", "answers"} 包裹格式原子写事件级 VLM 缓存。

    Args:
        path: 缓存文件路径。
        cache: answers 字典。
        protocol: 当前协议指纹。

    Raises:
        OSError: IO 重试耗尽（由 atomic_write_json 抛出）。
    """
    atomic_write_json(path, {"_protocol": protocol, "answers": cache}, what="VLM事件缓存")


def parse_argv(argv: list[str]) -> dict[str, Any]:
    """解析命令行参数。

    Args:
        argv: 参数列表（不含程序名）。

    Returns:
        {"index", "goals", "hoops", "cache", "rounds", "model", "evaluate",
        "renormalize"}。
    """
    opts: dict[str, Any] = {
        "index": INDEX_JSON,
        "goals": GOALS_JSON,
        "hoops": HOOPS_JSON,
        "cache": CACHE_JSON,
        "rounds": MAX_NEW_PER_RUN,
        "model": MODEL,
        "evaluate": False,
        "renormalize": False,
    }
    i: int = 0
    while i < len(argv):
        arg: str = argv[i]
        if arg in ("--index", "--goals", "--hoops", "--cache", "--model") and i + 1 < len(argv):
            opts[arg[2:]] = argv[i + 1]
            i += 2
        elif arg == "--rounds" and i + 1 < len(argv):
            opts["rounds"] = int(argv[i + 1])
            i += 2
        elif arg == "--evaluate":
            opts["evaluate"] = True
            i += 1
        elif arg == "--renormalize":
            opts["renormalize"] = True
            i += 1
        else:
            i += 1
    return opts


def main() -> None:
    """主入口：逐事件三值 VLM 判定（断点续判）并对齐真值评估。"""
    run_id: str = new_run_id()
    configure_logging(run_id)
    opts: dict[str, Any] = parse_argv(sys.argv[1:])
    protocol: str = protocol_fp(opts["model"])
    logger.info("模型 %s，协议指纹 %s", opts["model"], protocol)

    events: list[dict[str, Any]] = load_events(opts["index"])
    goals: list[dict[str, Any]] = load_goals(opts["goals"])
    logger.info("事件 %d，真值 %d", len(events), len(goals))

    if os.path.exists(opts["cache"]):
        bak: str = opts["cache"] + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(opts["cache"], bak)
            logger.info("旧缓存已备份: %s", bak)
    cache: dict[str, Any] = load_cache(opts["cache"], protocol)

    if opts["renormalize"]:
        hoops_rn: dict[str, list[dict[str, Any]]] = tvf.load_hoops(opts["hoops"])
        hoops_by_key_rn: dict[str, dict[str, Any]] = {
            ev["key"]: ev for evs in hoops_rn.values() for ev in evs if ev.get("key")
        }
        fb_keys: set[str] = fallback_keys(events, hoops_by_key_rn)
        cache, n_demoted = renormalize_cache(cache, fb_keys)
        save_cache(opts["cache"], cache, protocol)
        logger.info(
            "重规范化：%d 条判定降级为 UNCLEAR（无筐回退事件 %d 个）", n_demoted, len(fb_keys)
        )

    if not opts["evaluate"]:
        tvf.load_token()
        hoops_by_fid: dict[str, list[dict[str, Any]]] = tvf.load_hoops(opts["hoops"])
        hoops_by_key: dict[str, dict[str, Any]] = {
            ev["key"]: ev for evs in hoops_by_fid.values() for ev in evs if ev.get("key")
        }
        jobs: list[dict[str, Any]] = [
            ev for ev in events if cache.get(ev["key"], {}).get("answer") not in JUDGED_ANSWERS
        ]
        jobs = jobs[: opts["rounds"]]
        logger.info("本轮待判 %d 事件 (上限 %d)", len(jobs), opts["rounds"])

        headers: dict[str, str] = {"Authorization": f"Bearer {tvf.load_token()}"}
        with (
            httpx.Client(headers=headers) as client,
            cf.ThreadPoolExecutor(max_workers=WORKERS) as pool,
        ):
            futs: dict[cf.Future[dict[str, Any]], str] = {}
            fb_set: set[str] = fallback_keys(events, hoops_by_key)
            for ev in jobs:
                centers: list[tuple[int, int]] | None = event_centers(
                    hoops_by_key.get(ev["key"]), float(ev["anchor_t0"])
                )
                futs[pool.submit(ask_vlm_event, client, ev, opts["model"], centers)] = ev["key"]
            if fb_set:
                logger.warning(
                    "%d/%d 事件无有效筐轨迹，裁剪中心不可信（其 NO 将降级 UNCLEAR）",
                    len(fb_set),
                    len(jobs),
                )
            for done_n, fut in enumerate(cf.as_completed(futs), start=1):
                key: str = futs[fut]
                try:
                    cache[key] = demote_fallback_no(
                        tvf.normalize_verdict(fut.result()), key in fb_set
                    )
                except (httpx.HTTPError, OSError, KeyError, ValueError, RuntimeError) as exc:
                    cache[key] = {
                        "answer": "ERR",
                        "usage": None,
                        "raw": str(exc),
                        "stack": traceback.format_exc()[-500:],
                    }
                    logger.warning("判定异常 %s: %s", key, exc)
                if done_n % 10 == 0:
                    logger.info("  进度 %d/%d", done_n, len(jobs))
                    save_cache(opts["cache"], cache, protocol)
        save_cache(opts["cache"], cache, protocol)
        n_judged: int = sum(
            1 for ev in events if cache.get(ev["key"], {}).get("answer") in JUDGED_ANSWERS
        )
        logger.info("判定完成度: %d/%d", n_judged, len(events))

    print_report(evaluate(events, goals, cache))


if __name__ == "__main__":
    main()
