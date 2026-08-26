# todo：标注页 J 键人工锚点（goal-anchor）

- [x] 1. gen_review_clips：events_index 加 `clip_src_start`（round 0.1，复用 `start` 变量）与 `continued`（cut_cluster_clip/cut_wide_clip 透出 plan_clip_segments 标志）
- [x] 2. gen_label_page：模板注入 `__SPEED__`；mark 支持 anchor（存入即 round 0.1）；J 键与进球按钮同路径捕锚；T 机器锚兜底；旧索引缺字段 / continued 事件 J 退化（continued 进度行提示）
- [x] 3. gen_label_page：导出换算（人工锚优先，窗口 anchor∓4/2；同组确认框优先显示人工锚）；进度行锚点显示；按键帮助更新；模块 docstring 同步
- [x] 4. 测试：events_index 新字段（含 <2s 钳 0、continued 两态）；build_html 注入/透传/旧事件兼容
- [x] 5. 关口全绿：ruff format + ruff check --fix（复核 diff）+ pytest -q
- [x] 6. 实测回放：重生成 20260822_citymonkey review_batch1 events_index + label.html，浏览器验证 J 捕锚/导出/T 兜底/旧索引退化/continued 退化/循环补按
- [x] 7. review01.md 存档（含 spec-reviewer Blocked→修订对照）
- [x] 8. 使用手册.html 快捷键表同步
- [x] 9. git commit（feat: 标注页 J 键人工锚点）
