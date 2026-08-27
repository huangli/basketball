# review01：标注页"跳到进球"导航（label-jump-goal）

## 结论

**通过**。spec-reviewer 首轮 Blocked（1 阻断 B1 + 4 建议），全部修订后落地；ruff/pytest 全绿（843 passed），浏览器实测命中全部成功标准。

## spec-reviewer 首轮（Blocked）→ 修订对照

| 条目 | 级别 | 内容 | 处置 |
|---|---|---|---|
| B1 | 阻断 | 一次性补字段脚本仅"先备份"不够：回放 key 集合与旧索引不一致时宽松合并会静默写错 clip_src_start | 已修：plan 补硬断言——key 集合完全相等才写回，不等打印差异中止（备份未动天然安全）+ 原子写 + continued 清单打印 |
| S1 | 建议 | 全批无 goal 标记时 jumpGoal 行为未定义 | 已修：落空 `show(cur)` 原地不动；spec/plan 注明循环语义与 jumpUnmarked 差异属刻意 |
| S2 | 建议 | clip_src_start 补写需 round 0.1 与 main 同口径 | 已吸收进 plan |
| S3 | 建议 | continued 重算对素材流动敏感，需抽查清单 | 已吸收：脚本打印 continued 事件清单 |
| S4 | 建议 | AGENTS.md 键位口径漂移（T 也没同步） | 已吸收：本次一并改为 J 定锚/T 机器锚/P/F + G |

## 实现清单

- `scripts/gen_label_page.py`：`jumpGoal()`（当前位之后首个 goal → 回绕全列首个 → 落空 `show(cur)`）；按钮 `跳到进球 (G)`；keydown 绑 `g`；帮助文案补 G
- `tests/test_gen_label_page.py` +1：按钮/函数/绑定/条件/落空模式断言
- 一次性脚本 `work/_chk/patch_index_anchor_fields.py`（豁免 rules.md 不入库）

## 实测账（2026-08-27）

- **补字段脚本**：回放 351 事件 key 集合与旧索引**完全一致**（聚类确定性假设成立），补 `clip_src_start`（round 0.1）+ `continued` 写回（备份 `events_index.json.bak_goalanchor`）；`continued=true` 1 个（0250#e71，窗口越界续接 0251）；0251 越界无下一片回退截断（与当初烘焙一致）
- **label.html 重生成**：LSKEY 不变（`label_20260822_citymonkey_batch1`），立哥自己浏览器里的标注进度不受影响（MCP 浏览器为独立 profile，进度为 0 属预期，非数据丢失）
- **G 跳转**：注入 3 个假 goal 标记（事件 0/5/10）连按 4 次 G → 落点序列 `[5,10,0,5]` 精确命中循环语义；清库后 G 原地不动（S1 落空模式 ✓）
- 关口：ruff format/check 全绿；`pytest` **843 passed**

## 遗留与边界（接受）

- 立哥需知：补锚操作在**他自己的浏览器**里进行——打开 review_batch1/label.html → G 跳到进球 → 循环播放入网帧按 J → 再 G；全部补完点导出覆盖 goals_batch1.json 即可，未补锚的进球仍按机器锚导出（行为同旧版）
- 一次性脚本与 `.bak_goalanchor` 备份留在 work/ 不入库；确认无误后可随手删
