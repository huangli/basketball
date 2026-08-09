#!/usr/bin/env python3
"""生成认人确认页 scorer.html：立哥逐球确认进球者归属（spec: docs/scorer/spec.md T4）。

读取 crop_scorers 产出的 scorer_candidates.json（每球一条：key/裁图/clip 预览
片段/team_guess/SKIP 状态）+ goals.json（confirmed 球为页面条目全集），在同目录
生成自包含 scorer.html（数据内联、裁图/视频相对路径、按键+按钮、localStorage
进度、一键导出 roster_<session>.json）。立哥浏览器打开即可：看裁图与预览片段，
点球员按钮（数字键 1-9）或自由文本输入归属，S 跳过；SKIP 球标"无法定位"
照常列出可手选；导出物 schema 严格过 scripts/roster.py（format_key 键、
validate_roster 可校验），confirmed=true 仅当全部非 SKIP 球已归属。

视频来源优先级：candidates 的 "clip"（按进球锚点现切的预览片段，与裁图同球
同时刻，crop_scorers --rawdir 产物）＞ events_index 的 clip_wide 匹配（仅作
无预览片段时的兜底——事件片段覆盖长事件全程，开头可能是另一回合）。

输入：--scorers scorer_candidates.json、--goals goals.json、--session（缺省取
    candidates 里的 session）、--index（可选 events_index.json，兜底视频按
    src_file 相同且 |anchor_t0−anchor_time|≤4s 匹配 clip_wide）、--players（可选
    "黑21=大斌,白-熊志鹏=熊志鹏" 式逗号分隔名单）、--roster-existing（可选，
    合并已有 roster：assignments 并集预填、players 以新名单为准缺 tag WARNING）
输出：<scorer_candidates.json 同目录>/scorer.html
依赖：scripts/roster.py（format_key/validate_roster/Player，契约唯一入口）、
    scripts/pipe_common.py（read_json/run_id 日志）、scripts/errors.py
典型调用：
    python scripts/gen_scorer_page.py --scorers work/20260722/scorers/scorer_candidates.json \
        --goals work/20260722/goals.json --session 20260722 \
        --index work/20260722/review_v3/events_index.json \
        --players "黑21=大斌,白-熊志鹏=熊志鹏"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from errors import BasketballPipelineError, SchemaError
from pipe_common import configure_logging, new_run_id, read_json
from roster import Player, format_key, validate_roster

logger = logging.getLogger(__name__)

# 兜底视频匹配：同 src_file 且事件锚点与进球锚点相差不超过 4s（spec T4；
# 4s = 剪辑窗口前段长度，同一片段窗口内的事件视为同一球）
CLIP_MATCH_MAX_DT_SEC: float = 4.0

STATUS_OK: str = "OK"
STATUS_SKIP: str = "SKIP"

TEAM_BLACK: str = "黑"
TEAM_WHITE: str = "白"
TEAM_CASUAL: str = "便服"

_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>认人确认 __SESSION__</title>
<style>
body { font-family: sans-serif; background: #111; color: #eee; margin: 16px; }
#bar { position: sticky; top: 0; background: #111; padding: 8px 0; z-index: 9; }
button { font-size: 18px; padding: 10px 18px; margin: 4px; border-radius: 8px;
         border: 0; cursor: pointer; }
button.sel { outline: 3px solid #fc3; }
.team-黑 { background: #222; color: #fff; border: 1px solid #666; }
.team-白 { background: #eee; color: #111; }
.team-便服 { background: #777; color: #fff; }
.nav { background: #444; color: #fff; }
#skip { background: #7a5c00; color: #fff; }
#accept { background: #2c9e4b; color: #fff; }
#export { background: #8a6d00; color: #fff; }
#go { background: #2c9e4b; color: #fff; }
#free { font-size: 18px; padding: 8px; width: 10em; background: #222;
        color: #eee; border: 1px solid #555; border-radius: 8px; }
#crop { max-width: 44vw; max-height: 68vh; background: #000; }
video { max-width: 48vw; max-height: 68vh; background: #000; }
.badge { color: #fc3; }
small { color: #999; }
</style>
</head>
<body>
<div id="bar">
  <span id="prog"></span> <span class="badge" id="cur"></span><br>
  <span id="players"></span>
  <input id="free" placeholder="自由输入标签"><button id="go">归属 (回车)</button>
  <button id="accept" style="display:none"></button>
  <button id="skip">跳过 (S)</button>
  <button class="nav" id="prev">← 上一个</button>
  <button class="nav" id="next">下一个 →</button>
  <button class="nav" id="toun">跳到未归属</button>
  <button id="export">导出 roster.json</button>
  <br><small>按键：1-9=选球员 E=采用号码预填 S=跳过 ←/→=翻页；SKIP 球标"无法定位"可手选</small>
  <small>进度自动存 localStorage，刷新回到上次位置；导出文件名 roster___SESSION__.json</small>
</div>
<img id="crop" alt="投篮者裁图">
<video id="v" autoplay loop muted playsinline></video>
<script>
const ITEMS = __ITEMS__;
const PLAYERS = __PLAYERS__;
const EXISTING = __EXISTING__;
const EXPLAYERS = __EXPLAYERS__;
const SESSION = "__SESSION__";
const LSKEY = "scorer_" + SESSION;
const POSKEY = LSKEY + "_pos";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { marks = {}; }
// 已有 roster 归属作底，本页改动覆盖之（立哥在页面上的修改是终裁）
marks = Object.assign({}, EXISTING, marks);
let cur = 0;
function save() {
  // 合并写入：先读回存储与本页记录合并再写，防止同时开多个页面互相覆盖
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { stored = {}; }
  marks = Object.assign(stored, marks);
  localStorage.setItem(LSKEY, JSON.stringify(marks));
}
function teamOfTag(tag) {
  // 与 Python 端 team_of_tag 同规则：标签前缀定队，其余便服
  if (tag.startsWith("黑")) return "黑";
  if (tag.startsWith("白")) return "白";
  return "便服";
}
function nDone() { return ITEMS.filter(it => marks[it.key]).length; }
function renderPlayers() {
  const box = document.getElementById("players");
  box.innerHTML = "";
  PLAYERS.forEach((p, idx) => {
    const b = document.createElement("button");
    b.textContent = (idx < 9 ? (idx + 1) + " " : "") + p.tag +
      (p.name ? "=" + p.name : "");
    b.className = "team-" + p.team;
    if (ITEMS.length && marks[ITEMS[cur].key] === p.tag) b.classList.add("sel");
    b.onclick = () => assign(p.tag);
    box.appendChild(b);
  });
}
function show(i) {
  if (!ITEMS.length) return;
  cur = Math.max(0, Math.min(i, ITEMS.length - 1));
  const it = ITEMS[cur];
  const img = document.getElementById("crop");
  if (it.crop) { img.src = it.crop; img.style.display = "inline-block"; }
  else { img.removeAttribute("src"); img.style.display = "none"; }
  const v = document.getElementById("v");
  if (it.clip) { v.src = it.clip; v.style.display = "inline-block"; v.play().catch(() => {}); }
  else { v.pause(); v.removeAttribute("src"); v.load(); v.style.display = "none"; }
  localStorage.setItem(POSKEY, String(cur));
  let info = `第 ${cur + 1}/${ITEMS.length} 个 | 已归属 ${nDone()}/${ITEMS.length}` +
    ` | ${it.file} t=${it.anchor_time}s`;
  // 预填优先级：号码匹配（K3 读号）> 颜色 team_guess；歧义不预填
  const ab = document.getElementById("accept");
  if (it.status === "SKIP") info += " | 无法定位";
  else if (it.prefill_tag) info += ` | 号码预填:${it.prefill_tag}`;
  else if (it.prefill_note === "ambiguous") info += " | 号码歧义(同号多人)";
  else if (it.team_guess) info += ` | 颜色预填:${it.team_guess}`;
  const ng = it.number_guess;
  if (ng && ng.number) info += ` (读号:${ng.color || ""}${ng.number})`;
  if (it.prefill_tag) {
    ab.textContent = `采用 ${it.prefill_tag} (E)`;
    ab.style.display = "inline-block";
    ab.onclick = () => assign(it.prefill_tag);
  } else {
    ab.style.display = "none";
    ab.onclick = null;
  }
  document.getElementById("prog").textContent = info;
  document.getElementById("cur").textContent =
    marks[it.key] ? "当前归属: " + marks[it.key] : "未归属";
  renderPlayers();
}
function assign(tag) {
  if (!ITEMS.length) return;
  marks[ITEMS[cur].key] = tag;
  save();
  let nxt = ITEMS.findIndex((x, idx) => idx > cur && !marks[x.key]);
  if (nxt < 0) nxt = ITEMS.findIndex(x => !marks[x.key]);
  show(nxt >= 0 ? nxt : cur);
}
function skip() {
  let nxt = ITEMS.findIndex((x, idx) => idx > cur && !marks[x.key]);
  if (nxt < 0) nxt = (cur + 1) % ITEMS.length;
  show(nxt);
}
function freeAssign() {
  const inp = document.getElementById("free");
  const tag = inp.value.trim();
  if (!tag) return;
  inp.value = "";
  assign(tag);
}
function jumpUnassigned() {
  const n = ITEMS.findIndex(it => !marks[it.key]);
  show(n >= 0 ? n : cur);
}
function exportRoster() {
  // assignments 并集 = 已有 roster 归属 + 本页全部标记（键即 candidates 的
  // format_key 产物，两端共用 roster.py 契约，此处不再拼键）
  const assignments = {};
  for (const [k, t] of Object.entries(marks)) { if (t) assignments[k] = t; }
  // players 以本页名单为准；归属到名单外标签（自由输入）的自动补录，
  // 名字/队别优先沿用已有 roster 记录，否则按标签前缀推队
  const players = PLAYERS.map(p => ({ tag: p.tag, name: p.name, team: p.team }));
  const known = new Set(players.map(p => p.tag));
  for (const t of new Set(Object.values(assignments))) {
    if (known.has(t)) continue;
    const old = EXPLAYERS[t];
    players.push({ tag: t, name: old ? old.name : "", team: old ? old.team : teamOfTag(t) });
    known.add(t);
  }
  // confirmed=true 仅当全部非 SKIP 球已归属（SKIP 球允许未归属，spec 契约）
  const confirmed = ITEMS.every(it => it.status === "SKIP" || marks[it.key]);
  const payload = JSON.stringify({ session: SESSION, confirmed, players, assignments }, null, 1);
  const blob = new Blob([payload], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "roster_" + SESSION + ".json";
  a.click();
  const nUn = ITEMS.filter(it => it.status !== "SKIP" && !marks[it.key]).length;
  alert("已下载 roster_" + SESSION + ".json（归属 " + Object.keys(assignments).length +
        "/" + ITEMS.length + "，confirmed=" + confirmed +
        (nUn ? "，还有 " + nUn + " 个非 SKIP 球未归属" : "") + "），把它发给助手即可");
}
document.getElementById("go").onclick = freeAssign;
document.getElementById("skip").onclick = skip;
document.getElementById("prev").onclick = () => show(cur - 1);
document.getElementById("next").onclick = () => show(cur + 1);
document.getElementById("toun").onclick = jumpUnassigned;
document.getElementById("export").onclick = exportRoster;
document.addEventListener("keydown", (ev) => {
  if (ev.target && ev.target.id === "free") {
    if (ev.key === "Enter") freeAssign();
    return;
  }
  const k = ev.key.toLowerCase();
  if (k >= "1" && k <= "9") {
    const idx = parseInt(k, 10) - 1;
    if (idx < PLAYERS.length) assign(PLAYERS[idx].tag);
  } else if (k === "s") skip();
  else if (k === "e" && ITEMS.length && ITEMS[cur].prefill_tag) assign(ITEMS[cur].prefill_tag);
  else if (ev.key === "ArrowLeft") show(cur - 1);
  else if (ev.key === "ArrowRight") show(cur + 1);
});
// 启动：优先回到上次位置；无记录则跳到第一个未归属球
let start = parseInt(localStorage.getItem(POSKEY) || "-1", 10);
if (isNaN(start) || start < 0 || start >= ITEMS.length) {
  start = ITEMS.findIndex(it => !marks[it.key]);
}
show(start >= 0 ? start : 0);
</script>
</body>
</html>
"""


