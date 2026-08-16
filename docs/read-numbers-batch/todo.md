# Todo: 读号默认开 + 确认页一键全收号码预填

- [ ] Task 1: video.py people parser 加 --no-read-numbers（store_false，
  与 --read-numbers 同 dest），两条之后 pp.set_defaults(read_numbers=True)
  - Acceptance: 改动仅限 parser add_argument 区域；老命令 `--read-numbers`
    显式传仍生效；缺省 True 由 set_defaults 保证（非 add_argument default
    参数——argparse 先注册者胜出，review01 B1）
  - Verify: pytest -q -k video；git diff 复核仅限该区域
  - Files: scripts/video.py, tests/test_video.py（只新增 people 用例，
    不改既有 build 用例）
- [ ] Task 2: Phase 1 单测 + 质量门 + 提交
  - Acceptance: 缺省 read_numbers=True；--no-read-numbers → False；
    build_people_steps 默认 argv 含 --read-numbers 与 --max-reads=confirmed×3，
    关闭时两者均不出现
  - Verify: ruff format/check + pytest -q 全绿；people --dry-run 两种参数
    各跑一次看 argv
- [ ] Task 3: gen_scorer_page _HTML 加「接受全部号码预填」按钮 + JS
  - Acceptance: 仅 prefill_tag 非空且未 touched 的球写入 marks；不写
    touched；歧义/SKIP 不动；alert 报"已接受 N（歧义 X / 已手改 Y 跳过）"
  - Verify: pytest -q -k scorer_page；实页 node --check 通过
  - Files: scripts/gen_scorer_page.py, tests/test_gen_scorer_page.py
- [ ] Task 4: Phase 2 质量门 + 实页手工清单 + 提交
  - Acceptance: 四类球（号码预填/歧义/SKIP/已手改）点一次按钮，仅第一类
    落 marks；导出 roster 归属数与 confirmed 计数正确
  - Verify: ruff+pytest 全绿；手工清单逐项过
- [ ] Task 5: 使用手册.html 同步（读号默认开/适用前提/token 成本/新按钮/
  更新日期；仅动 people/认人小节，build 小节不碰）
  - Verify: 浏览器打开手册目检对应小节
  - Files: 使用手册.html
- [ ] Task 6: 调研依据归档 research.md + 经验教训.md 补记跨批聚类继承证伪
  - Acceptance: research.md 含实测数（纯度 49.5%、b2 2/29、b3 1/25、
    阈值 0.06 仍 2/6、0/1）；经验教训.md §2 新增一条
  - Files: docs/read-numbers-batch/research.md, docs/经验教训.md
- [ ] Task 7: 四件套收尾 + 提交（review 由独立 spec-reviewer 子代理产出后
  归档为 docs/read-numbers-batch/reviewNN.md，按轮次编号递增）
  - Verify: 文档过 spec-reviewer 无阻断问题
