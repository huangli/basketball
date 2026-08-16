# review01：标注页两个 bug 修复 四件套（spec/plan/todo）审查

日期：2026-08-16　审查员：独立规格审查　对象：`docs/label-page-fixes/` spec.md / plan.md / todo.md

## 整体评价

三件套问题定位准确、边界清晰、成功标准可机检，所有行号引用与实证声明经逐条核对均与真实代码/产物一致；未发现阻断问题，建议改进两条。

## 核查记录（行号引用抽查，全部命中）

| 文档声明 | 真实代码 | 结果 |
|---|---|---|
| spec:11-15 sound onclick 在 `gen_label_page.py:282` | :282 `document.getElementById("sound").onclick = () => { v.muted = !v.muted; show(cur); };` | ✓ |
| spec:17-18 show() 在 `:170-196`，重设 src / playbackRate=1 / wide=true | :170-196 函数体，:175 `v.src=`、:178 `v.playbackRate = 1`、:174 `wide = true` | ✓ |
| spec:29-30 LSKEY/POSKEY 在 `:150-151` | :150 `const LSKEY = "label_" + SESSION;` :151 POSKEY 派生 | ✓ |
| spec:31-32 run_session 传同一 `--session session_dir.name` 在 `:454-455` | :454-455 确为 `"--session", session_dir.name`；同段 :458 已按批传 `--batch` | ✓ |
| spec:38 stats() 在 `:164-169`、:41 启动逻辑 `:298-303` | 均命中 | ✓ |
| spec:33-35 三批 label.html 均 `SESSION = "20260805_车百鼎"` | grep 实证 review_batch{1,2,3}/label.html 完全一致 | ✓ |
| spec:43 marks 键 `fid#eN` 各批不重叠 | `gen_review_clips.py:819` `"key": f"{fid}#e{idx}"`；run_session 按 fid 切批 | ✓ |
| spec:85 现有断言 test_build_html_export_has_same_rally_confirm | tests/test_gen_label_page.py:203 存在 | ✓ |
| spec 引用 经验教训 §4 / 主文档 §3.6（欢呼是进球信号） | 经验教训.md §4（:122 标注与审核提效）:125 命中；主文档 §3 第 6 条 :65 命中 | ✓ |

命令可执行性：`node` v24.15.0 在 PATH；ruff/pytest 为 AGENTS.md 既定关口；`build_html(events, session, batch=)` 签名（gen_label_page.py:310）与 spec 成功标准 2 的调用形式一致；现有 node --check 测试（test_gen_label_page.py:66，batch=2 路径）可直接覆盖模板改动。run_session 阶段⑦断点条件（:503-505，label.html 存在且非空即跳）证实「续跑不会自动重生成页面」，spec 风险表的场景界定成立。

## 阻断问题

无。

## 建议改进

1. **plan.md Step 2 测试断言面窄于 spec 成功标准**（plan.md:28-29 vs spec.md:72-74）。spec 要求「POSKEY 随之隔离」，但 plan 的测试只断 LSKEY 含 `_batchK`。模板 :151 `const POSKEY = LSKEY + "_pos";` 是派生行，建议测试加一条断该派生形式不变（如 `assert 'POSKEY = LSKEY + "_pos"' in html`），防止改模板时误伤派生逻辑而测试不报警。修法：plan Step 2 测试项补一条 POSKEY 派生断言。
2. **spec 风险表可补一条实证强化决策依据**（spec.md:82-86 与 :49-55「作废不迁移」）。已实证 `work/20260805_车百鼎/` 下 goals_batch1/2/3.json 全部导出完毕，本次换键对唯一在用场次无存量进度损失，「作废」的实际成本为零。补上这一句可让立哥确认时不必自己查证。修法：风险表首行或旧键口径段末补一句实证。

## 可选优化

1. **plan Step 1 顺手统一按钮初始文案**（plan.md:12-15）。模板 :137 初始文案是「声音开/关」，运行时 show() :193 与修复后 onclick 都是「声音：关/开」；show(start) 启动即覆盖，无功能影响，但改成一致的初始文案可消歧。
2. **todo Task 1/2 的 node --check 可点名现有测试**（todo.md:10、:17）。该关口由 `test_generated_js_syntax_node_check`（batch=2）自动覆盖，非新增手工步骤；写明可避免执行人误解为要手动跑 node。

## 与 AGENTS.md 冲突对照表

无冲突。plan 的「不碰」清单与另一 session 边界一致；commit 范围（只 add 本功能文件、不 push）符合自动提交约定；手册同步符合「CLI 行为变更时同步更新 使用手册.html」的精神（本次为页面行为变更）。

## 结论

**通过**（无阻断问题；两条建议改进可由作者酌情吸收，不阻塞实施）。