def team_of_tag(tag: str) -> str:
    """按标签前缀推定队别：黑*/白* 归队，其余（灰T恤-A 等）归便服。

    页面导出自动补录名单外标签时用同一规则（JS teamOfTag 与本文档同步，
    改规则须两端一起改）。

    Args:
        tag: 球员标签，如 ``黑21`` / ``白-熊志鹏`` / ``灰T恤-A``。

    Returns:
        "黑" / "白" / "便服"。
    """
    if tag.startswith(TEAM_BLACK):
        return TEAM_BLACK
    if tag.startswith(TEAM_WHITE):
        return TEAM_WHITE
    return TEAM_CASUAL


def parse_players(spec: str) -> list[Player]:
    """解析 --players 名单串："黑21=大斌,白-熊志鹏=熊志鹏" → Player 列表。

    每条为 ``tag[=name]``（name 可省，省则为空串）；队别按 team_of_tag 推定。

    Args:
        spec: 逗号分隔的名单串；空串返回空列表。

    Returns:
        Player 列表（保持给定顺序）。

    Raises:
        SchemaError: 条目为空 tag（如 "、" 或 "=大斌"）。
    """
    players: list[Player] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        tag, sep, name = item.partition("=")
        tag = tag.strip()
        if not tag:
            raise SchemaError(f"--players 条目缺 tag: {item!r}")
        players.append(Player(tag=tag, name=name.strip() if sep else "", team=team_of_tag(tag)))
    return players


