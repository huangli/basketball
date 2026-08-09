# Todo: 认人提效——轨迹选帧多裁 + CLIP 聚类逐人确认

- [ ] Task 1: 人框 IoU 链 trace_person
  - Acceptance: 合成 persons 序列链上/链断/多人交叉三种情形断言正确
  - Verify: pytest -q -k trace_person
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py
- [ ] Task 2: 质量选帧 + 多裁落 entry（--best-crops 默认 3）
  - Acceptance: entry 含 crops/crop_scores；crop==crops[0]；间隔 ≥0.5s；旧数据兼容
  - Verify: pytest -q -k best_crops；scorers_b3 实跑抽 5 球目检
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py
- [ ] Task 3: Phase 1 质量门 + 提交 Phase 1
  - Verify: ruff format/check + pytest -q 全绿
- [ ] Task 4: cluster_scorers embedding + 缓存（key=model+裁图 md5）
  - Acceptance: clip_cache.json 断点续跑不重复推理；坏 candidates 抛 SchemaError
  - Verify: pytest -q -k cluster
  - Files: scripts/cluster_scorers.py, tests/test_cluster_scorers.py
- [ ] Task 5: 聚类 + scorer_clusters.json + --evaluate（--candidates 重复传参
  合并三批次；evaluate 只统计 roster assignments 的键）
  - Acceptance: 输出契约符合 spec；--evaluate 报簇数/纯度
  - Verify: pytest -q -k cluster；实跑三批次合并
  - Files: scripts/cluster_scorers.py, tests/test_cluster_scorers.py
- [ ] Task 6: Phase 2 质量门 + 阈值标定（0.20/0.25/0.30 最多 3 档，
  不达标走降级出口）+ 提交 Phase 2
  - Verify: 全绿；标定结果记 review01
- [ ] Task 7: gen_scorer_page --clusters 簇级确认
  - Acceptance: 簇区选人应用全簇；逐球覆盖；无 --clusters 行为不变
  - Verify: pytest -q -k scorer_page
  - Files: scripts/gen_scorer_page.py, tests/test_gen_scorer_page.py
- [ ] Task 8: Phase 3 质量门 + 实页目检 + review01 存档 + 提交 Phase 3
  - Verify: 全绿；四件套齐
