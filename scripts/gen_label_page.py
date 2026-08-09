#!/usr/bin/env python3
"""生成标注网页 label.html：本地快速标注进球（免文本输入）。

读取 gen_review_clips --keep-clips 产出的事件索引（events_index.json），
在同目录生成自包含 label.html（事件数据内联，视频用相对路径 clips/）。
立哥用浏览器打开即可：视频循环播，点按钮或按键标注，进度存 localStorage
（可中断续标，刷新/重开回到上次标注位置），最后一键下载 goals.json
（无需手敲任何文本）。

输入：--index 指定的 events_index.json；缺省自动取 work/ 下最新的
      work/<场次>/review*/events_index.json（新增场次素材跑完
      gen_review_clips --keep-clips 后零参数直接生成本场标注页）
输出：同目录 label.html
依赖：标准库 + scripts/ 内模块（gen_review_clips 的窗口常量经全模块路径引用，
      其 import 链 extract_frames/pipe_common 均为标准库、无模块级副作用）
典型调用：
    python scripts/gen_label_page.py                      # 自动取最新索引
    python scripts/gen_label_page.py --index work/20260722/review_v3/events_index.json

导出 goals.json 规格：{"session", "goals": [{file, anchor_time, clip_start,
clip_end, status, scorer}]}；窗口 = 锚点前 4s + 后 2s（剪辑规格）。
status：进球=confirmed（进集锦）；进球但不收（训练球）=rejected（如实记录、
不进集锦，build_highlight 按 SPEC status 白名单跳过）。scorer 兼容历史
标注（旧版"进球·大斌"按钮产出），当前页面不产生 scorer。
"""

import argparse
import glob
import json
import logging
import os
from typing import Any

import gen_review_clips  # 全模块路径引用其 CLIP_BEFORE/AFTER_SEC（审核窗口口径）；

# 注意与本文件同名常量（导出剪辑窗口）值不同，禁止 from-import 裸引同名常量
from errors import BasketballPipelineError
from pipe_common import configure_logging, new_run_id, read_json

logger = logging.getLogger(__name__)

CLIP_BEFORE_SEC: float = 4.0  # 剪辑规格：锚点前
CLIP_AFTER_SEC: float = 2.0  # 剪辑规格：锚点后


def assign_same_rally_groups(events: list[dict[str, Any]]) -> dict[str, int]:
    """标记疑似同回合事件组（同 fid 内审核窗口重叠即同组，机器只提示不判定）。

    窗口近似取 [anchor_t0 − 前窗, anchor_t0 + 后窗]，前/后窗引自
    gen_review_clips（审核片段口径，前 2s 后 4s）：实际片段左界相对事件
    首候选（比 anchor_t0 更早），events_index 无事件跨度字段，左界为保守
    子集——重叠判定偏严，可能漏组但绝不误并。依据与反例约束见
    docs/dedup-same-goal/spec.md。

    Args:
        events: events_index.json 的事件列表，每条需含 key/fid/anchor_t0；
            缺字段的事件跳过（记 WARNING），不影响其余事件分组。

    Returns:
        {event_key: 组号}，仅含 ≥2 事件的组；组号按 fid 首现顺序、
        组内按 anchor_t0 升序扫描，从 1 递增。
    """
    before: float = gen_review_clips.CLIP_BEFORE_SEC
    after: float = gen_review_clips.CLIP_AFTER_SEC
    by_fid: dict[str, list[tuple[float, str]]] = {}
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
            logger.warning("事件缺 fid/anchor_t0/key，跳过同回合分组: %s", str(e)[:80])
            continue
        by_fid.setdefault(fid, []).append((float(anchor), key))

    groups: dict[str, int] = {}
    gid: int = 0
    for items in by_fid.values():
        items.sort()  # anchor 升序（同 anchor 按 key，确定性）
        cur: list[str] = []
        right: float = float("-inf")
        for anchor, key in items:
            if anchor - before <= right:  # 与当前组窗口重叠，传递闭包并入
                cur.append(key)
                right = max(right, anchor + after)
            else:
                if len(cur) >= 2:
                    gid += 1
                    for k in cur:
                        groups[k] = gid
                cur = [key]
                right = anchor + after
        if len(cur) >= 2:
            gid += 1
            for k in cur:
                groups[k] = gid
    return groups


