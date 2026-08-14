# 认人页簇合并 + 折叠 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 认人确认页簇区支持拖拽合并（含归属预填跟随、合并弹条就地选人、拆开撤销）与折叠（已归属自动收起），认 52 簇压到按人确认。

**Architecture:** 全部改动在 `scripts/gen_scorer_page.py` 的 `_HTML` 模板字符串内（CSS + JS），零 Python 逻辑变更。新增页面态 `scorer_<session>_clusters`（localStorage：`merges`/`clAssign`/`collapsed` 三子键），加载时把 CLUSTERS 解析为显示组；导出 roster.json 契约不动。

**Tech Stack:** Python 3.14 模板字符串内嵌原生 JS（HTML5 Drag & Drop + localStorage），零新依赖；测试 = pytest 模板断言 + node --check（沿用 tests/test_gen_scorer_page.py 既有模式）。

## Global Constraints

- 遵守根目录 `rules.md`（鲁棒优先 ＞ 性能 ＞ 简洁）
- **不改** roster.json 导出 schema、不改 scorer_clusters.json 产物、不回写任何 work/ 文件
- 逐球覆盖（`touched`）优先于一切簇级批量改动：批量预填一律 `if (!touched[k])`
- JSON 对象键为字符串而 cluster_id 是 int：读写一律 `String(cid)` 字符串化
- 模板改动必须保留既有测试断言标识符：`clusterAssign`、`cluster-row`、`const CLUSTERS = [];`、`id="clusters"`
- 每步质量门：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q`（--fix 后复核 diff）
- 提交：中文 conventional 风格（参照 git log），只 commit 不 push
- spec：`docs/scorer-cluster-merge/spec.md`（数据契约以此为准）

---

### Task 1: 页面态层 + 组解析工具函数

**Files:**
- Modify: `scripts/gen_scorer_page.py`（_HTML 模板 `<script>` 段，约 :130-155 变量声明区、:220-227 `clusterAssign`、:241 组号显示）
- Test: `tests/test_gen_scorer_page.py`（新增 TestBuildHtmlClusterMerge 类）

**Interfaces:**
- Produces（后续 Task 依赖的 JS 标识符，全在模板内）:
  - `CLSTATE_KEY` = `LSKEY + "_clusters"`；`clState` = `{ merges, clAssign, collapsed }`
  - `saveClState(del)` — 子键分别读回合并写；`del` = `{ merges: [], clAssign: [] }`
    待删键清单（读回合并会把本地删掉的键从 stored 复活，必须在合并后再删）
  - `groupIdOf(cid) -> int` — 沿 merges 链解析最终组 id（环防御）
  - `computeGroups() -> [{gid, cids, keys, rep_crops}]` — 组位置 = gid 原簇在 CLUSTERS 的位置
  - `groupTag(g) -> {tag, mixed, assigned}` — 组内非空 marks 众数
  - `clusterAssign(cid, tag)` 改造：按组作用 + 记 `clState.clAssign[String(gid)]`

- [ ] **Step 1: 写失败测试**

在 `tests/test_gen_scorer_page.py` 的 `TestBuildHtmlClusters` 类后新增：

```python
class TestBuildHtmlClusterMerge:
    """簇合并+折叠模板断言（docs/scorer-cluster-merge/spec.md）：标识符在，JS 语法合法。"""

    def _html(self) -> str:
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        return build_html(entries, [], "s", {}, {}, clusters=page_clusters)

    def test_cluster_state_layer_present(self) -> None:
        html = self._html()
        assert 'CLSTATE_KEY = LSKEY + "_clusters"' in html
        assert "function saveClState(" in html
        assert "function groupIdOf(" in html
        assert "function computeGroups(" in html
        assert "function groupTag(" in html
        assert "clState.clAssign" in html
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlClusterMerge -x -q`
Expected: FAIL（`CLSTATE_KEY` 不在模板里）

- [ ] **Step 3: 实现——模板 `<script>` 变量声明区（`let touched = {};` 块之后）插入**

```js
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
```

- [ ] **Step 4: 改造 `clusterAssign`（整段替换模板中现有实现）**

```js
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
```

- [ ] **Step 5: `show()` 里逐球区簇号改显示组 id**

模板中找到 `if (it.cluster_id) info += \` | 簇#${it.cluster_id}\`;` 改为：

```js
  if (it.cluster_id) info += ` | 簇#${groupIdOf(it.cluster_id)}`;
