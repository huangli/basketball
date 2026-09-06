# Spec: 对手过滤——进球按我方/对手两队划分（opponent-filter）

> 2026-09-06 立哥立项："进球按照两支队伍划分，对手一个标注，有时候对手的进球我不想看了，可以瞬间过滤掉，半截篮一个合集"。代码改动在新仓库 `C:\Code\basketball_clip`。

## Objective

认人阶段给每个进球两种归属：**我方球员**（现有流程）或**对手**（一键伪身份，不识别具体是谁）。
出合集时按队伍过滤——默认出**我方合集**（不含对手进球），对手进球瞬间排除。

**用户故事**：
1. 认人确认页上，看到是对手进的球，点一下"标为对手"（整簇也可一键）——不用管是哪个对手
2. 出合集时默认只出"半截篮（我方）合集"，对手进球自然不在里面
3. 偶尔想看对手进球，也能单独出对手合集（保留通道）

## 设计

1. **伪球员"对手"**：roster 中特设 tag `对手`，team 字段 = **当前场次有效对手名**
   （`team_config.opponent` 缺省则按场次 ID 后缀派生 `opponent_of(session)`，与确认页
   UI 注入的 OPP 同口径）。归属对手的进球不需要逐人识别，一键归属。
2. **认人确认页**（gen_scorer_page.py）：每个进球卡片和每个聚类簇各加"标为对手"按钮；
   对手归属的进球在页面上归入"对手"分组（可折叠，不占认人精力）；导出 roster.json 时写入。
   **tag="对手" 必须特判**：现有 JS `teamOfTag`（黑/蓝/白前缀匹配，其余归便服）会把
   "对手"误判为便服——伪球员的 team 写入与页面分组都不得走 teamOfTag 兜底。
3. **roster schema**：沿用现有 players/assignments 结构，伪球员是一条普通 player 记录
   （tag="对手"），不引入新 schema 版本——build_highlight 现有 --team 过滤天然兼容。
4. **出合集**（build_highlight.py / video.py build）：
   - `--team <我方队名>` 出我方合集 = 现状，天然过滤对手（核心交付）
   - `--all` 展开时**显式跳过 tag="对手" 的个人合集与其对手队的分队合集**
     （注意不是便服口径：便服只跳分队、个人照出；对手是个人+分队全跳，防止
     `队伍_对手_进球集锦.mp4` 混进默认产物）
   - `--team 对手`（或有效对手名）显式给出对手合集（保留通道）
5. **GUI**：认人步确认页沿用（按钮已在页面内）；出合集步默认按钮文案改为
   "出我方合集"（--team 取 team_config.team_name），高级选项保留 --all / --scorer / --team 自定义。

## Commands

```powershell
C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m pytest -q
python -m ruff format scripts tests gui; python -m ruff check --fix scripts tests gui
```

## Project Structure

- `scripts/gen_scorer_page.py`：确认页"标为对手"按钮 + 对手分组展示 + tag="对手" 特判（不走 teamOfTag 兜底）
- `scripts/roster.py`：伪球员常量与校验放行（若现有 schema 校验拦住再动，先实证）
- `scripts/video.py`：build --all 显式跳过对手伪球员个人合集与对手队分队合集
- `gui/app.py` / `gui/static/app.js`：出合集步"出我方合集"默认按钮
- `tests/`：roster/scorer_page/video/GUI 对应用例
- 文档：本目录四件套（旧工作区）

## Code Style / Boundaries

- 同 rules.md；确认页交互风格沿用现有（簇级 + 逐球覆盖）
- 队伍特殊语义现状：便服队不出分队集锦——对手伪球员同口径处理，不新增第三种特例
- Ask first：roster schema 结构变更（本设计沿用 v 现状不动）；Never：不改 goals.json 契约

## Testing Strategy

- 单测：伪球员写入/读出 roster、--all 跳过对手、--team 我方过滤正确、确认页导出含对手归属
- 浏览器冒烟：确认页"标为对手"按钮真实可用、导出后 build 出我方合集不含对手球
- 存量 pytest/ruff 全绿

## Success Criteria

1. 认人页一键标对手（逐球 + 整簇），导出 roster 含对手归属
2. 我方合集零对手进球；--all 不出对手个人合集；--team 对手可出对手合集
3. GUI 出合集步一键"出我方合集"
4. 新增测试全绿，存量不破

## Open Questions

- O1：便服球员与对手共存时 --all 行为（便服有个人合集、对手没有）——按本设计便服照旧，待实测确认
- O2：历史场次的 黑/白 阵营映射与"对手"伪球员的关系（白*=我方、其余=对手？）——实施时先摸清现状口径，伪球员与旧阵营体系并存不冲突即可，不强行统一
