"""P1 试单：火山方舟（Volcengine Ark）视频理解模型判定慢放片段是否进球。

输入：work/20260722/p1_slowmo/manifest.json（[{key, truth, file, crop}]）
      与同目录 20 个 0.2 倍慢放 mp4（每片段 20 秒，锚点前后各 2 秒实拍）。
输出：work/20260722/p1_slowmo/ark_results.json（_meta 记录模型/prompt 版本/fps/model_errors，
      results 逐片段 verdict/raw/usage/latency；每片段原子落盘，断点续跑幂等）。
依赖：httpx；环境变量 ARK_API_KEY（只经环境变量传入，禁止写入任何文件/日志）；
      vlm_filter 的 parse_answer / normalize_verdict（三值协议与裸判定降级规则）。
典型调用：
    export ARK_API_KEY=<key>
    python scripts/vlm_trial_ark.py             # 串行判定全部未判片段并打印混淆统计
    python scripts/vlm_trial_ark.py --limit 2   # 调试：本轮最多新判 2 个片段
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from errors import BasketballPipelineError, ExternalApiError, ModelUnavailableError, SchemaError
from pipe_common import atomic_write_json, configure_logging, new_run_id, read_json
from vlm_filter import normalize_verdict, parse_answer

logger = logging.getLogger(__name__)

MANIFEST_PATH: Path = Path("work/20260722/p1_slowmo/manifest.json")
RESULTS_PATH: Path = Path("work/20260722/p1_slowmo/ark_results.json")
ARK_API_URL: str = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
# 候选模型按优先级排序；遇模型 ID 报错（NotFound/未开通/Shutdown）切下一个并把错误如实记录
MODEL_CANDIDATES: tuple[str, ...] = (
    "doubao-seed-1-6-vision-250815",
    "doubao-seed-2-0-pro-260215",
    "doubao-seed-1-6-250615",
)
PROMPT_VERSION: str = "ark-p1-v1"  # prompt 语义变更即升版本，旧结果作废（幂等可追溯）
VIDEO_FPS: float = 2.0  # 抽帧频率（文档范围 0.2~5）；20s 慢放取 40 帧，入网瞬间约 0.5s 不漏
MAX_OUTPUT_TOKENS: int = 1024  # 可见输出上限（思维链不计入），证据分析+判定足够
HTTP_TIMEOUT_SEC: float = 300.0  # 视频理解单次最长等待
HTTP_MAX_ATTEMPTS: int = 2  # 首次 + 1 次重试（仅网络错误/429/5xx 可重试）
RETRY_BACKOFF_SEC: float = 5.0
MAX_RAW_STORE: int = 2000  # raw 存档上限（字符），防异常长回复撑爆结果文件
MAX_ERR_BODY: int = 500  # 错误响应体记录上限（字符）
FINAL_VERDICTS: tuple[str, ...] = ("YES", "NO", "UNCLEAR")  # 终态；ERR 下次运行重判
VERDICT_ORDER: tuple[str, ...] = ("YES", "UNCLEAR", "NO", "ERR", "PENDING")
# 模型不可用判定：HTTP 404，或错误体含以下标记（小写匹配；方舟模型未开通/已下线/无权限）
MODEL_ERROR_MARKERS: tuple[str, ...] = (
    "notfound",
    "not found",
    "modelnotopen",
    "not open",
    "shutdown",
    "does not exist",
    "nopermission",
)

PROMPT: str = (
    "这是一段室内篮球场的 0.2 倍慢放视频（约 20 秒，对应真实时间约 4 秒）。"
    "注意：墙上广告海报里可能有印刷的篮球图案，那不是真实篮球。"
    "请判断视频中真实篮球是否穿过篮网进球。"
    "判定规则："
    "1）判 YES 必须给出直接证据：指明约第几秒看到球在网中或正在穿过篮网；"
    "禁止只凭球员跑动、攻防转换节奏等场面线索推断进球；"
    "2）只有同时满足以下条件才允许判 UNCLEAR：能看到投篮动作且球朝篮筐运动、"
    "球到达筐区附近，但入网的关键瞬间没拍到（被遮挡/出画/卡筐沿）；"
    "明显没有投篮动作、球不在筐区、或只是运球/传球/走动的场面，判 NO。"
    "最后一行只输出 YES、NO 或 UNCLEAR 之一，不要输出其他内容。"
)


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """manifest.json 单条：片段键、真值、文件名、是否筐居中裁剪。不可变。"""

    key: str
    truth: str  # "POS"（真进球）| "NEG"（干扰）
    file: str
    crop: bool


@dataclass(frozen=True, slots=True)
class Usage:
    """Ark 单次调用的 token 用量（缺字段归一为 0）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ClipResult:
    """单个片段的判定结果（落盘可序列化）。verdict 为 YES/NO/UNCLEAR/ERR。"""

    key: str
    verdict: str
    raw: str
    model: str
    latency_sec: float
    usage: Usage
    ts: str


