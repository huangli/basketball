#!/usr/bin/env python3
"""生成缩略图墙扫尾页面 triage.html：人工视频标注前先用 3 帧快照扫掉垃圾事件。

读取 gen_review_clips --keep-clips 产出的事件索引（events_index.json，事件顺序
= 筐距序），对每事件从 work/frames/<fid>/ 取锚点帧及其 ±2 帧（±0.4s @5fps）。
传 --hoops 时用 detect_hoops 的事件锚点（筐/球静止点）裁筐区放大（帧宽 40%
窗口，640px 落盘）——全景缩略图球太小看不清入网，筐区裁剪才可判读（批次 3
实测）；锚点缺失事件降级全景。缩略图落 <review_dir>/thumbs/，并在
<review_dir> 生成 triage.html 网格墙（锚点帧大图主判、±帧小图参考）。墙与
label.html 共享 localStorage（同 LSKEY、同 marks 结构），墙标"不是"的事件
label.html 侧自动视为已标并跳过。

交互红线（docs/batch-speedup/spec.md F1 三条硬规定）：
1. 墙只能否、不能是——缩略图看不清入网瞬间，判"是"必须去 label.html 放视频；
2. 渲染与点击均以 localStorage 实时值为准，已标事件（goal/practice/no 一律）
   展示其标注且 F 按钮禁用，只允许对未标事件写 {r:"no"}；
3. save 合并写复刻 label.html（保存前重读 LSKEY + Object.assign(stored, marks)
   再写），绝不写 LSKEY_pos 位置键（写了会破坏 label.html 断点续标）。

输入：--index 指定的 events_index.json（结构 {"events": [{key, fid, event_idx,
      clip, clip_wide, src_file, anchor_t0, hoop_dist, verdict}, ...]}）；
      --hoops 指定的 detect_hoops 产物（{"events": [{key, anchor: [cx,cy]}]}，
      可选，提供筐区裁剪锚点）；
      work/frames/<fid>/f_%05d.jpg（5fps 抽帧，已存在，零新计算）
输出：<review_dir>/thumbs/t_<safekey>_<i>.jpg（筐区 640px / 全景 480px 宽）
      + <review_dir>/triage.html
依赖：PIL（pillow）；scripts/ 内 gen_label_page（assign_same_rally_groups）、
      mot_candidates（SAMPLE_FPS）、pipe_common（sec_to_frame_idx/read_json/日志）
典型调用：
    python scripts/gen_triage_page.py --index work/20260722/review_batch3/events_index.json \
        --session 20260722 --hoops work/20260722/hoops_batch3.json
"""

import argparse
import json
import logging
import math
import re
from pathlib import Path
from typing import Any

from PIL import Image

from errors import BasketballPipelineError
from gen_label_page import assign_same_rally_groups
from mot_candidates import SAMPLE_FPS
from pipe_common import configure_logging, new_run_id, read_json, sec_to_frame_idx

logger = logging.getLogger(__name__)

THUMB_WIDTH: int = 480  # 全景降级缩略图宽（px，spec F1）
CROP_WIDTH: int = 640  # 筐区裁剪缩略图宽（px，入网瞬间可判读的实测下限）
CROP_RATIO: float = 0.4  # 裁剪窗宽 = 帧图宽 × 此比例（1920 帧 → 768px 实测球/筐清晰）
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


