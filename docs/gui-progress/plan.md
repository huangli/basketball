# Plan: GUI 检测百分比进度

> 依据 spec.md（本目录）。单任务体量，plan 从简。

## 实施步骤

1. **runner 协议 v1.1**（gui/runner.py）：三个解析规则——`=== <fid> (<N>帧) ===` 注册分母、"命中缓存"行标记 fid 完成、`第(\d+)/(\d+)帧` 更新当前帧；`frame_progress` 事件（fid/frame/total_frames/overall_pct，overall_pct 单调不减裁剪）。
2. **测试先行**（tests/gui/test_runner.py）：帧进度事件字段与计算、单调不减、无帧行不发事件、**缓存命中 fid + 新检 fid 混合**（续跑口径）。
3. **前端**（gui/static/app.js）：检测步进度区显示"约 N%"与 fid x/y；无帧进度维持不定态。
4. **浏览器冒烟**：注入帧进度日志验证渲染。
5. **顺手 chore**：新仓 .gitignore 加 `20260829第六人/`（立哥的发布前测试素材，防误提交），独立小 commit。

## 验证点

- 单测全绿（含新用例）+ 存量 1088 不破
- 冒烟截图
- git grep 确认 scripts/ 零改动

## 风险

| 风险 | 对策 |
|---|---|
| 分母逐步并入致百分比跳变 | 事件侧单调不减裁剪 |
| 其他含"第x/y帧"字样的日志误匹配 | 正则锚定 mot_candidates 实际格式（含 fid 前缀语境），单测覆盖 |
