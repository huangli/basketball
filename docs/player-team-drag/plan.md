# 队员拖拽改队 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。Steps 用 checkbox 跟踪。

**Goal:** 认人页顶部名单区队员按钮可拖拽到队伍行改队别，导出 roster 带新队别。

**Architecture:** 全部改动在 `scripts/gen_scorer_page.py` 的 `_HTML` 模板（CSS/JS）。新 localStorage 键 `scorer_<session>_teamovr`（tag→team 平铺对象），加载时应用回 PLAYERS；改队直接写 PLAYERS 内存值，导出零改动自动跟随。

**Tech Stack:** Python 3.14 模板内嵌原生 JS（HTML5 DnD + localStorage），零新依赖；测试 = pytest 模板断言 + node --check 既有模式。

## Global Constraints

- 遵守 rules.md；质量门：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q`
- 中文 conventional 提交，只 commit 不 push；git add 点名文件（仓库有并行会话）
- 不改 roster.json schema；不改 marks/归属语义；单击选人语义不变
- 簇区选人按钮、合并弹条按钮**不**加 draggable
- "其他"兜底行不是放置目标
- 保留既有断言标识符：`clusterAssign`/`cluster-row`/`const CLUSTERS = [];`/`id="clusters"`/PICKER-HOOK/`const OPP`/teamClass
- spec：docs/player-team-drag/spec.md（契约以此为准）

---

### Task 1: 名单区队员拖拽改队

**Files:**
- Modify: `scripts/gen_scorer_page.py`（_HTML 模板：CSS、变量声明区、renderPlayers、新增函数）
- Test: `tests/test_gen_scorer_page.py`（TestBuildHtmlClusterMerge 类后加断言用例）

**Interfaces:**
- Consumes: 现有 `PLAYERS`（内联名单）、`OPP`、`teamClass`、save() 读回合并写模式
- Produces: `TEAMOVR_KEY = LSKEY + "_teamovr"`；`teamOvr`（{tag: team}）；`saveTeamOvr()`；`changeTeam(tag, team)`；名单区队伍行 div 带 `data-team` 属性（drop 目标识别）

- [ ] **Step 1: 写失败测试**

tests/test_gen_scorer_page.py 的 TestBuildHtmlClusterMerge 类后新增方法（或新类 TestBuildHtmlTeamDrag）：

```python
class TestBuildHtmlTeamDrag:
    """队员拖拽改队模板断言（docs/player-team-drag/spec.md）。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_team_drag_present(self) -> None:
        html = self._html()
        assert '"_teamovr"' in html
        assert "function changeTeam(" in html
        assert "function saveTeamOvr(" in html
        assert "div.dataset.team" in html
        assert 'b.draggable = true' in html
        assert "text/player-tag" in html
```

（`build_html` 末参为 opp——Task 2 队名会话化后的签名；以实际签名为准。）

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlTeamDrag -x -q`
Expected: FAIL（`_teamovr` 不在模板里）

- [ ] **Step 3: CSS——drop-target 作用域扩到队伍行**

模板 `.cluster-row.drop-target` 规则后加：

```css
.teamrow.drop-target { outline: 3px dashed #fc3; }
```

（renderPlayers 的行 div 加 `className = "teamrow"`，见 Step 5。）

- [ ] **Step 4: 变量声明区（collapseAll 声明后）加**

```js
const TEAMOVR_KEY = LSKEY + "_teamovr";
// 队员改队覆盖：{ tag: team }；改队直接写 PLAYERS 内存值，导出自动跟随
let teamOvr = {};
try { teamOvr = JSON.parse(localStorage.getItem(TEAMOVR_KEY) || "{}"); }
catch (e) { teamOvr = {}; }
for (const p of PLAYERS) {
  if (teamOvr[p.tag] !== undefined) p.team = teamOvr[p.tag];
}
function saveTeamOvr() {
  // 读回再合并写，防多开页面互踩（沿用 save() 模式）
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(TEAMOVR_KEY) || "{}"); }
  catch (e) { stored = {}; }
  teamOvr = Object.assign(stored, teamOvr);
  localStorage.setItem(TEAMOVR_KEY, JSON.stringify(teamOvr));
}
function changeTeam(tag, team) {
  // 拖拽改队：只动队别（分队合集/分行/着色），不碰任何 marks 归属
  const p = PLAYERS.find(x => x.tag === tag);
  if (!p || p.team === team) return; // 原队行 drop = 无操作
  p.team = team;
  teamOvr[tag] = team;
  saveTeamOvr();
  show(cur);
}
```

- [ ] **Step 5: renderPlayers 改造（四处）**

① 已知三行**恒渲染**（删 `if (!row.length) continue;`——空队也渲染行，
否则该队零队员时无处可拖入）；行 div 创建处（两处）后加：

```js
    div.className = "teamrow";
```

② 仅**已知三行**（非兜底行）加 data-team + drop 事件（MIME 隔离版，
放在 ① 后）：

```js
    div.dataset.team = tm;
    div.ondragover = (ev) => {
      // 只响应队员拖拽（text/player-tag）；簇行拖拽（text/plain）不高亮
      if (!ev.dataTransfer.types.includes("text/player-tag")) return;
      ev.preventDefault();
      div.classList.add("drop-target");
    };
    div.ondragleave = () => div.classList.remove("drop-target");
    div.ondrop = (ev) => {
      ev.preventDefault();
      div.classList.remove("drop-target");
      const tag = ev.dataTransfer.getData("text/player-tag");
      if (tag) changeTeam(tag, tm);
    };
```

③ 两处队员按钮创建循环（已知三行与兜底行各一处，`b.className = teamClass(p.team);` 后）加：

```js
      b.draggable = true;
      b.ondragstart = (ev) => {
        // 自定义 MIME：与簇行拖拽的 text/plain 隔离，防跨域误触发
        ev.dataTransfer.setData("text/player-tag", p.tag);
        ev.dataTransfer.effectAllowed = "move";
      };
```

（注意：只改 renderPlayers 内的按钮；renderClusters 与弹条块的按钮不动。）

④ 簇行 dragover/drop 补 MIME 守卫（renderClusters 现有 ondragover/
ondrop 开头各加一行，防队员拖拽触发簇行高亮/误合并）：

```js
      if (!ev.dataTransfer.types.includes("text/plain")) return;
```

- [ ] **Step 6: 跑测试确认通过 + 全量质量门**

Run: `python -m pytest tests/test_gen_scorer_page.py -q` → PASS（含 node --check）；质量门全绿。

- [ ] **Step 7: Commit**

```bash
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页队员拖拽改队——便服队员归队，导出 roster 带新队别"
```

---

### Task 2: 实跑重生成 + 手册 + 收尾

**Files:**
- Run: `work/20260805_车百鼎/`（重生成 b1/b2 页面）
- Modify: `使用手册.html`、`docs/player-team-drag/todo.md`

- [ ] **Step 1: 重生成 b1/b2 认人页**（b2 有 events_index.json，两条都带 --index；
  命令同 docs/session-opponent-name/plan.md Task 3 Step 2）

- [ ] **Step 2: 使用手册.html 认人节补一条**（拖拽合并那条之后）：

```html
<li><b>便服队员可以拖拽归队</b>：把顶部名单里的队员按钮拖到正确的队伍行上松开即改队别（着色和分行跟着变，刷新不丢）；队别影响分队合集，改完导出 roster 就带新队别。注意只拖得动顶部名单区的按钮，簇行里的名字按钮仍是单击选人。</li>
```

- [ ] **Step 3: todo.md 勾完 + 质量门终跑 + Commit**

```bash
git add 使用手册.html docs/player-team-drag/
git commit -m "docs: 手册补队员拖拽改队说明 + 四件套收尾"
```

---

## Self-Review 记录

- spec 覆盖：页面态/交互/导出（Task 1）、手册+重生成（Task 2）——全覆盖
- 占位符：无；标识符跨步骤一致（TEAMOVR_KEY/teamOvr/saveTeamOvr/changeTeam/teamrow/data-team）
- 边界：原队行无操作（changeTeam 早退）、兜底行非目标（②只挂已知三行）、
  簇区/弹条按钮不动（③只改 renderPlayers 两处循环）