def make_thumbnail(
    src: Path,
    dst: Path,
    *,
    width: int = THUMB_WIDTH,
    anchor: tuple[float, float] | None = None,
) -> str:
    """把帧图缩成缩略图 JPEG；给 anchor 时以其为中心裁筐区再缩放。

    anchor 是 hoops 检测输出的事件锚点（筐/球静止点，帧图像素坐标系）。
    裁剪窗 = 帧宽 × CROP_RATIO 的 16:9 矩形（比例固定，任何宽高比帧图
    均在帧内；4:3 帧裁出横向带），中心钳位在帧图内。无 anchor 时等比
    缩全图（不裁不切，与旧行为一致）。

    Args:
        src: 源帧图路径。
        dst: 目标缩略图路径（父目录须已存在）。
        width: 全景模式目标宽度（px）；裁剪模式固定用 CROP_WIDTH。
        anchor: 事件锚点 (cx, cy)；None 走全景模式。

    Returns:
        实际模式："crop" 或 "full"（供事件数据记录展示）。

    Raises:
        OSError: 源图不可读/不可识别或写盘失败（PIL UnidentifiedImageError
            是 OSError 子类，一并覆盖）。
    """
    with Image.open(src) as im:
        rgb = im.convert("RGB")
        if anchor is not None:
            cw: int = min(rgb.width, max(1, round(rgb.width * CROP_RATIO)))
            ch: int = min(rgb.height, max(1, round(cw * 9 / 16)))
            cx, cy = anchor
            x0: int = min(max(round(cx - cw / 2), 0), rgb.width - cw)
            y0: int = min(max(round(cy - ch / 2), 0), rgb.height - ch)
            rgb = rgb.crop((x0, y0, x0 + cw, y0 + ch))
            width = CROP_WIDTH
        height: int = max(1, round(rgb.height * width / rgb.width))
        rgb.resize((width, height), Image.Resampling.LANCZOS).save(
            dst, "JPEG", quality=THUMB_QUALITY
        )
        return "crop" if anchor is not None else "full"


