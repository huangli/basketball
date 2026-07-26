#!/usr/bin/env python3
"""VLM 候选精筛（Kimi K3 视觉，双尺度 YES/NO 协议）。

对每个候选取 t0-1s/t0/t0+1s 三帧，分别以 420/630 两种裁剪半径调用 K3
问"球是否进了篮筐"，任一尺度判 YES 即保留（召回优先；实测单次判定会
摇摆，双尺度任一 YES 可对冲）。

用法:
    python scripts/test_vlm_filter.py [--candidates PATH] [--cache PATH] [--limit N]

- 凭证：复用本机 Kimi Code 托管订阅（~/.kimi-code/credentials/kimi-code.json），
  仅在进程内读取，不打印；token 有效期仅 900s，每次调用前重读文件；
- 响应缓存：默认 work/label/vlm_cache_dual.json，幂等可断点续跑；落盘格式
  {"_protocol", "answers"}，协议指纹（MODEL|IMG_SIZE|PROMPT 的 sha1 前 12 位）
  变更即作废重开；无 _protocol 的旧平铺格式按当前协议沿用（保住已耗 token 的成果）；
- 分批：每轮最多 MAX_NEW_PER_RUN 次调用（绕 token 过期，轮间由 CLI 活动刷新）。
"""

import base64
import concurrent.futures as cf
import hashlib
import io
import json
import logging
import os
import sys
import time
import traceback
from typing import Any

import httpx
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_label_sheet as gls
from pipe_common import atomic_write_json, configure_logging, new_run_id

logger = logging.getLogger(__name__)

TOKEN_PATH: str = os.path.expanduser("~/.kimi-code/credentials/kimi-code.json")
API_URL: str = "https://api.kimi.com/coding/v1/chat/completions"
MODEL: str = "k3"
CANDIDATES_JSON: str = "work/label/candidates.json"
LABELS_JSON: str = "work/label/labels.json"
CACHE_JSON: str = "work/label/vlm_cache_dual.json"

IMG_SIZE: int = 840  # 发给 VLM 的图边长（448 时球仅 ~8px，K3 会漏看）
HTTP_TIMEOUT_SEC: int = 180  # K3 推理恒 max，单次可能较慢
HTTP_RETRY: int = 2
WORKERS: int = 6
VLM_CROP_HALFS: list[int] = [420, 630]  # 双尺度裁剪半径（img 系）
MAX_NEW_PER_RUN: int = 75  # 每轮最多新调用数（OAuth token 仅 900s，分批轮间刷新）

PROMPT: str = (
    "这三张图是同一位置相隔约1秒的连续三帧（室内篮球场）。"
    "注意墙上广告海报里可能有印刷的篮球图案，那不是真实篮球。"
    "请分析三帧中真实篮球与篮筐/篮网的位置变化，判断篮球是否进了篮筐"
    "（球穿过篮网）。最后一行只输出 YES 或 NO，不要输出其他内容。"
)
# 缓存协议指纹：MODEL/IMG_SIZE/PROMPT 任一变更即作废旧缓存（判定口径已变）
PROTOCOL: str = hashlib.sha1(
    f"{MODEL}|{IMG_SIZE}|{PROMPT}".encode(), usedforsecurity=False
).hexdigest()[:12]

_token_state: dict[str, Any] = {"token": "", "expires_at": 0}


def load_token(force: bool = False) -> str:
    """读取本机 Kimi Code OAuth access_token（不打印）。

    token 有效期仅 900s，Kimi Code CLI 的活动会刷新凭证文件；
    本函数在临期时重读文件获取最新 token。

    Args:
        force: 强制重读（用于 401 后）。

    Returns:
        access_token 字符串。

    Raises:
        RuntimeError: 凭证缺失或无 token。
    """
    now: float = time.time()
    if not force and _token_state["token"] and _token_state["expires_at"] > now + 60:
        return _token_state["token"]
    try:
        with open(TOKEN_PATH, encoding="utf-8") as f:
            cred: dict[str, Any] = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"读取凭证失败: {exc}") from exc
    token: str = cred.get("access_token", "")
    if not token:
        raise RuntimeError("凭证中无 access_token")
    _token_state["token"] = token
    _token_state["expires_at"] = float(cred.get("expires_at", 0))
    return token


