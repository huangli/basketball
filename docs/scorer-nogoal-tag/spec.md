# Spec: 认人页"不算进球"标签（页面剔除假进球）

## Objective

问题（2026-08-15 立哥）：确认页逐球核对时发现有些球不是进球（误判/犯规不算），
现状只能攒清单报给代理改 goals.json，多一道转手。

方案（立哥定）：页面加"不算进球"标签——顶部按钮 + N 键，把球归到特殊标签
`不算进球`。该标签**只在页面内流转**，导出 roster 时自动剔除：

- 导出的 assignments 不含这些键、players 不补录该标签（build 合成只按
  roster 归属查球，这些球自然被跳过——有 roster 无过滤模式对未归属球
  WARNING 跳过，个人/分队合集更沾不上）
- 它算"已处理"，**不挡 confirmed=true**（confirmed 条件只看 marks 非空）
- 打错了可逆：核对对象行选"不算进球"能列出全部剔除球，点正确球员即改归
  （一切按普通标签行为，无需特殊分支）

为什么不动 goals.json / build_highlight：页面写不了文件（localStorage 模型），
build 只认 roster——导出剔除已能保证合成结果正确，零 Python 变更。代价：
goals.json 里这些球仍是 confirmed（重新生成确认页会再出现，需重新剔除——
localStorage 在同浏览器同 session 下保持，可接受；换机/清站点数据后的恢复
路径是重新过一遍未归属集）。口径说明：哨兵只在 roster 驱动的合成里生效；
build_highlight 无 roster 的裸跑模式仍含全部 confirmed 球（当前合集口径都走
roster，不算漏洞）。

成功标准：

- 顶部有"不算进球 (N)"按钮；点钮或按 N = 当前球归到 `不算进球`（记 touched、
  照常前进，行为与 assign 一致）
- 导出 roster：assignments 无这些键、players 无该标签、confirmed 不被它挡；
  alert 提示剔除球数
- 核对对象行动态列出"不算进球"（marks 里有即列，复用 reviewTargets 零改动），
  选中可逐球复查改归
- 簇区行为不特殊处理：打了标签的球记 touched，簇级选人/合并预填盖不动
- roster schema 不变；build_highlight 零改动；pytest 全绿、ruff 干净；四件套齐全

## Tech Stack

纯前端：`scripts/gen_scorer_page.py` 的 `_HTML` 模板（CSS + JS），零 Python
逻辑变更、零新依赖、零新存储键（哨兵值走既有 marks/touched 键）。

## 数据契约

- 哨兵常量 `const NOGOAL = "不算进球";`（普通字符串标签，与 `__none__` 无涉；
  自由输入框敲同名标签等效，不另设防）
- 入口：#bar 跳过钮旁加 `<button id="nogoal">不算进球 (N)</button>` +
  keydown 加 `k === "n"` 分支 → 都调 `assign(NOGOAL)`（前进/touched/过滤集
  离集语义全自动继承，按人核对模式下打标签同样离集）
- 导出两处过滤（exportRoster 内）：
  - assignments 收集：`if (t && t !== NOGOAL)` 才写入
  - alert 文案补"不算进球 X 球（已剔除不参与合成）"
  - players 自动补录循环读的是已过滤的 assignments，哨兵自然进不来（零改动）
- confirmed 条件不动：`marks[it.key]` 非空即已处理，哨兵值满足
- 显示行为全继承普通标签：进度行"当前归属: 不算进球"、簇标签众数、核对对象
  行按钮（无 name 纯显示 tag）、localStorage 持久——全部零特殊分支

## Code Style

rules.md；模板 JS 沿用现有风格。

## Testing Strategy

- 模板字符串断言 + node --check 既有模式：
  - 新断言：`const NOGOAL = "不算进球"`、`id="nogoal"`、`t !== NOGOAL`、
    `k === "n"`、alert 剔除提示文案
  - 既有断言标识符保留（`id="skip"`、`"s"`、`function assign(` 等）
- 手工验证（立哥浏览器实测）：
  - [ ] 点"不算进球"/按 N：当前球打标签并前进；刷新保持；进度行显示该归属
  - [ ] 核对对象行出现"不算进球"，选中只列剔除球；点正确球员改归后球离集
  - [ ] 导出 roster.json：无剔除球的键、无该标签球员、confirmed=true
        （其余球都认完时）；alert 报剔除数
  - [ ] 用该 roster 跑 `video build`：剔除球不进任何合集（全归属模式 WARNING
        跳过），不再报 confirmed 拒收
  - [ ] 打错改归：剔除球改归球员后，导出恢复进 assignments

## Boundaries

- Always：质量门全绿后提交；哨兵语义只在 exportRoster 有两处过滤，其余零特殊分支
- Ask first：无（零新依赖、零新 CLI 参数、零 schema 变更、零新存储键）
- Never：不动 goals.json；不动 build_highlight / roster.py；不改 confirmed
  条件与 touched 规则；不把哨兵写进 players

## Success Criteria

- [ ] 按钮 + N 键打标签（assign 全语义继承）
- [ ] 导出剔除 + alert 报数 + 不挡 confirmed
- [ ] 可逆（核对对象复查改归）
- [ ] 手工验证清单全过（含 build 实测）
- [ ] 使用手册.html 第三步补一句
- [ ] ruff+pytest 全绿；四件套齐全