@dataclass(frozen=True, slots=True)
class ConfusionStats:
    """混淆统计：POS/NEG 各判定分布、漏报/误报清单、token 与耗时。"""

    pos: dict[str, int]
    neg: dict[str, int]
    pos_as_no: tuple[str, ...]
    neg_as_yes: tuple[str, ...]
    pending: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    latency_sec: float
    judged: int


def load_api_key() -> str:
    """从环境变量读取 ARK_API_KEY（唯一合法传入途径，不落盘、不打印）。

    Returns:
        API Key 字符串。

    Raises:
        ExternalApiError: 环境变量缺失或为空。
    """
    key: str = os.environ.get("ARK_API_KEY", "").strip()
    if not key:
        raise ExternalApiError("缺环境变量 ARK_API_KEY（火山方舟 API Key 只经环境变量传入）")
    return key


def load_manifest(path: Path) -> list[ManifestEntry]:
    """读取并校验 manifest.json（schema 损坏必须停，rules.md §0.2）。

    Args:
        path: manifest.json 路径。

    Returns:
        条目列表（保持文件顺序）。

    Raises:
        SchemaError: 顶层非数组、字段缺失/类型错、truth 非 POS/NEG、key 重复。
    """
    payload: Any = read_json(path, what="manifest.json")
    if not isinstance(payload, list) or not payload:
        raise SchemaError(f"manifest.json 顶层应为非空数组: {path}")
    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            raise SchemaError(f"manifest.json[{i}] 应为对象: {path}")
        key = item.get("key")
        truth = item.get("truth")
        fname = item.get("file")
        crop = item.get("crop")
        if not isinstance(key, str) or not key:
            raise SchemaError(f"manifest.json[{i}].key 缺失或非字符串: {path}")
        if truth not in ("POS", "NEG"):
            raise SchemaError(f"manifest.json[{i}].truth 应为 POS/NEG，实为 {truth!r}")
        if not isinstance(fname, str) or not fname:
            raise SchemaError(f"manifest.json[{i}].file 缺失或非字符串: {path}")
        if not isinstance(crop, bool):
            raise SchemaError(f"manifest.json[{i}].crop 应为 bool: {path}")
        if key in seen:
            raise SchemaError(f"manifest.json key 重复: {key}")
        seen.add(key)
        entries.append(ManifestEntry(key=key, truth=truth, file=fname, crop=crop))
    return entries


def is_model_unavailable(status_code: int, body: str) -> bool:
    """判断 HTTP 错误是否属模型 ID 不可用（应切换下一个候选模型）。

    Args:
        status_code: HTTP 状态码。
        body: 错误响应体（截断后）。

    Returns:
        True 表示模型 NotFound/未开通/已下线/无权限。
    """
    if status_code == 404:
        return True
    low: str = body.lower()
    return any(marker in low for marker in MODEL_ERROR_MARKERS)