```

- [ ] **Step 6: 跑测试确认通过 + 全量质量门**

Run: `python -m pytest tests/test_gen_scorer_page.py -q`
Expected: PASS（含既有 `test_generated_js_syntax_node_check`）
再跑质量门（Global Constraints 命令），全绿。

- [ ] **Step 7: Commit**

```bash
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页簇合并状态层——merges/clAssign/collapsed 页面态与组解析（spec docs/scorer-cluster-merge）"
```

---

### Task 2: renderClusters 按组渲染 + 拆开

**Files:**
- Modify: `scripts/gen_scorer_page.py`（模板 `renderClusters` 整段，约 :188-219）
- Test: `tests/test_gen_scorer_page.py`（TestBuildHtmlClusterMerge 加断言）

**Interfaces:**
- Consumes: Task 1 的 `computeGroups/groupTag/groupIdOf/saveClState/clState`
- Produces: `splitGroup(gid)`；`groupLabel(g) -> str`；组行 DOM 约定 `row.dataset.gid`（Task 3 拖拽用）

- [ ] **Step 1: 加失败断言**

TestBuildHtmlClusterMerge 加：

```python
    def test_group_render_and_split_present(self) -> None:
        html = self._html()
        assert "function splitGroup(" in html
        assert "function groupLabel(" in html
        assert "并自" in html
        assert "row.dataset.gid" in html
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlClusterMerge::test_group_render_and_split_present -q`
Expected: FAIL

- [ ] **Step 3: 整段替换模板 `renderClusters`，并新增 `groupLabel`/`splitGroup`**

```js
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
```

- [ ] **Step 4: 跑测试 + 质量门**

Run: `python -m pytest tests/test_gen_scorer_page.py -q` → PASS；质量门全绿。

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页簇区按显示组渲染——组标签/并自段/归的人众数/拆开按钮"
```

---

### Task 3: 拖拽合并 mergeInto + 预填跟随

**Files:**
- Modify: `scripts/gen_scorer_page.py`（模板 `renderClusters` 行创建处加拖拽事件、新增 `mergeInto`、CSS 加 `.drop-target`/拖拽光标）
- Test: `tests/test_gen_scorer_page.py`（加断言）

**Interfaces:**
- Consumes: 全部 Task 1/2 标识符
- Produces: `mergeInto(srcGid, dstGid)`（Task 4 在其尾部 PICKER-HOOK 注释行
  挂弹条调用，替换行保留 "PICKER-HOOK" 字样保证断言持续有效）

- [ ] **Step 1: 加失败断言**

```python
    def test_drag_merge_present(self) -> None:
        html = self._html()
        assert "function mergeInto(" in html
        assert "row.draggable = true" in html
        assert "drop-target" in html
        assert "PICKER-HOOK" in html
```

- [ ] **Step 2: 跑测试确认失败**（同上模式，FAIL）

- [ ] **Step 3: CSS 追加（`.clusterlabel` 规则后）**

```css
.cluster-row { cursor: grab; }
.cluster-row.drop-target { outline: 3px dashed #fc3; }
```

- [ ] **Step 4: 新增 `mergeInto`（放 `splitGroup` 后）**

```js
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
```

- [ ] **Step 5: `renderClusters` 行创建处（`row.dataset.gid = g.gid;` 之后）加拖拽事件**

```js
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
```

- [ ] **Step 6: 跑测试 + 质量门** → PASS / 全绿

- [ ] **Step 7: Commit**

```bash
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 簇行拖拽合并——预填跟随目标组/被并组 clAssign 清除/同组与环防御"
```

---

### Task 4: 合并弹条就地选人 + 数字键屏蔽

**Files:**
- Modify: `scripts/gen_scorer_page.py`（新增 `openPicker/closePicker`、`mergeInto` 尾部 hook、`renderClusters` 弹条渲染块、keydown 处理、document 点击外关、CSS `.picker`）
- Test: `tests/test_gen_scorer_page.py`（加断言）

**Interfaces:**
- Consumes: `mergeInto` 的 PICKER-HOOK、`clusterAssign`
- Produces: `pickerGid`（null=无弹条）；`openPicker(gid)`；`closePicker()`

- [ ] **Step 1: 加失败断言**

```python
    def test_merge_picker_present(self) -> None:
        html = self._html()
        assert "function openPicker(" in html
        assert "pickerGid" in html
        assert "openPicker(dstGid)" in html
        assert 'className = "picker"' in html
        assert 'ev.key === "Escape"' in html
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: CSS 追加**

```css
.picker { background: #2a2a12; border: 1px solid #fc3; border-radius: 8px;
          padding: 6px; margin: 4px 0; width: 100%; }
