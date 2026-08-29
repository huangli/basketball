# todo：热图落点飞行段链接修复（heatmap-flight-link）

- [x] 1. spec 审查通过（plan 代理代行 spec-reviewer 职责：1 阻断 B1 + 建议 S1~S6 已全部修订）
- [x] 2. 测试先行 A：tests/test_mot_candidates.py（飞行碎裂/放宽链接/默认回归）
- [x] 3. 实现 run_mot max_match_dist 参数（A 组转绿）
- [x] 4. 测试先行 B：select_goal_track prefer_longer 五例（滑窗内选长轨/滑窗外选碎片/池内全超界 None/时间分支两例）
- [x] 5. 实现 select_goal_track prefer_longer + docstring（B 组转绿）
- [x] 6. 测试先行 C：find_landing 飞行段三例（C1 锁 max_match_dist 接线、C2 锁 prefer_longer 接线、C3 锁 anchor_xy 落空回退）
- [x] 7. 实现 goal_heatmap find_landing 接入 + params 键 + docstring（C 组转绿）
- [x] 8. 关口全绿：ruff format / ruff check --fix / pytest -q
- [x] 9. 实场验证：citymonkey 覆盖率 45.7%→85.7%（≥55% 过关），no_landing 19→5，目击拼图机检无异常（终裁权在立哥）
- [x] 10. review01.md + docs/heatmap/spec.md 加 v4.3 指针
- [ ] 11. git commit（中文 conventional，只 commit 不 push）
