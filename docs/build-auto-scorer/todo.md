# Todo: build 认人可选化（颜色分队集锦 + 自动个人合集）

依据 `docs/build-auto-scorer/spec.md` + `plan.md`。按依赖序执行，逐项验收。
（2026-08-22 口径变更：默认产物不含全员集锦，改按球衣颜色分队出队伍集锦；
T2 的 ①改名撤销，T3/T4 相应修订为 R 轮任务。）

- [x] T1 build_highlight 真值表⑨ `--per-goal`
  - Acceptance: `--per-goal` 每 confirmed 球独立出 `output/<场次>/进球片段/NNN_<主名>@<t:.1f>s.mp4`
    （目录自建）；NNN 按全部 confirmed 球时序编号、原片缺失跳号保留（编号=进球序号，稳定不 compact）；
    与 --scorer/--team/--roster 互斥报错；同名产物幂等跳过；
    部分原片缺失出完能出的 exit 1；模块 docstring 组合真值表同步加⑨（rules.md 契约）
  - Verify: `pytest tests/test_build_highlight.py -k per_goal`
  - Files: scripts/build_highlight.py、tests/test_build_highlight.py
- [x] T2 build_highlight 真值表⑩ `--allow-unconfirmed`（①改名已撤销，见 T2R）
  - Acceptance: ⑩ = 仅豁免 require_confirmed 的闸门旗标（逐簇/逐队分组归 video.py
    循环 --scorer/--team）；未 confirmed roster + 旗标 → 放行；无 --roster 给旗标 → 报错；
    无旗标显式 --roster 未确认仍拒收；模块 docstring 组合真值表同步加⑩
  - Verify: `pytest tests/test_build_highlight.py`
  - Files: scripts/build_highlight.py、tests/test_build_highlight.py
- [x] T2R 撤销①改名（口径变更返工）
  - Acceptance: ① stem 恢复 `个人_全员_进球合集`（初稿误改为 `全员_进球集锦`）；
    ③ 同名不动；docstring 真值表去掉①改行；相关测试断言恢复
  - Verify: `pytest tests/test_build_highlight.py`
  - Files: scripts/build_highlight.py、tests/test_build_highlight.py
- [x] T3R auto_roster.py 加颜色分队（口径变更返工）
  - Acceptance: 新增 `--candidates`（可重复）读各批 scorer_candidates.json 的
    `team_guess`；簇内多数票定 team（平票取首球；缺 team_guess 不计票；
    全簇无票归"便服"）；players 的 team 从固定"球员"改为多数票队别；
    坏 candidates schema → SchemaError；原有用例按新 team 语义调整
  - Verify: `pytest tests/test_auto_roster.py`
  - Files: scripts/auto_roster.py、tests/test_auto_roster.py
- [x] T4R video.py 自动模式改三产物链（口径变更返工）
  - Acceptance: 删除全员集锦步骤；产物链 = ① --per-goal → ② crop → ③ cluster →
    ④ auto_roster（带 --candidates）→ ⑤ 逐颜色队 --team（便服除外、零命中跳过）→
    ⑥ 逐簇 --scorer → ⑦ 热图跳过；识别链失败 ERROR 留痕退出 1、① 保留；其余 T4 口径不变
  - Verify: `pytest tests/test_video.py`
  - Files: scripts/video.py、tests/test_video.py
- [x] T5R 文档再同步（口径变更返工）
  - Acceptance: AGENTS.md 合集口径行、使用手册.html（命令卡/第 4 步/命令表/文件位置/
    成品规格命名行）改为"队伍集锦（颜色分队）+进球片段+自动个人合集"口径；
    主文档 :86 注记改为"① 旧名维持"；`全员_进球集锦` 无残留引用
  - Verify: `grep -rn 全员_进球集锦 AGENTS.md 使用手册.html docs/` 无命中（本目录四件套说明除外）
  - Files: AGENTS.md、使用手册.html、docs/2026-07-26-current-goal-detection-pipeline.md
- [x] T6 spec-reviewer 审查 + 全量关口 + 真机抽验 + 提交
  - Acceptance: review02.md 归档（口径变更轮）且阻断问题清零；
    ruff format/check + pytest -q 全绿；真机抽验 20260813_淳化街道 `video build`
    出齐三类产物 exit 0 且无 `全员_进球集锦.mp4` 新产出；按逻辑改动提交
  - Verify: 关口命令全绿 + `ls output/20260813_淳化街道/`
  - Files: docs/build-auto-scorer/review02.md、git commit