.picker .hint { color: #fc3; margin-right: 8px; }
```

- [ ] **Step 4: 新增弹条函数（`mergeInto` 后）+ 变量声明（`clState` 声明块后）**

变量声明区加：

```js
let pickerGid = null; // 合并弹条：非 null = 该组行正弹选人条
```

新函数：

```js
function openPicker(gid) {
  pickerGid = gid;
  show(cur);
}
function closePicker() {
  if (pickerGid === null) return;
  pickerGid = null;
  show(cur);
}
```

- [ ] **Step 5: `mergeInto` 尾部 PICKER-HOOK 注释行替换为（保留 "PICKER-HOOK" 字样）**

```js
  // PICKER-HOOK 已挂接：未自动预填 → 就地弹选人条（spec 合并动作 7）
  if (!tag) openPicker(dstGid);
```

- [ ] **Step 6: `renderClusters` 选人按钮循环之后、`box.appendChild(row)` 之前加弹条渲染块**

```js
    if (pickerGid === g.gid) {
      const pk = document.createElement("div");
      pk.className = "picker";
      const hint = document.createElement("span");
      hint.className = "hint";
      hint.textContent = "合并完成，选人应用到整组（" + g.keys.length + " 球）：";
      pk.appendChild(hint);
      for (const p of PLAYERS) {
        const b = document.createElement("button");
        b.textContent = p.tag + (p.name ? "=" + p.name : "");
        b.className = "team-" + p.team;
        b.onclick = () => { pickerGid = null; clusterAssign(g.gid, p.tag); };
        pk.appendChild(b);
      }
      const cancel = document.createElement("button");
      cancel.textContent = "取消";
      cancel.className = "nav";
      cancel.onclick = () => closePicker();
      pk.appendChild(cancel);
      row.appendChild(pk);
    }
```

- [ ] **Step 7: keydown 监听开头（自由输入框分支之后）加屏蔽段**

模板现有：

```js
document.addEventListener("keydown", (ev) => {
  if (ev.target && ev.target.id === "free") {
    if (ev.key === "Enter") freeAssign();
    return;
  }
  const k = ev.key.toLowerCase();
```

在 `const k = ...` 行后插入：

```js
  if (pickerGid !== null) {
    // 弹条期间：Esc 关闭；数字键 1-9/E 屏蔽（防误触逐球归属改错球）
    if (ev.key === "Escape") closePicker();
    if ((k >= "1" && k <= "9") || k === "e") return;
  }
```

- [ ] **Step 8: 点弹条外区域关闭（keydown 监听注册后加）**

```js
document.addEventListener("click", (ev) => {
  if (pickerGid === null) return;
  if (ev.target && ev.target.closest && ev.target.closest(".picker")) return;
  closePicker();
});
```

（注意：弹条内按钮 onclick 先执行选人/取消，随后冒泡到此监听时 pickerGid 已为 null，不会误关；选人按钮已先把 pickerGid 置 null。）

- [ ] **Step 9: 跑测试 + 质量门** → PASS / 全绿

- [ ] **Step 10: Commit**

```bash
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 簇合并弹条就地选人——无归属组合并一步命名，弹条期间屏蔽逐球快捷键"
```

---

### Task 5: 折叠（默认规则 + 显式覆盖 + 总开关）

**Files:**
- Modify: `scripts/gen_scorer_page.py`（新增 `isCollapsed/toggleCollapse`、`renderClusters` 折叠态分支与总开关、CSS）
- Test: `tests/test_gen_scorer_page.py`（加断言）

**Interfaces:**
- Consumes: `clState.collapsed`、`groupTag`
- Produces: `collapseAll`（null=随规则 / true=全折 / false=全展，瞬态不入存储）；`isCollapsed(g)`；`toggleCollapse(gid)`

- [ ] **Step 1: 加失败断言**

```python
    def test_collapse_present(self) -> None:
        html = self._html()
        assert "function isCollapsed(" in html
        assert "function toggleCollapse(" in html
        assert "collapseAll" in html
        assert "全部展开" in html
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: CSS 追加**

```css
.cluster-row.collapsed img.rep { max-height: 48px; max-width: 64px; }
.cluster-row .foldbtn { font-size: 12px; padding: 2px 8px; }
```

- [ ] **Step 4: 变量声明区加 + 新函数（`closePicker` 后）**

```js
let collapseAll = null; // 总开关：null=随规则 / true=全折 / false=全展（瞬态，刷新回规则；
                        // 点击后 null→true→false→true… 两态循环回不到"随规则"系有意
                        // 为之——回规则态靠刷新，spec 未要求三态）
```

```js
function isCollapsed(g) {
  // 优先级：总开关 > 显式 collapsed > 默认规则（组内全部球有 marks → 折叠）
  if (collapseAll !== null) return collapseAll;
  const ex = clState.collapsed[String(g.gid)];
  if (ex !== undefined) return !!ex;
  return g.keys.every(k => marks[k]);
}
function toggleCollapse(gid) {
  const g = computeGroups().find(x => x.gid === gid);
  if (!g) return;
  clState.collapsed[String(gid)] = !isCollapsed(g);
  saveClState();
  show(cur);
}
```

- [ ] **Step 5: `renderClusters` 改造（三处）**

① 函数体 `box.style.display = "block";` 后加总开关行：

```js
  const tbar = document.createElement("div");
  const tall = document.createElement("button");
  tall.textContent = "全部展开/折叠";
  tall.className = "nav";
  tall.onclick = () => {
    collapseAll = collapseAll === null ? true : !collapseAll;
    renderClusters();
  };
  tbar.appendChild(tall);
  box.appendChild(tbar);
```

② 组行循环开头（`row.dataset.gid = g.gid;` 后）加折叠态分支：

```js
    const folded = isCollapsed(g);
    if (folded) row.classList.add("collapsed");
    const fb = document.createElement("button");
    fb.textContent = folded ? "▸" : "▾";
    fb.className = "foldbtn nav";
    fb.title = folded ? "展开" : "折叠";
    fb.onclick = () => toggleCollapse(g.gid);
    row.appendChild(fb);
```

③ 图墙循环改为折叠态只放首图，且折叠态跳过选人按钮/拆开钮（小结一行）：

把现有 `for (const rc of g.rep_crops) {...}` 循环改为：

```js
    for (const rc of folded ? g.rep_crops.slice(0, 1) : g.rep_crops) {
      const im = document.createElement("img");
      im.src = rc;
      im.className = "rep";
      im.alt = "簇代表图";
      row.appendChild(im);
    }
```

并在 `if (g.cids.length > 1) {`（拆开钮）与 `for (const p of PLAYERS) {`（选人按钮）两处条件前各加 `!folded &&` 守卫：

```js
    if (!folded && g.cids.length > 1) {
```

```js
    if (!folded) {
      for (const p of PLAYERS) {
```

（花括号包住整个选人按钮 for 循环体，防后续误改。）

弹条块**不加** `!folded` 守卫，保持 `if (pickerGid === g.gid) {`——pickerGid
优先于折叠态：目标组归属混合且整组全有 marks 时默认折叠规则会判定
folded=true，若加守卫弹条被吞、pickerGid 挂着不可见（spec 合并动作 7
要求此边界必弹）；弹条自带选人按钮，行折叠不影响就地选人。

- [ ] **Step 6: 跑测试 + 质量门** → PASS / 全绿

- [ ] **Step 7: Commit**

```bash
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 簇折叠——全归属自动收起/显式覆盖刷新保持/全部展开折叠总开关"
```

---

### Task 6: 实跑验证 + 使用手册同步 + 收尾

**Files:**
- Run: `work/20260805_车百鼎/`（只读，页面生成到 scorers_b1/）
- Modify: `使用手册.html`（认人一节补簇合并/折叠/弹条说明）

- [ ] **Step 1: 用实数据生成页面**

```bash
python scripts/gen_scorer_page.py \
  --scorers work/20260805_车百鼎/scorers_b1/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch1.json \
  --clusters work/20260805_车百鼎/scorers_b1/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch1/events_index.json
```

Expected: 退出码 0，`work/20260805_车百鼎/scorers_b1/scorer.html` 生成

- [ ] **Step 2: 无 --clusters 兼容性回归**

```bash
python scripts/gen_scorer_page.py \
  --scorers work/20260805_车百鼎/scorers_b1/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch1.json
```

Expected: 退出码 0；生成页 `const CLUSTERS = [];`（grep 验证），簇区隐藏

- [ ] **Step 3: 手工验证清单交付立哥**（spec Testing Strategy 全 11 条，
  含拖拽合并/链式并/冲突并/弹条/拆开/折叠/导出 diff/刷新持久/无簇兼容）——
  代理侧自动验 node --check 与页面生成；导出 diff 对比与拖拽/弹条交互
  需浏览器内操作序列，归立哥手工过

- [ ] **Step 4: 使用手册.html 认人一节补三段**（拖拽合并=拖到目标行松开、
  合并后弹条就地选人、已归属簇自动折叠+总开关），改完过 spec-reviewer
  （参照 commit 901c67c 先例）

- [ ] **Step 5: todo.md 勾完 + 质量门终跑 + Commit**

```bash
git add 使用手册.html docs/scorer-cluster-merge/
git commit -m "docs: 使用手册补认人页簇合并/折叠/弹条操作说明"
```

---

## Self-Review 记录

- spec 覆盖：数据契约（Task 1）/ 显示组解析（1、2）/ 合并动作 1-6（3）/
  动作 7 弹条（4）/ 拆开（2）/ 折叠（5）/ 实跑与手册（6）——全覆盖
- 占位符：无；每步代码完整
- 标识符一致性：`mergeInto/openPicker/closePicker/isCollapsed/toggleCollapse/
  splitGroup/groupLabel/groupTag/computeGroups/groupIdOf/saveClState/clState/
  pickerGid/collapseAll` 跨 Task 引用一致；PICKER-HOOK 注释在 Task 3 埋点、
  Task 4 替换，断言先行锁定
