# Todo: 进球人识别（plan: docs/scorer/plan.md）

- [x] T1: scripts/roster.py 契约模块 + tests/test_roster.py
  - Acceptance: roster schema 校验（缺 players/tag 重复/team 非法/键格式错 → SchemaError）；
    format_key 双端一致（4.1234→"4.1"）；fid_of 去扩展名；resolve_scorer 命中 tag 或 name
  - Verify: pytest tests/test_roster.py 全绿
  - Files: scripts/roster.py, tests/test_roster.py（S）

- [x] T2: scripts/crop_scorers.py 投篮者定位 + 裁图 + tests
  - Acceptance: 合成 mot_cache 下 IoU 链关联正确、投票众数胜出、并列取更近；
    有效票 <2 → SKIP（含 anchor<1.5s）；裁图外扩 20%、短边 ≥400px；
    CLI（--goals/--detectdir/--framesdir/--out）产出 crops + scorer_candidates.json
  - Verify: pytest 全绿；批次 1 goals.json 实跑 17 球出图无炸
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py（M）

- [x] T3: 颜色分队 + 批次 1 实跑验收
  - Acceptance: 采样区=水平中 60%×垂直 25~60%；HSV 双阈三分类、近阈归便服；
    阈值按 17 张实裁图标定并注释来源；scorer_candidates.json 含 team_guess 字段
  - Verify: pytest 全绿；立哥抽查 ≥3 张裁图是投篮者、颜色分布合理（Checkpoint 1）
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py（M）

- [ ] T4: scripts/gen_scorer_page.py 认人确认页 + tests
  - Acceptance: 每球显示片段+裁图+预填（颜色/号码）；球员按钮（--players）或
    自由文本（无名单）；SKIP 球标"无法定位"仍可手选；导出 roster.json
    （format_key 用 roster.py，默认输出 <scorer_candidates.json 同目录>/scorer.html）；
    --roster-existing 并集合并、同键冲突退出 1；进度存 localStorage
  - Verify: pytest 全绿；页面可开、可导出、build_highlight 能读导出物
  - Files: scripts/gen_scorer_page.py, tests/test_gen_scorer_page.py（M）

- [ ] T5: build_highlight.py 真值表改造 + tests
  - Acceptance: 分支全实现（①无 roster 无过滤=全员现状不变；②无 roster 给 --scorer=
    goals.scorer 精确匹配+0 命中 WARNING；③有 roster 无过滤=全归属球（未归属 WARNING 跳过）；
    ④--scorer 解析 tag|name、输出名用解析后 tag；⑤--team 出 队伍_{team}_进球集锦.mp4；
    ⑥--scorer+--team 互斥退出 1；⑦无 roster 给 --team 退出 1；
    ⑧--team 便服 退出 1；--roster 未 confirmed=true 拒收退出 1）
  - Verify: pytest 全绿（分支逐一覆盖）；git status 无 gen_review_clips/gen_label_page
    改动、无 work/20260722/review_batch2/ 写入（Checkpoint 2）
  - Files: scripts/build_highlight.py, tests/test_build_highlight.py（M）

- [ ] T6: 批次 1 端到端试点
  - Acceptance: 17 球裁图→确认页→立哥确认导出 roster.json→--scorer/--team 出合集；
    合集进球数与归属数一致；SKIP 未归属 WARNING 不阻塞
  - Verify: 立哥验收个人+分队合集（Checkpoint 3）
  - Files: 无新代码（work/20260722/scorers/、roster.json、output/20260722/）

- [ ] T7（可选，先问立哥）：号码识别试点
  - Acceptance: --read-numbers 走 number_cache.json 幂等；≤20 次调用；预填准确率告知立哥
  - Verify: 缓存命中不重复扣费；立哥拍板是否常态启用
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py（S）

- [ ] T8: 收尾
  - Acceptance: spec-reviewer 审 plan/todo/最终 diff；AGENTS.md 状态同步；git 提交（立哥确认）
  - Verify: ruff+pytest 全绿；立哥确认提交
