# Todo: opponent-prefill

- [x] T1 黑球衣自动对手预填 + 一键全收——commit cf4c5b7，审查 Approved
  - 实现：show() 提示分支"对手预填：黑"（优先于颜色预填）；黑候选球按钮"接受对手预填"；
    acceptopp 按钮 + acceptAllOpponent（只写未归属未手改黑候选、不标 touched、幂等、
    已归属他队不覆盖）；预填不写 marks（人终裁红线）
  - 测试：TestOpponentPrefill 5 条（提示/按钮文案/批量函数/预填不写 marks/node 语法）
  - Verify: pytest 1134 全绿；ruff 全绿
  - Files: `scripts/gen_scorer_page.py`、`tests/test_gen_scorer_page.py`
- [ ] T2 立哥实机验证（重打 dist 后：黑球衣球自动出预填，一键全收后翻检）

> 实施备注：主会话亲自实施 + 独立审查员审查（子代理配额波动期）。
> 审查非阻断观察：acceptAllOpponent 比 acceptAllPrefills 多"已归属他队不覆盖"守卫，
> 两者批量口径后续可统一（本 spec 文字自洽，不算违规）。
