#!/usr/bin/env python3
"""生成缩略图墙扫尾页面 triage.html：人工视频标注前先用 3 帧快照扫掉垃圾事件。

读取 gen_review_clips --keep-clips 产出的事件索引（events_index.json，事件顺序
= 筐距序），对每事件从 work/frames/<fid>/ 取锚点帧及其 ±2 帧（±0.4s @5fps），
PIL 缩成 480px 宽缩略图落 <review_dir>/thumbs/，并在 <review_dir> 生成
triage.html 网格墙。墙与 label.html 共享 localStorage（同 LSKEY、同 marks
结构），墙标"不是"的事件 label.html 侧自动视为已标并跳过。

交互红线（docs/batch-speedup/spec.md F1 三条硬规定）：
1. 墙只能否、不能是——缩略图看不清入网瞬间，判"是"必须去 label.html 放视频；
2. 渲染与点击均以 localStorage 实时值为准，已标事件（goal/practice/no 一律）
   展示其标注且 F 按钮禁用，只允许对未标事件写 {r:"no"}；
3. save 合并写复刻 label.html（保存前重读 LSKEY + Object.assign(stored, marks)
   再写），绝不写 LSKEY_pos 位置键（写了会破坏 label.html 断点续标）。

输入：--index 指定的 events_index.json（结构 {"events": [{key, fid, event_idx,
      clip, clip_wide, src_file, anchor_t0, hoop_dist, verdict}, ...]}）；
      work/frames/<fid>/f_%05d.jpg（5fps 抽帧，已存在，零新计算）
输出：<review_dir>/thumbs/t_<safekey>_<i>.jpg（480px 宽）+ <review_dir>/triage.html
依赖：PIL（pillow）；scripts/ 内 gen_label_page（assign_same_rally_groups）、
      mot_candidates（SAMPLE_FPS）、pipe_common（sec_to_frame_idx/read_json/日志）
典型调用：
    python scripts/gen_triage_page.py --index work/20260722/review_batch3/events_index.json \
        --session 20260722_3
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

from PIL import Image

from errors import BasketballPipelineError
from gen_label_page import assign_same_rally_groups
from mot_candidates import SAMPLE_FPS
from pipe_common import configure_logging, new_run_id, read_json, sec_to_frame_idx

logger = logging.getLogger(__name__)

THUMB_WIDTH: int = 480  # 缩略图宽（px，spec F1）
FRAME_WINDOW: int = 2  # 锚点帧前后各取帧数（±0.4s @5fps，spec F1）
THUMB_QUALITY: int = 85  # JPEG 质量（扫尾看图够用即可）
FRAMES_ROOT: Path = Path("work/frames")  # 抽帧根目录（extract_frames 产物）
FRAME_GLOB: str = "f_*.jpg"  # 抽帧文件命名（extract_frames 口径）
FRAME_NAME: str = "f_{:05d}.jpg"  # 帧号 → 文件名


def frame_indices(anchor_t0: float, frame_count: int, *, fps: float = SAMPLE_FPS) -> list[int]:
    """锚点秒数 → 3 个抽帧帧号：锚点帧及其 ±FRAME_WINDOW 帧，钳位 [1, 帧数] 并去重。

    锚点帧用 pipe_common.sec_to_frame_idx（与 mot_candidates.parse_sec 互逆的
    单点映射，不另写魔数）。锚点距片尾 <0.4s 时 +2 帧钳位到末帧（大疆尾截短
    素材的合法降级）；frame_count <= 0（帧目录缺失/为空）返回空列表。

    Args:
        anchor_t0: 事件锚点秒数。
        frame_count: 该 fid 的抽帧总数（work/frames/<fid>/ 下 f_*.jpg 计数）。
        fps: 抽帧帧率（生产为 mot_candidates.SAMPLE_FPS=5.0）。

    Returns:
        1 起帧号列表，升序去重，长度 0~3。
    """
    if frame_count <= 0:
        return []
    center: int = sec_to_frame_idx(anchor_t0, fps)
    clamped = [min(max(center + off, 1), frame_count) for off in (-FRAME_WINDOW, 0, FRAME_WINDOW)]
    return list(dict.fromkeys(clamped))


def safe_name(key: str) -> str:
    """事件 key → 文件名安全串：非 [0-9A-Za-z._-] 字符一律替换为下划线。

    key 含 `#`（如 <fid>#e3）等 URL/文件名不友好字符，缩略图文件名必须安全化；
    不同 key 替换后撞名时后者覆盖前者（同 fid 内 key 前缀相同、仅事件号不同，
    `#eN`→`_eN` 不撞，实测可接受）。

    Args:
        key: 事件 key。

    Returns:
        仅含安全字符的文件名片段。
    """
    return re.sub(r"[^0-9A-Za-z._-]+", "_", key)


def count_frames(frames_root: Path, fid: str) -> int:
    """数 work/frames/<fid>/ 下的抽帧数；目录缺失返回 0。"""
    d: Path = frames_root / fid
    if not d.is_dir():
        return 0
    return len(list(d.glob(FRAME_GLOB)))


def make_thumbnail(src: Path, dst: Path, *, width: int = THUMB_WIDTH) -> None:
    """把帧图缩成 width px 宽 JPEG 缩略图（等比缩放，不裁不切）。

    Args:
        src: 源帧图路径。
        dst: 目标缩略图路径（父目录须已存在）。
        width: 目标宽度（px）。

    Raises:
        OSError: 源图不可读/不可识别或写盘失败（PIL UnidentifiedImageError
            是 OSError 子类，一并覆盖）。
    """
    with Image.open(src) as im:
        rgb = im.convert("RGB")
        height: int = max(1, round(rgb.height * width / rgb.width))
        rgb.resize((width, height), Image.Resampling.LANCZOS).save(
            dst, "JPEG", quality=THUMB_QUALITY
        )


def build_event_thumbs(
    events: list[dict[str, Any]],
    frames_root: Path,
    thumbs_dir: Path,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """逐事件生成 3 帧缩略图，返回（增强事件列表, 降级清单, 跳过清单）。

    残次事件（缺 fid/anchor_t0/key）跳过 + WARNING（与 assign_same_rally_groups
    同款口径）；帧目录缺失或帧文件缺失降级用可用帧 + WARNING，不崩。增强事件 =
    原 dict 副本加 thumbs 字段（[{"src": 相对路径, "frame": 帧号}]），不改调用方
    原 dict。

    Args:
        events: events_index.json 的事件列表。
        frames_root: 抽帧根目录（work/frames）。
        thumbs_dir: 缩略图输出目录（须已创建）。

    Returns:
        (enriched, degraded, skipped)：enriched 为可上墙事件（含 thumbs）；
        degraded/skipped 为人类可读条目，供结尾汇总。
    """
    enriched: list[dict[str, Any]] = []
    degraded: list[str] = []
    skipped: list[str] = []
    frame_counts: dict[str, int] = {}
    for e in events:
        fid: Any = e.get("fid")
        anchor: Any = e.get("anchor_t0")
        key: Any = e.get("key")
        if (
            not isinstance(fid, str)
            or not isinstance(anchor, (int, float))
            or isinstance(anchor, bool)
            or not isinstance(key, str)
        ):
            logger.warning("事件缺 fid/anchor_t0/key，跳过缩略图: %s", str(e)[:80])
            skipped.append(str(e)[:80])
            continue
        if fid not in frame_counts:
            frame_counts[fid] = count_frames(frames_root, fid)
        count: int = frame_counts[fid]
        if count <= 0:
            logger.warning("帧目录缺失或为空 %s（%s），降级为零帧卡片", frames_root / fid, key)
            degraded.append(f"{key}: 帧目录缺失 {fid}")
        safe: str = safe_name(key)
        thumbs: list[dict[str, Any]] = []
        for n, idx in enumerate(frame_indices(float(anchor), count)):
            src: Path = frames_root / fid / FRAME_NAME.format(idx)
            if not src.is_file():
                logger.warning("缺帧 %s（%s t=%ss），降级用可用帧", src, key, anchor)
                degraded.append(f"{key}: 缺帧 {FRAME_NAME.format(idx)}")
                continue
            dst: Path = thumbs_dir / f"t_{safe}_{n}.jpg"
            try:
                make_thumbnail(src, dst)
            except OSError as exc:
                logger.warning("缩略图失败 %s -> %s: %s，降级用可用帧", src, dst, exc)
                degraded.append(f"{key}: 缩略图失败 {FRAME_NAME.format(idx)}")
                continue
            thumbs.append({"src": f"thumbs/{dst.name}", "frame": idx})
        item: dict[str, Any] = dict(e)
        item["thumbs"] = thumbs
        enriched.append(item)
    return enriched, degraded, skipped


# 注意必须是 raw string：模板内 JS 字符串含 \n 转义（扫尾完成提示文案），
# 普通三引号会被 Python 转义成真实换行，导致 JS 字符串跨行 SyntaxError（整页黑屏）
_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>扫尾墙 __SESSION__</title>
<style>
body { font-family: sans-serif; background: #111; color: #eee; margin: 16px; }
#bar { position: sticky; top: 0; background: #111; padding: 8px 0; z-index: 9; }
#grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
        gap: 12px; }
.card { background: #1d1d1d; border-radius: 8px; padding: 8px; }
.card.marked { opacity: 0.55; }
.thumbs { display: flex; gap: 4px; margin-bottom: 6px; }
.thumbs img { width: 32%; border-radius: 4px; background: #000; }
button.f { font-size: 16px; padding: 6px 14px; margin-top: 6px; border-radius: 6px;
           border: 0; background: #b03a3a; color: #fff; cursor: pointer; }
button.f:disabled { background: #444; color: #999; cursor: default; }
.badge { color: #fc3; }
.grp { color: #3cf; }
small { color: #999; }
</style>
</head>
<body>
<div id="bar">
  <b>缩略图墙扫尾 __SESSION__</b> <span id="prog"></span><br>
  <small>墙只能否、不能是：拿不准一律不标，判“是”去 label.html 放视频。
  与标注页共享进度，已标事件在此只读展示（F 按钮禁用）。</small>
</div>
<div id="grid"></div>
<script>
const EVENTS = __EVENTS__;
const SESSION = "__SESSION__";
const LSKEY = "label_" + SESSION;
const RLABEL = { goal: "进球", practice: "进球但不收", no: "不是" };
let marks = loadMarks();
function loadMarks() {
  try { return JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { return {}; }
}
function save() {
  // 合并写入：先读回存储与本页记录合并再写，防止与 label.html 同时开互相覆盖
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { stored = {}; }
  marks = Object.assign(stored, marks);
  localStorage.setItem(LSKEY, JSON.stringify(marks));
}
function esc(s) {
  return String(s).replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function render() {
  marks = loadMarks();  // 渲染以 localStorage 实时值为准（硬规定 2：墙不得覆盖已有标注）
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  let marked = 0, nos = 0;
  for (const e of EVENTS) {
    const m = marks[e.key];
    if (m) { marked++; if (m.r === "no") nos++; }
    const card = document.createElement("div");
    card.className = "card" + (m ? " marked" : "");
    const imgs = e.thumbs.map(t =>
      `<img loading="lazy" src="${esc(t.src)}" title="帧 ${t.frame}">`).join("");
    const grp = e.grp
      ? ` <span class="grp">疑似同回合（组 ${e.grp}，共 ${e.grp_size} 个）</span>` : "";
    const badge = m ? ` <span class="badge">已标：${RLABEL[m.r] || m.r}</span>` : "";
    const verdict = e.verdict ? ` | 机器: ${esc(e.verdict)}` : "";
    card.innerHTML =
      `<div class="thumbs">${imgs}</div>` +
      `<div><b>${esc(e.key)}</b> t=${e.anchor_t0}s${badge}${grp}<br>` +
      `<small>${esc(e.src_file)}${verdict}</small></div>`;
    const btn = document.createElement("button");
    btn.className = "f";
    btn.textContent = "不是 (F)";
    btn.disabled = !!m;  // 已标事件（goal/practice/no 一律）F 按钮禁用
    btn.onclick = () => markNo(e.key);
    card.appendChild(btn);
    grid.appendChild(card);
  }
  document.getElementById("prog").textContent =
    `共 ${EVENTS.length} 事件 | 已标 ${marked}（墙标不是 ${nos}）`;
}
function markNo(key) {
  marks = loadMarks();  // 点击以 localStorage 实时值为准，绝不覆盖已有标注
  if (marks[key]) { render(); return; }
  marks[key] = { r: "no" };
  save();
  render();
  if (EVENTS.every(e => marks[e.key])) {
    alert("全部事件均已有标注。\n判“是”请去 label.html 放视频确认。");
  }
}
render();
</script>
</body>
</html>
"""


