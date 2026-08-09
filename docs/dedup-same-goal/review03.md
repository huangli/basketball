# review03：标注页同球双 J 自动识别（spec-reviewer 第 3 轮）

审查日期：2026-08-09。审查对象：实施完成后增量——spec.md 成功标准口径修订（2026-08-09）、
scripts/gen_label_page.py 实现、tests/test_gen_label_page.py 新增用例、todo.md Task 勾选回填。
审查方式：只读全文比对 spec.md / review02.md（已审定基准）/ todo.md / rules.md；
逐行核对 gen_label_page.py 与 test_gen_label_page.py 全文件；核实常量来源
gen_review_clips.py:50-53（2.0/4.0）与 import 链（gen_review_clips → extract_frames /
pipe_common 均无模块级副作用）；核读一次性回放脚本 work/dedup_replay_check.py 断言口径。

## 结论：有阻断问题（1 条 spec 表述，已修订；建议项全部采纳）——修订后通过

## 阻断问题（已修订）

1. **spec.md 成功标准新口径字面自相矛盾**。"8 组同球对全部命中分组、0 误分组"与
   "'0 误分组'口径 = 任意两个 confirmed J 不被并入同组"字面冲突：8 组同球对每对恰为
   2 个 confirmed J 且必须同组，按字面定义它们自身即"误分组"，成功标准永不可达。
   → 已修订为"任意两个**不同球**的 confirmed J 不被并入同组（同组 ≥2 J ⇒ 同一球）"。
   该 spec 是二期跨文件识别的设计依据，字面误读会导出相反规则。回放脚本断言②的
   实现口径本来就正确（独立球不与任何其他 confirmed J 同组，pair_keys/triple_keys
   排除同球对），错的仅 spec 文字。

## 核实事实（通过项）

- 口径修订方向自洽：9 例（203006/201624/201818/203810/203544/205108/204554/205834/210126）
  每组恰 1 J、不触发导出确认、无双 J 风险；严格口径会倒逼收紧窗口并危及 8 组同球对
  召回（anchor 差上限 4.2s，对 6s 窗口余量仅 1.8s），修订成立。
- 实现与 spec 方案 3 点逐条相符：①分组规则同 fid、窗口 [anchor−2, anchor+4]、
  传递闭包，常量经 `gen_review_clips.CLIP_BEFORE_SEC/AFTER_SEC` 全模块路径引用，
  本文件同名导出窗口常量（4.0/2.0）未被触碰；②页面组标签"疑似同回合（组 N，共 M 个）"
  组号 %4 轮换色；③exportGoals 前置 confirm：确定=两个球放行 / 取消=同一球阻止，
  与 todo Task 4 映射一致，列出组号+文件名+各 anchor，选择不持久化每次导出都问。
- 传递闭包实现正确：anchor 升序 + 右界 max 更新的标准区间连通合并，含端点。
- build_html 复制 dict 注入 grp/grp_size，不改调用方数据（测试锁定）。
- JS 无回归：断点续标（POSKEY）、W 切换、J/P/F/方向键、save() 合并写均未动；
  导出 schema（file/anchor_time/clip_start/clip_end/status/scorer）逐字段不变。
- 缺字段防御到位：fid/anchor_t0/key 类型校验（含 bool 排除）+ WARNING 跳过。
- 测试质量合格：断言为精确 dict 相等；`'"grp":' not in html` 负断言可靠
  （模板无该子串：`getElementById("grp")` 为 `"grp")`，`"grp_size":` 不含 `"grp":`）。
- todo Task 1/2 回填与实测一致（6 用例 commit dfcf697；回放 234 事件→111 入 48 组、
  8 组全命中、0 漏网双 J、9 例正确提示的口径说明与脚本断言吻合）。

## 建议项（已全部采纳）

- work/dedup_replay_check.py 注释"误标 F 的真球由导出确认框兜底"不成立（confirm 仅在
  同组 ≥2 个 goal 时触发，1 J + 1 F 不弹窗）→ 已修正注释：该场景实际兜底仅组标签
  视觉提示（既有漏标风险，与本功能无关）。
- spec 方案 2"同色边框"与实现（单事件翻页器有色文字标签）不符 → spec 已同步为"同色标识"。
- gen_label_page.py 模块 docstring"依赖：仅标准库"过时 → 已更新依赖说明。
- 缺字段跳过 + WARNING 分支无单测 → 已补 test_groups_skips_events_missing_fields
  （3 条残缺事件跳过 + WARNING 计数 + 合法事件正常成组）。
- todo Task 3/4 人工验收步骤未见完成记录 → 保留待立哥页面级验收（批次 3 label.html
  已按新代码重新生成备好，session 不变、localStorage 标注记录保留），验收后回填。

## 处置

阻断问题修订完毕，建议项全部采纳，本件通过。功能交付状态：代码完成、关口全绿、
回放验证 PASS；待立哥页面级验收（组标签呈现 + 同组 2 J 弹窗两条路径）。
