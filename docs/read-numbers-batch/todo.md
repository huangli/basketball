# Todo: 读号默认开 + 确认页一键全收号码预填

- [x] Task 1: video.py people parser 加 --no-read-numbers（store_false，
  与 --read-numbers 同 dest），两条之后 pp.set_defaults(read_numbers=True)
  - Acceptance: 改动仅限 parser add_argument 区域；老命令 `--read-numbers`
    显式传仍生效；缺省 True 由 set_defaults 保证（非 add_argument default
    参数——argparse 先注册者胜出，review01 B1）✅ 行内注释已写明
  - Verify: pytest -q -k video 全绿；git diff 复核仅限该区域 ✅
  - Files: scripts/video.py, tests/test_video.py（只新增 people 用例，
    不改既有 build 用例）
- [x] Task 2: Phase 1 单测 + 质量门 + 提交（commit 4c54f4e）
  - Acceptance: 缺省 read_numbers=True（test_read_numbers_default_on）；
    --no-read-numbers → False（test_no_read_numbers_disables）；
    build_people_steps 默认 argv 含 --read-numbers 与 --max-reads=confirmed×3，
    关闭时两者均不出现 ✅（既有 test_three_steps_verbatim /
    test_rawdir_from_state 按新默认口径适配）
  - Verify: ruff format/check + pytest -q 全绿；people --dry-run 实跑：
    默认含 `--read-numbers --max-reads 147`（b2 confirmed 49×3），
    --no-read-numbers 时零旗标 ✅
- [x] Task 3: gen_scorer_page _HTML 加「接受全部号码预填」按钮 + JS
  - Acceptance: 仅 prefill_tag 非空且未 touched 的球写入 marks；不写
    touched；歧义/SKIP 不动；alert 报"已接受 N（歧义 X / 已手改 Y 跳过）"
    ✅（外加幂等：已是该预填不重复计数）
  - Verify: pytest -q -k scorer_page 全绿（TestAcceptAllPrefills 3 用例：
    按钮渲染+handler、守卫口径锁定含"不写 touched"反向断言、node --check）✅
  - Files: scripts/gen_scorer_page.py, tests/test_gen_scorer_page.py
- [x] Task 4: Phase 2 质量门 + 提交（commit f1b4d3d）
  - Acceptance: 四类球（号码预填/歧义/SKIP/已手改）逻辑由单测守卫口径锁定；
    实页手工清单待立哥下次跑 people（b2/b3）时过一遍
  - Verify: ruff+pytest 全绿 ✅
- [x] Task 5: 使用手册.html 同步（读号默认开/适用前提/token 成本/新按钮；
  仅动 people/认人小节与速查表 people 行）✅
  - Verify: 浏览器打开手册目检对应小节
  - Files: 使用手册.html
- [x] Task 6: 调研依据归档 research.md（随四件套 commit 已入库）+
  经验教训.md §3 补记跨批聚类继承证伪 ✅
  - Files: docs/read-numbers-batch/research.md, docs/经验教训.md
- [ ] Task 7: 四件套收尾 + 提交（review 由独立 spec-reviewer 子代理产出后
  归档为 docs/read-numbers-batch/reviewNN.md，按轮次编号递增）
  - 遗留验收项：Task 4 实页手工清单（四类球点一次按钮的 marks 落位）由立哥
    下次跑 people（b2/b3）时实页过一遍
  - Verify: 文档过 spec-reviewer 无阻断问题
