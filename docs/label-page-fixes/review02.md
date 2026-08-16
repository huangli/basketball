# review02：标注页两个 bug 修复 实施终审

日期：2026-08-16　审查员：独立规格审查　对象：git 工作区未提交改动
（scripts/gen_label_page.py、tests/test_gen_label_page.py、使用手册.html、docs/label-page-fixes/todo.md）
前序：review01.md（通过，含 2 条建议改进）

## 整体评价

实施与 spec/review01 闭环后的契约完全一致，两个 bug 的修复手法、测试断言面、手册同步均到位；独立复跑 pytest（24 用例）与 ruff format/check 全绿。未发现阻断问题；手册 warn 块有一处措辞过度泛化，建议修订（不阻塞）。

## 契约核对（spec 成功标准 → 实施）

| spec 成功标准 | 实施证据 | 结果 |
|---|---|---|
| ①onclick 不含 `show(`，含 `v.muted = !v.muted` 与按钮文本更新 | gen_label_page.py:283-287 多行语句块：只切 muted + 就地更新 textContent；注释说明缘由并指向 Bug① | ✓ |
| ①按钮文案与 show() :193 一致 | 两处均为 `v.muted ? "声音：关" : "声音：开"`，逐字一致 | ✓ |
| ②batch=2/3 键互不相同（`_batch2`/`_batch3`） | 模板 :150 `LSKEY = "label_" + SESSION + "__LSUFFIX__"`；build_html :351 注入 `_batch{batch}`；test_localstorage_keys_isolated_per_batch 断言两条完整 LSKEY 行 | ✓ |
| ②不传 batch 旧键逐字节不变 | 注入空串，键值仍为 `label_<场次>`；test_localstorage_keys_unchanged_without_batch 锁定（源码行变为 `+ ""` 拼空串，**键值**不变——见可选优化 1） | ✓ |
| ②POSKEY 派生隔离 | :151 `POSKEY = LSKEY + "_pos"` 未动；测试断言派生形式（review01 建议改进 1 已采纳） | ✓ |
| ③node --check / ruff / pytest 全绿 | 独立复跑：pytest 24 用例全过（含 node --check）；`ruff check` All checks passed；`ruff format --check` 2 files already formatted | ✓ |
| 现有 label-speedup / same-rally 断言不回归 | 24 用例全绿即证 | ✓ |

review01 建议改进 2（spec 风险表补车百鼎实证）属 spec 文档增补，实施未改 spec——封存中的 spec 不必回头改，该实证可由本报告承载（见下）。

## 代码质量检查

- raw string/转义约束未破坏：模板仅改两行（:150 LSKEY、:283-287 onclick），未碰 confirm 文案与 `\n` 串；node --check 通过即证 JS 语法
- `__LSUFFIX__` 占位全模板仅 LSKEY 一处出现，`.replace` 链无串扰（`__LSUFFIX__`/`__SESSION__` 等占位互不包含）
- 测试提取逻辑稳健：`html.index('getElementById("sound").onclick')` 起点在新增注释**之后**（注释含 `show(`，若起点靠前会误判——当前写法正确避开了），`"};"` 边界与多行块匹配
- todo.md 已按实施实况回填，与 diff 一致

## 阻断问题

无。

## 建议改进

1. **手册 warn 块措辞过度泛化**（使用手册.html:111，diff 新增行）。「重生成会换存储键、该批进度清零」只对 **2026-08-16 之前生成的页面**成立（旧共享键 → 新 `_batchK` 键的一次性切换）；修复后生成的页面，键由场次名+批次号确定性拼出，重生成 label.html **键不变、进度不受影响**。且车百鼎三批 goals 已全部导出（review01 已实证），真实受影响存量为零。当前措辞会让立哥对未来场次产生不必要的顾虑。修法（二选一）：
   - 改为「**2026-08-16 之前生成的旧页面**重新生成会换存储键、该批进度清零；之后生成的页面无此问题」；或
   - 保留保守口径但加半句「新页面重生成键不变、进度不受影响」。
   注：此措辞源自 spec 风险表（spec.md:84）与 plan Step 3 的既定文案，实施忠实执行了契约——根因修订点在手册措辞本身，改动一行即可，可在本次 commit 一并带入或下轮再改。

## 可选优化

1. **spec 成功标准 2 与实现源码行的字面差**（spec.md:73-74）。spec 写「不传 batch 时 LSKEY 维持 `"label_" + SESSION` 无后缀」，实现生成行为 `"label_" + SESSION + ""`——**键值**逐字节一致（契约本意），仅 JS 源码行字面不同。test_localstorage_keys_unchanged_without_batch 已按 `+ ""` 形式锁定，行为无问题；若追求 spec 字面可对模板做条件拼接，但收益为零，建议仅在此记录备查。
2. POSKEY 派生断言只验了 h2（未验 h3 与无 batch 路径）。派生行全模板仅一处，覆盖已足够，不补亦可。

## 与 AGENTS.md 冲突对照表

无冲突。待办：AGENTS.md「修改完成即 commit」约定下，本次改动（gen_label_page.py / test_gen_label_page.py / 使用手册.html / docs/label-page-fixes/）尚未提交，plan Step 4 既定在审查通过后单 commit、只 add 本功能文件、不 push——照此执行即可。

## 结论

**通过**（无阻断问题；建议改进 1 条为手册一行措辞修订，可并入本次 commit，不影响交付）。
