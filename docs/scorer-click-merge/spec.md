# Spec: 认人页簇区点选合并（与拖拽并存）

## Objective

问题（2026-08-15 立哥）：簇特别多时拖拽合并不便，尤其末行拖到首行要长距滚动拖拽。

方案（立哥选定）：**点选合并**——簇行加"合并"钮，点源行进入待并状态（行高亮），
再点目标行的"并入这里"完成合并。两次点击与距离无关；**拖拽保留，两套并存**。

成功标准：

- 每个显示组行（展开/折叠都有）有"合并"钮；点源行后该行高亮、其他行钮变
  "并入这里"、源行钮变"取消"
- 点目标行"并入这里" = 与拖拽完全相同的合并语义（复用 mergeInto：预填/弹条/
  拆开/clAssign 清理全部不变）
- 取消路径：再点源行 / 按 Esc（弹条开着时 Esc 优先只关弹条，再按一次才清
  点选态）；源组被并走/被删（不再可见）后待并状态自动清除；拆开不影响
  （源组还在，待并态保留）
- 瞬态不持久（刷新即清，与 collapseAll 总开关同口径）；无新 localStorage 键
- 无 --clusters 页面行为不变；pytest 全绿、ruff 干净；四件套齐全

## Tech Stack

纯前端：`scripts/gen_scorer_page.py` 的 `_HTML` 模板（CSS + JS），零 Python
逻辑变更、零新依赖。

## 数据契约

- `mergeSrc`：瞬态变量（null = 未选源；gid = 该组为源）。**不进 localStorage**
  （操作中途刷新丢状态无害，重点一次即可；持久化反而有 stale gid 清理负担）
- 行尾钮渲染（所有组行，展开/折叠都有，与"删除"钮同排）：
  - `mergeSrc === null` → 所有行显示"合并"
  - `mergeSrc === g.gid` → 源行显示"取消"且行加 `.merge-src` 高亮
  - 其余行 → 显示"并入这里"
- `pickMerge(gid)` 三分支：未选源 → 记源；点的是源 → 取消；点的是目标 →
  **先清 mergeSrc 再调 mergeInto(src, gid)**（mergeInto 内部 show 重渲染，
  避免残态参与渲染）
- 残态清理单一入口：`renderClusters()` 开头算完显示组后，
  `mergeSrc` 不在可见组（被并走/被删/被拆开）→ 置 null。mergeInto/
  splitGroup/deleteCluster 都经 show→renderClusters，一处守卫全覆盖
- Esc 取消：keydown 里 picker Esc 分支后追加 `mergeSrc !== null` 清态分支
  （与弹条 Esc 并存不冲突）；不屏蔽数字键/E（点选态不影响逐球归属）

## Code Style

rules.md；模板 JS 沿用现有风格（无框架、瞬态变量模式参照 collapseAll）。

## Testing Strategy

- 模板字符串断言 + node --check 既有模式：
  - 新断言：`function pickMerge(`、`mergeSrc`、`并入这里`、`merge-src`
  - 既有断言标识符保留（`function mergeInto(`、`row.draggable = true`、
    `text/plain` 拖拽路径、`PICKER-HOOK` 等）
- 手工验证（立哥浏览器实测）：
  - [ ] 点源行"合并"→ 行高亮、他行变"并入这里"；点目标行 → 合并成功
        （组标签"并自"、归属预填/弹条与拖拽一致）
  - [ ] 再点源行"取消"、Esc 取消都好使
  - [ ] 合并/拆开/删除后无残留高亮行
  - [ ] 拖拽合并照旧可用；刷新后无待并状态残留
  - [ ] 长列表（b2 有 22 簇）末行点选合并到首行实测

## Boundaries

- Always：质量门全绿后提交；mergeInto 语义零改动（点选只是新入口）
- Ask first：无（零新依赖、零新 CLI 参数、零 schema 变更、零新存储键）
- Never：不动拖拽合并路径；不动 marks/touched/clState 任何键格式；
  不给 mergeSrc 做持久化

## Success Criteria

- [ ] 点选合并三态按钮 + 高亮 + Esc/再点取消 + 残态守卫
- [ ] 与拖拽并存、合并语义一致
- [ ] 手工验证清单全过
- [ ] 使用手册.html 第二步补一句点选合并操作
- [ ] ruff+pytest 全绿；四件套齐全
