# Todo: event-split

- [x] T1 cluster_candidates 空间约束 + 时长上限（单测先行 + 真实数据对比）——commit db88a6e + 19c3276，审查 Approved；第六人 294→216 事件，16 组跨场地案例 100% 切开，trial 片段在 `dist/basketball-clip/work/_event_split_trial/` 待立哥过目
  - Acceptance: spec.md 设计 4 条全落实；第六人目击案例被切开、补篮不拆；单测 5 条全绿；存量不破
  - Verify: `C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m pytest -q`；ruff 全绿；临时目录新旧事件清单对比表
  - Files: `scripts/gen_review_clips.py`、`tests/test_gen_review_clips.py`
- [ ] T2 立哥过目后重出正式 review_batch1（含 10 对 406~726px 疑似镜头误切抽样定夺，O1 阈值定稿）
  - Acceptance: 立哥确认效果；正式片段重出，标注页可用
  - Verify: 标注页打开新片段正常
  - Files: 无（操作类）
