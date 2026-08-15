# Spec: 对手队名会话化——从场次 ID 后缀自动取，废除硬编码"地平线"

## Objective

现状问题（2026-08-15 立哥指出）：20260805 场次对手是**车百鼎**（文件夹名
`20260805车百鼎` 即说明），但代码把对手队名写死为"地平线"
（20260722 场次的历史口径）：

- `roster.py:29` `VALID_TEAMS = ("地平线", "半截篮", "便服")`——roster 校验
  只认这三个值
- `gen_scorer_page.py` `TEAM_BLACK = "地平线"` + JS `teamOfTag` 同款硬编码 +
  CSS 类名 `.team-地平线` + 队分行顺序写死
- 后果：本场 roster_20260805_车百鼎.json 里黑队球员 team 已被落成"地平线"，
  认人页队分行也显示"地平线"——队名错了

方案（2026-08-15 立哥拍板）：**对手队名 = 场次 ID 第一个 `_` 后的后缀**
（AGENTS.md 约定场次 ID = `YYYYMMDD_对手名`），零配置。不变的前提：
白=半截篮（立哥队）、黑/蓝=对手队、其余=便服。

本功能做四件事：

1. **roster.py team 校验放宽**：team 合法值从三枚举改为任意非空 str
   （"半截篮"/"便服"保留特殊语义：build_highlight `--team 便服` 拒收、
   页面分行；对手队名随场次自由取值）
2. **gen_scorer_page.py 队名动态化**：`opponent_of(session)` 派生对手队名
   （session 含 `_` 取后缀；无后缀回退 "地平线"——老场次 20260722 历史
   兼容，注释注明）；Python/JS 两端 teamOfTag 用派生值；CSS 类名改语义类
   （opp/home/casual，任意对手名可渲染）
3. **数据迁移**：roster_20260805_车百鼎.json players 里 team "地平线" →
   "车百鼎"（一次性命令，不立脚本；output/ 尚未出合集，无下游影响）
4. **页面重生成**：scorers_b1/b2 的 scorer.html 用动态队名重生成
   （localStorage 键不含队名，立哥页面进度不丢）

成功标准：

- pytest 全绿（含新单测：opponent_of 派生/回退、team 校验新口径）
- 迁移后 roster_20260805_车百鼎.json 过 validate_roster，黑队球员
  team=车百鼎
- 重生成的认人页队分行显示"车百鼎"；20260722 口径回退行为有单测锁定
- ruff format/check 干净

## Tech Stack

- Python 3.14 现有栈，零新依赖
- 改动面：`scripts/roster.py`（校验放宽）、`scripts/gen_scorer_page.py`
  （派生函数 + 模板 CSS/JS）、`tests/`（口径更新 + 新单测）
- **不改**：build_highlight.py / video.py（team 均从 roster 数据驱动，
  已天然跟随；video.py 只认 CASUAL_TEAM="便服" 常量）

## Commands

```bash
# 质量门（改动后必跑）
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && \
  python -m ruff check --fix scripts tests && python -m pytest -q

# 数据迁移（一次性；先备份）
cp work/20260805_车百鼎/roster_20260805_车百鼎.json \
   work/20260805_车百鼎/roster_20260805_车百鼎.json.bak
python -c "..."  # players 里 team==地平线 → 车百鼎，写回

# 页面重生成（迁移后跑，两条；--clusters 与 --scorers 同目录）
python scripts/gen_scorer_page.py --scorers work/20260805_车百鼎/scorers_b1/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch1.json \
  --clusters work/20260805_车百鼎/scorers_b1/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch1/events_index.json
# b2 同理（goals_batch2 / review_batch2 / scorers_b2）
```

## 数据契约

### opponent_of(session) -> str（gen_scorer_page.py 新增，唯一派生入口）

- `session.split("_", 1)` 有后半部分且非空 → 返回该后缀
  （`20260805_车百鼎` → `车百鼎`）
