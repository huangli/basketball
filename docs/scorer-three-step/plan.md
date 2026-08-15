# 认人页三步引导流程 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 认人页 scorer.html 加三步引导（标题条 / 改名 / 按人核对 / 删簇 / 定高布局+悬停放大），spec = `docs/scorer-three-step/spec.md`（唯一契约）。

**Architecture:** 零 Python 逻辑变更，全部改 `scripts/gen_scorer_page.py` 的 `_HTML` 模板（CSS+JS）；localStorage 新增两个独立键（`_names` / `_review`），clState 扩一个 `deleted` 子键；roster 导出契约、marks/touched/teamovr 既有键格式不动。

**Tech Stack:** 纯前端模板字符串；测试 = pytest 模板字符串断言 + node --check（既有模式）。

## Global Constraints

- 称用户"立哥"；提交信息中文 conventional；只 commit 不 push；git add 点名文件（**有并行会话在同 repo 工作**，严禁 `git add -A`/`git add .`）
- 质量门（每次代码提交前）：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py` 全绿（test_release_probe.py 是并行会话 WIP，与本次无关）
- spec 边界（Never）：不给改标签（tag）；不改 roster.json schema；不改既有 marks/touched/clState 三子键/teamovr 键格式（clState 只**新增** deleted 子键）；核对过滤不改 ITEMS 本体；删簇不动 marks/touched/ITEMS
- localStorage 一律 try/catch 容错 + 读回合并写；**清空/切回 = 写空串不删键**（读回合并写会复活删键，saveClState 前科）
- 既有断言标识符不得破坏（点名：`"scorer_" + SESSION`、`const CLUSTERS = [];`、`clusterAssign`、`cluster-row`、`id="clusters"`、`teamClass`、`const KNOWN_TEAMS = [OPP, `、`teamovr`、`text/player-tag`、`PICKER-HOOK`、`b.className = teamClass(p.team)`、`b.textContent = (idx < 9 ...` 两行）
- 模板 JS 无框架、无新依赖、无新 CLI 参数
- 任务按顺序执行（后序任务的锚点文本依赖前序任务的产物）

---

### Task 1: 三步引导标题条

**Files:**
- Modify: `scripts/gen_scorer_page.py`（_HTML 模板：style 段约 95 行后、body 段 119-134、renderClusters 约 430 行）
- Test: `tests/test_gen_scorer_page.py`（文件末尾追加新 class）

**Interfaces:**
- Produces: CSS 类 `.stepbar`；HTML `id="step2"`（Task 4 的 reviewbar 插在它后面）；断言锚 `第一步：判队伍`/`第二步：并簇认人`/`第三步：逐球核对`

- [ ] **Step 1: 写失败测试**

`tests/test_gen_scorer_page.py` 末尾追加：

```python
class TestBuildHtmlStepBars:
    """三步引导标题条（docs/scorer-three-step/spec.md）：判队伍/并簇认人/逐球核对。"""

    def _html(self, with_clusters: bool = True) -> str:
        if with_clusters:
            entries = build_entries(
                [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
            )
            page_clusters = build_page_clusters([_cluster()], entries)
            return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)
        return build_html([], [], "s", {}, {}, "地平线")

    def test_step_bars_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "stepbar" in html
        assert "第一步：判队伍" in html
        assert "第二步：并簇认人" in html
        assert "第三步：逐球核对" in html

    def test_step2_toggles_with_clusters(self) -> None:
        # Arrange / Act：无簇页面也要有 step2 元素 + JS 开关（随簇区隐藏）
        html = self._html(with_clusters=False)
        # Assert
        assert 'id="step2"' in html
        assert 'getElementById("step2")' in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlStepBars -q
```

Expected: FAIL（`stepbar` 断言不成立）

- [ ] **Step 3: 实现模板改动（4 处）**

E1 — CSS：在 `#free { ... }` 规则后插入：

```css
.stepbar { color: #fc3; font-size: 14px; margin: 10px 0 2px; }
.stepbar small { color: #999; margin-left: 8px; font-size: 12px; }
```

E2 — HTML `#bar` 内，`<span id="players"></span>` 前插入一行：

```html
  <div class="stepbar">第一步：判队伍<small>拖队员到正确队伍行，点"改名"填真名</small></div>
```

E3 — HTML `<div id="clusters"></div>` 前插入：

```html
<div class="stepbar" id="step2">第二步：并簇认人<small>同人的簇拖到一起，点队员名应用到整组；误分组的簇点"删除"移除（不动球和归属）</small></div>
```

E4 — HTML `<img id="crop" alt="投篮者裁图">` 前插入：

```html
<div class="stepbar">第三步：逐球核对<small>选核对对象，判错直接点正确球员</small></div>
```

E5 — `renderClusters()` 开头，把：

```js
  if (!CLUSTERS.length) { box.style.display = "none"; return; }
  box.style.display = "block";
```

改为（第二步标题条随簇区显隐，无 --clusters 时整条隐藏）：

```js
  const step2 = document.getElementById("step2");
  if (!CLUSTERS.length) {
    box.style.display = "none";
    if (step2) step2.style.display = "none";
    return;
  }
  box.style.display = "block";
  if (step2) step2.style.display = "block";
```

- [ ] **Step 4: 跑测试确认通过 + JS 语法校验**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py -q
```

Expected: 全绿（含既有 `test_generated_js_syntax_node_check`，node --check 自动覆盖）

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页三步引导标题条（判队伍/并簇认人/逐球核对）"
```

---

### Task 2: 删簇（clState 新增 deleted 墓碑子键）

**Files:**
- Modify: `scripts/gen_scorer_page.py`（clState 初始值约 157/165 行、加载白名单约 161 行、saveClState 约 202 行、computeGroups 约 237 行、splitGroup 后插入 deleteCluster、renderClusters 约 503 行前）
- Test: `tests/test_gen_scorer_page.py`（末尾追加）

**Interfaces:**
- Consumes: `clState`/`saveClState(del)`/`computeGroups()`/`groupIdOf()`/`show(cur)`（既有）
- Produces: `function deleteCluster(gid)`；`clState.deleted`（`{ gid: true }` 墓碑，只加不减）

- [ ] **Step 1: 写失败测试**

```python
class TestBuildHtmlDeleteCluster:
    """删簇（docs/scorer-three-step/spec.md）：deleted 墓碑子键，组从簇区隐藏不动归属。"""

    def _html(self) -> str:
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)

    def test_delete_cluster_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "function deleteCluster(" in html
        assert "deleted:" in html
        assert "clState.deleted" in html
        assert "删除簇#" in html

    def test_deleted_subkey_loaded_and_saved(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert：加载白名单与 saveClState 合并分支都带上 deleted
        assert '"deleted"' in html
        assert "stored.deleted" in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlDeleteCluster -q
```

Expected: FAIL

- [ ] **Step 3: 实现模板改动（6 处）**

E1 — clState 初始值（约 157 行），注释与对象一起改：

```js
// 簇合并页面态：merges=被并cid→组id，clAssign=组id→tag（仅作合并预填来源，
// 显示/折叠判定一律以 marks 为准），collapsed=显式折叠（true/false 都存），
// deleted=删簇墓碑（gid→true，只加不减；删的是显示组，不动球和归属）
let clState = { merges: {}, clAssign: {}, collapsed: {}, deleted: {} };
```

E2 — 加载白名单（约 161 行）：

```js
    for (const sub of ["merges", "clAssign", "collapsed", "deleted"]) {
```

E3 — catch 回退（约 165 行）：

```js
} catch (e) { clState = { merges: {}, clAssign: {}, collapsed: {}, deleted: {} }; }
```

E4 — saveClState：注释里"del = { merges: [...], clAssign: [...] 待删键"一句后补"（deleted 墓碑只加不减，del 清单无需扩展）"，merged 对象加一行：

```js
  const merged = {
    merges: Object.assign({}, stored.merges || {}, clState.merges),
    clAssign: Object.assign({}, stored.clAssign || {}, clState.clAssign),
    collapsed: Object.assign({}, stored.collapsed || {}, clState.collapsed),
    deleted: Object.assign({}, stored.deleted || {}, clState.deleted),
  };
```

E5 — computeGroups 返回处（约 237 行），把：

```js
  return [...byGid.values()].sort((a, b) => (pos.get(a.gid) ?? 0) - (pos.get(b.gid) ?? 0));
```

改为：

```js
  // 删簇墓碑过滤在折叠成显示组之后：删的是立哥肉眼所见的行；
  // merges 链不动（groupIdOf 照常解析，逐球区"簇#N"标注保留）
  return [...byGid.values()]
    .filter(g => !clState.deleted[String(g.gid)])
    .sort((a, b) => (pos.get(a.gid) ?? 0) - (pos.get(b.gid) ?? 0));
```

E6 — 在 `splitGroup` 函数后插入新函数：

```js
function deleteCluster(gid) {
  // 删簇 = 墓碑隐藏显示组：只移除分组视图，ITEMS/marks/touched/clAssign 一律不动
  // （簇只是分组预填，组内球在逐球区照常核对）；无页内撤销，找回=清站点数据
  const g = computeGroups().find(x => x.gid === gid);
  if (!g) return;
  if (!confirm("删除簇#" + gid + "？组内 " + g.keys.length +
               " 球的归属不变，可在第三步逐球核对")) return;
  clState.deleted[String(gid)] = true;
  if (pickerGid === gid) pickerGid = null; // 顺手清悬挂弹条状态（组已不渲染）
  saveClState();
  show(cur);
}
```

E7 — renderClusters 组行内，`if (pickerGid === g.gid) {` 之前插入（行尾删除钮，展开/折叠行都有，位置不依赖"拆开"钮）：

```js
    const del = document.createElement("button");
    del.textContent = "删除";
    del.className = "nav";
    del.title = "移除该簇分组（不动球和归属）";
    del.onclick = () => deleteCluster(g.gid);
    row.appendChild(del);
```

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py -q
```

Expected: 全绿

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页删簇——误分组簇墓碑隐藏，不动球与归属"
```

---

### Task 3: 页内改真名（_names 键）

**Files:**
- Modify: `scripts/gen_scorer_page.py`（CSS 一处、changeTeam 函数后插入改名状态块、renderPlayers 两处循环各加一个钮）
- Test: `tests/test_gen_scorer_page.py`（末尾追加）

**Interfaces:**
- Consumes: `PLAYERS`（`p.tag`/`p.name`）、`show(cur)`、LSKEY
- Produces: `function renamePlayer(tag)`、`function saveNames()`、`NAMES_KEY = LSKEY + "_names"`；CSS 类 `.renamebtn`

- [ ] **Step 1: 写失败测试**

```python
class TestBuildHtmlRename:
    """页内改真名（docs/scorer-three-step/spec.md）：独立 _names 键，清空=写空串不删键。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_rename_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert '"_names"' in html
        assert "function renamePlayer(" in html
        assert "function saveNames(" in html
        assert "改名" in html

    def test_rename_entry_in_player_rows(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert：改名钮只挂队伍区（含兜底行）按钮旁，簇区/弹条不加
        assert "renamePlayer(p.tag)" in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlRename -q
```

Expected: FAIL

- [ ] **Step 3: 实现模板改动（4 处）**

E1 — CSS（`.stepbar` 规则后即可）：

```css
.renamebtn { font-size: 12px; padding: 4px 8px; }
```

E2 — 在 `changeTeam` 函数定义后插入（首次渲染前应用回 PLAYERS）：

```js
const NAMES_KEY = LSKEY + "_names";
// 页内改真名覆盖：{ tag: name }；清空真名=写空串不删键（读回合并写会复活删键，
// saveClState 前科），加载时空串视为无真名
let nameOvr = {};
try { nameOvr = JSON.parse(localStorage.getItem(NAMES_KEY) || "{}"); }
catch (e) { nameOvr = {}; }
for (const p of PLAYERS) {
  if (nameOvr[p.tag] !== undefined) p.name = nameOvr[p.tag];
}
function saveNames() {
  // 读回再合并写，防多开页面互踩（沿用 save() 模式）
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(NAMES_KEY) || "{}"); }
  catch (e) { stored = {}; }
  nameOvr = Object.assign(stored, nameOvr);
  localStorage.setItem(NAMES_KEY, JSON.stringify(nameOvr));
}
function renamePlayer(tag) {
  // 只改真名不改标签（tag 是归属键，级联风险）；三态：非空=改 / 空串=清 / 取消=不动；
  // 四处按钮文字（队伍区主行/兜底行/簇区/弹条）都读 p.name，改内存值 show 即全刷
  const p = PLAYERS.find(x => x.tag === tag);
  if (!p) return;
  const v = prompt("真名（空=清除）", p.name);
  if (v === null) return;
  p.name = v.trim();
  nameOvr[tag] = p.name;
  saveNames();
  show(cur);
}
```

E3 — renderPlayers 队伍主行循环，`div.appendChild(b);` 之后插入（**不动** `b.textContent`/`b.className = teamClass(p.team)` 原行——有子串断言锁定）：

```js
      const rn = document.createElement("button");
      rn.textContent = "改名";
      rn.className = "nav renamebtn";
      rn.title = "改真名（不改标签）";
      rn.onclick = () => renamePlayer(p.tag);
      div.appendChild(rn);
```

E4 — renderPlayers 兜底行（"其他"行）循环，`div.appendChild(b);` 之后插入同 E3 的 6 行（变量名相同，各循环作用域独立）。

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py -q
```

Expected: 全绿

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页页内改真名——队伍区改名钮，_names 键持久，导出跟随"
```

---

### Task 4: 按人核对（_review 键 + 可见集抽象）

**Files:**
- Modify: `scripts/gen_scorer_page.py`（HTML 一处、CSS 一处、renamePlayer 后插入核对状态块、show/assign/skip/freeAssign/jumpUnassigned/renderPlayers/keydown/启动段改写）
- Test: `tests/test_gen_scorer_page.py`（末尾追加）

**Interfaces:**
- Consumes: Task 1 的第三步 stepbar（reviewbar 插在其后）、Task 3 的 renamePlayer（核对状态块插在其后）
- Produces: `function visible()`（可见集，cur 索引作用于它）、`function reviewTarget(tag)`、`function renderReviewBar()`、`function posKey()`、`REVIEW_KEY = LSKEY + "_review"`；特殊值 `"__none__"`=未归属

- [ ] **Step 1: 写失败测试**

```python
class TestBuildHtmlReviewByPlayer:
    """按人核对（docs/scorer-three-step/spec.md）：_review 键 + 可见集过滤 + 位置分键。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_review_state_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert '"_review"' in html
        assert "function reviewTarget(" in html
        assert "function visible(" in html
        assert "function renderReviewBar(" in html
        assert "function posKey(" in html

    def test_review_bar_and_special_value(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "核对对象" in html
        assert "__none__" in html
        assert 'id="reviewbar"' in html

    def test_free_input_rejects_none_sentinel(self) -> None:
        # Arrange / Act：自由输入拒绝 __none__（防撞未归属特殊值）
        html = self._html()
        # Assert
        assert 'tag === "__none__"' in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlReviewByPlayer -q
```

Expected: FAIL

- [ ] **Step 3: 实现模板改动**

E1 — HTML：第三步 stepbar（Task 1 E4 产物）之后、`<img id="crop" ...>` 之前插入：

```html
<div id="reviewbar"></div>
```

E2 — CSS（`.renamebtn` 后即可）：

```css
#reviewbar { margin: 4px 0; }
#reviewbar button { font-size: 14px; padding: 6px 10px; }
```

E3 — 在 `renamePlayer` 函数后插入核对状态块：

```js
const REVIEW_KEY = LSKEY + "_review";
// 按人核对：{ target: "" }；""=全部（切回全部=写空串不删键，理由同 names 键），
// "__none__"=未归属，其余=球员 tag（含名单外自由输入 tag，无 name 纯显示 tag）
let review = { target: "" };
try {
  const rawR = JSON.parse(localStorage.getItem(REVIEW_KEY) || "{}");
  if (rawR && typeof rawR === "object" && typeof rawR.target === "string") {
    review.target = rawR.target;
  }
} catch (e) { review = { target: "" }; }
function saveReview() {
  // 读回再合并写（沿用 save() 模式）
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(REVIEW_KEY) || "{}"); }
  catch (e) { stored = {}; }
  review = Object.assign(stored, review);
  localStorage.setItem(REVIEW_KEY, JSON.stringify(review));
}
function reviewTargets() {
  // 核对对象候选 = 当前 marks 里有归属球的 tag（按 ITEMS 序去重；含名单外 tag）
  const seen = [];
  for (const it of ITEMS) {
    const t = marks[it.key];
    if (t && !seen.includes(t)) seen.push(t);
  }
  return seen;
}
function visible() {
  // 可见集 = 按核对对象过滤的 ITEMS 子集；ITEMS 本体不动（spec 边界）
  if (review.target === "") return ITEMS;
  if (review.target === "__none__") return ITEMS.filter(it => !marks[it.key]);
  return ITEMS.filter(it => marks[it.key] === review.target);
}
function posKey() {
  // 位置按核对对象分键（不同对象下同索引指向不同球，不分键会错位）；
  // 全部沿用旧 _pos 键兼容存量
  return review.target === "" ? POSKEY
    : POSKEY + "_" + encodeURIComponent(review.target);
}
function reviewTarget(tag) {
  // 切核对对象：持久 + 定位（有位置记录回记录；无则按人=第一个球，
  // 全部/未归属=第一个未归属球）；集空交给 show 的空态分支回退全部
  review.target = tag;
  saveReview();
  const vis = visible();
  let start = parseInt(localStorage.getItem(posKey()) || "-1", 10);
  if (isNaN(start) || start < 0 || start >= vis.length) {
    start = (tag !== "" && tag !== "__none__")
      ? 0 : vis.findIndex(it => !marks[it.key]);
  }
  show(start >= 0 ? start : 0);
}
function renderReviewBar() {
  // 核对对象行：全部 / 各已归属球员（marks 里有球才列）/ 未归属；选中态 sel 高亮
  const bar = document.getElementById("reviewbar");
  bar.innerHTML = "";
  const lab = document.createElement("span");
  lab.textContent = "核对对象：";
  lab.className = "teamlabel";
  bar.appendChild(lab);
  const mk = (text, target) => {
    const b = document.createElement("button");
    b.textContent = text;
    b.className = "nav";
    if (review.target === target) b.classList.add("sel");
    b.onclick = () => reviewTarget(target);
    bar.appendChild(b);
  };
  mk("全部", "");
  for (const t of reviewTargets()) {
    const p = PLAYERS.find(x => x.tag === t);
    mk(t + (p && p.name ? "=" + p.name : ""), t);
  }
  mk("未归属", "__none__");
}
```

E4 — `show(i)` 整体替换为（要点：cur/进度/位置读写全部作用于可见集；空可见集 → 提示并自动切回全部，不得早退停在旧画面）：

```js
function show(i) {
  let vis = visible();
  let flash = "";
  if (!vis.length && review.target !== "") {
    // 空可见集（改归离集/持久 target 失效）→ 提示并自动切回全部（spec 空态契约；
    // 不得像旧版 !ITEMS.length 早退那样停在旧画面）
    flash = review.target === "__none__" ? "未归属清零，已切回全部 | "
      : "此人核对完毕，已切回全部 | ";
    review.target = "";
    saveReview();
    vis = visible();
  }
  if (!vis.length) return; // ITEMS 本身为空（无球）：旧行为不变
  cur = Math.max(0, Math.min(i, vis.length - 1));
  const it = vis[cur];
  const img = document.getElementById("crop");
  if (it.crop) { img.src = it.crop; img.style.display = "inline-block"; }
  else { img.removeAttribute("src"); img.style.display = "none"; }
  const v = document.getElementById("v");
  if (it.clip) { v.src = it.clip; v.style.display = "inline-block"; v.play().catch(() => {}); }
  else { v.pause(); v.removeAttribute("src"); v.load(); v.style.display = "none"; }
  localStorage.setItem(posKey(), String(cur));
  let info = flash + `第 ${cur + 1}/${vis.length} 个`;
  if (review.target !== "") {
    // 进度行带核对对象后缀（有真名则 tag=真名）；全部模式不带
    const rp = PLAYERS.find(x => x.tag === review.target);
    info += "（核对：" + (review.target === "__none__" ? "未归属"
      : review.target + (rp && rp.name ? "=" + rp.name : "")) + "）";
  }
  info += ` | 已归属 ${nDone()}/${ITEMS.length} | ${it.file} t=${it.anchor_time}s`;
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
  renderReviewBar();
}
```

E5 — renderPlayers 开头（`box.innerHTML = "";` 之后）加可见集当前键，两处 sel 高亮改读它：

```js
  const vis = visible(); // sel 高亮读可见集当前项（按人核对时 ITEMS[cur] 不是当前球）
  const curKey = vis.length && cur < vis.length ? vis[cur].key : null;
```

两处 `if (ITEMS.length && marks[ITEMS[cur].key] === p.tag) b.classList.add("sel");` 都改为：

```js
      if (curKey && marks[curKey] === p.tag) b.classList.add("sel");
```

E6 — `assign(tag)` 整体替换（全部模式=现状；按人/未归属模式=离集落原索引）：

```js
function assign(tag) {
  const vis = visible();
  if (!vis.length) return;
  marks[vis[cur].key] = tag;
  touched[vis[cur].key] = true;
  save();
  if (review.target !== "") {
    // 按人/未归属模式：改归后球离集，落原索引位置的新当前项（[i] 即下一个），到尾停末尾
    show(cur);
    return;
  }
  // 全部模式 = 现状：跳下一个未归属球（全局 findIndex）
  let nxt = vis.findIndex((x, idx) => idx > cur && !marks[x.key]);
  if (nxt < 0) nxt = vis.findIndex(x => !marks[x.key]);
  show(nxt >= 0 ? nxt : cur);
}
```

E7 — `skip()` 整体替换：

```js
function skip() {
  const vis = visible();
  if (!vis.length) return;
  let nxt = vis.findIndex((x, idx) => idx > cur && !marks[x.key]);
  if (nxt < 0) nxt = (cur + 1) % vis.length;
  show(nxt);
}
```

E8 — `freeAssign()` 整体替换（拒 `__none__` 一行守卫）：

```js
function freeAssign() {
  const inp = document.getElementById("free");
  const tag = inp.value.trim();
  if (!tag) return;
  if (tag === "__none__") { inp.value = ""; return; } // 保留特殊值，防撞未归属集语义
  inp.value = "";
  assign(tag);
}
```

E9 — `jumpUnassigned()` 整体替换（与核对对象行"未归属"同一口径）：

```js
function jumpUnassigned() {
  // 跳到未归属 = 切到未归属核对对象（spec 手工清单：两者一致）
  reviewTarget("__none__");
}
```

E10 — keydown 的 E 键分支，把：

```js
  else if (k === "e" && ITEMS.length && ITEMS[cur].prefill_tag) assign(ITEMS[cur].prefill_tag);
```

改为（`'"e"'` 子串断言保留在此行）：

```js
  else if (k === "e") {
    const vis = visible();
    if (vis.length && cur < vis.length && vis[cur].prefill_tag) assign(vis[cur].prefill_tag);
  }
```

E11 — 启动段（文件尾部），把：

```js
// 启动：优先回到上次位置；无记录则跳到第一个未归属球
let start = parseInt(localStorage.getItem(POSKEY) || "-1", 10);
if (isNaN(start) || start < 0 || start >= ITEMS.length) {
  start = ITEMS.findIndex(it => !marks[it.key]);
}
show(start >= 0 ? start : 0);
```

改为：

```js
// 启动：恢复核对对象（其集无球时 show 空态分支自动回退全部）→ 读该对象的位置键；
// 无记录则：全部/未归属=第一个未归属球，按人=第一个球
const vis0 = visible();
let start = parseInt(localStorage.getItem(posKey()) || "-1", 10);
if (isNaN(start) || start < 0 || start >= vis0.length) {
  start = (review.target !== "" && review.target !== "__none__")
    ? 0 : vis0.findIndex(it => !marks[it.key]);
}
show(start >= 0 ? start : 0);
```

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py -q
```

Expected: 全绿（含既有全部断言与 node --check）

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页按人核对——_review 键/可见集过滤/位置分键/空态回退全部"
```

---

### Task 5: 逐球区定高不定宽布局 + 悬停放大

**Files:**
- Modify: `scripts/gen_scorer_page.py`（CSS `#crop`/`video` 规则替换 + 样式表末尾加 hover 浮层；HTML crop/video 包进 `#review`）
- Test: `tests/test_gen_scorer_page.py`（末尾追加）

**Interfaces:**
- Consumes: Task 4 之后的 HTML 结构（reviewbar 已插在 crop 前）
- Produces: `#review` flex 容器；`#review #crop:hover` / `.cluster-row img.rep:hover` 浮层规则

- [ ] **Step 1: 写失败测试**

```python
class TestBuildHtmlReviewLayout:
    """逐球区布局（docs/scorer-three-step/spec.md）：#review flex 定高不定宽 + 悬停放大浮层。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_review_flex_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert 'id="review"' in html
        assert "align-items: flex-start" in html
        assert "68vh" in html

    def test_hover_zoom_present(self) -> None:
        # Arrange / Act：悬停浮层规则须在（点击放大已证伪）
        html = self._html()
        # Assert
        assert "#review #crop:hover" in html
        assert "img.rep:hover" in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlReviewLayout -q
```

Expected: FAIL

- [ ] **Step 3: 实现模板改动（3 处）**

E1 — CSS 替换，把：

```css
#crop { max-width: 44vw; max-height: 68vh; background: #000; }
video { max-width: 48vw; max-height: 68vh; background: #000; }
```

改为：

```css
/* 逐球区：图/视频定高不定宽顶端对齐（68vh 等高、翻球不跳、无黑边——
   固定框留边方案有黑边已证伪，docs/scorer-three-step/spec.md Objective 第 5 条） */
#review { display: flex; align-items: flex-start; gap: 8px; }
#review #crop { height: 68vh; width: auto; background: #000; }
#review video { height: 68vh; width: auto; background: #000; }
```

E2 — CSS 在 `</style>` 前（**样式表末尾**，压平级 tie 靠源码序）插入：

```css
/* 悬停放大浮层：置于样式表末尾——#review #crop:hover 特异度压过 #review #crop；
   .cluster-row img.rep:hover 与 .cluster-row.collapsed img.rep 同特异度靠后写胜出
   （点击放大已证伪；移开即收回） */
#review #crop:hover, .cluster-row img.rep:hover {
  position: fixed; z-index: 99; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  height: 92vh; width: auto; max-width: 96vw; max-height: 96vh;
  outline: 3px solid #fc3; background: #000;
}
```

E3 — HTML，把：

```html
<img id="crop" alt="投篮者裁图">
<video id="v" autoplay loop muted playsinline></video>
```

改为：

```html
<div id="review">
<img id="crop" alt="投篮者裁图">
<video id="v" autoplay loop muted playsinline></video>
</div>
```

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py -q
```

Expected: 全绿

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页逐球区定高不定宽并排布局 + 裁图/簇图悬停放大"
```

---

### Task 6: 实数据重生成 + 使用手册 + 终审收尾

**Files:**
- Run: `work/20260805_车百鼎/`（只读输入，页面重生成到 scorers_b1/ scorers_b2/）
- Modify: `使用手册.html`（认人节改三步流程描述）、`docs/scorer-three-step/todo.md`
- Create: `docs/scorer-three-step/review02.md`（终审报告）

- [ ] **Step 1: 全量质量门**

```bash
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py
```

Expected: 全绿（506+ passed）

- [ ] **Step 2: 重生成 b1/b2 正式页面 + 刷新 demo 副本**

```bash
python scripts/gen_scorer_page.py \
  --scorers work/20260805_车百鼎/scorers_b1/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch1.json \
  --clusters work/20260805_车百鼎/scorers_b1/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch1/events_index.json

python scripts/gen_scorer_page.py \
  --scorers work/20260805_车百鼎/scorers_b2/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch2.json \
  --clusters work/20260805_车百鼎/scorers_b2/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch2/events_index.json

cp work/20260805_车百鼎/scorers_b1/scorer.html work/20260805_车百鼎/scorers_b1/scorer_demo.html
```

Expected: 两条命令退出码 0；grep 验证新页含 `function deleteCluster(`、`function reviewTarget(`、`id="review"`；demo 副本同步为新模板（旧手工补丁版被覆盖，删簇 hack 由正式功能取代）

- [ ] **Step 3: 手工验证清单交付立哥**（spec Testing Strategy 全量）：

  - [ ] 三步标题条显示；无 --clusters 页面同现状
  - [ ] 改名：按钮文字即时变、刷新保持、导出 name 跟随、清空回退
  - [ ] 按人核对：选人只显示其球；改归别人后球消失并前进；核对完提示并切回全部
  - [ ] 未归属集与"跳到未归属"一致；切回全部恢复现状行为
  - [ ] 删簇：confirm 取消不动；确认后组消失、刷新仍隐藏；组内球逐球区还在、marks/touched 未动；删簇6（酒瓶簇）实测
  - [ ] 改名后簇区/弹条按钮文字同步变
  - [ ] 逐球区布局：图/视频顶端对齐同高、无黑边无间隙、翻球不跳；悬停放大好使
  - [ ] 导出 roster.json schema 不变（diff 旧产物仅 name 字段差异）
  - [ ] 边缘态体感：删光所有簇后 step2 标题条+空工具条仍显示（spec 未要求处理，
        看一眼即可）；无未归属球时点"跳到未归属" → 提示"未归属清零"并切回全部落第 0 球

- [ ] **Step 4: 使用手册.html 认人节改写为三步流程**

要点：第一步判队伍（拖队员改队、改名钮填真名）；第二步并簇认人（拖拽合并/点队员名应用到整组/误分组点"删除"——注明**找回=浏览器清站点数据后重开页面**）；第三步逐球核对（核对对象行选全部/某球员/未归属，判错点正确球员改归；裁图与视频并排同高，悬停放大看细节）。改完必须过 spec-reviewer（Task 工具，subagent_type=plan 扮演）再放行。

- [ ] **Step 5: todo.md 勾完 + 终审（code-reviewer 子代理）**

终审要点：对照 spec 数据契约逐条核实现（重点：clState 只增 deleted 子键、marks/touched/ITEMS 本体不动、改名不动 b.textContent/teamClass 原行、visible() 过滤不改 ITEMS）；报告存 `docs/scorer-three-step/review02.md`。

- [ ] **Step 6: 文档提交**

```bash
git add 使用手册.html docs/scorer-three-step/todo.md docs/scorer-three-step/review02.md
git commit -m "docs: 使用手册认人节改三步流程 + 三步流程终审存档"
```

---

## Self-Review 记录

- spec 覆盖：三步标题条→Task 1；删簇→Task 2；改名→Task 3；按人核对→Task 4；
  定高布局+悬停放大→Task 5；手工清单/手册/四件套/质量门→Task 6。无遗漏。
- 既有断言保护：E 键 `'"e"'` 子串保留（Task 4 E10）；`b.textContent`/`teamClass`
  原行不动（Task 3 E3/E4 明确）；`if (!ITEMS.length) return;` 语义由
  `if (!vis.length) return;` 在 ITEMS 空时等价承接。
- 类型/命名一致：visible()/reviewTarget()/renderReviewBar()/posKey()/
  deleteCluster()/renamePlayer()/saveNames() 全文一致；`review.target` 三态
  （""/"__none__"/tag）在 spec、plan、断言间一致。
- 已证伪不碰：点击放大、固定框留边布局、del 清单扩展 deleted（墓碑只加不减）。