def crop_to_b64(img: Image.Image) -> str:
    """图像缩放为 IMG_SIZE 边长并编码 base64 JPEG。

    Args:
        img: 原图。

    Returns:
        base64 字符串。
    """
    small = img.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def parse_answer(raw: str) -> str:
    """从 VLM 回复解析 YES/NO（优先末行，其次最后一次出现）。

    Args:
        raw: 回复全文。

    Returns:
        "YES" / "NO" / "ERR"。
    """
    lines: list[str] = [ln.strip().upper() for ln in raw.strip().splitlines() if ln.strip()]
    for ln in reversed(lines):
        if "YES" in ln:
            return "YES"
        if "NO" in ln:
            return "NO"
    return "ERR"


def gls_crops(cand: dict[str, Any], half: int) -> list[Image.Image]:
    """取候选三帧裁剪图（缺帧用可用帧补齐）。

    Args:
        cand: 候选。
        half: 裁剪半径（img 系）。

    Returns:
        三张裁剪图。
    """
    imgs: list[Image.Image | None] = []
    for off in gls.STRIP_OFFSETS:
        path: str = gls.frame_path(cand["fid"], cand["t0"] + off)
        try:
            imgs.append(Image.open(path).convert("RGB"))
        except FileNotFoundError:
            imgs.append(None)
    avail: Image.Image | None = next((im for im in imgs if im is not None), None)
    if avail is None:
        raise FileNotFoundError(f"{cand['fid']}{cand['label']} 三帧全缺")
    return [
        gls.crop_around(im if im is not None else avail, cand["cx"], cand["cy"], half)
        for im in imgs
    ]


def ask_vlm(client: httpx.Client, cand: dict[str, Any], half: int) -> dict[str, Any]:
    """对单个候选以指定尺度调用一次 VLM。

    Args:
        client: httpx 客户端。
        cand: 候选（fid/t0/cx/cy/label）。
        half: 裁剪半径（img 系）。

    Returns:
        {"answer": "YES"|"NO"|"ERR", "usage": dict|None, "raw": str}。
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    try:
        for crop in gls_crops(cand, half):
            b64: str = crop_to_b64(crop)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )
    except FileNotFoundError as exc:
        return {"answer": "ERR", "usage": None, "raw": str(exc)}

    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
    }
    last_err: str = ""
    for _ in range(HTTP_RETRY + 1):
        try:
            auth: dict[str, str] = {"Authorization": f"Bearer {load_token()}"}
            resp = client.post(API_URL, json=payload, headers=auth, timeout=HTTP_TIMEOUT_SEC)
        except httpx.HTTPError as exc:
            last_err = f"网络错误: {exc}"
            continue
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            raw: str = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            answer: str = parse_answer(raw)
            return {"answer": answer, "usage": data.get("usage"), "raw": raw[-300:]}
        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 401:
            logger.warning("401，等待后强制重载 token 重试")
            time.sleep(8)
            load_token(force=True)
            continue
        if resp.status_code in (400, 403):
            break
    return {"answer": "ERR", "usage": None, "raw": last_err}


def load_labels() -> tuple[set[str], set[str]]:
    """读取正样本键集与 uncertain 键集（文件缺失则返回空集）。

    Returns:
        (正样本键集, uncertain键集)。
    """
    if not os.path.exists(LABELS_JSON):
        return set(), set()
    with open(LABELS_JSON, encoding="utf-8") as f:
        labels: dict[str, Any] = json.load(f)
    pos: set[str] = {f"{fid}{lb}" for fid, lbs in labels["positives"].items() for lb in lbs}
    unc: set[str] = set(labels.get("uncertain", []))
    return pos, unc


def parse_argv() -> tuple[str, str, int]:
    """解析命令行参数。

    Returns:
        (candidates 路径, cache 路径, limit)。
    """
    candidates: str = CANDIDATES_JSON
    cache: str = CACHE_JSON
    limit: int = 0
    args: list[str] = sys.argv[1:]
    i: int = 0
    while i < len(args):
        if args[i] == "--candidates" and i + 1 < len(args):
            candidates = args[i + 1]
            i += 2
        elif args[i] == "--cache" and i + 1 < len(args):
            cache = args[i + 1]
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i].isdigit():
            limit = int(args[i])
            i += 1
        else:
            i += 1
    return candidates, cache, limit


def load_cache(path: str) -> dict[str, Any]:
    """读取 VLM 响应缓存并按协议指纹迁移（缓存可再生，任何损坏只 WARNING 不抛错）。

    迁移逻辑：
    - 文件不存在 → 空缓存；
    - JSON 损坏或顶层不是 dict → WARNING 后空缓存重开；
    - 有 ``_protocol`` 且与当前 PROTOCOL 匹配 → 沿用 ``answers``；
    - 有 ``_protocol`` 但不匹配 → WARNING 作废重开（判定口径已变）；
    - 无 ``_protocol``（旧格式平铺 dict）→ 按当前协议沿用整个 dict
      （旧条目是现行 prompt 判的，必须保住已耗 token 的成果）。

    Args:
        path: 缓存文件路径。

    Returns:
        answers 字典（键形如 ``<fid><label>@<half>``）。
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            payload: Any = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("缓存损坏(%s)，重新开始", exc)
        return {}
    if not isinstance(payload, dict):
        logger.warning("缓存结构异常，重新开始")
        return {}
    if "_protocol" not in payload:
        logger.info("旧格式缓存按当前协议沿用")
        return payload
    if payload["_protocol"] != PROTOCOL:
        logger.warning("缓存协议变更，作废重开")
        return {}
    answers: Any = payload.get("answers")
    if not isinstance(answers, dict):
        logger.warning("缓存 answers 结构异常，重新开始")
        return {}
    return answers