# 注意必须是 raw string：模板内 JS 字符串含 \n 转义（导出确认框文案），
# 普通三引号会被 Python 转义成真实换行，导致 JS 字符串跨行 SyntaxError（整页黑屏）
_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>进球标注 __SESSION__</title>
<style>
body { font-family: sans-serif; background: #111; color: #eee; margin: 16px; }
#bar { position: sticky; top: 0; background: #111; padding: 8px 0; z-index: 9; }
button { font-size: 18px; padding: 10px 18px; margin: 4px; border-radius: 8px;
         border: 0; cursor: pointer; }
#goal { background: #2c9e4b; color: #fff; }
#prac { background: #7a5c00; color: #fff; }
#no { background: #b03a3a; color: #fff; }
.nav { background: #444; color: #fff; }
#export { background: #8a6d00; color: #fff; }
video { max-width: 96vw; max-height: 62vh; background: #000; display: block; }
.badge { color: #fc3; }
small { color: #999; }
</style>
</head>
<body>
<div id="bar">
  <span id="prog"></span> <span class="badge" id="verdict"></span>
  <span class="badge" id="grp"></span><br>
  <button id="goal">进球 (J)</button>
  <button id="prac">进球但不收 (P)</button>
  <button id="no">不是 (F)</button>
  <button class="nav" id="prev">← 上一个</button>
  <button class="nav" id="next">下一个 →</button>
  <button class="nav" id="toun">跳到未标</button>
  <button class="nav" id="sound">声音开/关</button>
  <button class="nav" id="wide">筐区视角 (W)</button>
  <button id="export">导出 goals.json</button>
  <br><small>按键：J=进球 P=进球不收 F=不是 W=全景/筐区切换 ←/→=翻页（默认全景）</small>
  <small>进度与位置自动存，刷新回到上次位置</small>
</div>
<video id="v" autoplay loop muted playsinline></video>
<script>
const EVENTS = __EVENTS__;
const SESSION = "__SESSION__";
const BEFORE = __BEFORE__, AFTER = __AFTER__;
const LSKEY = "label_" + SESSION;
const POSKEY = LSKEY + "_pos";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { marks = {}; }
const v = document.getElementById("v");
let cur = 0;
let wide = false;
function save() {
  // 合并写入：先读回存储与本页记录合并再写，防止同时开多个标注页互相覆盖
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { stored = {}; }
  marks = Object.assign(stored, marks);
  localStorage.setItem(LSKEY, JSON.stringify(marks));
}
function stats() {
  const done = Object.keys(marks).length;
  const goals = Object.values(marks).filter(m => m.r === "goal").length;
  const pracs = Object.values(marks).filter(m => m.r === "practice").length;
  return [done, goals, pracs];
}
function show(i) {
  if (!EVENTS.length) return;
  cur = Math.max(0, Math.min(i, EVENTS.length - 1));
  const e = EVENTS[cur];
  wide = true;
  v.src = e.clip_wide || e.clip;
  v.play().catch(() => {});
  localStorage.setItem(POSKEY, String(cur));
  const [done, goals, pracs] = stats();
  document.getElementById("prog").textContent =
    `第 ${cur + 1}/${EVENTS.length} 个 | 已标 ${done}` +
    `（进球 ${goals} 不收 ${pracs}） | ${e.key} t=${e.anchor_t0}s`;
  document.getElementById("verdict").textContent = e.verdict || "";
  const grpEl = document.getElementById("grp");
  if (e.grp) {
    grpEl.textContent = `疑似同回合（组 ${e.grp}，共 ${e.grp_size} 个）`;
    grpEl.style.color = ["#fc3", "#3cf", "#f6c", "#6f6"][e.grp % 4];
  } else {
    grpEl.textContent = "";
  }
  document.getElementById("sound").textContent = v.muted ? "声音：关" : "声音：开";
  document.getElementById("wide").textContent = "筐区视角 (W)";
}
function toggleWide() {
  const e = EVENTS[cur];
  if (!e.clip_wide) return;
  wide = !wide;
  v.src = wide ? e.clip_wide : e.clip;
  v.play().catch(() => {});
  document.getElementById("wide").textContent = wide ? "筐区视角 (W)" : "全景视角 (W)";
}
function mark(r, scorer) {
  const e = EVENTS[cur];
  marks[e.key] = scorer ? { r, scorer } : { r };
  save();
  let nxt = EVENTS.findIndex((x, idx) => idx > cur && !marks[x.key]);
  if (nxt < 0) nxt = EVENTS.findIndex(x => !marks[x.key]);
  show(nxt >= 0 ? nxt : cur + 1);
}
function jumpUnmarked() {
  const n = EVENTS.findIndex(e => !marks[e.key]);
  show(n >= 0 ? n : cur);
}
function exportGoals() {
  // 疑似同回合组多 J 前置检查（dedup-same-goal：机器只提示，判定权在人；
  // 每次导出都问，选择不持久化）
  const byGrp = {};
  for (const e of EVENTS) {
    if (!e.grp) continue;
    const m = marks[e.key];
    if (m && m.r === "goal") (byGrp[e.grp] = byGrp[e.grp] || []).push(e);
  }
  const issues = Object.entries(byGrp).filter(([, es]) => es.length >= 2);
  if (issues.length) {
    const lines = issues.map(([g, es]) =>
      "组" + g + " " + es[0].src_file + "：" +
      es.map(e => "t=" + e.anchor_t0 + "s").join(" 与 "));
    const msg = "以下疑似同回合的组标了多个进球：\n" + lines.join("\n") +
      "\n\n确定 = 确实是两个球（照导出）\n取消 = 是同一球（返回，把多余的进球改判）";
    if (!confirm(msg)) return;
  }
  const goals = [];
  for (const e of EVENTS) {
    const m = marks[e.key];
    if (!m || (m.r !== "goal" && m.r !== "practice")) continue;
    goals.push({
      file: e.src_file,
      anchor_time: e.anchor_t0,
      clip_start: Math.max(0, Math.round((e.anchor_t0 - BEFORE) * 10) / 10),
      clip_end: Math.round((e.anchor_t0 + AFTER) * 10) / 10,
      status: m.r === "goal" ? "confirmed" : "rejected",
      scorer: m.scorer || ""
    });
  }
  const payload = JSON.stringify({ session: SESSION, goals }, null, 1);
  const blob = new Blob([payload], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "goals_" + SESSION + ".json";
  a.click();
  const nGoal = goals.filter(g => g.status === "confirmed").length;
  alert("已下载 goals_" + SESSION + ".json（进球 " + nGoal +
        " 个，不收 " + (goals.length - nGoal) + " 个），把它发给助手即可");
}
document.getElementById("goal").onclick = () => mark("goal");
document.getElementById("prac").onclick = () => mark("practice");
document.getElementById("no").onclick = () => mark("no");
document.getElementById("prev").onclick = () => show(cur - 1);
document.getElementById("next").onclick = () => show(cur + 1);
document.getElementById("toun").onclick = jumpUnmarked;
document.getElementById("sound").onclick = () => { v.muted = !v.muted; show(cur); };
document.getElementById("wide").onclick = toggleWide;
document.getElementById("export").onclick = exportGoals;
document.addEventListener("keydown", (ev) => {
  const k = ev.key.toLowerCase();
  if (k === "j") mark("goal");
  else if (k === "p") mark("practice");
  else if (k === "f") mark("no");
  else if (k === "w") toggleWide();
  else if (ev.key === "ArrowLeft") show(cur - 1);
  else if (ev.key === "ArrowRight") show(cur + 1);
});
// 启动：优先回到上次标注位置；无记录则跳到第一个未标注事件
let start = parseInt(localStorage.getItem(POSKEY) || "-1", 10);
if (isNaN(start) || start < 0 || start >= EVENTS.length) {
  start = EVENTS.findIndex(e => !marks[e.key]);
}
show(start >= 0 ? start : 0);
</script>
</body>
</html>
"""


def build_html(events: list[dict[str, Any]], session: str) -> str:
    """把事件列表渲染为自包含标注页 HTML。

    疑似同回合分组（assign_same_rally_groups）在此注入：成组事件内联数据
    加 grp（组号）/ grp_size（组大小）字段，页面据以显示"疑似同回合"标签，
    导出时同组多进球弹确认（机器只提示，判定权在人）。

    Args:
        events: events_index.json 中的事件列表（复制后加 grp 字段内联，
            不改调用方原 dict）。
        session: 场次名（页面标题与 localStorage 键后缀）。

    Returns:
        label.html 全文。
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
    return (
        _HTML.replace("__EVENTS__", json.dumps(enriched, ensure_ascii=False))
        .replace("__SESSION__", session)
        .replace("__BEFORE__", str(CLIP_BEFORE_SEC))
        .replace("__AFTER__", str(CLIP_AFTER_SEC))
    )


def find_latest_index(work_root: str = "work") -> str | None:
    """在 work_root 下找最新的 events_index.json（新增场次自动化入口）。

    匹配 ``<work_root>/<场次>/review*/events_index.json``，按修改时间取最新。

    Args:
        work_root: work 目录路径。

    Returns:
        最新索引路径；找不到返回 None。
    """
    pattern: str = os.path.join(work_root, "*", "review*", "events_index.json")
    matches: list[str] = glob.glob(pattern)
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)


def main() -> int:
    """主入口：读事件索引，生成同目录 label.html。

    Returns:
        进程退出码：0=成功；1=索引缺失/损坏。
    """
    run_id: str = new_run_id()
    configure_logging(run_id)
    ap = argparse.ArgumentParser(description="生成进球标注网页")
    ap.add_argument("--index", default="", help="events_index.json 路径（缺省取 work/ 下最新的）")
    ap.add_argument("--session", default="", help="场次名（默认取 index 父目录名）")
    args = ap.parse_args()

    index_path: str = args.index
    if not index_path:
        found: str | None = find_latest_index()
        if found is None:
            logger.error("未指定 --index 且 work/ 下找不到 events_index.json")
            return 1
        index_path = found
        logger.info("自动选取最新索引: %s", index_path)

    try:
        payload = read_json(index_path, what="events_index.json")
    except (BasketballPipelineError, OSError) as exc:
        logger.error("读取索引失败: %s", exc)
        return 1
    events = payload.get("events", []) if isinstance(payload, dict) else []
    if not events:
        logger.error("索引中无事件: %s", index_path)
        return 1
    index_dir: str = os.path.dirname(os.path.abspath(index_path))
    parent: str = os.path.basename(index_dir)
    session: str = args.session or (
        os.path.basename(os.path.dirname(index_dir)) if parent.startswith("review") else parent
    )
    html: str = build_html(events, session)
    out_path: str = os.path.join(index_dir, "label.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("标注页 %d 事件 -> %s（浏览器打开即可标注）", len(events), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
