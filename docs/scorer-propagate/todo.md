# Todo: 认人提效二期——轨迹传播 + 离线读号

- [x] Task 1: crop_scorers entry 落 seed_frame/seed_box/seed_team（可选字段，
  SKIP 不落；种子帧单次解码复用；解码失败记 decode_failed）
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py
- [x] Task 2: propagate_scorers.py 贪心跟踪器 + 颜色守卫 + 进球映射 +
  track_links.json（candidates 只读）
  - Files: scripts/propagate_scorers.py, tests/test_propagate_scorers.py
- [x] Task 3: 传播来源（自身不算源/冲突不预填/NOGOAL 不作源）+ --evaluate
  报表（roster-seeded 主 + number-seeded 副；纯函数可测）
- [x] Task 4: Phase 1a 质量门 + 提交（9e3ecce；过 code-reviewer：R1 颜色守卫
  按帧去重 + N1~N3 已修，1042 绿）
- [x] Task 5: gen_scorer_page --track-links（传播预填：无 marks+无 prefill_tag+
  未 touched 才写、NOGOAL 不传播、徽标、acceptAll/E 键隔离、无参兼容）+
  提交 Phase 1b（451ec1f，1068 绿）
- [x] Task 6: video.py people 接线（裁图→传播→聚类→确认页；--track-links
  预传+执行时探测剥离）+ 提交 Phase 1c（a285977，1102 绿）
- [x] Task 7: offline_number.py（预处理+切字+模板匹配+自举对齐规则+
  offline_number_cache.json 隔离缓存，K3 链路零感知）
  - Files: scripts/offline_number.py, tests/test_offline_number.py
- [x] Task 8: Phase 2 质量门 + 提交（e75b035）；跳票模式接入等 Task 10 达标后做
- [ ] Task 9【挂起·等新场次 confirmed roster】：--evaluate 实跑标定
  （≥90% / ≥1.5，守卫参数最多 3 档），结果记 review02
- [ ] Task 10【挂起·同前置】：离线读号对照实跑，一致率 ≥70% 留 / <70% 砍，
  结论记 review02
- [x] 收官：AGENTS.md + 使用手册.html 更新 + spec-reviewer（通过，采纳 2 条
  表述精确化建议）+ 提交
