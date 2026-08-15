# 认人页簇区点选合并 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 簇行加点选合并（"合并"→"并入这里"两次点击），与拖拽并存；spec = `docs/scorer-click-merge/spec.md`（唯一契约）。

**Architecture:** 零 Python 逻辑变更，只改 `scripts/gen_scorer_page.py` 的 `_HTML` 模板；瞬态 `mergeSrc` 变量，无新存储键；合并语义零改动（复用 mergeInto）。

**Tech Stack:** 纯前端模板字符串；pytest 模板断言 + node --check。

## Global Constraints

- 提交信息中文 conventional；只 commit 不 push；git add 点名文件（**有并行会话在同 repo 工作**，严禁 `git add -A`/`.`）
- 质量门（每次代码提交前）：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py` 全绿
- mergeInto 零改动；拖拽路径（`row.draggable`/`text/plain`/drop 守卫）零改动
- 既有断言标识符不得破坏（`function mergeInto(`、`row.draggable = true`、`PICKER-HOOK`、`function deleteCluster(`、`function reviewTarget(` 等）
- mergeSrc 不持久化；无新 localStorage 键、无新 CLI 参数、无新依赖

---

### Task 1: 点选合并（pickMerge + 行尾钮 + 高亮 + Esc）

**Files:**
- Modify: `scripts/gen_scorer_page.py`（_HTML 模板：CSS 一处、collapseAll 声明后一处、renderClusters 两处、keydown 一处）
- Test: `tests/test_gen_scorer_page.py`（末尾追加新 class）

**Interfaces:**
- Consumes: `mergeInto(srcGid, dstGid)`、`computeGroups()`、`show(cur)`、keydown 既有 Esc 分支（Task 1-5 已合入的模板现状）
- Produces: `let mergeSrc`、`function pickMerge(gid)`、CSS `.cluster-row.merge-src`

- [ ] **Step 1: 写失败测试**

`tests/test_gen_scorer_page.py` 末尾追加：

```python
class TestBuildHtmlClickMerge:
    """点选合并（docs/scorer-click-merge/spec.md）：与拖拽并存，复用 mergeInto 语义。"""

    def _html(self) -> str:
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)

    def test_click_merge_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "function pickMerge(" in html
        assert "let mergeSrc = null" in html
        assert "并入这里" in html
        assert "merge-src" in html

    def test_drag_merge_untouched(self) -> None:
        # Arrange / Act：拖拽路径标识符原样保留（两套并存）
        html = self._html()
        # Assert
        assert "row.draggable = true" in html
        assert "text/plain" in html
        assert "function mergeInto(" in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
export PYTHONIOENCODING=utf-8 && python -m pytest tests/test_gen_scorer_page.py::TestBuildHtmlClickMerge -q
```

Expected: FAIL（`function pickMerge(` 断言不成立）

- [ ] **Step 3: 实现模板改动（5 处）**

E1 — CSS：在 `.cluster-row.drop-target { outline: 3px dashed #fc3; }` 规则后插入：

```css
.cluster-row.merge-src { outline: 3px solid #fc3; }
```

E2 — JS：在 `let collapseAll = null;` 声明块之后插入：

```js
let mergeSrc = null; // 点选合并：非 null = 该 gid 组已被点为源（瞬态，刷新即清；
                     // 与拖拽并存，合并语义复用 mergeInto）
```

E3 — renderClusters：`for (const g of computeGroups()) {` 之前，把单独一句循环改为先取组列表 + 残态守卫：

旧代码：

```js
  for (const g of computeGroups()) {
```

新代码：

```js
  const groups = computeGroups();
  // 点选合并残态守卫：源组被并走/被删/被拆开后不在可见组里即清态
  // （mergeInto/splitGroup/deleteCluster 都经 show→renderClusters，此处一处全覆盖）
  if (mergeSrc !== null && !groups.some(g => g.gid === mergeSrc)) mergeSrc = null;
  for (const g of groups) {
```

E4 — renderClusters 组行内，删除钮块（`row.appendChild(del);`）之后插入：

```js
    const mg = document.createElement("button");
    mg.textContent = mergeSrc === null ? "合并"
      : (mergeSrc === g.gid ? "取消" : "并入这里");
    mg.className = "nav";
    mg.title = "点选合并：先点源行，再点目标行（拖拽也行）";
    mg.onclick = () => pickMerge(g.gid);
    row.appendChild(mg);
    if (mergeSrc === g.gid) row.classList.add("merge-src");
```

E5 — 在 `mergeInto` 函数定义后插入 pickMerge：

```js
function pickMerge(gid) {
  // 点选合并：未选源→记源；点源行→取消；点目标行→并入（先清态再合并，
  // mergeInto 内部 show 重渲染，避免残态参与渲染）
  if (mergeSrc === null) { mergeSrc = gid; show(cur); return; }
  if (mergeSrc === gid) { mergeSrc = null; show(cur); return; }
  const src = mergeSrc;
  mergeSrc = null;
  mergeInto(src, gid);
}
```

E6 — keydown：picker Esc 分支（`if (pickerGid !== null) { ... }` 整块）之后插入：

```js
  if (ev.key === "Escape" && pickerGid === null && mergeSrc !== null) {
    // 点选合并 Esc 取消（弹条开着时 Esc 优先只关弹条，再按一次才清点选态——
    // 避免一次按键双清两态；不屏蔽数字键/E，点选态不影响逐球归属）
    mergeSrc = null;
    show(cur);
    return;
  }
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
git commit -m "feat: 认人页簇区点选合并——两次点击与距离无关，与拖拽并存"
```

---

### Task 2: 实数据重生成 + 使用手册 + 终审收尾

**Files:**
- Run: `work/20260805_车百鼎/`（只读输入，页面重生成到 scorers_b1/ scorers_b2/）
- Modify: `使用手册.html`（第二步补一句点选合并）、`docs/scorer-click-merge/todo.md`
- Create: `docs/scorer-click-merge/review01.md`（任务级+终审合并存档）

- [ ] **Step 1: 全量质量门**

```bash
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q --deselect tests/test_release_probe.py
```

Expected: 全绿

- [ ] **Step 2: 重生成 b1/b2 + demo 副本**（命令同 docs/scorer-three-step/plan.md Task 6 Step 2，逐字照用），grep 验证新页含 `function pickMerge(`

- [ ] **Step 3: 使用手册.html 第二步那条（约 118 行"第二步：并簇认人"）补一句**：
  "簇多拖不动时改用点选：点源行的 <b>合并</b>（行变黄框），再点目标行的 <b>并入这里</b>；再点源行或按 <kbd>Esc</kbd> 取消。"
  改完过 spec-reviewer（Task 工具，subagent_type=plan 扮演）。

- [ ] **Step 4: 手工验证清单交付立哥**（spec Testing Strategy 5 条，含 b2 长列表末行并首行实测）

- [ ] **Step 5: todo.md 勾完 + 终审报告 review01.md + Commit**

```bash
git add 使用手册.html docs/scorer-click-merge/todo.md docs/scorer-click-merge/review01.md
git commit -m "docs: 使用手册补点选合并 + 点选合并终审存档"
```

---

## Self-Review 记录

- spec 覆盖：点选三态钮/高亮/Esc/残态守卫/拖拽并存→Task 1；手册/清单/终审→Task 2。无遗漏。
- 锚点已对照当前模板（Task 1-5 合入后）：`.cluster-row.drop-target` 规则、`let collapseAll = null;` 块、`for (const g of computeGroups()) {`、`row.appendChild(del);`、mergeInto 函数尾、picker Esc 分支——均在。
- 命名一致：mergeSrc/pickMerge/merge-src/并入这里 全文一致。
- 已证伪不碰：不给 mergeSrc 做持久化（spec Never）。
