# Review 03: 读号默认开 + 确认页一键全收号码预填（实施终审）

> 2026-08-16，独立审查员。审查对象：commit 4c54f4e（Phase 1）、f1b4d3d（Phase 2）、
> 未提交的 Phase 3 文档改动（使用手册.html / 经验教训.md / todo.md）。
> 对照 spec.md（review02 闭环版）契约逐条核验，质量门与 dry-run 由本审查员独立重跑。
> 只读审查，未改动任何文件。

## 整体评价

功能实现与 spec 契约高度一致：argparse 四态、dry-run 预算注入、批量接受守卫/不标
touched/alert X/Y 口径/幂等全部实测命中；test_video.py 适配守住「不改 build 用例」
红线；手册措辞与行为一致。**但质量门并非全绿**——f1b4d3d 引入一处 E501 超长行，
`ruff check` 当前红灯，与「ruff 全绿」的验证声称不符，须修复后方可收尾提交。

## 独立验证记录（审查员亲测，非转述）

| 项 | 结果 |
|---|---|
| `pytest -q` | exit=0 全绿 |
| `ruff format --check scripts tests` | 47 files already formatted ✓ |
| `ruff check scripts tests` | **1 error（见 B1）** ✗ |
| parser 四态（default / --no / 显式 / 双传） | True / False / True / False（双传后者胜出）✓ 与 spec Open Questions 2 锁定一致 |
| dry-run 默认（b2） | 带 `--read-numbers --max-reads 147`（confirmed 49×3）✓ |
| dry-run `--no-read-numbers` | 零读号旗标 ✓ |
| `git show 4c54f4e` scripts/video.py | diff 仅 people parser 参数区（含 set_defaults 与 B1 语义注释）✓ |
| `git show 4c54f4e` tests/test_video.py | 改动全部在 TestPeople 类内；test_three_steps_verbatim / test_rawdir_from_state 属 people 用例适配，未触碰 build 用例 ✓ |
| f1b4d3d JS 守卫 vs spec 契约 | prefill_tag 非空 + `!touched` ✓；不写 touched ✓；X=ambiguous 计数、Y=prefill 非空且 touched ✓；幂等（已是该预填不重复计数）✓；save()+show(cur) ✓；无快捷键、picker 零改动 ✓；按钮在 #accept 旁初始显示 ✓ |
| 手册 diff | 仅 people 小节 + 速查表 people 行；默认开/token ≤进球数×3/缓存幂等/预填非终裁/歧义与无法定位跳过，措辞与实施一致 ✓ |

## 阻断问题

### B1. f1b4d3d 引入 E501 超长行，`ruff check` 红灯

- 位置：`scripts/gen_scorer_page.py:144`（新增 `#acceptall` 按钮行，129 > 100 字符）。
- 实测输出：

  ```
  E501 Line too long (129 > 100)
     --> scripts\gen_scorer_page.py:144:67
  ```

- 违反：rules.md §1「单行 ≤ 100 字符（中文按字符计）」；AGENTS.md「代码改动须先过
  lint/format/test 关口全绿」再提交——f1b4d3d 是带红灯入库的，实施方「ruff
  format/check、pytest -q 全绿」的声称不属实（format 绿、check 红）。
- 修法：拆行（HTML 标签属性跨行书写，`_HTML` 是三引号字符串，直接换行即可）或精简
  title 文案至行内 ≤100 字符；修后重跑 `python -m ruff check scripts tests` 确认
  0 error，随 Phase 3 文档一起提交。

## 建议改进

### S1. 经验教训.md 补记落点与验收口径不一致

- todo Task 6 Acceptance 写「经验教训.md §2 新增一条」，AGENTS.md 指引「已证伪清单
  与依据见 docs/经验教训.md §2（机器裁判已证伪）」；实际补记落在 §3（认人流程，
  :112 区域），且 todo 已勾 ✅。
- 跨批聚类继承证伪属典型「已证伪方向」，放 §3 虽主题相关，但未来按 AGENTS.md 指引
  查 §2 会漏掉它。
- 修法（二选一）：把该条移到 §2；或保留 §3 落点并同步修订 todo 口径与 AGENTS.md
  指引文字。推荐前者。

## 可选优化

- O1. 覆盖顺序语义可提示：簇级选人（`clusterAssign`）不标 touched，若立哥先并簇
  再点「接受全部号码预填」，号码预填会覆盖簇级预填。spec 契约写死如此、实施符合
  spec，不算偏差；但手册可在新按钮说明里补一句操作建议（先点全收，再并簇/逐球调整）。
- O2. Task 4 实页手工清单推迟到下次实跑 people 时过——spec 成功标准 3（四类球实页
  验收）仍悬置，属流程安排而非缺陷；建议 Task 7 收尾提交前在 todo 里显式保留该
  待办提示，避免四件套关闭后遗忘。

## 与 AGENTS.md 冲突对照表

| 项 | AGENTS.md 原文 | 实施现状 | 判定 |
|---|---|---|---|
| 提交前质量门全绿 | 「代码改动须先过 lint/format/test 关口全绿」 | f1b4d3d 提交时 ruff check 红（B1） | **冲突**（已由 B1 覆盖，修复即消解） |
| 已证伪集中索引 | 「已证伪清单与依据见 docs/经验教训.md §2」 | 新证伪补记在 §3 | 边角偏差（见 S1） |
| CLI 行为变更同步手册 | 「CLI 行为变更时同步更新 使用手册.html」 | 已同步且措辞一致 | 无冲突 |
| 机器排序 + 人裁判 | 自动剔除长期关闭、终裁在人 | 批量接受走按钮不自动执行、不标 touched | 无冲突 |
| 只 commit 不 push | — | 两 commit 本地，未 push | 无冲突 |

## 结论

**需修订**（阻断 B1：质量门红灯）。修复 E501 并（建议）落实 S1 后，Phase 3 可收尾
提交；其余实施质量高，契约兑现完整。
