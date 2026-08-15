# 认人页"不算进球"标签 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 确认页加"不算进球"标签（按钮+N 键），导出 roster 自动剔除；spec = `docs/scorer-nogoal-tag/spec.md`（唯一契约）。

**Architecture:** 零 Python 逻辑变更，只改 `scripts/gen_scorer_page.py` 的 `_HTML` 模板；哨兵标签走既有 marks/touched 键，仅 exportRoster 两处过滤。

**Tech Stack:** 纯前端模板字符串；pytest 模板断言 + node --check。

## Global Constraints

- 提交信息中文 conventional；只 commit 不 push；git add 点名文件（**有并行会话在同 repo 工作**，严禁 `git add -A`/`.`）
- 质量门（每次代码提交前）：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py` 全绿
- 哨兵特殊分支只允许出现在 exportRoster（assignments 过滤 + alert 报数）；其余行为全部继承普通标签，不得加特例
- 不改 confirmed 条件、touched 规则、roster schema；不动 goals.json / build_highlight / roster.py
- 既有断言标识符不得破坏（`id="skip"`、`"s"`、`function assign(`、`k === "e"` 等）

---

### Task 1: 不算进球标签（按钮 + N 键 + 导出剔除）

**Files:**
- Modify: `scripts/gen_scorer_page.py`（_HTML 模板：CSS 一处、HTML 一处、JS 三处）
- Test: `tests/test_gen_scorer_page.py`（末尾追加新 class）

**Interfaces:**
- Consumes: `assign(tag)`（前进/touched/过滤集离集语义全继承）、`exportRoster()`、keydown 既有分支结构（当前模板已含三步流程全部功能）
- Produces: `const NOGOAL = "不算进球"`、`#nogoal` 按钮、keydown `k === "n"` 分支

- [ ] **Step 1: 写失败测试**

`tests/test_gen_scorer_page.py` 末尾追加：

```python
class TestBuildHtmlNoGoalTag:
    """不算进球标签（docs/scorer-nogoal-tag/spec.md）：页面剔除假进球，导出自动过滤。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_nogoal_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert 'const NOGOAL = "不算进球"' in html
        assert 'id="nogoal"' in html
        assert 'k === "n"' in html

    def test_export_strips_nogoal(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert：assignments 收集过滤哨兵 + alert 报剔除数
        assert "t !== NOGOAL" in html
        assert "已剔除不参与合成" in html

    def test_picker_shields_n_key(self) -> None:
        # Arrange / Act：弹条期间 N 与 1-9/E 同屏蔽（防误触静默剔除当前球）
        html = self._html()
        # Assert
        assert '|| k === "n") return;' in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlNoGoalTag -q
```

Expected: FAIL（`const NOGOAL` 断言不成立）

- [ ] **Step 3: 实现模板改动（7 处，E1-E7）**

E1 — CSS：在 `#skip { background: #7a5c00; color: #fff; }` 规则后插入：

```css
#nogoal { background: #7a2c2c; color: #fff; }
```

E2 — HTML：`<button id="skip">跳过 (S)</button>` 之后插入：

```html
  <button id="nogoal">不算进球 (N)</button>
```

E3 — JS：在 `const TOUCHKEY = LSKEY + "_touched";` 行后插入：

```js
// 不算进球哨兵标签：假进球/犯规不算的球归到这里——只在页面内流转，
// 导出 roster 时剔除（assignments/players 都不含），不挡 confirmed；可逆（改归球员即恢复）
const NOGOAL = "不算进球";
```

E4 — JS：事件绑定区，`document.getElementById("skip").onclick = skip;` 行后插入：

```js
document.getElementById("nogoal").onclick = () => assign(NOGOAL);
```

E5 — JS：keydown 两处。① `else if (k === "s") skip();` 分支后插入：

```js
  else if (k === "n") assign(NOGOAL);
```

② 弹条屏蔽名单加 N（与 1-9/E 同理由：防弹条期间误触逐球归属——N 更危险，
误按会把当前球静默剔除），把：

```js
    if ((k >= "1" && k <= "9") || k === "e") return;
```

改为：

```js
    if ((k >= "1" && k <= "9") || k === "e" || k === "n") return;
```

E6 — JS：exportRoster 内两处。① assignments 收集，把：

```js
  for (const [k, t] of Object.entries(marks)) { if (t) assignments[k] = t; }
```

改为：

```js
  // 不算进球哨兵剔除：不进 assignments（players 自动补录循环读本对象，哨兵随之不进名单）
  for (const [k, t] of Object.entries(marks)) { if (t && t !== NOGOAL) assignments[k] = t; }
```

② alert 文案，把：

```js
  alert("已下载 roster.json（归属 " + Object.keys(assignments).length +
        "/" + ITEMS.length + "，confirmed=" + confirmed +
        (nUn ? "，还有 " + nUn + " 个非 SKIP 球未归属" : "") + "），移到 work 场次目录即可");
```

改为（nNo 数全量 marks 的哨兵球——同 session 跨批次共享 localStorage，
只数本页 ITEMS 会漏报其他批次的剔除球）：

```js
  const nNo = Object.values(marks).filter(t => t === NOGOAL).length;
  alert("已下载 roster.json（归属 " + Object.keys(assignments).length +
        "/" + ITEMS.length + "，confirmed=" + confirmed +
        (nNo ? "，不算进球 " + nNo + " 球（已剔除不参与合成）" : "") +
        (nUn ? "，还有 " + nUn + " 个非 SKIP 球未归属" : "") + "），移到 work 场次目录即可");
```

E7 — HTML 按键提示行，把：

```html
  <br><small>按键：1-9=选球员 E=采用号码预填 S=跳过 ←/→=翻页；SKIP 球标"无法定位"可手选</small>
```

改为：

```html
  <br><small>按键：1-9=选球员 E=采用号码预填 S=跳过 N=不算进球 ←/→=翻页；SKIP 球标"无法定位"可手选</small>
```

- [ ] **Step 4: 跑测试确认通过**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py -q
```

Expected: 全绿（含既有断言与 node --check）

- [ ] **Step 5: Commit**

```bash
python -m ruff format scripts tests && python -m ruff check --fix scripts tests
git add scripts/gen_scorer_page.py tests/test_gen_scorer_page.py
git commit -m "feat: 认人页不算进球标签——N 键/按钮打标，导出 roster 自动剔除"
```

---

### Task 2: 实数据重生成 + 使用手册 + 终审收尾

**Files:**
- Run: `work/20260805_车百鼎/`（只读输入，页面重生成到 scorers_b1/b2/b3）
- Modify: `使用手册.html`（第三步补一句）、`docs/scorer-nogoal-tag/todo.md`
- Create: `docs/scorer-nogoal-tag/review01.md`

- [ ] **Step 1: 全量质量门**（命令见 Global Constraints）

Expected: 全绿

- [ ] **Step 2: 重生成 b1/b2/b3 + demo 副本**

b1/b2 命令逐字照用 docs/scorer-three-step/plan.md Task 6 Step 2；b3 类推
（`--scorers work/20260805_车百鼎/scorers_b3/scorer_candidates.json --goals work/20260805_车百鼎/goals_batch3.json --clusters work/20260805_车百鼎/scorers_b3/scorer_clusters.json --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json --index work/20260805_车百鼎/review_batch3/events_index.json`——先 `ls` 确认 scorers_b3 与 review_batch3 文件名再跑）。
grep 验证新页含 `id="nogoal"`。

注意：**roster-existing 改用 `work/20260805_车百鼎/roster.json`**（立哥 20:42
导出的最新全量；旧 `roster_20260805_车百鼎.json` 是历史产物）。若 roster.json
不存在再回退旧文件。

- [ ] **Step 3: 使用手册.html 第三步那条（约 121 行）补一句**：
  "不是进球的（误判/犯规不算）：点 <b>不算进球</b> 或按 <kbd>N</kbd>——导出时自动剔除不进合集；打错了在核对对象里选 <b>不算进球</b> 找回来改归。"
  改完过 spec-reviewer（Task 工具，subagent_type=plan 扮演）。

- [ ] **Step 4: 手工验证清单交付立哥**（spec Testing Strategy 5 条，含 build 实测）

- [ ] **Step 5: todo.md 勾完 + 终审报告 review01.md + Commit**

```bash
git add 使用手册.html docs/scorer-nogoal-tag/todo.md docs/scorer-nogoal-tag/review01.md
git commit -m "docs: 使用手册补不算进球标签 + 审查存档"
```

---

## Self-Review 记录

- spec 覆盖：按钮/N 键/导出剔除/alert 报数→Task 1；重生成/手册/终审→Task 2。无遗漏。
- 锚点已对照当前模板（三步流程+点选合并合入后）：`#skip` CSS 与 HTML 按钮行、
  `TOUCHKEY` 声明行、事件绑定区、`k === "s"` 分支、exportRoster 两处旧代码——均在且唯一。
- 哨兵零特殊分支原则：assign/renderReviewBar/reviewTargets/进度行/簇标签全继承；
  仅 exportRoster 两处过滤（E6），与 spec Boundaries 一致。
- confirmed 条件 `marks[it.key]` 非空即过，哨兵值满足——零改动成立。
