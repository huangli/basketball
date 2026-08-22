# Review 02：口径变更轮（颜色分队集锦）双代理审查

- 日期：2026-08-22
- 轮次：口径变更返工（T2R/T3R/T4R/T5R）—— 默认产物从"全员集锦"改为"按球衣颜色分队
  （黑/白，便服不出）的队伍集锦 + 进球片段 + 自动个人合集"
- 审查方式：两个独立子代理并行审查（spec 一致性审查 + 代码审查），结论已统一

## 结论

**两方均无阻断问题，APPROVE。** 多数票/平票/缺票语义正确且有测试锁定；便服过滤与
零命中预算不会漏出或误出合集；识别链失败路径退出码与"① 进球片段保留"承诺成立；
dry_run 覆盖全链；无静默吞异常、无魔法值；旧口径断言已全部改写无残留。

## 建议项处置（5 条，全部非阻断）

| # | 来源 | 内容 | 处置 |
|---|---|---|---|
| 1 | spec 审查 | build_highlight.py:29 docstring 真值表 spec 指针未覆盖⑨⑩出处 | 已修：指针分行标注 ①-⑧ / ⑨⑩ 各自 spec |
| 2 | spec 审查 | tests/test_build_highlight.py:476 注释"team=球员"过时 | 已修：注释改为说明"球员"系历史合法值、不断言语义 |
| 3 | spec 审查 | 成功标准未覆盖"全部批次缺 candidates"第三态 | 已修：spec.md 成功标准新增第 3 条（仅出进球片段 exit 0 合法） |
| 4 | 代码审查 | "平票且首球无票"场景未测，docstring 字面与实现有细微差别 | 已修：docstring 口径改为"平票取簇内最早有票球的队别"（auto_roster.py 模块头 + cluster_team + spec.md:80 三处同步），行为不变、不再字面误导 |
| 5 | 代码审查 | "便服"字面值三处独立定义（video.py / auto_roster.py / crop_scorers.py） | 接受现状：三处均命名常量带互相引用注释，错配时被真值表⑧拒收显式失败而非静默错；第四处出现时再收敛到 roster.py |

## 通过项摘录（逐项核对）

- spec/plan/todo 三件套口径互洽且与代码一致；链 ①--per-goal→②crop（幂等）→③cluster
  （complete/0.15）→④auto_roster（--candidates）→⑤逐颜色队 --team（便服除外、零命中跳过）
  →⑥逐簇 --scorer→⑦热图跳过，与 video.py:794-1006 逐步对应
- ① stem 恢复 `个人_全员_进球合集`（build_highlight.py:241/:254，单测+main 级双锁定）
- cluster_team 平票键 = 票数降序+最早有票球序（auto_roster.py:201），测试含键序反转用例
- 全仓 `全员_进球集锦` 残留仅在本目录四件套的说明性/历史文字中（允许范围）
- 失败路径：②-④ 失败 identify_ok=False → ERROR + exit 1；⑤⑥ 单步失败 ERROR + exit 1；
  ① 失败中止 exit 1；④ 报成功但产物缺失 exit 1（测试锁定）
- rules.md：schema 损坏全程显式失败（含 cluster_id 为 bool 的 Python 陷阱显式排除）

## 遗留（不属本轮）

- todo T6 剩余：全量关口复核、真机抽验 20260813_淳化街道、提交。
- output/20260813_淳化街道/ 内初版真机产物 `全员_进球集锦.mp4` 与 `_clips_tmp/` 残留，
  由立哥手删（output/ 产物不主动清理）。