def build_html(events: list[dict[str, Any]], session: str) -> str:
    """把增强事件列表渲染为自包含扫尾墙 HTML。

    疑似同回合分组（assign_same_rally_groups）在此注入：成组事件内联数据
    加 grp（组号）/ grp_size（组大小）字段，卡片显示"疑似同回合"标签
    （机器只提示不判定）。

    Args:
        events: build_event_thumbs 产出的增强事件列表（复制后加 grp 字段
            内联，不改调用方原 dict）。
        session: 场次名（页面标题与 localStorage 键后缀，LSKEY 与
            label.html 完全一致：label_<session>）。

    Returns:
        triage.html 全文。
    """
    groups: dict[str, int] = assign_same_rally_groups(events)
    sizes: dict[int, int] = {}
    for g in groups.values():
        sizes[g] = sizes.get(g, 0) + 1
    enriched: list[dict[str, Any]] = []
    for e in events:
        item: dict[str, Any] = dict(e)
        g: int | None = groups.get(e.get("key"))
        if g is not None:
            item["grp"] = g
            item["grp_size"] = sizes[g]
        enriched.append(item)
    return _HTML.replace("__EVENTS__", json.dumps(enriched, ensure_ascii=False)).replace(
        "__SESSION__", session
    )


def derive_session(index_dir: Path) -> str:
    """从 index 父目录名推导场次：父目录以 review 开头时上溯祖父目录名。

    与 gen_label_page 的推导条件逻辑一致（work/<场次>/review*/events_index.json
    → <场次>）。

    Args:
        index_dir: events_index.json 所在目录（review_dir）。

    Returns:
        场次名。
    """
    parent: str = index_dir.name
    return index_dir.parent.name if parent.startswith("review") else parent


