# plan：标注页提效（同组看一判全 + 默认有效 2 倍速）

依据 `docs/label-speedup/spec.md`。全部改动在 `scripts/gen_label_page.py`
（JS 模板）+ `tests/test_gen_label_page.py` + 一个 `work/` 下一次性回放脚本。

## 步骤

### Step 1：F2 倍速控制（小，先做）

- `_HTML` 模板（raw string，JS 文案可放心用 `\n` 字面量，勿改回普通三引号）：
  - `show(i)` 内 `v.src` 设置后显式 `v.playbackRate = 1;` 并同步 `#speed` 文本
    （片段已烘焙 2x，页面 1x = 有效 2x；2026-08-09 立哥拍板默认保持有效 2x，
    初版"页面 2x = 有效 4x"验收后回改）
  - 页头加一个与"声音"同款的 `<button id="speed">`（sound 控件实为 button，
    非 span，保持样式一致），显示"倍速：1x"；按键提示行加 `S=倍速`
  - keydown 加 `s` 键：`v.playbackRate = v.playbackRate === 2 ? 1 : 2`，同步更新显示
  - 边界：toggleWide 换 src 会重置倍速，保留当前值而非强制默认
- `tests/test_gen_label_page.py` 加回归断言：生成 html 含 `playbackRate = 1`
- 关口：ruff + pytest

### Step 2：F1 同组看一判全

- `mark(r, scorer)` 内，`r === "goal"` 且 `e.grp` 且**本次为新标注**
  （写 marks 前 `!marks[e.key]`）时：
  - 找同组（`EVENTS.filter(x => x.grp === e.grp && x.key !== e.key)`）中
    `!marks[x.key]` 的成员
  - 有则 `confirm(...)`（文案见 spec）；确定 → 这些成员写入
    `marks[x.key] = { r: "no" }` 并 `save()`
  - 之后走现有"跳下一个未标注"逻辑（被标成员自动被跳过）
- 回归断言：生成 html 含确认框文案关键片段（如 `疑似同回合组`），
  且 `node --check` 通过（node v24.15.0 已在 PATH，已验证）
- 关口：ruff + pytest + node --check

### Step 3：批次 3 回放验证（spec 成功标准 1）

- 一次性脚本 `work/label_speedup_replay.py`（不入库）：
  - **J 集合**：`20260722地平线/goals_20260722_3.json` 61 条 confirmed
    （立哥原始导出，anchor_time 就是事件 anchor_t0，按 `(file, anchor_time)`
    精确匹配 `work/20260722/review_batch3/events_index.json` 事件）
  - **真球集合**：`work/20260722/goals_batch3.json` 51 条 confirmed（去重后）
  - 按页面顺序（events_index 顺序 = 筐距序，非锚点序）模拟标注：
    遇 goal 事件且同组有未标注成员 → 视为确认跳过（标 no）
  - 输出：① 跳过事件数（要求 ≥8）；② 覆盖式断言——51 球每条至少仍有
    一条 goal 事件：同文件 ±2s（兼容 203628 修锚点 3.5→2.2 的 1.3s 偏差）
    **或同文件同组**（同球双 J 锚点差 2.3~4.2s，±2s 盖不住；批次 3 全部
    8 组同文件双 J 均为同球，同组即同球。实施时实测：不加同组条款则
    203946@5.9 假性失败）
- 注意：events_index 页面顺序是筐距排序，同球双 J 组内可能先遇到
  "去重时被删的那条"——覆盖式断言已正确处理该情形，不得改用
  "事件 key 仍是 goal"的口径（会假性失败）

### Step 4：文档与提交

- 本轮（实施前）文档审查存档为 `docs/label-speedup/review01.md`；
  实施后复审写 review02.md（轮次递增不覆盖，与 dedup-same-goal 惯例一致）
- 回填 todo.md 勾选
- commit（只 add 本功能文件；认人会话改动文件不碰）

## 依赖与顺序

Step 1 → Step 2 → Step 3 → Step 4，顺序执行。Step 1/2 可合一个 commit，
也可分开，按实际改动量定。

## 验收关口

- [x] ruff format / check --fix / pytest -q 全绿（274 passed）
- [x] node --check 生成页语法通过
- [x] 回放：跳过 15 ≥ 8 且 51 球覆盖断言 PASS（review02/03）
- [x] 立哥页面实操验收（2026-08-09 无痕窗口）
