# review02：筐检测消重 三件套复审（review01 修订核对）

日期：2026-08-16　审查员：独立 spec-reviewer（只读审查）
对象：`docs/detect-hoops-cache/` spec.md、plan.md、todo.md（review01 修订后版本）

## 整体评价

review01 的 B1/B2 与建议 1-5、可选 1/2 均已正确落实，修订方式与源码事实相符，未引入新的执行性错误。残留两处文档级瑕疵（风险表旧措辞未同步、审查编号表述过时），均不影响照做执行。**结论：通过**（两条建议改进可在实施前顺手修掉，不阻塞）。

## review01 问题闭环核对

| 编号 | 落实情况 | 证据 |
|---|---|---|
| B1（量化口径） | ✅ 闭环 | spec.md:35-37、plan.md:19-21、todo.md:13-14 三处一致钉死"cx/cy 用 int() 截断、conf 存原始 float"，与 `detect_hoop_frame`（detect_hoops.py:169）语义一致；成功标准 1 同步补了 diff 判定流程（spec.md:74-75） |
| B2（命令可执行） | ✅ 闭环 | plan.md:66-74 全部补全 `python scripts/` 前缀与 `work/20260805_车百鼎/` 路径；已核对三脚本 CLI 支持该用法（detect_hoops `--candidates/--fid/--out`、mot_candidates 位置参数 fid、pilot_candidates `--out`+位置参数） |
| 建议 1（等价性论证措辞） | ⚠ 半闭环 | §功能 3（spec.md:47-52）已改为"conf 过滤发生在 NMS 之前…逐框独立…按类分组"，正确；**但风险表第 4 行（spec.md:94）仍残留旧表述"ultralytics conf 为 NMS 后过滤"，与正文矛盾** |
| 建议 2（元素级校验） | ✅ 闭环 | plan.md:35-37（load_hoop_frames 元素级校验+整体 try 回退）、plan.md:55-56 与 todo.md:46/49（第 4 个单测用例：hoops 为 list 但元素损坏回退不崩）、todo.md:34-35（Task 2 验收）三处一致 |
| 建议 3（fid 形态） | ✅ 闭环 | plan.md:63-64 写明 fid 取 `events[].fid` 原值并给出完整文件名片段示例，与 work/detect/ 实际缓存主键一致 |
| 建议 4（diff 判定流程） | ✅ 闭环 | spec.md:74-75：先查量化口径（B1）再查漂移，确认漂移按 ±1px / conf ±0.005 容差复核并记录；与已钉死的量化口径自洽（理论应完全相等，容差仅兜底） |
| 建议 5（逐字节→schema 同构） | ✅ 闭环 | todo.md:33 已改为"与现行 schema 同构（key/detected/track/window/anchor 字段不变）" |
| 可选 1（git status 前置） | ✅ 闭环 | plan.md:81-82 |
| 可选 2（备份目录清理） | ✅ 闭环 | plan.md:75"验证后恢复备份缓存并删除空置的 bak_<日期>/" |

## 新引入问题检查

无执行性新问题。行号引用未变且仍属实（源码未动）；备份目录 `work/detect/bak_<日期>/` 与 `CACHE_PATTERN`（`work/detect/{}_mot_cache.json`）不匹配，不会干扰缓存命中判定。

## 建议改进（不阻塞）

1. **spec.md:94 风险表第 4 行措辞残留**："ultralytics conf 为 NMS 后过滤"与修订后 §功能 3（:47-48"conf 过滤发生在 NMS **之前**"）直接矛盾。修法：改为"conf 过滤逐框独立且在 NMS 之前，理论等价 + 成功标准 1 轨迹逐点 diff 实证"。
2. **plan.md:85 / plan.md:96 / todo.md:79 / todo.md:83 的审查编号表述过时**：仍写"review01.md 编号起排 / review01.md 落盘"。review01 已存在，按 AGENTS.md"review 按轮次编号递增不覆盖"，实施后审查应落下一个编号。修法：改为"reviewNN.md 按编号递增落盘"。（照字面执行有覆盖 review01 的歧义，但 AGENTS.md 规则会兜底，故不定阻断。）
3. **todo.md:42 标题"单测三分支"过时**：现为四个用例。顺手改"单测四分支"即可。

## 与 AGENTS.md 冲突对照表

无冲突（同 review01 结论；本次修订未改变边界声明与流程约定）。

## 结论

**通过**。B1/B2 与建议 1-5 实质闭环，修订未引入执行性错误。残留 3 条文档级建议改进（风险表旧措辞、审查编号表述、todo 标题计数），可在实施前顺手修订，无需再走一轮复审。
