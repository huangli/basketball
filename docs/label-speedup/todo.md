# todo：标注页提效（同组看一判全 + 默认 2 倍速）

依据 `docs/label-speedup/spec.md` / `plan.md`（review01 修订后版本）。

## Task 1：F2 默认 2 倍速

- [ ] `_HTML`：`show(i)` 设 `v.playbackRate = 2` 并同步 `#speed` 文本
- [ ] 页头加 `<button id="speed">`（与 sound 同款 button）+ 按键提示行加 `S=倍速`
- [ ] S 键 1x/2x 切换并同步显示
- [ ] 回归断言：生成 html 含 `playbackRate = 2`
- [ ] 关口：ruff format / check --fix / pytest -q 全绿

## Task 2：F1 同组看一判全

- [ ] `mark()` 内：goal 且成组且本次为新标注 → 查同组未标注成员 →
      confirm → 标 no 并跳过
- [ ] 只动未标注成员，已标注一律不覆盖；重复按 J 不再弹框
- [ ] 回归断言：生成 html 含确认框文案关键片段
- [ ] `node --check` 生成页语法通过（node v24.15.0 已在 PATH）
- [ ] 关口：ruff + pytest 全绿

## Task 3：批次 3 回放验证

- [ ] 写 `work/label_speedup_replay.py`（一次性，不入库）
- [ ] J 集合 = `20260722地平线/goals_20260722_3.json` 61 条精确匹配事件；
      真球集合 = `work/20260722/goals_batch3.json` 51 条
- [ ] 回放输出：跳过事件数 ≥ 8
- [ ] 覆盖式断言：51 球每条在同文件 ±2s 内至少仍有一条 goal 事件

## Task 4：收尾

- [ ] 用批次 3 events_index 重新生成 label.html（session 保持 20260722_3，
      保住立哥 localStorage 标注记录）
- [ ] spec-reviewer 实施复审，写 review02.md（review01.md = 实施前文档审查，
      已存档）
- [ ] 立哥页面实操验收：组内 J → 确认 → 跳过；S 键切速
- [ ] commit（只 add 本功能文件）
