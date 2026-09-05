# Todo: GUI 检测百分比进度

- [ ] T1 runner 协议 v1.1 + 测试 + 前端百分比
  - Acceptance: frame_progress 事件按 spec 口径发出；前端检测步显示"约 N%"；非检测任务行为不变；scripts/ 零改动
  - Verify: `C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m pytest -q` 全绿（含新用例）；ruff 全绿；浏览器冒烟截图；git diff 确认 scripts/ 未触碰
  - Files: `gui/runner.py`、`gui/static/app.js`、`tests/gui/test_runner.py`
- [ ] T2 .gitignore 加测试素材目录（chore）
  - Acceptance: `20260829第六人/` 被忽略，git status 不再出现
  - Verify: `git check-ignore -v 20260829第六人` 命中
  - Files: `.gitignore`
