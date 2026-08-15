# Review 01: 队员拖拽改队三件套审查（第 1 轮）

日期：2026-08-15
对象：docs/player-team-drag/{spec,plan,todo}.md（初版）
审查人：spec-reviewer 子代理（对照簇合并+折叠、队名会话化两轮改造后的
scripts/gen_scorer_page.py 当前版核查）

## 审查结论：无阻断，5 条非阻断建议全部采纳

| # | 建议 | 处理 |
|---|------|------|
| N1 | 跨拖拽域 payload 串扰：队员 tag 以数字开头时拖到簇行会被 parseInt 误当组 id 触发误合并 → 用自定义 MIME `text/player-tag` 隔离 | 采纳：spec 交互节 + plan Step 5 ③ 改自定义 MIME；簇行 dragover/drop 补 text/plain 守卫（Step 5 ④） |
| N2 | 空队伍行不渲染则无处可拖入 | 采纳：三行恒渲染（plan Step 5 ① 删 `if (!row.length) continue;`），手工清单补对应条目 |
| N3 | 拖簇行经过队伍行时队伍行误高亮 | 采纳：与 N1 同药（dragover 按 types 甄别） |
| N4 | spec 测试策略措辞（applyTeamOverride）与 plan 实现（changeTeam）收敛 | 采纳：spec 断言清单改为 changeTeam/saveTeamOvr/text-player-tag 实际标识符 |
| N5 | renderPlayers 两处行 div / 两处按钮循环锚点勿只改第一处 | plan 已注明"两处各一处"，实施时盯 |

## 核查通过项（审查代理确认）

- renderPlayers 三处锚点与当前代码精确吻合；"其他"行不加 drop 目标可
  干净实现（两块代码物理分离）
- TEAMOVR_KEY 与既有 marks/touched/clState 键模式同构；平铺对象简单
  Object.assign 合并即够
- 导出零改动属实：exportRoster 读 PLAYERS 内存值；changeTeam 写 p.team
  后自动跟随；marks/touched/confirmed 不读 team
- 拖拽与单击共存成立；show(cur) 重渲染同时刷分行/着色/簇区按钮色
- 测试断言标识符与 plan 代码逐字吻合；build_html 六位置参 opp 末位正确
- PLAYERS 是 const 数组但元素对象可写，覆盖应用循环早于首次渲染

## 结论

通过，可按 plan 实施。
