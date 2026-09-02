# Todo: 认人提效二期——轨迹传播 + 离线读号

- [ ] Task 1: crop_scorers entry 落 seed_frame/seed_box/seed_team（可选字段，
  SKIP 不落）
  - Acceptance: OK 球 entry 含三字段；消费方对缺字段旧数据不炸
  - Verify: pytest -q -k seed
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py
- [ ] Task 2: propagate_scorers.py 贪心跟踪器 + 颜色守卫 + 进球映射 +
  track_links.json（candidates 只读）
  - Acceptance: 合成序列覆盖链上/断轨封存/同帧竞争唯一性裁决/便服不计数/
    mixed 标记；seed 缺失 WARNING 进 unlinked
  - Verify: pytest -q -k propagate
  - Files: scripts/propagate_scorers.py, tests/test_propagate_scorers.py
- [ ] Task 3: 传播来源（自身不算源/冲突不预填/NOGOAL 不作源）+ --evaluate
  报表（roster-seeded 主 + number-seeded 副；分母口径写死；纯函数可测）
  - Acceptance: 合成轨迹+roster 断言准确率/覆盖倍数计算
  - Verify: pytest -q -k propagate
  - Files: scripts/propagate_scorers.py, tests/test_propagate_scorers.py
- [ ] Task 4: Phase 1a 质量门 + 提交
- [ ] Task 5: gen_scorer_page --track-links（传播预填：无 marks+无 prefill_tag+
  未 touched 才写、NOGOAL 不传播、徽标判定、acceptAll/E 键不收传播、
  无参兼容）+ 实页静态目检 + 提交 Phase 1b
  - Verify: pytest -q -k track；node --check 生成页
  - Files: scripts/gen_scorer_page.py, tests/test_gen_scorer_page.py
- [ ] Task 6: video.py people 接线（裁图→传播→聚类→确认页）+ 提交 Phase 1c
  - Verify: pytest -q -k video
  - Files: scripts/video.py, tests/test_video.py
- [ ] Task 7: offline_number.py（预处理+切字+模板匹配+自举对齐规则+
  offline_number_cache.json 隔离）
  - Acceptance: 合成数字图识别；连通域数≠位数丢弃记 INFO；每数字 ≥3 样本才启用
  - Verify: pytest -q -k offline
  - Files: scripts/offline_number.py, tests/test_offline_number.py
- [ ] Task 8: Phase 2 质量门 + 提交
- [ ] Task 9【挂起·等新场次 confirmed roster】：--evaluate 实跑标定
  （≥90% / ≥1.5，守卫参数最多 3 档），结果记 review02
- [ ] Task 10【挂起·同前置】：离线读号对照实跑，一致率 ≥70% 留 / <70% 砍，
  结论记 review02
- [ ] 收官：review01（第 1 轮修订记录）+ AGENTS.md 认人流程更新 +
  spec-reviewer + 提交