def build_payload(model: str, video_b64: str) -> dict[str, Any]:
    """构造 chat/completions 请求体（base64 data URI 视频 + 判定 prompt）。

    视频经 ``video_url`` content part 传入，``fps`` 控制抽帧频率（方舟文档：
    base64 方式文件 <50MB、请求体 <64MB；fps 范围 0.2~5）。

    Args:
        model: 模型 ID。
        video_b64: mp4 文件的 base64 编码。

    Returns:
        请求体 dict。
    """
    return {
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {
                            "url": f"data:video/mp4;base64,{video_b64}",
                            "fps": VIDEO_FPS,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    }


def extract_content(data: dict[str, Any]) -> str:
    """从 chat/completions 响应取助手文本（兼容 str 与 content parts 列表）。

    Args:
        data: 200 响应体。

    Returns:
        助手回复全文；取不到返回空串。
    """
    choices: Any = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first: Any = choices[0]
    if not isinstance(first, dict):
        return ""
    message: Any = first.get("message")
    if not isinstance(message, dict):
        return ""
    content: Any = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = [str(p.get("text", "")) for p in content if isinstance(p, dict)]
        return "\n".join(t for t in parts if t)
    return ""


def _to_int(value: Any) -> int:  # noqa: ANN401 JSON 字段类型不定
    """宽松转 int（usage 字段缺失/异常归一为 0）。"""
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def _to_float(value: Any) -> float:  # noqa: ANN401 JSON 字段类型不定
    """宽松转 float（latency_sec 字段缺失/异常归一为 0.0）。"""
    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0


def parse_response(
    key: str,
    model: str,
    data: dict[str, Any],
    latency_sec: float,
    ts: str,
) -> ClipResult:
    """把 200 响应体转为 ClipResult（三值解析 + 裸判定降级 + usage 归一）。

    裸 YES/NO（raw 全文 <15 字符）经 vlm_filter.normalize_verdict 降级 UNCLEAR。

    Args:
        key: 片段键。
        model: 本次调用所用模型 ID。
        data: 200 响应体。
        latency_sec: 调用耗时（秒）。
        ts: ISO8601 时间戳。

    Returns:
        判定结果（verdict 为 YES/NO/UNCLEAR/ERR）。
    """
    raw: str = extract_content(data)
    answer: str = parse_answer(raw)
    normalized: dict[str, Any] = normalize_verdict(
        {"answer": answer, "usage": data.get("usage"), "raw": raw}
    )
    usage_raw: Any = data.get("usage")
    usage_dict: dict[str, Any] = usage_raw if isinstance(usage_raw, dict) else {}
    usage = Usage(
        prompt_tokens=_to_int(usage_dict.get("prompt_tokens")),
        completion_tokens=_to_int(usage_dict.get("completion_tokens")),
        total_tokens=_to_int(usage_dict.get("total_tokens")),
    )
    return ClipResult(
        key=key,
        verdict=str(normalized["answer"]),
        raw=raw[:MAX_RAW_STORE],
        model=model,
        latency_sec=round(latency_sec, 2),
        usage=usage,
        ts=ts,
    )


def judge_clip(
    client: httpx.Client,
    *,
    api_key: str,
    model: str,
    clip_path: Path,
    key: str,
) -> ClipResult:
    """对单个片段调用一次 Ark 视频理解（网络/429/5xx 可重试 1 次）。

    Args:
        client: httpx 客户端（trust_env=False，国内直连不走代理）。
        api_key: ARK_API_KEY（仅用于请求头，不记录）。
        model: 模型 ID。
        clip_path: 慢放 mp4 路径。
        key: 片段键。

    Returns:
        判定结果；调用失败 verdict=ERR、raw 记错误摘要（不炸整批）。

    Raises:
        ModelUnavailableError: 模型 ID 不可用（调用方负责切换候选模型）。
        ExternalApiError: 凭证级失败（401/403），换模型无意义，应中止。
    """
    t0: float = time.monotonic()
    ts: str = _utc_now()
    try:
        video_b64: str = base64.b64encode(clip_path.read_bytes()).decode("ascii")
    except OSError as exc:
        return ClipResult(key, "ERR", f"读取片段失败: {exc}", model, 0.0, Usage(), ts)
    payload: dict[str, Any] = build_payload(model, video_b64)
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
    last_err: str = "未知错误"
    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        try:
            resp: httpx.Response = client.post(
                ARK_API_URL, json=payload, headers=headers, timeout=HTTP_TIMEOUT_SEC
            )
        except httpx.HTTPError as exc:
            last_err = f"网络错误: {type(exc).__name__}: {exc}"
            logger.warning("%s 第%d/%d次调用网络错误: %s", key, attempt, HTTP_MAX_ATTEMPTS, exc)
        else:
            if resp.status_code == 200:
                latency: float = time.monotonic() - t0
                try:
                    data: dict[str, Any] = resp.json()
                except json.JSONDecodeError as exc:
                    last_err = f"HTTP 200 但响应非 JSON: {exc}"
                else:
                    return parse_response(key, model, data, latency, ts)
            else:
                body: str = resp.text[:MAX_ERR_BODY]
                last_err = f"HTTP {resp.status_code}: {body}"
                if resp.status_code == 401:
                    raise ExternalApiError(f"ARK_API_KEY 认证失败 HTTP 401: {body}")
                if is_model_unavailable(resp.status_code, body):
                    raise ModelUnavailableError(
                        f"模型 {model} 不可用: HTTP {resp.status_code}: {body}"
                    )
                if resp.status_code == 403:
                    raise ExternalApiError(f"ARK_API_KEY 无权限 HTTP 403: {body}")
                if resp.status_code != 429 and resp.status_code < 500:
                    break  # 其他 4xx 属请求问题，重试无意义
                logger.warning(
                    "%s 第%d/%d次调用失败: %s", key, attempt, HTTP_MAX_ATTEMPTS, last_err
                )
        if attempt < HTTP_MAX_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_SEC)
    latency = time.monotonic() - t0
    return ClipResult(key, "ERR", last_err, model, round(latency, 2), Usage(), ts)


