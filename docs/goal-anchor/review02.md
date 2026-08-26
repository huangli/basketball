# review02（终审）：标注页 J 键人工锚点（goal-anchor）

## 结论

**Approved with suggestions**（通过，附 3 条非阻断建议，已全部吸收）。

首轮 B1 与 S1~S6 全部如实落地，修订后 spec/plan 与代码实现逐点一致，实测账内部数字自洽，手册改动准确反映行为。无新的阻断问题。

## 首轮 B1/S1~S6 落地核对

- **B1（阻断→已修）**：`plan_clip_segments` 返回 `(segs, bool)`；`cut_cluster_clip`/`cut_wide_clip` 透出 `continued`；events_index 记 `"continued": cont_clip or cont_wide`（取或，保守方向正确）；JS `markGoal` 在 `!e.continued` 时才捕锚，退化后不写 anchor 导出走机器锚；进度行提示与两处水印"跨文件续接"齐备。静默错算路径已封死
- **S1**：按钮 onclick 与 J 键同走 `markGoal(true)`；T 按钮/T 键同走 `markGoal(false)` ✓
- **S2**：同组多 J 确认框优先显示人工锚 ✓
- **S3**：`mark()` 存入即 `Math.round(anchor*10)/10`，显示与导出同源 ✓
- **S4**：两脚本 docstring 均已同步 ✓
- **S5**：spec 成功标准含 continued 验证条，review01 实测有对应行 ✓
- **S6**：循环补按等价性论证成立，review01 表格已补行留痕 ✓

## spec/plan 与实现一致性

- `clip_window()` helper 统一三处窗口口径（cut_cluster_clip / wide 窗口 / events_index），round 0.1、钳 0 符合 spec
- `__SPEED__` 全模块路径引用 `gen_review_clips.SPEED`，非硬编码；导出窗 4/2 与审核窗 2/4 同名常量隔离未混淆
- 旧索引退化守卫齐备，旧页面行为与旧版逐字一致；localStorage 合并写未动、anchor 随车保存；F 清除连带锚、重复按 J 覆盖锚符合 spec
- build_highlight 未改，其校验在人工锚窗口下天然满足，无兼容风险

## 实测账可信度

数字自洽（173.2=175.2−2；8.65×2+173.2=190.5；导出 186.5/192.5），四场景覆盖 spec 全部成功标准；测试断言与模板逐字核对一致。审查方为只读，ruff/pytest 与浏览器实测未亲自复跑，可信度基于代码-测试-实测账三方互证。

## 手册同步核对

快捷键表 J=定锚/T=机器锚与实现逐字吻合；tip（重复按 J 改锚、进度行人工锚显示、续接片段水印辨识+J 退化）与代码实际一致。

## 逐条问题

阻断：无。

- 建议 1（已吸收）：todo.md 9 项补勾选
- 建议 2（已吸收）：review01 实测账补 S6 循环补按等价性行
- 建议 3（已记录）：`clip_src_start` round 0.1 与 ffmpeg 全精度 `-ss` 间 ≤0.05s 系统偏差，远在 ±2s 容差内，review01 精度边界节留痕

观察（非问题）：认人链以 `(file, anchor_time)` 为主键，人工锚改变 anchor_time 取值——goals.json 内部自洽（crop_scorers 读同一文件），roster 按场次隔离且在 goals 之后生成，新旧不混；后续若出现"旧 roster 配新 goals"的用法需注意。