def merge_assignments(
    existing: dict[str, str], new: dict[str, str], what: str = "roster 合并"
) -> dict[str, str]:
    """assignments 并集合并：同键同值幂等，同键不同值 = 冲突显式失败（spec T4）。

    Args:
        existing: 已有 roster 的 assignments。
        new: 新增 assignments。
        what: 业务名称（用于错误信息）。

    Returns:
        合并后的 assignments（existing 在前，new 覆盖同键——但同键不同值已抛错，
        所以覆盖只发生在同值情形）。

    Raises:
        BasketballPipelineError: 同键冲突（调用方口径 = 报错退出 1）。
    """
    for key, value in new.items():
        if key in existing and existing[key] != value:
            raise BasketballPipelineError(
                f"{what}: 同键冲突 {key!r}: {existing[key]!r} vs {value!r}"
            )
    return {**existing, **new}


def _validate_candidates(data: Any, path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """校验 scorer_candidates.json 结构（rules.md §0.2：schema 损坏显式失败）。

    Args:
        data: read_json 读出的原始 JSON。
        path: 文件路径（仅用于错误信息）。

    Returns:
        candidates 记录列表（保留原始 dict）。

    Raises:
        SchemaError: 顶层非对象 / 缺 candidates 列表 / 记录缺 key/status 等字段或类型错。
    """
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: 顶层必须是对象，实际 {type(data).__name__}")
    candidates: Any = data.get("candidates")
    if not isinstance(candidates, list):
        raise SchemaError(f"{path}: 缺 candidates 列表或类型错误")
    for i, c in enumerate(candidates):
        if not isinstance(c, dict):
            raise SchemaError(f"{path}: 第{i}条候选不是对象")
        if not isinstance(c.get("key"), str) or not c["key"]:
            raise SchemaError(f"{path}: 第{i}条候选 key 缺失或不是非空 str")
        if c.get("status") not in (STATUS_OK, STATUS_SKIP):
            raise SchemaError(f"{path}: 第{i}条候选 status 非法: {c.get('status')!r}")
        if not isinstance(c.get("file"), str) or not c["file"]:
            raise SchemaError(f"{path}: 第{i}条候选 file 缺失或不是非空 str")
        anchor: Any = c.get("anchor_time")
        if isinstance(anchor, bool) or not isinstance(anchor, (int, float)):
            raise SchemaError(f"{path}: 第{i}条候选 anchor_time 缺失或非数值")
        if not isinstance(c.get("crop", ""), str):
            raise SchemaError(f"{path}: 第{i}条候选 crop 不是 str")
        if not isinstance(c.get("clip", ""), str):
            raise SchemaError(f"{path}: 第{i}条候选 clip 不是 str")
        if c.get("team_guess") is not None and c["team_guess"] not in (
            TEAM_BLACK,
            TEAM_WHITE,
            TEAM_CASUAL,
        ):
            raise SchemaError(f"{path}: 第{i}条候选 team_guess 非法: {c['team_guess']!r}")
        if c.get("number_guess") is not None and not isinstance(c["number_guess"], dict):
            raise SchemaError(f"{path}: 第{i}条候选 number_guess 不是对象")
    return candidates


def match_players_by_number(
    players: list[Player], number: str | None, color: str | None
) -> list[Player]:
    """号码+颜色匹配名单：tag 含颜色字且含独立号码数字（号码前后非数字）。

    "黑"+"21" 命中 黑21-大斌 / 黑21-王敏龙（同号多人 → 调用方判歧义）；
    "蓝"+"27" 命中 蓝色27；"2" 不会误中 "黑21"（数字边界防子串误配）。

    Args:
        players: 球员名单（--players 或已有 roster 的 players）。
        number: K3 读出的号码字符串；None 不参与匹配。
        color: K3 读出的颜色（黑/白/蓝/其他）；"其他"或 None 不参与匹配。

    Returns:
        命中的 Player 列表（0/1/N 个）。
    """
    if not number or not color or color == "其他":
        return []
    pat: re.Pattern[str] = re.compile(rf"(?<!\d){re.escape(number)}(?!\d)")
    return [p for p in players if color in p.tag and pat.search(p.tag)]


def _confirmed_goals(data: Any, goals_path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """从 goals.json 数据中取 confirmed 记录（缺 file/anchor_time 显式失败）。

    Args:
        data: read_json 读出的原始 JSON。
        goals_path: 文件路径（仅用于错误信息）。

    Returns:
        confirmed 记录列表（保留原始 dict）。

    Raises:
        SchemaError: 顶层非对象 / goals 非列表 / confirmed 记录缺字段或类型错。
    """
    if not isinstance(data, dict):
        raise SchemaError(f"{goals_path}: 顶层必须是对象，实际 {type(data).__name__}")
    goals: Any = data.get("goals")
    if not isinstance(goals, list):
        raise SchemaError(f"{goals_path}: 缺 goals 列表或类型错误")
    confirmed: list[dict[str, Any]] = []
    for i, g in enumerate(goals):
        if not isinstance(g, dict):
            raise SchemaError(f"{goals_path}: 第{i}条记录不是对象")
        if g.get("status") != "confirmed":
            continue
        if not isinstance(g.get("file"), str) or not g["file"]:
            raise SchemaError(f"{goals_path}: 第{i}条(confirmed) file 缺失或不是非空 str")
        anchor: Any = g.get("anchor_time")
        if isinstance(anchor, bool) or not isinstance(anchor, (int, float)):
            raise SchemaError(f"{goals_path}: 第{i}条(confirmed) anchor_time 缺失或非数值")
        confirmed.append(g)
    return confirmed


def _validate_events(data: Any, path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """校验 events_index.json 结构（只查本页用到的字段）。

    Args:
        data: read_json 读出的原始 JSON。
        path: 文件路径（仅用于错误信息）。

    Returns:
        events 记录列表。

    Raises:
        SchemaError: 顶层非对象 / events 非列表 / 记录缺 src_file/anchor_t0/clip 或类型错。
    """
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: 顶层必须是对象，实际 {type(data).__name__}")
    events: Any = data.get("events")
    if not isinstance(events, list):
        raise SchemaError(f"{path}: 缺 events 列表或类型错误")
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            raise SchemaError(f"{path}: 第{i}条事件不是对象")
        if not isinstance(ev.get("src_file"), str) or not ev["src_file"]:
            raise SchemaError(f"{path}: 第{i}条事件 src_file 缺失或不是非空 str")
        t0: Any = ev.get("anchor_t0")
        if isinstance(t0, bool) or not isinstance(t0, (int, float)):
            raise SchemaError(f"{path}: 第{i}条事件 anchor_t0 缺失或非数值")
        if not isinstance(ev.get("clip"), str) or not ev["clip"]:
            raise SchemaError(f"{path}: 第{i}条事件 clip 缺失或不是非空 str")
        if not isinstance(ev.get("clip_wide", ""), str):
            raise SchemaError(f"{path}: 第{i}条事件 clip_wide 不是 str")
    return events


def match_clip(
    events: list[dict[str, Any]],
    file: str,
    anchor_time: float,
    index_dir: str,
    out_dir: str,
) -> str:
    """按 src_file 相同且 |anchor_t0−anchor_time|≤4s 匹配审核片段（spec T4）。

    多个事件命中取时间差最小者；**优先取 clip_wide 全景**（认人需看清全身，
    筐区裁剪看不清人，2026-08-01 立哥反馈），无 clip_wide 回退 clip。
    返回相对 scorer.html 所在目录的正斜杠相对路径（events_index 里的
    clip 可能是 Windows 反斜杠，先归一）。

    Args:
        events: _validate_events 校验后的事件列表。
        file: 进球记录的视频文件名。
        anchor_time: 进球锚点（秒）。
        index_dir: events_index.json 所在目录（clip 相对它解析）。
        out_dir: scorer.html 输出目录（返回路径相对它）。

    Returns:
        相对路径串（如 ``../review_v3/clips/x_wide.mp4``）；无匹配返回空串。
    """
    best: dict[str, Any] | None = None
    best_dt: float = CLIP_MATCH_MAX_DT_SEC
    for ev in events:
        if ev["src_file"] != file:
            continue
        dt: float = abs(float(ev["anchor_t0"]) - anchor_time)
        if dt <= best_dt:
            best = ev
            best_dt = dt
    if best is None:
        return ""
    clip_val: str = str(best.get("clip_wide") or best["clip"])
    clip_norm: str = clip_val.replace("\\", "/")
    rel: str = os.path.relpath(os.path.join(index_dir, clip_norm), out_dir)
    return rel.replace(os.sep, "/")


def build_entries(
    confirmed: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    events: list[dict[str, Any]] | None,
    index_dir: str,
    out_dir: str,
    players: list[Player] | None = None,
) -> list[dict[str, Any]]:
    """组装页面条目：每条 = 一个 confirmed 球（按 file+anchor 排序）。

    以 goals.json 的 confirmed 球为全集，按 key 关联 candidates 取裁图/
    team_guess/number_guess/SKIP 状态；无候选记录（防御）按 SKIP 列出。视频优先级：
    candidates 的 "clip"（按进球锚点现切的预览片段，与裁图同球同时刻）＞
    events_index 的 clip_wide 匹配（仅作无预览片段时的兜底）。预填优先级：
    号码匹配（number_guess 的 number+color 与名单 tag 匹配）＞ 颜色 team_guess；
    号码匹配到多个球员 → 不预填，prefill_note="ambiguous"（页面标"号码歧义"）。

    Args:
        confirmed: goals.json 的 confirmed 记录。
        candidates: scorer_candidates.json 的候选记录。
        events: 事件列表；None 表示无 --index（无兜底视频）。
        index_dir: events_index.json 所在目录。
        out_dir: scorer.html 输出目录。
        players: 球员名单（号码匹配用）；None/空列表则只做颜色预填。

    Returns:
        页面条目列表（key/file/anchor_time/status/reason/crop/team_guess/clip/
        number_guess/prefill_tag/prefill_note）。
    """
    players = players or []
    by_key: dict[str, dict[str, Any]] = {c["key"]: c for c in candidates}
    entries: list[dict[str, Any]] = []
    ordered = sorted(confirmed, key=lambda g: (g["file"], float(g["anchor_time"])))
    for g in ordered:
        file: str = g["file"]
        anchor: float = float(g["anchor_time"])
        key: str = format_key(file, anchor)
        cand: dict[str, Any] | None = by_key.get(key)
        if cand is None:
            logger.warning("confirmed 球无定位候选记录: %s（按 SKIP 列出）", key)
        status: str = cand["status"] if cand is not None else STATUS_SKIP
        reason: str = str(cand.get("reason", "")) if cand is not None else "no_candidate"
        crop: str = str(cand.get("crop", "")) if cand is not None else ""
        team_guess: str | None = cand.get("team_guess") if cand is not None else None
        # 预览片段（candidates clip，与裁图同锚点）优先；无则回退事件 clip_wide 匹配
        clip: str = str(cand.get("clip", "")) if cand is not None else ""
        if not clip and events is not None:
            clip = match_clip(events, file, anchor, index_dir, out_dir)
        # 号码预填：恰匹配一名球员才预填；多人同号 → 歧义不预填
        number_guess: dict[str, Any] | None = cand.get("number_guess") if cand is not None else None
        prefill_tag: str = ""
        prefill_note: str = ""
        if isinstance(number_guess, dict):
            matches: list[Player] = match_players_by_number(
                players, number_guess.get("number"), number_guess.get("color")
            )
            if len(matches) == 1:
                prefill_tag = matches[0].tag
            elif len(matches) > 1:
                prefill_note = "ambiguous"
        entries.append(
            {
                "key": key,
                "file": file,
                "anchor_time": anchor,
                "status": status,
                "reason": reason,
                "crop": crop,
                "team_guess": team_guess,
                "clip": clip,
                "number_guess": number_guess,
                "prefill_tag": prefill_tag,
                "prefill_note": prefill_note,
            }
        )
    return entries


def build_html(
    entries: list[dict[str, Any]],
    players: list[Player],
    session: str,
    existing_assignments: dict[str, str],
    existing_players: dict[str, Player],
) -> str:
    """把条目/名单/已有归属渲染为自包含确认页 HTML。

    Args:
        entries: build_entries 产出的页面条目（原样内联）。
        players: 球员按钮名单（--players 或已有 roster 的 players）。
        session: 场次名（标题、localStorage 键、导出文件名后缀）。
        existing_assignments: 已有 roster 的 assignments（页面预填底色）。
        existing_players: 已有 roster 的 tag → Player（自动补录时沿用 name/team）。

    Returns:
        scorer.html 全文。
    """
    players_json = json.dumps(
        [{"tag": p.tag, "name": p.name, "team": p.team} for p in players],
        ensure_ascii=False,
    )
    explayers_json = json.dumps(
        {tag: {"name": p.name, "team": p.team} for tag, p in existing_players.items()},
        ensure_ascii=False,
    )
    return (
        _HTML.replace("__ITEMS__", json.dumps(entries, ensure_ascii=False))
        .replace("__PLAYERS__", players_json)
        .replace("__EXISTING__", json.dumps(existing_assignments, ensure_ascii=False))
        .replace("__EXPLAYERS__", explayers_json)
        .replace("__SESSION__", session)
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """解析 CLI 参数。"""
    parser = argparse.ArgumentParser(description="生成认人确认页 scorer.html（spec T4）")
    parser.add_argument("--scorers", required=True, type=Path, help="scorer_candidates.json 路径")
    parser.add_argument("--goals", required=True, type=Path, help="goals.json 路径")
    parser.add_argument("--session", default="", help="场次名（缺省取 candidates 里的 session）")
    parser.add_argument("--index", default="", help="events_index.json 路径（可选，引用审核片段）")
    parser.add_argument(
        "--players", default="", help='球员名单，如 "黑21=大斌,白-熊志鹏=熊志鹏"（可选）'
    )
    parser.add_argument("--roster-existing", default="", help="已有 roster.json（可选，合并预填）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。返回进程退出码（0=成功，1=参数/数据/合并冲突失败）。"""
    args = _parse_args(argv)
    run_id: str = new_run_id()
    configure_logging(run_id)
    try:
        scorers_path: Path = args.scorers
        cand_data: Any = read_json(scorers_path, what="scorer_candidates.json")
        candidates: list[dict[str, Any]] = _validate_candidates(cand_data, str(scorers_path))
        session: str = args.session or (
            cand_data.get("session", "") if isinstance(cand_data, dict) else ""
        )
        if not session:
            logger.error("缺 --session 且 candidates 无 session 字段")
            return 1

        goals_data: Any = read_json(args.goals, what="goals.json")
        confirmed: list[dict[str, Any]] = _confirmed_goals(goals_data, str(args.goals))

        events: list[dict[str, Any]] | None = None
        index_dir: str = ""
        if args.index:
            idx_data: Any = read_json(args.index, what="events_index.json")
            events = _validate_events(idx_data, args.index)
            index_dir = os.path.dirname(os.path.abspath(args.index))

        out_dir: str = str(scorers_path.resolve().parent)

        players: list[Player] = parse_players(args.players)
        existing_assignments: dict[str, str] = {}
        existing_players: dict[str, Player] = {}
        if args.roster_existing:
            roster_data: Any = read_json(args.roster_existing, what="roster.json")
            roster = validate_roster(roster_data, args.roster_existing)
            existing_assignments = merge_assignments(
                roster.assignments, {}, what=str(args.roster_existing)
            )
            existing_players = {p.tag: p for p in roster.players}
            if not players:
                # 未给新名单：沿用已有 roster 的 players 作按钮名单
                players = list(roster.players)
            else:
                # players 以新名单为准；已有归属引用了名单外 tag → WARNING
                known: set[str] = {p.tag for p in players}
                for tag in sorted(set(roster.assignments.values()) - known):
                    logger.warning(
                        "已有 roster 归属的 tag 不在新名单中（导出时将自动补录）: %s", tag
                    )

        entries: list[dict[str, Any]] = build_entries(
            confirmed, candidates, events, index_dir, out_dir, players
        )

        html: str = build_html(entries, players, session, existing_assignments, existing_players)
        out_path: Path = scorers_path.resolve().parent / "scorer.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        n_skip: int = sum(1 for e in entries if e["status"] == STATUS_SKIP)
        n_clip: int = sum(1 for e in entries if e["clip"])
        logger.info(
            "确认页 %d 球（SKIP %d，带片段 %d，球员按钮 %d）-> %s（浏览器打开即可认人）",
            len(entries),
            n_skip,
            n_clip,
            len(players),
            out_path,
        )
        return 0
    except BasketballPipelineError as exc:
        logger.error("管线失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1
    except OSError as exc:
        logger.error("IO 失败 run_id=%s: %s", run_id, exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
