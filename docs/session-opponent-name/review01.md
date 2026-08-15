# Review 01: 对手队名会话化三件套审查（第 1 轮）

日期：2026-08-15
对象：docs/session-opponent-name/{spec,plan,todo}.md（初版）
审查人：spec-reviewer 子代理（对照 scripts/{roster,gen_scorer_page,build_highlight,video}.py、
tests/ 38 处引用、work/20260805_车百鼎 真实数据核查）

## 审查结论：无阻断，5 条非阻断建议全部采纳

| # | 建议 | 处理 |
|---|------|------|
| 1 | test_invalid_team_raises（test_gen_scorer_page.py:175-178）用 team="白队"断言拒收，放宽后必红 | 采纳：plan Task 2 Step 5 点名改为空串/非 str 场景 |
| 2 | team_of_tag/parse_players 签名变更波及不含"地平线"的 5 行调用点（:96-125），21 处口径覆盖不到 | 采纳：Step 5 补"全部调用点补 opp 参数" |
| 3 | load_players_file docstring（:632）旧枚举口径过时 | 采纳：Step 5 顺手改 |
| 4 | 迁移后 python -c import roster 会 ImportError（scripts/ 不在 sys.path） | 采纳：删该命令，用页面生成内部 validate 验证 |
| 5 | roster.py:1 头部引用旧 spec 枚举口径 | 采纳：补"team 取值口径以 session-opponent-name/spec.md 为准" |

## 核查通过项（审查代理确认）

- roster.py / gen_scorer_page.py 行号与现状全部吻合；main 中 session 解析
  （:1176-1181）早于 parse_players（:1205），接线顺序成立
- VALID_TEAMS 全 scripts/ 仅 roster.py 自身引用，可安全删
- build_highlight / video.py 无需改属实（数据驱动；--team 便服拒收系独立
  硬编码 :183，spec 保留；video.py CASUAL_TEAM 在 :54）
- className 三处（:261/:410/:425）数量正确；38 处测试引用统计精确
- 迁移目标数据核实：7 名黑队球员 team="地平线"，预期 migrated 7；
  candidates 自带 session 字段，重生成不传 --session 也能派生车百鼎
- localStorage 键不含队名，重生成页面进度不丢；b3 未跑 people 不需重生成
- 模板 __OPP__ 注入模式与现有 __SESSION__ 链式 replace 一致，
  node --check 测试兜底

## 结论

通过，可进入实施。重点盯非阻断 #1（漏了必红）与 #2（隐形调用点）。
