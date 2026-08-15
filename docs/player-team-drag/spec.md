# Spec: 认人页队员拖拽改队——便服队员归队，导出 roster 带新队别

## Objective

现状问题（2026-08-15 立哥指出）：穿便服的队员实际属于某队（如黄远超是
半截篮的人），但认人页队别只读——队别来自标签前缀推定或 roster 已有
team 值，页面无修改入口，只能导出后手改 roster.json。队别错了直接
影响分队合集口径（build_highlight --team 按 team 过滤）。

本功能（2026-08-15 立哥拍板，拖拽方案）：**顶部名单区的队员按钮可拖拽
到另一队伍行**，松开即改队别——分行显示、按钮着色、导出 roster.json
的 players team 全部跟随；改动存 localStorage，刷新不丢。

成功标准：

- 名单区队员按钮可拖拽，拖到目标队伍行（对手队 OPP/半截篮/便服 三行）
  松开改队别；拖到原队行 = 无操作；拖拽不改任何 marks 归属
- 导出 roster.json 的 players team 反映改后队别（roster schema 不变）
- 刷新/重开页面后改队结果仍在（localStorage 持久）
- 簇区选人按钮、弹条按钮保持单击选人语义，不参与改队拖拽
- pytest 全绿、ruff 干净；四件套齐全

## Tech Stack

- 纯前端：`scripts/gen_scorer_page.py` 的 `_HTML` 模板（CSS + JS），
  零 Python 逻辑变更、零新依赖；roster 导出契约不动

## 数据契约

### 页面态（新 localStorage 键）

`scorer_<session>_teamovr`（平铺对象 `{ tag: team }`，独立键，不动
marks/touched/clState 既有存储）：

- 读写沿用 save() 的"读回再合并写"模式 + JSON 解析失败回退空对象
- 加载时把覆盖值应用回 PLAYERS（`p.team = ovr[p.tag]`），在首次渲染前
- 改队 = 直接改 PLAYERS 里该队员的 team + 写覆盖键 + save

### 交互

- **拖拽源**：仅顶部名单区（renderPlayers 的行，含"其他"兜底行）的
  队员按钮 `draggable = true`，dragstart 写自定义 MIME
  `text/player-tag = p.tag`（**不用 text/plain**——与簇行拖拽的
  text/plain 隔离：防数字开头的队员 tag 拖到簇行被 parseInt 误当组 id
  触发误合并，防拖簇行经过队伍行时队伍行误高亮）
- **放置目标**：三个已知队伍行（OPP/半截篮/便服）的行 div，**三行恒
  渲染**（空队也渲染行——否则该队零队员时无处可拖入）；
  dragover 仅在 `types` 含 `text/player-tag` 时 preventDefault + 高亮
  （复用 drop-target 样式，作用域扩到队伍行），dragleave/drop 移除高亮
- **drop**：`getData("text/player-tag")` 取 tag；目标行队名 ≠ 该队员现
  team → 改队（PLAYERS 内存值 + teamovr 持久化 + 重渲染）；相同 = 无操作
- **簇行 dragover/drop 补守卫**：仅当 `types` 含 `text/plain` 时响应
  （一行加固，防队员拖拽触发簇行高亮）
- **"其他"兜底行不是放置目标**（它只是展示，不是合法队别）
- 单击选人语义不变：拖拽与单击天然共存（click 在未拖动时触发）
- 簇区选人按钮、合并弹条按钮**不**加 draggable（保持纯单击选人；
  防"想选人的拖拽"误改队）

### 导出

- exportRoster 的 `players = PLAYERS.map(...)` 读的是内存 PLAYERS——
  改队已写内存值，导出自动跟随，**导出代码零改动**
- 自由输入补录、confirmed 判定均不受影响（team 不参与归属逻辑）

## Code Style

rules.md；模板 JS 沿用现有风格（无框架、localStorage 容错 try/catch）。

## Testing Strategy

- 零 Python 逻辑变更 → 模板字符串断言 + node --check 既有模式：
  - 新断言：`scorer_` + teamovr 键名片段（`"_teamovr"`）、
    `function changeTeam(` / `function saveTeamOvr(`、`text/player-tag`
    自定义 MIME、`div.dataset.team`、名单区按钮 draggable 设置点
  - 既有断言标识符保留（clusterAssign/cluster-row/const CLUSTERS 等）
- JS 交互走手工验证清单（立哥浏览器实测）：
  - [ ] 便服队员拖到半截篮行 → 移到该行、着色变、刷新后仍在
  - [ ] 拖到原队行 = 无操作；拖到"其他"行不高亮不响应
  - [ ] 某队当前零队员时该行仍渲染、可拖入（三行恒渲染）
  - [ ] 队员拖到簇行 / 簇行拖到队伍行：互不高亮、互不响应（MIME 隔离）
  - [ ] 单击队员按钮仍是选人（不因加 draggable 失效）
  - [ ] 簇区按钮不可拖、单击选人正常
  - [ ] 导出 roster.json 该队员 team = 新队别；归属不受影响

## Boundaries

- Always：质量门全绿后提交；localStorage 读写容错
- Ask first：无（零新依赖、零新 CLI 参数、零契约变更）
- Never：不改 roster.json schema；不改 marks/归属语义；
  簇区/弹条按钮不加拖拽；不改对手队名派生逻辑（刚定稿）

## Success Criteria

- [ ] 名单区队员按钮拖拽改队 + 持久化 + 重渲染
- [ ] 导出 team 跟随；marks 不动；单击语义不变
- [ ] 手工验证清单全过
- [ ] 使用手册.html 认人节补一条（队员可拖拽改队）
- [ ] ruff+pytest 全绿；四件套齐全
