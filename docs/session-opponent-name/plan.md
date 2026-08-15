# 对手队名会话化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。Steps 用 checkbox 跟踪。

**Goal:** 对手队名从场次 ID 后缀自动派生（`20260805_车百鼎`→车百鼎），废除硬编码"地平线"，迁移本场 roster 并重生成认人页。

**Architecture:** roster.py 校验放宽（team=任意非空 str）+ gen_scorer_page.py 派生函数 `opponent_of(session)` 注入模板（`const OPP`），CSS 类名改语义类 opp/home/casual；build_highlight/video.py 数据驱动天然跟随不动。

**Tech Stack:** Python 3.14 现有栈，零新依赖。

## Global Constraints

- 遵守 rules.md；质量门：`export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q`
- 中文 conventional 提交，只 commit 不 push；git add 点名文件（仓库有并行会话）
- 不改 roster.json schema 结构（只放宽 team 取值）；不迁移 20260722 老数据
- 白=半截篮、黑/蓝=对手队、其余=便服 的前缀映射规则不变
- 保留既有测试断言标识符（`clusterAssign`/`cluster-row`/`const CLUSTERS = [];`/`id="clusters"`/PICKER-HOOK）
- spec：docs/session-opponent-name/spec.md（契约以此为准）

---

### Task 1: roster.py team 校验放宽

**Files:**
- Modify: `scripts/roster.py`（:16 docstring、:29 VALID_TEAMS、:114-119 player_from_dict 校验）
- Test: `tests/test_roster.py`

**Interfaces:**
- Produces: `player_from_dict` 新口径——team 任意非空 str 合法；空串/非 str 抛 SchemaError

- [ ] **Step 1: 先改测试（TDD RED）**

tests/test_roster.py 中 team 枚举校验相关用例改新口径：
- 合法：`team="车百鼎"`（任意非空队名）通过
- 非法：`team=""`、`team=123` 仍 SchemaError
- 删除/改写 VALID_TEAMS 枚举断言

- [ ] **Step 2: 跑确认 RED**（VALID_TEAMS 枚举拒"车百鼎"）

- [ ] **Step 3: 实现**

roster.py：
- 删 `VALID_TEAMS`（已 grep 确认 scripts/ 内仅 roster.py 自身 :29/:115/:117
  引用，可安全删）
- :16 docstring 改为：`合法 team 值：任意非空 str（"半截篮"/"便服"有特殊语义；对手队名随场次 ID 后缀，见 docs/session-opponent-name/spec.md）`；
  :1 模块头部旧 spec 引用处补一句"team 取值口径以
  docs/session-opponent-name/spec.md 为准"
- player_from_dict 校验改：

```python
    team: Any = raw.get("team")
    if not isinstance(team, str) or not team.strip():
        raise SchemaError(f"{path}: players[{idx}]({tag}) team 必须是非空字符串，实际 {team!r}")
```

- [ ] **Step 4: GREEN + 质量门**
- [ ] **Step 5: Commit** `fix: roster team 校验放宽为任意非空 str——对手队名随场次（spec docs/session-opponent-name）`

---

### Task 2: gen_scorer_page 队名动态化

**Files:**
- Modify: `scripts/gen_scorer_page.py`（:61-68 常量区、模板 CSS/JS、:583 team_of_tag、:601 parse_players、build_html/main 接线）
- Test: `tests/test_gen_scorer_page.py`（21 处"地平线"引用按新口径更新 + 新单测）

**Interfaces:**
- Consumes: Task 1 的 roster 新口径
- Produces: `opponent_of(session: str) -> str`；`team_of_tag(tag: str, opp: str) -> str`；`parse_players(spec: str, opp: str)`；`build_html(..., opp: str)`（模板注入 `const OPP`）

- [ ] **Step 1: 先写新单测（TDD RED）**

```python
class TestOpponentOf:
    """对手队名派生：场次 ID 后缀；无后缀/空白后缀回退地平线（老场次历史口径）。"""

    def test_suffix(self) -> None:
        assert opponent_of("20260805_车百鼎") == "车百鼎"

    def test_no_suffix_fallback(self) -> None:
        assert opponent_of("20260722") == "地平线"

    def test_blank_suffix_fallback(self) -> None:
        assert opponent_of("20260722_") == "地平线"
```

