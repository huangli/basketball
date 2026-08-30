# Todo: 视频封面生成（cover-gen）

- [x] Task 1: gen_covers.py 核心（抽帧 clamp + 等比充满中心裁 1080×1440 + 叠文字 + 网格；filters/自动模式；load_font 回退）
  - Acceptance: tests/test_gen_covers.py 用例 1-10 全过
  - Verify: `pytest tests/test_gen_covers.py -q` → 11 passed
  - Files: scripts/gen_covers.py, tests/test_gen_covers.py
- [x] Task 2: video.py 加 covers 子命令（无过滤=--all；自动模式只出颜色队；多批 merge/--batch）
  - Acceptance: `video covers --session <场次>` 直跑通；test_video.py covers 回归用例
  - Verify: `pytest tests/test_video.py::TestCovers -q` → 3 passed；全量 suite 退出码 0
  - Files: scripts/video.py, tests/test_video.py
- [x] Task 3: 关口全绿
  - Verify: `ruff format scripts tests && ruff check --fix scripts tests && pytest -q` → 全过
- [ ] Task 4: 实机验证 20260822（--team 半截篮 出候选+sheet；--scorer 半截篮6 出个人合集封面）
  - Verify: 抽查封面 1080×1440、文字可见、无黑边（黄立单张已验；队伍集锦后台跑完后核）
- [x] Task 5: 文档同步（使用手册.html covers 行）+ docs/cover-gen 四件套过 spec-reviewer
  - Verify: 审查通过（review01/review02 无阻断）
- [ ] Task 6: git commit（feat，中文 conventional，不 push）
