# review01：标注页 J 键人工锚点（goal-anchor）

## 结论

**通过**。spec-reviewer 首轮 Blocked（1 阻断 B1 + 6 建议），全部修订后实现落地；ruff/pytest 全绿（842 passed），浏览器实测四项场景全部命中 spec 成功标准。

## spec-reviewer 首轮（Blocked）→ 修订对照

| 条目 | 级别 | 内容 | 处置 |
|---|---|---|---|
| B1 | 阻断 | 跨文件续接事件（`plan_clip_segments`，段 2 时间轴归零）J 捕锚会静默算出越界伪时刻 | 已修：`cut_cluster_clip`/`cut_wide_clip` 透出 `continued` 标志 → events_index 记 `continued` 字段；JS 侧 continued 事件 J 静默退化为机器锚 + 进度行提示"跨文件续接·锚点用机器值" |
| S1 | 建议 | "进球 (J)"按钮与 J 键行为分叉 | 已吸收：按钮 onclick 与 J 键同走 `markGoal(true)` |
| S2 | 建议 | 同组多 J 确认框显示机器锚 | 已吸收：确认框文案优先显示人工锚 |
| S3 | 建议 | anchor 存入 marks 时即 round 0.1 | 已吸收：`Math.round(anchor*10)/10` 落在 `mark()` |
| S4 | 建议 | gen_label_page 模块 docstring 同步 | 已吸收：补锚点口径段落 |
| S5 | 建议 | 成功标准补 continued 验证条 | 已吸收并进实测 |
| S6 | 建议 | 循环重播中补按 J 换算正确性验证 | 已吸收：实测 currentTime 定位换算（见下），循环重播只重置播放头、换算公式不变 |

## 实现清单

- `scripts/gen_review_clips.py`：`clip_window()` helper 统一窗口口径（cut_cluster_clip 与 events_index 共用，防漂移）；两个 cut 函数返回 `continued`；events_index 事件加 `clip_src_start`（round 0.1）与 `continued`；模块 docstring 同步
- `scripts/gen_label_page.py`：模板注入 `__SPEED__`（全模块路径引 gen_review_clips.SPEED）；`markGoal(withAnchor)` 统一 J/按钮/T 入口；`mark()` 支持 anchor（存入即 round）；导出人工锚优先（窗口 anchor∓4/2）；进度行人工锚/续接提示；按键帮助与 T 按钮；模块 docstring 同步
- 测试：`test_gen_review_clips.py` +3（clip_window 公式与钳 0、continued 两态透出）；`test_gen_label_page.py` +3（SPEED 注入、字段透传、JS 路径断言）

## 实测账（2026-08-26，Chrome 驱动验证）

生成端：0248  fid 170~205s 子集（19 候选）真跑 gen_review_clips → 6 事件，`clip_src_start`/`continued` 字段齐全（e2 即原 e16：src_start=173.2 = 首候选 175.2 − 2 ✓）。

页面端（file:// 打开，脚本驱动）：

| 场景 | 操作 | 结果 |
|---|---|---|
| J 捕锚（spec 成功标准） | e2 播放头定位 8.65s（=(190.5−173.2)/2）按 J | `anchor=190.5`，导出 `186.5~192.5` ✓ 精确命中 |
| T 机器锚兜底 | e1 按 T | marks 无 anchor，导出 anchor_time=172.4=机器锚 ✓ |
| 旧索引兼容 | 旧 events_index（无新字段）页面按 J | 静默退化机器锚，无报错 ✓ |
| continued 退化（B1 验证） | 事件置 continued=true 按 J | 不捕锚退化为机器锚 ✓；进度行显示"跨文件续接·锚点用机器值" ✓ |
| 循环重播补按（S6） | 脚本定位 currentTime=8.65s 按 J | HTML5 loop 只重置播放头、换算公式 `clip_src_start + currentTime × SPEED` 不含播放次数项——定位任意播放头按 J 与循环第 N 遍补按数学等价，换算正确 ✓ |

关口：`ruff format` + `ruff check --fix`（复核 diff：仅本功能 4 文件）+ `pytest`：**842 passed**（含既有 JS 语法 node --check 用例，新 JS 模板语法有效）。

精度边界（review02 记录，无需改）：`clip_src_start` round 0.1 写索引、ffmpeg 裁剪用全精度 `-ss .2f`，J 捕锚存在 ≤0.05s 系统偏差，远在窗口 ±2s 容差内。

## 遗留与边界（接受）

- 立哥肌肉记忆按 J 时机可能偏晚 ~0.5-1s：窗口前 4 后 2 容忍 ±2s，可接受，用几次即适应
- continued 事件暂无页面内人工锚能力（时间轴不归零，换算不可行）——明示提示 + 机器锚兜底，属刻意边界
- `work/_chk/anchor_test*` 为本次实测一次性产物，不入库