（import 从 gen_scorer_page 现有 import 行补 opponent_of。）

- [ ] **Step 2: 跑确认 RED**（opponent_of 不存在）

- [ ] **Step 3: 实现 Python 侧**

常量区（:61-68）改：

```python
TEAM_WHITE: str = "半截篮"  # 白队队名（立哥队，固定）
TEAM_CASUAL: str = "便服"
# 对手队名不再硬编码：opponent_of(session) 从场次 ID 后缀派生
# （黑/蓝球衣=对手队；2026-08-09 立哥定前缀映射，2026-08-15 队名会话化）
OPPONENT_FALLBACK: str = "地平线"  # 无后缀老场次（20260722）的历史口径
# 标签前缀 → 阵营（顺序即优先级；蓝色27 归对手系立哥 2026-08-09 口径）
_TEAM_PREFIXES: tuple[tuple[str, str], ...] = (
    ("黑", "opp"),
    ("蓝", "opp"),
    ("白", "home"),
)
```

新增函数（team_of_tag 前）：

```python
def opponent_of(session: str) -> str:
    """对手队名 = 场次 ID 第一个 ``_`` 后的后缀（AGENTS.md 约定 YYYYMMDD_对手名）。

    无后缀 / 后缀空白 → 回退 OPPONENT_FALLBACK（20260722 等老场次历史口径）。

    Args:
        session: 场次 ID，如 ``20260805_车百鼎``。

    Returns:
        对手队名（黑/蓝球衣标签的 team 值）。
    """
    parts = session.strip().split("_", 1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()
    return OPPONENT_FALLBACK
```

team_of_tag 改签名：

```python
def team_of_tag(tag: str, opp: str) -> str:
    """按标签前缀推定队别：黑*/蓝*→对手队（opp）、白*→半截篮，其余归便服。

    页面导出自动补录名单外标签时用同一规则（JS teamOfTag 与本文档同步，
    改规则须两端一起改）。蓝色27 归对手系 2026-08-09 立哥口径。

    Args:
        tag: 球员标签，如 ``黑21`` / ``白-熊志鹏`` / ``灰T恤-A``。
        opp: 对手队名（opponent_of 产物）。

    Returns:
        opp / "半截篮" / "便服"。
    """
    for prefix, side in _TEAM_PREFIXES:
        if tag.startswith(prefix):
            return opp if side == "opp" else TEAM_WHITE
    return TEAM_CASUAL
```

parse_players 加 `opp: str` 参数，:624 改 `team=team_of_tag(tag, opp)`；
main 里 `opp: str = opponent_of(session)`（session 解析后、parse_players 前），
parse_players 调用点与 build_html 调用点都传 opp。

- [ ] **Step 4: 模板动态化**

CSS：`.team-地平线` → `.team-opp`、`.team-半截篮` → `.team-home`、
`.team-便服` → `.team-casual`（样式值不动）。

模板 JS：
- 常量区加 `const OPP = __OPP__;`（__OPP__ 由 build_html 用
  `json.dumps(opp, ensure_ascii=False)` 注入）
- `teamOfTag`：`黑/蓝 → OPP`；白 → "半截篮"；其余 → "便服"
- 新增：

```js
function teamClass(team) {
  // 队名→CSS 语义类：任意对手队名都能渲染（队名随场次，类名固定）
  if (team === "半截篮") return "team-home";
  if (team === "便服") return "team-casual";
  return "team-opp";
}
```

- 所有 `b.className = "team-" + p.team`（renderPlayers / renderClusters /
  弹条块三处）改 `b.className = teamClass(p.team)`
- 队分行顺序数组 `["地平线", "半截篮", "便服"]` 改 `[OPP, "半截篮", "便服"]`
  （含 renderPlayers 注释更新）

build_html 加 `opp: str` 参数 + `.replace("__OPP__", json.dumps(opp, ensure_ascii=False))`。

- [ ] **Step 5: 测试更新**