def result_from_dict(key: str, data: dict[str, Any]) -> ClipResult:
    """从落盘 dict 还原 ClipResult（字段缺失/类型异常宽松归一，缓存可再生）。

    Args:
        key: 片段键。
        data: 落盘的单条结果 dict。

    Returns:
        还原后的 ClipResult。
    """
    usage_raw: Any = data.get("usage")
    usage_dict: dict[str, Any] = usage_raw if isinstance(usage_raw, dict) else {}
    return ClipResult(
        key=key,
        verdict=str(data.get("verdict", "ERR")),
        raw=str(data.get("raw", "")),
        model=str(data.get("model", "")),
        latency_sec=_to_float(data.get("latency_sec")),
        usage=Usage(
            prompt_tokens=_to_int(usage_dict.get("prompt_tokens")),
            completion_tokens=_to_int(usage_dict.get("completion_tokens")),
            total_tokens=_to_int(usage_dict.get("total_tokens")),
        ),
        ts=str(data.get("ts", "")),
    )


def load_results(path: Path) -> tuple[dict[str, Any], dict[str, ClipResult]]:
    """读取 ark_results.json；缺失→空；协议（prompt 版本/fps）不符→作废重开。

    Args:
        path: 结果文件路径。

    Returns:
        (meta dict, key → ClipResult)。
    """
    if not path.exists():
        return {}, {}
    payload: Any = read_json(path, what="ark_results.json")
    if not isinstance(payload, dict):
        logger.warning("ark_results.json 结构异常，重新开始")
        return {}, {}
    meta: Any = payload.get("_meta")
    meta_dict: dict[str, Any] = meta if isinstance(meta, dict) else {}
    if meta_dict and (
        meta_dict.get("prompt_version") != PROMPT_VERSION or meta_dict.get("fps") != VIDEO_FPS
    ):
        logger.warning("prompt 版本或 fps 变更，旧结果作废重开")
        return {}, {}
    raw_results: Any = payload.get("results")
    results: dict[str, ClipResult] = {}
    if isinstance(raw_results, dict):
        for k, v in raw_results.items():
            if isinstance(v, dict):
                results[k] = result_from_dict(k, v)
    return meta_dict, results


def save_results(
    path: Path,
    model: str,
    model_errors: dict[str, str],
    results: dict[str, ClipResult],
) -> None:
    """原子写 ark_results.json（_meta 记录模型/prompt 版本/fps/model_errors）。

    Args:
        path: 结果文件路径。
        model: 当前采用的模型 ID。
        model_errors: 模型 ID → 不可用错误摘要（如实记录，可追溯）。
        results: key → ClipResult。

    Raises:
        OSError: IO 重试耗尽（由 atomic_write_json 抛出）。
    """
    meta: dict[str, Any] = {
        "prompt_version": PROMPT_VERSION,
        "fps": VIDEO_FPS,
        "model": model,
        "model_candidates": list(MODEL_CANDIDATES),
        "model_errors": model_errors,
        "updated_at": _utc_now(),
    }
    payload: dict[str, Any] = {
        "_meta": meta,
        "results": {k: asdict(v) for k, v in results.items()},
    }
    atomic_write_json(path, payload, what="ark_results.json")


