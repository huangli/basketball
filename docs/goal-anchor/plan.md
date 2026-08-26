# plan：标注页 J 键人工锚点（goal-anchor）

## 执行步骤

1. **gen_review_clips.py**：events_index 事件字典加 `clip_src_start` 与 `continued` 字段
   - 位置：`index_events.append({...})`（现 `scripts/gen_review_clips.py:817` 附近）
   - `clip_src_start`：复用同函数内已算出的 `start` 变量（806 行），`round(start, 1)`
   - `continued`：`cut_cluster_clip`/`cut_wide_clip` 内部 `plan_clip_segments` 已知续接标志，改两函数返回该标志（或另行透出），事件字典记 `"continued": bool`
   - docstring/模块头注释同步（输出字段清单）
2. **gen_label_page.py 模板与逻辑**
   - 模板注入：`__SPEED__` ← `gen_review_clips.SPEED`（build_html 的 replace 链加一条；模块已 import gen_review_clips，直接引用）
   - JS `mark(r, scorer)` 签名扩展：`mark(r, scorer, anchor)`，anchor 存在时写入 `marks[e.key].anchor`（**存入即 `Math.round(a*10)/10`**）
   - J 键与**"进球 (J)"按钮 onclick 同一捕锚路径**：`a = e.clip_src_start + v.currentTime * SPEED`；`typeof e.clip_src_start === "number" && !e.continued` 才传 anchor，否则等同 T（旧索引/跨文件续接兜底）；continued 事件进度行提示"跨文件续接，锚点用机器值"
   - T 键处理：`mark("goal")`（不传 anchor）；keydown 绑定加 `t`
   - 进度行：当前事件 marks 有 anchor 时追加 `锚 t=xx.xs`；按键帮助文案更新（J=进球·定锚 / T=进球·机器锚）
   - 导出 `exportGoals()`：`m.anchor` 为有限数值时 `anchor_time = m.anchor`，`clip_start/clip_end = anchor ∓ BEFORE/AFTER`（沿用现有 round 0.1 口径）；否则走现有 `e.anchor_t0` 路径；同组多 J 确认框文案优先显示人工锚
   - 同组提示逻辑不动（J/T 都是 `r === "goal"` 自然覆盖）
   - 模块 docstring 同步（导出规格 + J/T 键语义）
3. **测试**
   - `tests/test_gen_review_clips.py`（无则新建，仿现有测试风格）：events_index 事件含 `clip_src_start`（值 = `round(max(0, 首成员t0 − 2), 1)`；`members[0].t0 < 2` 钳 0）与 `continued`（续接/不续接两态）
   - `tests/test_gen_label_page.py`：build_html 注入 `SPEED` 常量值；事件 `clip_src_start`/`continued` 透传进页面 JSON；旧事件（无两字段）页面正常生成
   - JS 换算/退化逻辑不做单测（浏览器行为），靠模板常量断言 + 实测回放验证
4. **关口**：`ruff format scripts tests && ruff check --fix scripts tests`（复核 diff）→ `pytest -q` 全绿
5. **实测回放**：重新生成 20260822_citymonkey review_batch1 的 events_index + label.html（正式验证以生成端为准），浏览器验证：J 捕锚换算、导出值、T 兜底、旧索引退化、continued 事件退化与提示、**片段循环重播中补按 J 换算仍正确**（防"循环后时间轴漂移"误判）
6. **review01.md**：四件套审查报告存档（结论 + 实测账，含 spec-reviewer Blocked→修订对照）
7. **文档同步**：`使用手册.html` 快捷键表（J/T 新语义）；AGENTS.md 无需改（工作流口径不变）
8. **提交**：`feat: 标注页 J 键人工锚点——按下时刻即入网锚点，T 机器锚兜底（goal-anchor）`

## 风险与回退

- 风险：立哥肌肉记忆按 J 的时机偏晚 → 锚点系统性偏晚 ~0.5-1s。窗口前 4 后 2 容忍 ±2s，可接受；用几次即适应
- 风险：旧 review 目录（无 `clip_src_start`）打开新页面 → J 退化为机器锚，行为与现状一致，无回归
- 回退：改动集中在两脚本 + 测试，git revert 单提交即可
