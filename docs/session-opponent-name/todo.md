# Todo: 对手队名会话化

## Task 1: roster.py team 校验放宽

- [x] 改测试（新口径：车百鼎过 / 空串非 str 拒）确认 RED
- [x] 删 VALID_TEAMS + player_from_dict 校验改非空 str + docstring 更新
- [x] GREEN + 质量门
- [x] Commit

## Task 2: gen_scorer_page 队名动态化

- [x] 新单测 TestOpponentOf（后缀/无后缀回退/空白回退）确认 RED
- [x] Python 侧：opponent_of + team_of_tag(tag, opp) + parse_players/build_html/main 接线
- [x] 模板：CSS 语义类 + const OPP 注入 + teamClass + 三处 className + 队分行顺序
- [x] 测试 21 处口径更新 + 新模板断言
- [x] GREEN + 质量门
- [x] Commit

## Task 3: 迁移 + 重生成 + 手册 + 收尾

- [x] roster_20260805_车百鼎.json 备份 .bak + 迁移 地平线→车百鼎 + validate 过
- [x] b1/b2 认人页重生成，grep 验证 `const OPP = "车百鼎"`、无地平线
- [x] 使用手册.html 认人节补口径
- [x] todo 勾完 + 质量门终跑 + Commit