def aggregate_confusion(
    entries: list[ManifestEntry],
    results: dict[str, ClipResult],
) -> ConfusionStats:
    """按真值聚合判定分布与用量（纯函数，供统计打印与单测）。

    Args:
        entries: manifest 条目（含真值）。
        results: 已判结果（key → ClipResult）；缺失条目记 PENDING。

    Returns:
        ConfusionStats（POS/NEG 各判定计数、POS 判 NO / NEG 判 YES 清单、token 与耗时）。
    """
    pos: dict[str, int] = {v: 0 for v in VERDICT_ORDER}
    neg: dict[str, int] = {v: 0 for v in VERDICT_ORDER}
    pos_as_no: list[str] = []
    neg_as_yes: list[str] = []
    pending: list[str] = []
    in_tok: int = 0
    out_tok: int = 0
    latency: float = 0.0
    judged: int = 0
    for e in entries:
        bucket: dict[str, int] = pos if e.truth == "POS" else neg
        res: ClipResult | None = results.get(e.key)
        if res is None:
            bucket["PENDING"] += 1
            pending.append(e.key)
            continue
        verdict: str = res.verdict if res.verdict in VERDICT_ORDER else "ERR"
        bucket[verdict] += 1
        judged += 1
        in_tok += res.usage.prompt_tokens
        out_tok += res.usage.completion_tokens
        latency += res.latency_sec
        if e.truth == "POS" and verdict == "NO":
            pos_as_no.append(e.key)
        if e.truth == "NEG" and verdict == "YES":
            neg_as_yes.append(e.key)
    return ConfusionStats(
        pos=pos,
        neg=neg,
        pos_as_no=tuple(pos_as_no),
        neg_as_yes=tuple(neg_as_yes),
        pending=tuple(pending),
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_sec=round(latency, 2),
        judged=judged,
    )


def run_trial(
    entries: list[ManifestEntry],
    results: dict[str, ClipResult],
    *,
    client: httpx.Client,
    api_key: str,
    start_model: str,
    model_errors: dict[str, str],
    work_dir: Path,
    limit: int,
    results_path: Path,
) -> str:
    """串行判定未判片段（每片段后原子落盘，断点续跑；ERR 下次重判）。

    模型不可用时作废该模型已判结果并切换下一个候选（保证混淆统计单一模型）；
    单片段失败记 ERR 不炸整批。

    Args:
        entries: manifest 条目。
        results: 已有结果（原地更新）。
        client: httpx 客户端。
        api_key: ARK_API_KEY。
        start_model: 起始模型 ID。
        model_errors: 模型 ID → 错误摘要（原地更新）。
        work_dir: 片段所在目录。
        limit: 本轮最多新判定片段数（0=不限）。
        results_path: 结果落盘路径。

    Returns:
        最终采用的模型 ID。

    Raises:
        ExternalApiError: 凭证失败或所有候选模型均不可用。
    """
    models: list[str] = [start_model] + [m for m in MODEL_CANDIDATES if m != start_model]
    mi: int = 0
    judged_this_run: int = 0
    i: int = 0
    while i < len(entries):
        entry: ManifestEntry = entries[i]
        cur: ClipResult | None = results.get(entry.key)
        if cur is not None and cur.model == models[mi] and cur.verdict in FINAL_VERDICTS:
            i += 1
            continue
        if limit > 0 and judged_this_run >= limit:
            logger.info("达到本轮 limit=%d，退出（剩余待判下次继续）", limit)
            break
        clip_path: Path = work_dir / entry.file
        if not clip_path.exists():
            logger.error("片段缺失，记 ERR: %s", clip_path)
            results[entry.key] = ClipResult(
                entry.key, "ERR", "片段文件缺失", models[mi], 0.0, Usage(), _utc_now()
            )
            i += 1
            continue
        try:
            res: ClipResult = judge_clip(
                client, api_key=api_key, model=models[mi], clip_path=clip_path, key=entry.key
            )
        except ModelUnavailableError as exc:
            model_errors[models[mi]] = str(exc)[:MAX_ERR_BODY]
            logger.error("模型 %s 不可用: %s", models[mi], exc)
            stale: list[str] = [k for k, v in results.items() if v.model == models[mi]]
            for k in stale:
                del results[k]
            mi += 1
            if mi >= len(models):
                raise ExternalApiError("所有候选模型均不可用，详见 model_errors") from exc
            logger.warning("切换候选模型 → %s（作废旧模型结果 %d 条）", models[mi], len(stale))
            i = 0  # 新模型从头扫（其已判条目会被上面的跳过条件挡住）
            continue
        results[entry.key] = res
        judged_this_run += 1
        logger.info(
            "[%d/%d] %s → %s（%.1fs, in=%d out=%d）",
            judged_this_run,
            len(entries),
            entry.key,
            res.verdict,
            res.latency_sec,
            res.usage.prompt_tokens,
            res.usage.completion_tokens,
        )
        save_results(results_path, models[mi], model_errors, results)
        i += 1
    return models[mi]


def _first_line(raw: str, limit: int = 80) -> str:
    """取 raw 首个非空行并截断（一句话理由摘要）。

    Args:
        raw: 模型回复全文。
        limit: 截断长度（字符）。

    Returns:
        一句话摘要；无内容返回空串。
    """
    for ln in raw.splitlines():
        s: str = ln.strip()
        if s:
            return s[:limit]
    return ""


