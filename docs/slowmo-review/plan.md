# Plan: 标注页慢放视角（spec: docs/slowmo-review/spec.md）

1. `gen_review_clips.py`：抽 `cut_slow_clip()`（复用 cut_wide_clip 的滤镜组装，
   参数：窗口 ±1.5s、setpts*2.0、fps=30、-an）；`--slow-clips` 选项接入 main；
   events_index 写 `clip_slow`（相对 out_dir 路径）
2. `tests/test_gen_review_clips.py`：补纯函数测试（slow 滤镜串参数、index 字段）
3. `gen_label_page.py`：模板加「慢放 (S)」按钮 + S 键 + 三视角切换逻辑
   （wide/slow 两个布尔态 → 单 state 字段：crop|wide|slow）
4. `tests/test_gen_label_page.py`：补 S 控件存在性断言
5. 质量门：ruff format/check + pytest -q 全绿
6. 批次 2 启用：`gen_review_clips --slow-clips` 重跑（或增量补 slow 片段）
   → `gen_label_page` 重新生成 → 通知立哥
7. spec-reviewer 审 spec 与最终 diff；git 提交（立哥确认后）