- 否则回退 `"地平线"`（20260722 等无后缀老场次的历史口径；注释注明）
- session 两端空白先 strip；后缀 strip 后为空也走回退

### roster.py team 校验新口径

- `Player.team`：任意**非空 str** 合法（strip 后非空）；非 str / 空串 →
  SchemaError（报错文案不再列枚举，改为"team 必须是非空字符串"）
- `VALID_TEAMS` 常量**删除**（语义已被场次动态化取代；grep 确认无
  scripts/ 内其他引用方可删，有则改引用方）。不新增 TEAM_HOME 等常量
  ——各消费方已有的本地常量（gen_scorer_page 的 TEAM_WHITE/TEAM_CASUAL、
  video.py 的 CASUAL_TEAM）保持不动（YAGNI）
- 模块 docstring 与错误信息同步更新（"合法 team 值"段改为新口径）

### gen_scorer_page.py 页面

- 模板注入新占位符 `__OPP__` → JS `const OPP = "..."`（json.dumps 注入）
- JS `teamOfTag`：黑/蓝 → OPP；白 → "半截篮"；其余 → "便服"
- 队分行顺序 `[OPP, "半截篮", "便服"]`（现状地平线位置换 OPP）
- CSS 类名改语义类：`.team-opp`（= 现 .team-地平线 样式值）、
  `.team-home`（= 现 .team-半截篮）、`.team-casual`（= 现 .team-便服）；
  JS 新增 `teamClass(team)`：半截篮→team-home、便服→team-casual、
  其余→team-opp；全部 `b.className = "team-" + p.team` 改走 teamClass
- Python `team_of_tag(tag, opp)` 加 opp 参数；`parse_players` 与
  exportRoster 的自动补录（JS 端 teamOfTag）同步用 OPP
- 既有测试断言标识符保留义务继续有效（`clusterAssign` 等）

## Code Style

遵守 rules.md；roster.py 契约改动同步 docstring；模板 JS 沿用现有风格。

## Testing Strategy

- test_roster.py：team 校验口径更新——非空 str（含"车百鼎"等新队名）通过；
  空串/非 str 仍 SchemaError；删 VALID_TEAMS 枚举用例
- test_gen_scorer_page.py：21 处"地平线"引用按新口径更新；新增单测
  `opponent_of`（带后缀 / 无后缀回退 / 空白后缀回退）；模板断言补
  `const OPP` 与 `team-opp`
- test_build_highlight.py 等其余 38 处引用逐个核对：凡依赖"地平线"作为
  合法 team 枚举的改新口径；仅作示例队名使用的可保留
- 质量门全绿

## Boundaries

- Always：质量门全绿后提交；roster 迁移先备份（.bak）；页面重生成前
  完成迁移（顺序敏感——页面从 roster 读 team 预填）
- Ask first：无（零新依赖、零新 CLI 参数）
- Never：不改 roster.json schema 结构（只放宽 team 取值）；
  不迁移 20260722 老数据（已定稿，队名本就是地平线）；
  不动 build_highlight / video.py；便服/半截篮特殊语义不变

## Success Criteria

- [ ] roster.py team 校验放宽 + docstring/报错文案更新
- [ ] gen_scorer_page opponent_of 派生 + 模板/JS/CSS 动态化
- [ ] 测试口径更新 + 新单测，pytest 全绿
- [ ] roster_20260805_车百鼎.json 迁移（先 .bak 备份）且过 validate
- [ ] scorers_b1/b2 页面重生成，队分行显示车百鼎
- [ ] 使用手册.html 认人节补口径（对手队名=场次名后缀自动取）
- [ ] 四件套齐全（review 按轮次编号）

## Open Questions

- 无后缀场次回退"地平线"是历史兼容口径；若未来出现第三个对手且场次
  ID 忘带后缀，页面会显示地平线——可接受（AGENTS.md 已约定场次 ID 带
  对手名，声明优先）