tests/test_gen_scorer_page.py 的 21 处"地平线"逐个核对，外加签名变更的
隐形调用点（审查非阻断 #1/#2，不全含"地平线"字面量，逐一必改）：
- **必改**：`test_invalid_team_raises`（:175-178）用 `team="白队"` 断言
  SchemaError——roster 放宽后"白队"变合法，此用例必红；改为空串
  `team=""` / 非 str 场景（与 test_roster 新口径对齐）
- **必改**：`team_of_tag` 调用（:96/:97）、`parse_players` 调用
  （:109/:119/:125）补 opp 参数；build_html 调用点补 opp 参数
- 模板断言/CSS 类相关 → 改 team-opp / const OPP 新断言
- 仅作示例队名的 Player 构造 → 可保留（任意非空队名现在都合法）
- 新增模板断言：`assert "const OPP = " in html`、`assert "team-opp" in html`
- `load_players_file` docstring（gen_scorer_page.py:632）"team ∈
  地平线/半截篮/便服"同步改新口径（rules.md 契约改动同步 docstring）

- [ ] **Step 6: GREEN + 质量门全绿**
- [ ] **Step 7: Commit** `feat: 认人页队名会话化——opponent_of 从场次 ID 后缀派生，CSS 类改语义类 opp/home/casual`

---

### Task 3: 数据迁移 + 页面重生成 + 手册口径 + 收尾

**Files:**
- Data: `work/20260805_车百鼎/roster_20260805_车百鼎.json`（gitignore 排除，不入 git）
- Modify: `使用手册.html`、`docs/session-opponent-name/todo.md`

- [ ] **Step 1: 备份 + 迁移 roster**

```bash
cp work/20260805_车百鼎/roster_20260805_车百鼎.json work/20260805_车百鼎/roster_20260805_车百鼎.json.bak
export PYTHONIOENCODING=utf-8 && python -c "
import json
from pathlib import Path
p = Path('work/20260805_车百鼎/roster_20260805_车百鼎.json')
d = json.loads(p.read_text(encoding='utf-8'))
n = 0
for pl in d['players']:
    if pl['team'] == '地平线':
        pl['team'] = '车百鼎'
        n += 1
p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
print('migrated', n)
"
```

Expected: `migrated 7`（7 名黑队球员）；随后跑一次 Step 2 的页面生成即内部
过 validate_roster 完成验证（roster.py 在 scripts/ 下不在 sys.path，
不要单独 python -c import roster）。

- [ ] **Step 2: 重生成 b1/b2 认人页**（b2 无 events_index.json 则省略 --index）

```bash
python scripts/gen_scorer_page.py --scorers work/20260805_车百鼎/scorers_b1/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch1.json \
  --clusters work/20260805_车百鼎/scorers_b1/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch1/events_index.json
python scripts/gen_scorer_page.py --scorers work/20260805_车百鼎/scorers_b2/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch2.json \
  --clusters work/20260805_车百鼎/scorers_b2/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch2/events_index.json
```

Expected: 退出码 0；grep 生成页含 `const OPP = "车百鼎"`，无 `地平线`

- [ ] **Step 3: 使用手册.html 认人节补口径**（第 3 步认人 ul 里加一条）：

```html
<li><b>对手队名自动取场次名后缀</b>（如 <code>20260805_车百鼎</code> → 车百鼎）：建新场次文件夹/声明场次时把对手名写对，页面分队和合集文件名都跟着它走。</li>
```

- [ ] **Step 4: todo.md 勾完 + 质量门终跑 + Commit**

```bash
git add 使用手册.html docs/session-opponent-name/
git commit -m "docs: 手册补对手队名口径（场次名后缀自动取）+ 四件套收尾"
```

---

## Self-Review 记录

- spec 覆盖：roster 放宽（Task 1）/ 派生+动态化（Task 2）/ 迁移+重生成+手册（Task 3）——全覆盖
- 占位符：无；接口签名跨 Task 一致（opponent_of/team_of_tag(tag, opp)/parse_players(spec, opp)/build_html opp）
- 边界：无后缀回退、空白后缀、CSS 类动态化、localStorage 不受影响（键不含队名）