def log_confusion(entries: list[ManifestEntry], results: dict[str, ClipResult]) -> None:
    """打印混淆统计与逐片段一句话理由（面向用户的最终结果）。

    Args:
        entries: manifest 条目（含真值）。
        results: 已判结果（key → ClipResult）。
    """
    stats: ConfusionStats = aggregate_confusion(entries, results)
    logger.info("===== 混淆统计（真值 × 判定） =====")
    for truth, counts in (("POS", stats.pos), ("NEG", stats.neg)):
        parts: str = ", ".join(f"{v}={counts[v]}" for v in VERDICT_ORDER)
        logger.info("%s 共 %d: %s", truth, sum(counts.values()), parts)
    for k in stats.pos_as_no:
        logger.info("POS 判 NO（漏报）: %s", k)
    for k in stats.neg_as_yes:
        logger.info("NEG 判 YES（误报）: %s", k)
    logger.info("逐片段判定与理由:")
    for e in entries:
        res: ClipResult | None = results.get(e.key)
        if res is None:
            logger.info("  [PENDING] %s", e.key)
        else:
            logger.info("  [%s→%s] %s | %s", e.truth, res.verdict, e.key, _first_line(res.raw))
    logger.info(
        "token 用量: 输入 %d, 输出 %d; 已判 %d/%d, 累计耗时 %.1fs",
        stats.input_tokens,
        stats.output_tokens,
        stats.judged,
        len(entries),
        stats.latency_sec,
    )


def _utc_now() -> str:
    """UTC ISO8601 时间戳（结果落盘用）。"""
    return datetime.now(UTC).isoformat()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """解析 CLI 参数。

    Args:
        argv: 参数列表（None 取 sys.argv）。

    Returns:
        解析后的命名空间。
    """
    parser = argparse.ArgumentParser(description="P1 试单：Ark 视频理解判定慢放片段")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="manifest.json 路径")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="结果 JSON 路径")
    parser.add_argument("--limit", type=int, default=0, help="本轮最多新判定片段数（0=不限）")
    parser.add_argument("--model", default="", help="强制起始模型（默认按候选优先级探测）")
    return parser.parse_args(argv)


def _run(args: argparse.Namespace, *, run_id: str) -> int:
    """业务主流程：读 manifest → 逐片段判定 → 落盘 → 混淆统计。

    Args:
        args: CLI 参数。
        run_id: 本次运行 ID。

    Returns:
        进程退出码（0=正常完成，1=凭证/模型全局失败，已完成部分仍落盘并出统计）。
    """
    api_key: str = load_api_key()
    entries: list[ManifestEntry] = load_manifest(args.manifest)
    meta, results = load_results(args.results)
    model_errors: dict[str, str] = {}
    if isinstance(meta.get("model_errors"), dict):
        model_errors = {str(k): str(v) for k, v in meta["model_errors"].items()}
    start_model: str = args.model or str(meta.get("model") or "") or MODEL_CANDIDATES[0]
    if start_model not in MODEL_CANDIDATES:
        logger.warning("起始模型 %s 不在候选清单，按 --model/历史结果继续", start_model)
    work_dir: Path = args.manifest.parent
    logger.info("run=%s 片段 %d 个，起始模型 %s", run_id, len(entries), start_model)
    exit_code: int = 0
    final_model: str = start_model
    with httpx.Client(trust_env=False) as client:  # trust_env=False：国内直连，不走代理
        try:
            final_model = run_trial(
                entries,
                results,
                client=client,
                api_key=api_key,
                start_model=start_model,
                model_errors=model_errors,
                work_dir=work_dir,
                limit=args.limit,
                results_path=args.results,
            )
        except ExternalApiError as exc:
            logger.error("试单中止 run_id=%s: %s", run_id, exc)
            exit_code = 1
    save_results(args.results, final_model, model_errors, results)
    log_confusion(entries, results)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。返回进程退出码（0=成功，非 0=失败）。

    Args:
        argv: 参数列表（None 取 sys.argv）。
    """
    args: argparse.Namespace = _parse_args(argv)
    run_id: str = new_run_id()
    configure_logging(run_id)
    try:
        return _run(args, run_id=run_id)
    except BasketballPipelineError as exc:
        logger.error("试单失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1
    except OSError as exc:
        logger.error("IO 失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