def main(argv: list[str] | None = None) -> int:
    """主入口：读事件索引，产缩略图与 triage.html，结尾汇总降级/跳过清单。

    Returns:
        进程退出码：0=成功（降级/跳过按 spec 仅 WARNING 不失败）；
        1=索引缺失/损坏/无事件。
    """
    run_id: str = new_run_id()
    configure_logging(run_id)
    ap = argparse.ArgumentParser(description="生成缩略图墙扫尾页面")
    ap.add_argument("--index", required=True, help="events_index.json 路径")
    ap.add_argument(
        "--session", default="", help="场次名（默认取 index 父目录名，review 开头则上溯祖父）"
    )
    args = ap.parse_args(argv)

    index_path: Path = Path(args.index)
    try:
        payload = read_json(index_path, what="events_index.json")
    except (BasketballPipelineError, OSError) as exc:
        logger.error("读取索引失败: %s", exc)
        return 1
    events = payload.get("events", []) if isinstance(payload, dict) else []
    if not events:
        logger.error("索引中无事件: %s", index_path)
        return 1

    review_dir: Path = index_path.resolve().parent
    session: str = args.session or derive_session(review_dir)
    thumbs_dir: Path = review_dir / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    enriched, degraded, skipped = build_event_thumbs(events, FRAMES_ROOT, thumbs_dir)
    html: str = build_html(enriched, session)
    out_path: Path = review_dir / "triage.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(
        "扫尾墙 %d/%d 事件（缩略图目录 %s）-> %s",
        len(enriched),
        len(events),
        thumbs_dir,
        out_path,
    )
    if degraded:
        logger.warning("降级清单（%d 条）:", len(degraded))
        for line in degraded:
            logger.warning("  降级: %s", line)
    if skipped:
        logger.warning("跳过清单（%d 条）:", len(skipped))
        for line in skipped:
            logger.warning("  跳过: %s", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