def build_event_thumbs(
    events: list[dict[str, Any]],
    frames_root: Path,
    thumbs_dir: Path,
    anchors: dict[str, tuple[float, float]] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """逐事件生成 3 帧缩略图，返回（增强事件列表, 降级清单, 跳过清单）。

    残次事件（缺 fid/anchor_t0/key）跳过 + WARNING（与 assign_same_rally_groups
    同款口径）；帧目录缺失或帧文件缺失降级用可用帧 + WARNING，不崩。增强事件 =
    原 dict 副本加 thumbs 字段（[{"src": 相对路径, "frame": 帧号, "mode":
    crop/full}]），不改调用方原 dict。

    Args:
        events: events_index.json 的事件列表。
        frames_root: 抽帧根目录（work/frames）。
        thumbs_dir: 缩略图输出目录（须已创建）。
        anchors: 事件 key → 筐区锚点 (cx, cy)（来自 hoops json）；None 或
            缺 key 时该事件走全景降级。

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
        crop_anchor: tuple[float, float] | None = anchors.get(key) if anchors else None
        if anchors is not None and crop_anchor is None:
            degraded.append(f"{key}: hoops 无锚点，全景降级")
        thumbs: list[dict[str, Any]] = []
        anchor_frame: int = sec_to_frame_idx(float(anchor), SAMPLE_FPS)
        for n, idx in enumerate(frame_indices(float(anchor), count)):
            src: Path = frames_root / fid / FRAME_NAME.format(idx)
            if not src.is_file():
                logger.warning("缺帧 %s（%s t=%ss），降级用可用帧", src, key, anchor)
                degraded.append(f"{key}: 缺帧 {FRAME_NAME.format(idx)}")
                continue
            dst: Path = thumbs_dir / f"t_{safe}_{n}.jpg"
            try:
                mode: str = make_thumbnail(src, dst, anchor=crop_anchor)
            except OSError as exc:
                logger.warning("缩略图失败 %s -> %s: %s，降级用可用帧", src, dst, exc)
                degraded.append(f"{key}: 缩略图失败 {FRAME_NAME.format(idx)}")
                continue
            # 显式标记锚点帧：钳位去重/缺帧时锚点项不一定是 thumbs 中间项，
            # 页面大图主判必须按标记取，不能按位置假设
            thumbs.append(
                {
                    "src": f"thumbs/{dst.name}",
                    "frame": idx,
                    "mode": mode,
                    "is_anchor": idx == anchor_frame,
                }
            )
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
#grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(660px, 1fr));
        gap: 12px; }
.card { background: #1d1d1d; border-radius: 8px; padding: 8px; }
.card.marked { opacity: 0.55; }
.main { width: 100%; border-radius: 4px; background: #000; margin-bottom: 4px; }
.subs { display: flex; gap: 4px; margin-bottom: 6px; }
.subs img { width: 24%; border-radius: 4px; background: #000; }
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
    // 锚点帧（入网瞬间）大图主判，±0.4s 帧小图参考；全景降级事件同布局仍可看。
    // 主图按 is_anchor 标记取（钳位去重/缺帧时锚点项不在中间），无标记回退中间项
    let mainIdx = e.thumbs.findIndex(t => t.is_anchor);
    if (mainIdx < 0) mainIdx = Math.floor(e.thumbs.length / 2);
    const mainImg = e.thumbs.length
      ? `<img class="main" loading="lazy" src="${esc(e.thumbs[mainIdx].src)}"` +
        ` title="锚点帧 ${e.thumbs[mainIdx].frame}">`
      : "";
    const subImgs = e.thumbs.filter((_, i) => i !== mainIdx).map(t =>
      `<img loading="lazy" src="${esc(t.src)}" title="帧 ${t.frame}">`).join("");
    const grp = e.grp
      ? ` <span class="grp">疑似同回合（组 ${e.grp}，共 ${e.grp_size} 个）</span>` : "";
    const badge = m ? ` <span class="badge">已标：${RLABEL[m.r] || m.r}</span>` : "";
    // 全景降级（hoops 无锚点/未传 --hoops）角标：提醒此卡不是筐区特写，判读慎用
    const fullBadge = e.thumbs.some(t => t.mode === "full")
      ? ` <span class="grp">全景降级</span>` : "";
    const verdict = e.verdict ? ` | 机器: ${esc(e.verdict)}` : "";
    card.innerHTML =
      mainImg +
      `<div class="subs">${subImgs}</div>` +
      `<div><b>${esc(e.key)}</b> t=${e.anchor_t0}s${badge}${grp}${fullBadge}<br>` +
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


def load_anchors(path: Path) -> dict[str, tuple[float, float]]:
    """读 hoops json，建 事件 key → 筐区锚点 (cx, cy) 映射。

    hoops json 是 detect_hoops 产物（{"events": [{key, anchor: [cx, cy], ...}]}），
    anchor 为帧图像素坐标。锚点缺失或形状非法（非两数列表）的事件不进映射，
    由调用方走全景降级；文件级损坏抛给调用方处理。

    Args:
        path: hoops json 路径。

    Returns:
        key → (cx, cy) 字典。

    Raises:
        BasketballPipelineError/OSError: 文件缺失或 JSON 损坏（read_json 口径）。
    """
    payload: Any = read_json(path, what="hoops json")
    events: Any = payload.get("events", []) if isinstance(payload, dict) else []
    anchors: dict[str, tuple[float, float]] = {}
    for e in events if isinstance(events, list) else []:
        if not isinstance(e, dict):
            continue
        key: Any = e.get("key")
        a: Any = e.get("anchor")
        if (
            isinstance(key, str)
            and isinstance(a, list)
            and len(a) == 2
            and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in a
            )
        ):
            anchors[key] = (float(a[0]), float(a[1]))
    return anchors


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
    ap.add_argument(
        "--hoops",
        default="",
        help="hoops json 路径（detect_hoops 产物，提供筐区锚点做裁剪放大；不传则全景缩略图）",
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

    anchors: dict[str, tuple[float, float]] | None = None
    if args.hoops:
        try:
            anchors = load_anchors(Path(args.hoops))
        except (BasketballPipelineError, OSError) as exc:
            logger.error("读取 hoops 失败: %s", exc)
            return 1
        logger.info("筐区锚点 %d/%d 事件（%s）", len(anchors), len(events), args.hoops)

    enriched, degraded, skipped = build_event_thumbs(events, FRAMES_ROOT, thumbs_dir, anchors)
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
