# plan：标注页同球双 J 自动识别

## Overview

标注页（gen_label_page.py）增加"疑似同回合"分组能力：同 fid 内审核窗口重叠的事件分组标色提示，导出 goals 时同组 ≥2 个 J 弹确认。机器只提示不自动删，判定权在人。一期仅同文件，跨文件留二期。

## Architecture Decisions

- **分组函数放 gen_label_page.py 本地**：一期只有它用，不进 pipe_common.py（避免过早抽象）
- **窗口口径近似取 `[anchor_t0 − CLIP_BEFORE_SEC, anchor_t0 + CLIP_AFTER_SEC]`**：实际片段左界相对事件首候选（比 anchor 更早），events_index 无事件跨度字段；左界为保守子集——重叠判定偏严、可能漏组但绝不误并，一期可接受
- **分组结果在 Python 侧生成页面时内联进事件数据**：页面 JS 只做呈现与导出检查，不在 JS 里重算分组（单一事实源）
- **导出确认选择不持久化**：每次导出都问，防误记
- **常量引用写全模块路径**：gen_review_clips 与 gen_label_page 有同名不同值的 CLIP_BEFORE_SEC/CLIP_AFTER_SEC（审核窗口前2后4 vs 导出剪辑前4后2），禁止裸 from-import

## Task List

### Phase 1：分组逻辑与验证（先证明规则对）

- [ ] Task 1：分组纯函数 + 单测
- [ ] Task 2：批次 3 回放验证（8 组全命中、0 误分组）

### Checkpoint：分组规则可信

- [ ] 单测 5 用例全过；回放断言全过；失败则回 Task 1 修口径，**不进入 Phase 2**

### Phase 2：标注页呈现与导出校验

- [ ] Task 3：同组卡片视觉分组 + "疑似同回合"标签（可与 Task 4 并行）
- [ ] Task 4：导出前置确认框（可与 Task 3 并行）

### Checkpoint：功能完整

- [ ] 生成的 label.html 分组标记与确认框人工点开核对通过

### Phase 3：关口与交付

- [ ] Task 5：lint/format/test 关口 + commit

## Risks and Mitigations

| 风险 | 影响 | 对策 |
|---|---|---|
| 窗口口径漂移（gen_review_clips 参数未来调整） | 中 | 从同一常量取值，注释写明耦合 |
| 同名常量误引（两模块 CLIP_* 值不同） | 高 | import 写全模块路径或 as 别名；review 时专项检查 |
| 传递闭包误并（训练时段密集事件连成大组） | 低 | 提示性质不阻断；导出确认框按组列出由人判 |
| 回放漏命中（anchor 差超窗口） | 中 | 说明口径取错，回 Task 1 修正，不动 UI |

## Open Questions

- 无（跨文件同球识别、自动合并均已明确划到二期/非目标）