def save_cache(path: str, cache: dict[str, Any]) -> None:
    """以 {"_protocol", "answers"} 包裹格式原子写 VLM 响应缓存。

    Args:
        path: 缓存文件路径。
        cache: answers 字典。

    Raises:
        OSError: IO 重试耗尽（由 atomic_write_json 抛出）。
    """
    atomic_write_json(path, {"_protocol": PROTOCOL, "answers": cache}, what="VLM缓存")


def main() -> None:
    """主入口：逐候选双尺度 VLM 判定并汇总。"""
    run_id: str = new_run_id()
    configure_logging(run_id)
    candidates_path, cache_path, limit = parse_argv()
    load_token()

    with open(candidates_path, encoding="utf-8") as f:
        records: list[dict[str, Any]] = json.load(f)
    pos, unc = load_labels()
    samples: list[dict[str, Any]] = [r for r in records if f"{r['fid']}{r['label']}" not in unc]
    if limit > 0:
        samples = samples[:limit]

    cache: dict[str, Any] = load_cache(cache_path)

    jobs: list[tuple[dict[str, Any], int]] = []
    for r in samples:
        key: str = f"{r['fid']}{r['label']}"
        for half in VLM_CROP_HALFS:
            if cache.get(f"{key}@{half}", {}).get("answer") not in ("YES", "NO"):
                jobs.append((r, half))
    jobs = jobs[:MAX_NEW_PER_RUN]
    logger.info(
        "候选 %d，本轮待判 %d 次调用 (上限 %d)",
        len(samples),
        len(jobs),
        MAX_NEW_PER_RUN,
    )

    headers: dict[str, str] = {"Authorization": f"Bearer {load_token()}"}
    with (
        httpx.Client(headers=headers) as client,
        cf.ThreadPoolExecutor(max_workers=WORKERS) as pool,
    ):
        futs: dict[cf.Future[dict[str, Any]], str] = {}
        for r, half in jobs:
            key = f"{r['fid']}{r['label']}@{half}"
            futs[pool.submit(ask_vlm, client, r, half)] = key
        for done_n, fut in enumerate(cf.as_completed(futs), start=1):
            key = futs[fut]
            try:
                cache[key] = fut.result()
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
                save_cache(cache_path, cache)

    save_cache(cache_path, cache)

    n_pos_hit: int = 0
    n_pos: int = 0
    n_neg_yes: int = 0
    n_neg: int = 0
    n_pending: int = 0
    in_tokens: int = 0
    out_tokens: int = 0
    for r in samples:
        key = f"{r['fid']}{r['label']}"
        answers: list[str] = []
        for half in VLM_CROP_HALFS:
            res: dict[str, Any] = cache.get(f"{key}@{half}", {})
            if res.get("usage"):
                in_tokens += int(res["usage"].get("prompt_tokens", 0))
                out_tokens += int(res["usage"].get("completion_tokens", 0))
            answers.append(res.get("answer", "ERR"))
        valid: list[str] = [a for a in answers if a in ("YES", "NO")]
        if not valid:
            n_pending += 1
            continue
        kept: bool = "YES" in valid
        if key in pos:
            n_pos += 1
            n_pos_hit += int(kept)
        else:
            n_neg += 1
            n_neg_yes += int(kept)
            if kept:
                logger.info("  保留(负): %s t=%.1fs", key, r["t0"])
    logger.info(
        "\n双尺度任一YES: 正样本保留 %d/%d, 负样本保留 %d/%d, 待判 %d",
        n_pos_hit,
        n_pos,
        n_neg_yes,
        n_neg,
        n_pending,
    )
    logger.info("token 用量: 输入 %d, 输出 %d", in_tokens, out_tokens)


if __name__ == "__main__":
    main()
