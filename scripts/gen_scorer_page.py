#!/usr/bin/env python3
"""生成认人确认页 scorer.html：立哥逐球确认进球者归属（spec: docs/scorer/spec.md T4）。

读取 crop_scorers 产出的 scorer_candidates.json（每球一条：key/裁图/clip 预览
片段/team_guess/SKIP 状态）+ goals.json（confirmed 球为页面条目全集），在同目录
生成自包含 scorer.html（数据内联、裁图/视频相对路径、按键+按钮、localStorage
进度、一键导出 roster.json——文件名即 CLI 认的名字，移到 work/<场次>/
即可接入 people 预填链与 build，无需改名）。立哥浏览器打开即可：看裁图与预览片段，
点球员按钮（数字键 1-9）或自由文本输入归属，S 跳过；SKIP 球标"无法定位"
照常列出可手选；导出物 schema 严格过 scripts/roster.py（format_key 键、
validate_roster 可校验），confirmed=true 仅当全部非 SKIP 球已归属。

视频来源优先级：candidates 的 "clip"（按进球锚点现切的预览片段，与裁图同球
同时刻，crop_scorers --rawdir 产物）＞ events_index 的 clip_wide 匹配（仅作
无预览片段时的兜底——事件片段覆盖长事件全程，开头可能是另一回合）。

输入：--scorers scorer_candidates.json、--goals goals.json、--session（缺省取
    candidates 里的 session）、--index（可选 events_index.json，兜底视频按
    src_file 相同且 |anchor_t0−anchor_time|≤4s 匹配 clip_wide）、--players（可选
    "黑21=大斌,白-熊志鹏=熊志鹏" 式逗号分隔名单）、--players-file（可选，与
    roster.players 同构的 JSON 数组名单文件，与 --players 互斥；spec:
    docs/scorer-reid/spec.md）、--roster-existing（可选，
    合并已有 roster：assignments 并集预填、players 以新名单为准缺 tag WARNING）、
    --clusters（可选 scorer_clusters.json，必须与 --scorers 同目录：rep_crops 与
    裁图同目录相对引用；有则页面顶部出簇区，簇级选人批量预填簇内全部球，
    逐球区单独改覆盖簇归属，导出 roster 契约不变；spec: docs/scorer-cluster/spec.md）
输出：<scorer_candidates.json 同目录>/scorer.html
依赖：scripts/roster.py（format_key/validate_roster/Player/player_from_dict，
    契约唯一入口）、scripts/pipe_common.py（read_json/run_id 日志）、scripts/errors.py
典型调用：
    python scripts/gen_scorer_page.py --scorers work/20260722/scorers/scorer_candidates.json \
        --goals work/20260722/goals.json --session 20260722 \
        --index work/20260722/review_v3/events_index.json \
        --players-file work/20260722/players.json
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
from roster import Player, format_key, player_from_dict, validate_roster

logger = logging.getLogger(__name__)

# 兜底视频匹配：同 src_file 且事件锚点与进球锚点相差不超过 4s（spec T4；
# 4s = 剪辑窗口前段长度，同一片段窗口内的事件视为同一球）
CLIP_MATCH_MAX_DT_SEC: float = 4.0

STATUS_OK: str = "OK"
STATUS_SKIP: str = "SKIP"

TEAM_BLACK: str = "地平线"  # 黑队队名（黑/蓝球衣；2026-08-09 立哥定队名）
TEAM_WHITE: str = "半截篮"  # 白队队名
TEAM_CASUAL: str = "便服"
# 标签前缀 → 队名（顺序即优先级；蓝色27 归地平线系立哥 2026-08-09 口径）
_TEAM_PREFIXES: tuple[tuple[str, str], ...] = (
    ("黑", TEAM_BLACK),
    ("蓝", TEAM_BLACK),
    ("白", TEAM_WHITE),
)
# team_guess 合法值：crop_scorers 颜色分队产出的是颜色（黑/白/便服），与队名不同命名空间
TEAM_GUESS_VALUES: tuple[str, ...] = ("黑", "白", "便服")

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
.team-地平线 { background: #222; color: #fff; border: 1px solid #666; }
.team-半截篮 { background: #eee; color: #111; }
.team-便服 { background: #777; color: #fff; }
.teamlabel { color: #aaa; margin-right: 6px; }
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
#clusters { margin: 8px 0; }
.cluster-row { display: flex; align-items: center; flex-wrap: wrap; gap: 4px;
               background: #1c1c1c; border: 1px solid #333; border-radius: 8px;
               padding: 6px; margin: 6px 0; }
.cluster-row img.rep { max-height: 120px; max-width: 160px; background: #000; }
.clusterlabel { color: #fc3; margin: 0 8px; }
.cluster-row { cursor: grab; }
.cluster-row.drop-target { outline: 3px dashed #fc3; }
.cluster-row button { font-size: 14px; padding: 6px 10px; }
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
  <small>进度自动存 localStorage，刷新回到上次位置；导出文件名 roster.json</small>
</div>
<div id="clusters"></div>
<img id="crop" alt="投篮者裁图">
<video id="v" autoplay loop muted playsinline></video>
<script>
const ITEMS = __ITEMS__;
const PLAYERS = __PLAYERS__;
const EXISTING = __EXISTING__;
const EXPLAYERS = __EXPLAYERS__;
const CLUSTERS = __CLUSTERS__;
const SESSION = "__SESSION__";
const LSKEY = "scorer_" + SESSION;
const POSKEY = LSKEY + "_pos";
const TOUCHKEY = LSKEY + "_touched";
let marks = {};
try { marks = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { marks = {}; }
// 已有 roster 归属作底，本页改动覆盖之（立哥在页面上的修改是终裁）
marks = Object.assign({}, EXISTING, marks);
// touched = 逐球手动改过的 key（簇级批量预填不得覆盖；独立 localStorage 键，
// 不动既有 marks 存储格式）
let touched = {};
try { touched = JSON.parse(localStorage.getItem(TOUCHKEY) || "{}"); } catch (e) { touched = {}; }
const CLSTATE_KEY = LSKEY + "_clusters";
// 簇合并页面态：merges=被并cid→组id，clAssign=组id→tag（仅作合并预填来源，
// 显示/折叠判定一律以 marks 为准），collapsed=显式折叠（true/false 都存）
let clState = { merges: {}, clAssign: {}, collapsed: {} };
try {
  const rawCl = JSON.parse(localStorage.getItem(CLSTATE_KEY) || "{}");
  if (rawCl && typeof rawCl === "object") {
    for (const sub of ["merges", "clAssign", "collapsed"]) {
      if (rawCl[sub] && typeof rawCl[sub] === "object") clState[sub] = rawCl[sub];
    }
  }
} catch (e) { clState = { merges: {}, clAssign: {}, collapsed: {} }; }
function saveClState(del) {
  // 子键分别读回再合并写（嵌套对象整体浅合并会丢多页防护粒度；spec 数据契约）；
  // del = { merges: [...], clAssign: [...] } 待删键——读回合并会把本地已删的键
  // 从 stored 复活，必须在合并后再删（拆开/合并吸收依赖此语义）
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(CLSTATE_KEY) || "{}"); }
  catch (e) { stored = {}; }
  const merged = {
    merges: Object.assign({}, stored.merges || {}, clState.merges),
    clAssign: Object.assign({}, stored.clAssign || {}, clState.clAssign),
    collapsed: Object.assign({}, stored.collapsed || {}, clState.collapsed),
  };
  for (const k of (del && del.merges) || []) delete merged.merges[k];
  for (const k of (del && del.clAssign) || []) delete merged.clAssign[k];
  clState = merged;
  localStorage.setItem(CLSTATE_KEY, JSON.stringify(merged));
}
function groupIdOf(cid) {
  // 沿 merges 链解析最终组 id；环防御：visited 集合，成环即停不报错
  let cur = String(cid);
  const seen = new Set([cur]);
  while (clState.merges[cur] !== undefined &&
         !seen.has(String(clState.merges[cur]))) {
    cur = String(clState.merges[cur]);
    seen.add(cur);
  }
  const gid = parseInt(cur, 10);
  return isNaN(gid) ? cid : gid;
}
function computeGroups() {
  // CLUSTERS → 显示组：keys/rep_crops 按原簇序拼接；组位置 = gid 原簇原位
  const byGid = new Map();
  for (const cl of CLUSTERS) {
    const gid = groupIdOf(cl.cluster_id);
    if (!byGid.has(gid)) byGid.set(gid, { gid, cids: [], keys: [], rep_crops: [] });
    const g = byGid.get(gid);
    g.cids.push(cl.cluster_id);
    g.keys = g.keys.concat(cl.keys);
    g.rep_crops = g.rep_crops.concat(cl.rep_crops);
  }
  const pos = new Map(CLUSTERS.map((cl, i) => [cl.cluster_id, i]));
  // ?? 0 兜底：localStorage 残留失效簇 id 时 pos.get 为 undefined，防 NaN 序不稳
  return [...byGid.values()].sort((a, b) => (pos.get(a.gid) ?? 0) - (pos.get(b.gid) ?? 0));
}
function groupTag(g) {
  // 组内非空 marks 众数（显示"归的人"唯一口径；不读 clAssign）
  const counts = {};
  let assigned = 0;
  for (const k of g.keys) {
    const t = marks[k];
    if (t) { counts[t] = (counts[t] || 0) + 1; assigned++; }
  }
  let best = "", n = 0;
  for (const t of Object.keys(counts)) {
    if (counts[t] > n) { n = counts[t]; best = t; }
  }
  return { tag: best, mixed: Object.keys(counts).length > 1, assigned };
}
let cur = 0;
function save() {
  // 合并写入：先读回存储与本页记录合并再写，防止同时开多个页面互相覆盖
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(LSKEY) || "{}"); } catch (e) { stored = {}; }
  marks = Object.assign(stored, marks);
  localStorage.setItem(LSKEY, JSON.stringify(marks));
  let storedTouched = {};
  try { storedTouched = JSON.parse(localStorage.getItem(TOUCHKEY) || "{}"); }
  catch (e) { storedTouched = {}; }
  touched = Object.assign(storedTouched, touched);
  localStorage.setItem(TOUCHKEY, JSON.stringify(touched));
}
function teamOfTag(tag) {
  // 与 Python 端 team_of_tag 同规则：标签前缀定队，其余便服
  if (tag.startsWith("黑") || tag.startsWith("蓝")) return "地平线";
  if (tag.startsWith("白")) return "半截篮";
  return "便服";
}
function nDone() { return ITEMS.filter(it => marks[it.key]).length; }
function renderPlayers() {
  // 按队分行（地平线/半截篮/便服），找人不用扫全名单（2026-08-09 立哥要求）
  const box = document.getElementById("players");
  box.innerHTML = "";
  const numbered = PLAYERS.map((p, idx) => [p, idx]);
  for (const tm of ["地平线", "半截篮", "便服"]) {
    const row = numbered.filter(([p]) => p.team === tm);
    if (!row.length) continue;
    const div = document.createElement("div");
    const lab = document.createElement("span");
    lab.textContent = tm + "：";
    lab.className = "teamlabel";
    div.appendChild(lab);
    for (const [p, idx] of row) {
      const b = document.createElement("button");
      b.textContent = (idx < 9 ? (idx + 1) + " " : "") + p.tag +
        (p.name ? "=" + p.name : "");
      b.className = "team-" + p.team;
      if (ITEMS.length && marks[ITEMS[cur].key] === p.tag) b.classList.add("sel");
      b.onclick = () => assign(p.tag);
      div.appendChild(b);
    }
    box.appendChild(div);
  }
}
function groupLabel(g) {
  // 组标签：簇#gid（N 球，已归属 X[，并自 #a/#b]）；未并过无"并自"段
  const t = groupTag(g);
  let s = "簇#" + g.gid + "（" + g.keys.length + " 球，已归属 " + t.assigned;
  if (g.cids.length > 1) {
    s += "，并自 " + g.cids.filter(c => c !== g.gid).map(c => "#" + c).join("/");
  }
  return s + "）";
}
function splitGroup(gid) {
  // 拆开 = 删 merges 中指向该组的所有条目；不动 marks / 目标组 clAssign；
  // doomed 必须传给 saveClState 的删除清单，否则读回合并会把删除的键复活
  const doomed = Object.keys(clState.merges)
    .filter(k => groupIdOf(parseInt(k, 10)) === gid);
  for (const k of doomed) delete clState.merges[k];
  saveClState({ merges: doomed, clAssign: [] });
  show(cur);
}
function mergeInto(srcGid, dstGid) {
  // 拖拽合并：被并组全部原始簇指向目标组；预填来源 = 目标组 clAssign，
  // 无则组内非空 marks 全一致的 tag，混合/未归不预填；被并组 clAssign 删除
  srcGid = groupIdOf(srcGid);
  dstGid = groupIdOf(dstGid);
  if (srcGid === dstGid) return; // 自身/同组无操作
  const groups = computeGroups();
  const src = groups.find(g => g.gid === srcGid);
  const dst = groups.find(g => g.gid === dstGid);
  if (!src || !dst) return;
  for (const cid of src.cids) clState.merges[String(cid)] = dstGid;
  let tag = clState.clAssign[String(dstGid)];
  if (!tag) {
    const ts = dst.keys.map(k => marks[k]).filter(Boolean);
    if (ts.length && ts.every(x => x === ts[0])) tag = ts[0];
  }
  if (tag) {
    for (const k of src.keys) { if (!touched[k]) marks[k] = tag; }
  }
  const delAssign = [];
  for (const cid of src.cids) {
    const k = String(cid);
    delete clState.clAssign[k]; // 本地有无都删：stored 里独有的残留键靠删除清单压住
    delAssign.push(k);
  }
  save();
  saveClState({ merges: [], clAssign: delAssign });
  show(cur);
  // PICKER-HOOK: 合并弹条在 Task 4 挂这里（!tag 时 openPicker(dstGid)，
  // 替换行须保留 "PICKER-HOOK" 字样，否则 test_drag_merge_present 红）
}
function renderClusters() {
  // 簇区按显示组渲染：图墙拼接 + 组标签 + 拆开钮（合并组才有）+ 选人按钮；
  // 无簇数据整区隐藏（无 --clusters 行为同旧版）
  const box = document.getElementById("clusters");
  box.innerHTML = "";
  if (!CLUSTERS.length) { box.style.display = "none"; return; }
  box.style.display = "block";
  for (const g of computeGroups()) {
    const row = document.createElement("div");
    row.className = "cluster-row";
    row.dataset.gid = g.gid;
    row.draggable = true;
    row.ondragstart = (ev) => {
      ev.dataTransfer.setData("text/plain", String(g.gid));
      ev.dataTransfer.effectAllowed = "move";
    };
    row.ondragover = (ev) => {
      ev.preventDefault();
      row.classList.add("drop-target");
    };
    row.ondragleave = () => row.classList.remove("drop-target");
    row.ondrop = (ev) => {
      ev.preventDefault();
      row.classList.remove("drop-target");
      const src = parseInt(ev.dataTransfer.getData("text/plain"), 10);
      if (!isNaN(src)) mergeInto(src, g.gid);
    };
    for (const rc of g.rep_crops) {
      const im = document.createElement("img");
      im.src = rc;
      im.className = "rep";
      im.alt = "簇代表图";
      row.appendChild(im);
    }
    const lab = document.createElement("span");
    lab.className = "clusterlabel";
    const gt = groupTag(g);
    lab.textContent = groupLabel(g) +
      (gt.tag ? " → " + gt.tag + (gt.mixed ? "（混合）" : "") : "");
    row.appendChild(lab);
    if (g.cids.length > 1) {
      const sp = document.createElement("button");
      sp.textContent = "拆开";
      sp.className = "nav";
      sp.onclick = () => splitGroup(g.gid);
      row.appendChild(sp);
    }
    for (const p of PLAYERS) {
      const b = document.createElement("button");
      b.textContent = p.tag + (p.name ? "=" + p.name : "");
      b.className = "team-" + p.team;
      b.onclick = () => clusterAssign(g.gid, p.tag);
      row.appendChild(b);
    }
    box.appendChild(row);
  }
}
function clusterAssign(cid, tag) {
  // 簇级选人 = 按组批量预填：只写未 touched 的 key（逐球覆盖优先）；
  // 记 clAssign 作合并预填来源（spec：clAssign 唯一用途）
  const gid = groupIdOf(cid);
  const g = computeGroups().find(x => x.gid === gid);
  if (!g) return;
  for (const k of g.keys) { if (!touched[k]) marks[k] = tag; }
  clState.clAssign[String(gid)] = tag;
  save();
  saveClState();
  show(cur);
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
  if (it.cluster_id) info += ` | 簇#${groupIdOf(it.cluster_id)}`;
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
  renderClusters();
}
function assign(tag) {
  if (!ITEMS.length) return;
  marks[ITEMS[cur].key] = tag;
  touched[ITEMS[cur].key] = true;
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
  a.download = "roster.json";
  a.click();
  const nUn = ITEMS.filter(it => it.status !== "SKIP" && !marks[it.key]).length;
  alert("已下载 roster.json（归属 " + Object.keys(assignments).length +
        "/" + ITEMS.length + "，confirmed=" + confirmed +
        (nUn ? "，还有 " + nUn + " 个非 SKIP 球未归属" : "") + "），移到 work 场次目录即可");
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
    """按标签前缀推定队别：黑*/蓝*→地平线、白*→半截篮，其余（灰T恤-A 等）归便服。

    页面导出自动补录名单外标签时用同一规则（JS teamOfTag 与本文档同步，
    改规则须两端一起改）。蓝色27 归地平线系 2026-08-09 立哥口径。

    Args:
        tag: 球员标签，如 ``黑21`` / ``白-熊志鹏`` / ``灰T恤-A``。

    Returns:
        "地平线" / "半截篮" / "便服"。
    """
    for prefix, team in _TEAM_PREFIXES:
        if tag.startswith(prefix):
            return team
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


def load_players_file(path: Path) -> list[Player]:
    """加载 --players-file 名单文件：JSON 数组，与 roster.players 同构。

    每条记录的校验复用 roster.player_from_dict（tag 非空唯一 / name 为 str /
    team ∈ 地平线/半截篮/便服），与 roster.json 同一契约入口（rules.md §0.2：
    schema 损坏必须显式失败，不静默容错）。

    Args:
        path: 名单文件路径（如 ``work/<场次>/players.json``）。

    Returns:
        Player 列表（保持文件顺序）。

    Raises:
        SchemaError: 坏 JSON / 顶层非数组 / 记录结构损坏 / tag 重复 / 队名非法。
        OSError: IO 重试耗尽（文件不存在等）。
    """
    data: Any = read_json(path, what="players 名单文件")
    if not isinstance(data, list):
        raise SchemaError(
            f"{path}: 顶层必须是数组（与 roster.players 同构），实际 {type(data).__name__}"
        )
    seen_tags: set[str] = set()
    return [player_from_dict(raw, str(path), i, seen_tags) for i, raw in enumerate(data)]


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
        if c.get("team_guess") is not None and c["team_guess"] not in TEAM_GUESS_VALUES:
            raise SchemaError(f"{path}: 第{i}条候选 team_guess 非法: {c['team_guess']!r}")
        if c.get("number_guess") is not None and not isinstance(c["number_guess"], dict):
            raise SchemaError(f"{path}: 第{i}条候选 number_guess 不是对象")
    return candidates


def match_players_by_number(
    players: list[Player], number: str | None, color: str | None
) -> list[Player]:
    """号码匹配名单：号码唯一优先，颜色作消解提示（容忍 K3 颜色误读）。

    立哥 2026-08-09 确认同场号码极少重复，故：
    - 号码在名单中唯一 → 直接命中（不看颜色：颜色误读不该挡掉正确号码）；
    - 同号多人 → 用颜色进一步过滤，滤后唯一则命中、滤后为空或仍多个 → 歧义
      （返回全部候选，调用方判歧义）；
    - "2" 不会误中 "黑21"（数字边界防子串误配）。

    Args:
        players: 球员名单（--players 或已有 roster 的 players）。
        number: K3 读出的号码字符串；None 直接无匹配。
        color: K3 读出的颜色（黑/白/蓝/其他），仅作同号消解提示。

    Returns:
        命中的 Player 列表（0/1/N 个；N>1 表示歧义）。
    """
    if not number:
        return []
    pat: re.Pattern[str] = re.compile(rf"(?<!\d){re.escape(number)}(?!\d)")
    by_num: list[Player] = [p for p in players if pat.search(p.tag)]
    if len(by_num) <= 1:
        return by_num
    if color and color != "其他":
        by_col: list[Player] = [p for p in by_num if color in p.tag]
        if by_col:
            return by_col
    return by_num


def _edit_distance_le1(a: str, b: str) -> bool:
    """两字符串是否相等或只差 1 个字符（增/删/改）——K3 印名误读容差（大秋≈大斌）。"""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def match_players_by_name(players: list[Player], name_text: str | None) -> list[Player]:
    """球衣印名匹配名单：精确或差 1 字符（K3 误读容差），只看非空 name。

    Args:
        players: 球员名单。
        name_text: K3 读出的印名文本；None/空串无匹配。

    Returns:
        命中的 Player 列表（0/1/N 个；N>1 表示歧义）。
    """
    if not name_text or not name_text.strip():
        return []
    t: str = name_text.strip()
    return [p for p in players if p.name and _edit_distance_le1(t, p.name)]


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


def _validate_clusters(data: Any, path: str) -> list[dict[str, Any]]:  # noqa: ANN401
    """校验 scorer_clusters.json 结构（cluster_scorers 输出契约；rules.md §0.2）。

    Args:
        data: read_json 读出的原始 JSON。
        path: 文件路径（仅用于错误信息）。

    Returns:
        clusters 记录列表（保留原始 dict）。

    Raises:
        SchemaError: 顶层非对象 / 缺 clusters 列表 / 簇缺 cluster_id/keys/rep_crops
            或类型错 / cluster_id 重复。
    """
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: 顶层必须是对象，实际 {type(data).__name__}")
    clusters: Any = data.get("clusters")
    if not isinstance(clusters, list):
        raise SchemaError(f"{path}: 缺 clusters 列表或类型错误")
    seen_ids: set[int] = set()
    for i, cl in enumerate(clusters):
        if not isinstance(cl, dict):
            raise SchemaError(f"{path}: 第{i}个簇不是对象")
        cid: Any = cl.get("cluster_id")
        if isinstance(cid, bool) or not isinstance(cid, int):
            raise SchemaError(f"{path}: 第{i}个簇 cluster_id 缺失或非 int")
        if cid in seen_ids:
            raise SchemaError(f"{path}: cluster_id 重复: {cid}")
        seen_ids.add(cid)
        keys: Any = cl.get("keys")
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise SchemaError(f"{path}: 第{i}个簇 keys 缺失或非 str 列表")
        rep: Any = cl.get("rep_crops")
        if not isinstance(rep, list) or not all(isinstance(r, str) for r in rep):
            raise SchemaError(f"{path}: 第{i}个簇 rep_crops 缺失或非 str 列表")
    return clusters


def build_cluster_map(clusters: list[dict[str, Any]], candidate_keys: set[str]) -> dict[str, int]:
    """key → cluster_id 映射；引用 candidates 之外的 key 记 WARNING 跳过（不炸）。

    同一 key 出现在多个簇（聚类契约本应互斥）取首个并记 WARNING，容忍不炸。

    Args:
        clusters: _validate_clusters 校验后的簇列表。
        candidate_keys: 本页 candidates 的 key 集合。

    Returns:
        key → cluster_id（只含 candidates 里存在的 key）。
    """
    mapping: dict[str, int] = {}
    for cl in clusters:
        cid: int = cl["cluster_id"]
        for key in cl["keys"]:
            if key not in candidate_keys:
                logger.warning("簇 %d 引用的 key 不在 candidates 里，跳过: %s", cid, key)
                continue
            if key in mapping:
                logger.warning("key 同时属于簇 %d 与簇 %d，取前者: %s", mapping[key], cid, key)
                continue
            mapping[key] = cid
    return mapping


def build_page_clusters(
    clusters: list[dict[str, Any]], entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """簇 → 页面簇区数据：keys 过滤到本页条目（confirmed 球），过滤后为空的簇剔除。

    rep_crops 原样透传（文件名相对 candidates 同目录，与逐球区 crop 引用口径一致；
    --clusters 必须与 --scorers 同目录由 CLI 层保证）。

    Args:
        clusters: _validate_clusters 校验后的簇列表。
        entries: build_entries 产出的页面条目。

    Returns:
        页面簇区数据列表（cluster_id/keys/rep_crops），保持入参簇序。
    """
    entry_keys: set[str] = {e["key"] for e in entries}
    page: list[dict[str, Any]] = []
    for cl in clusters:
        keys: list[str] = [k for k in cl["keys"] if k in entry_keys]
        dropped: int = len(cl["keys"]) - len(keys)
        if dropped:
            logger.info(
                "簇 %d 有 %d 个 key 不在本页 confirmed 球里（其他批次/非 confirmed，页面不显示）",
                cl["cluster_id"],
                dropped,
            )
        if not keys:
            continue
        page.append(
            {
                "cluster_id": cl["cluster_id"],
                "keys": keys,
                "rep_crops": list(cl["rep_crops"]),
            }
        )
    return page


def build_entries(
    confirmed: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    events: list[dict[str, Any]] | None,
    index_dir: str,
    out_dir: str,
    players: list[Player] | None = None,
    cluster_map: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """组装页面条目：每条 = 一个 confirmed 球（按 file+anchor 排序）。

    以 goals.json 的 confirmed 球为全集，按 key 关联 candidates 取裁图/
    team_guess/number_guess/SKIP 状态；无候选记录（防御）按 SKIP 列出。视频优先级：
    candidates 的 "clip"（按进球锚点现切的预览片段，与裁图同球同时刻）＞
    events_index 的 clip_wide 匹配（仅作无预览片段时的兜底）。预填优先级：
    号码匹配（number_guess 的 number+color 与名单 tag 匹配）＞ 颜色 team_guess；
    号码匹配到多个球员 → 不预填，prefill_note="ambiguous"（页面标"号码歧义"）。
    给了 cluster_map 则每条追加 cluster_id（不在任何簇/unclustered → None）。

    Args:
        confirmed: goals.json 的 confirmed 记录。
        candidates: scorer_candidates.json 的候选记录。
        events: 事件列表；None 表示无 --index（无兜底视频）。
        index_dir: events_index.json 所在目录。
        out_dir: scorer.html 输出目录。
        players: 球员名单（号码匹配用）；None/空列表则只做颜色预填。
        cluster_map: key → cluster_id（build_cluster_map 产物）；None 表示无
            --clusters，条目 cluster_id 全为 None（页面不渲染簇区）。

    Returns:
        页面条目列表（key/file/anchor_time/status/reason/crop/team_guess/clip/
        number_guess/prefill_tag/prefill_note/cluster_id）。
    """
    players = players or []
    cluster_map = cluster_map or {}
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
        # 预填：号码唯一匹配；同号歧义时用印名消解；无号码则印名直配
        number_guess: dict[str, Any] | None = cand.get("number_guess") if cand is not None else None
        prefill_tag: str = ""
        prefill_note: str = ""
        if isinstance(number_guess, dict):
            matches: list[Player] = match_players_by_number(
                players, number_guess.get("number"), number_guess.get("color")
            )
            name_matches: list[Player] = match_players_by_name(
                players, number_guess.get("name_text")
            )
            if not matches:
                matches = name_matches
            elif len(matches) > 1 and name_matches:
                narrowed: list[Player] = [p for p in matches if p in name_matches]
                if narrowed:
                    matches = narrowed
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
                "cluster_id": cluster_map.get(key),
            }
        )
    return entries


def build_html(
    entries: list[dict[str, Any]],
    players: list[Player],
    session: str,
    existing_assignments: dict[str, str],
    existing_players: dict[str, Player],
    clusters: list[dict[str, Any]] | None = None,
) -> str:
    """把条目/名单/已有归属/簇数据渲染为自包含确认页 HTML。

    Args:
        entries: build_entries 产出的页面条目（原样内联）。
        players: 球员按钮名单（--players 或已有 roster 的 players）。
        session: 场次名（标题、localStorage 键、导出文件名后缀）。
        existing_assignments: 已有 roster 的 assignments（页面预填底色）。
        existing_players: 已有 roster 的 tag → Player（自动补录时沿用 name/team）。
        clusters: build_page_clusters 产出的簇区数据；None/空列表不渲染簇区
            （无 --clusters 时页面行为与旧版一致）。

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
        .replace("__CLUSTERS__", json.dumps(clusters or [], ensure_ascii=False))
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
        "--players",
        default="",
        help='球员名单，如 "黑21=大斌,白-熊志鹏=熊志鹏"（可选，与 --players-file 互斥）',
    )
    parser.add_argument(
        "--players-file",
        type=Path,
        default=None,
        help="球员名单 JSON 文件（与 roster.players 同构的数组；可选，与 --players 互斥）",
    )
    parser.add_argument("--roster-existing", default="", help="已有 roster.json（可选，合并预填）")
    parser.add_argument(
        "--clusters",
        type=Path,
        default=None,
        help="scorer_clusters.json 路径（可选，簇级确认；必须与 --scorers 同目录）",
    )
    ns = parser.parse_args(argv)
    if ns.players and ns.players_file is not None:
        parser.error("--players 与 --players-file 互斥：名单只给一个来源（防双源不一致）")
    if ns.clusters is not None and ns.clusters.resolve().parent != ns.scorers.resolve().parent:
        parser.error("--clusters 必须与 --scorers 同目录（rep_crops 与裁图同目录相对引用口径）")
    return ns


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

        clusters_raw: list[dict[str, Any]] | None = None
        cluster_map: dict[str, int] | None = None
        if args.clusters is not None:
            cl_data: Any = read_json(args.clusters, what="scorer_clusters.json")
            clusters_raw = _validate_clusters(cl_data, str(args.clusters))
            cluster_map = build_cluster_map(clusters_raw, {c["key"] for c in candidates})

        players: list[Player] = (
            load_players_file(args.players_file)
            if args.players_file is not None
            else parse_players(args.players)
        )
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
            confirmed, candidates, events, index_dir, out_dir, players, cluster_map=cluster_map
        )

        page_clusters: list[dict[str, Any]] | None = None
        if clusters_raw is not None:
            page_clusters = build_page_clusters(clusters_raw, entries)

        html: str = build_html(
            entries,
            players,
            session,
            existing_assignments,
            existing_players,
            clusters=page_clusters,
        )
        out_path: Path = scorers_path.resolve().parent / "scorer.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        n_skip: int = sum(1 for e in entries if e["status"] == STATUS_SKIP)
        n_clip: int = sum(1 for e in entries if e["clip"])
        logger.info(
            "确认页 %d 球（SKIP %d，带片段 %d，球员 %d，簇 %d）-> %s（浏览器打开即可认人）",
            len(entries),
            n_skip,
            n_clip,
            len(players),
            len(page_clusters or []),
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
