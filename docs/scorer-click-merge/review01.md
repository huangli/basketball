# Review 01: 审查存档——认人页簇区点选合并

- 范围：87730ae..cb286ad（6929cb7 点选合并 + cb286ad Esc 弹条优先修复）
- 审查方式：任务级 spec+质量双审查（plan 子代理）+ 修复后复审（2026-08-15）
- 结论：**Approved**（修复后无 Critical / 无 Important）

## 核实要点

- E1-E6 与 plan 逐字一致：CSS 高亮 / mergeSrc 瞬态声明 / 循环前残态守卫 /
  行尾三态钮（合并/取消/并入这里，展开折叠行都有）/ pickMerge 复用 mergeInto /
  Esc 分支
- mergeInto 与拖拽路径（row.draggable/text/plain/drop 守卫）零改动，
  `test_drag_merge_untouched` 锚住回归
- 残态守卫单入口全覆盖：mergeInto/splitGroup/deleteCluster 均经 show→
  renderClusters；collapseAll 总开关直调 renderClusters 同过守卫
- 无新存储键；无 --clusters 兼容（CLUSTERS 空时无钮可点，mergeSrc 恒 null）

## 审查发现与处理

- **Important（已修，cb286ad）**：picker Esc 分支无 return，closePicker 置
  pickerGid=null 后同一按键连带清 mergeSrc（一次 Esc 双清两态），与 spec
  "弹条优先"语义矛盾。修复 = 该分支补 `{ closePicker(); return; }` 一行，
  复审确认：一次 Esc 只关弹条，再按一次才清点选态；其他按键路径无误伤；
  `ev.key === "Escape"` 既有断言子串保留。教训：plan 给定代码本身有缺陷时
  实现者逐字照抄无过，终审/任务审查的语义推演是兜网。
- Minor（不修）：源行被拖拽悬停时 merge-src 实线与 drop-target 虚线 outline
  叠加，"取消源"与"拖放目标"态视觉不区分——行为确定（实线压虚线），可接受。

## 交付物

- 质量门 509 passed 全绿；b1（29球/13簇）/b2（49球/22簇）+ demo 副本均已
  用新模板重生成（grep 验证 `function pickMerge(` 各 1 处）
- 使用手册.html:118 第二步补点选合并操作说明（spec-reviewer PASS）

## 放行条件

- 立哥手工验证清单（spec Testing Strategy 5 条，含 b2 长列表末行并首行实测）
