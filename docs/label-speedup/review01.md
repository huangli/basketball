# review01：标注页提效（spec-reviewer 第 1 轮，实施前文档审查）

审查日期：2026-08-09　审查方式：spec-reviewer 子代理（plan 型，只读）
审查对象：`docs/label-speedup/` spec.md / plan.md / todo.md 初版
判定：**有阻断问题（3 条）** → 已全部修订，见下。

## 阻断问题与处置

### B1. plan Step 3 数据前提颠倒 → 已修订

- 问题：plan 初版称"goals_20260722_3.json 是去重后 51 球，61 J 拿不到"，
  与 spec 自相矛盾。实测（本会话复核）：`20260722地平线/goals_20260722_3.json`
  = 61 条全 confirmed（立哥原始导出）；`work/20260722/goals_batch3.json`
  = 51 条 confirmed（去重后机读版）。
- 处置：plan Step 3 重写——J 集合用 61 条按 `(file, anchor_time)` 精确匹配
  事件（导出时 anchor_time 就是 anchor_t0，无需近似）；真球集合用 51 条。
  todo Task 3 同步。

### B2. "误标 0"口径会假性失败 → 已修订

- 问题：events_index 页面顺序是筐距序非锚点序，同球双 J 组内可能先遇到
  "去重被删的那条"，确认跳过后"保留条"被标 F——按初版口径（51 球事件 key
  全部仍是 goal）判失败，但球实际已被先遇到那条的 J 捕获，合集不少球。
- 处置：spec 成功标准 1 改为覆盖式断言——51 球每个至少仍有一条 goal 事件
  （同球重复视为同一球）；plan Step 3 落地为"同文件 ±2s 内至少一条 goal
  事件"（±2s 兼容 203628 修锚点 3.5→2.2 的 1.3s 偏差），并明文禁止回退到
  key 级口径。

### B3. review 轮次编号冲突 → 已修订

- 问题：plan 把实施后审查叫 review01，则本轮实施前文档审查无存档位置，
  与 AGENTS.md"review 按轮次递增"及 dedup-same-goal 惯例冲突。
- 处置：本轮存档为 review01.md（本文件）；实施后复审写 review02.md。
  plan Step 4 / todo Task 4 已改。

## 建议项处置

| # | 建议 | 处置 |
|---|---|---|
| 1 | node --check 可执行性 | 已验证 node v24.15.0 在 PATH，关口保留 |
| 2 | show() 换片后同步 #speed 文本 + 提示行加 S=倍速 | 已入 plan Step 1 / todo Task 1 |
| 3 | sound 控件是 button 非 span | 已改 plan/todo（`<button id="speed">`） |
| 4 | raw string 下 `\n` 字面量提醒 | 已入 plan Step 1 开头 |
| 5 | J 改判后被标 F 成员不复活的边界 | 已入 spec 风险表 |
| 6 | 重复按 J 重复弹框 | 已入 spec/plan：仅本次为新标注时触发 |
| 7 | ≥8 下限口径可保留 | 采纳，不动 |

## 结论

3 条阻断全部修订、7 条建议全部处置。修订后版本交第 2 轮复审确认。
