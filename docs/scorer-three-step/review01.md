# Review 01: 三步引导流程 spec 审查（第 1 轮）

日期：2026-08-15
对象：docs/scorer-three-step/spec.md（初版）
审查人：spec-reviewer 子代理（对照三轮改造后的 scripts/gen_scorer_page.py
当前版与 tests/test_gen_scorer_page.py 核查）

## 审查结论：1 个阻断已修订，12 条非阻断处理如下

### 阻断 1（已修）：names/review 两键"删键"契约与读回合并写模式矛盾

- 问题：清空真名删键 + 读回合并写 = 单页必现复活 bug（save() 的
  `Object.assign(stored, marks)` 会复活本地已删键；saveClState 有同样
  前科，为此引入了 del 删除清单参数）
- 修订：**清空/切回全部 = 写空串不删键**，加载时空串视为无真名/全部
  （spec 数据契约两节均已改写，附前科注释）

### 非阻断建议的处理

| # | 建议 | 处理 |
|---|------|------|
| N1 | POSKEY 语义：过滤集索引 vs 存量全局索引错位 | 采纳：位置持久按核对对象分键 `_pos_<target>`（全部沿用旧键兼容） |
| N2 | 漏点：renderPlayers 两处 sel 高亮直接引用 ITEMS | 采纳：spec 列明"ITEMS 直接引用点全部改读可见集"清单 |
| N3 | 漏点：keydown E 键与 accept 钮同样直引 ITEMS | 采纳：同上清单 |
| N4 | assign 前进语义须按模式分支（共用入口多） | 采纳：spec 写明全部=现状、按人/未归属=落原索引新当前项 |
| N5 | 空集早退会停在旧画面 | 采纳：空可见集渲染空态，不得早退 |
| N6 | 启动定位与持久 target 优先级 | 采纳：启动定位规则明写（恢复 target→分键位置→默认定位） |
| N7 | 核对对象含名单外自由输入 tag | 采纳：spec 点名属正常 |
| N8 | 进度行人名格式、未归属集完成文案 | 采纳：`tag=真名`；"未归属清零" |
| N9 | 按钮文字是四处不是三处 | 采纳：spec 改"四处" |
| N10 | 保留断言清单补 `"scorer_" + SESSION`、`const CLUSTERS = [];` | 采纳 |
| N11 | 改名钮勿动 b.textContent/className 原行（子串断言会红） | 记录：plan 阶段写给实施者 |
| N12 | `__none__` 与自由输入理论可撞 | 采纳：自由输入框加一行守卫拒绝该值 |

## 核查通过项（审查代理确认）

- 改名内存可写模式成立（changeTeam 同构前例）；四处按钮文字都读
  p.name，一次 show 全刷；导出跟随成立，自动补录与 names 无交集
- 可见集抽象可行：ITEMS 本体不动，改造集中在 show/assign/skip/
  jumpUnassigned/keydown-E/sel 高亮/启动块；exportRoster 的 confirmed/
  nUn/nDone 保持全局口径
- 键命名与既有模式一致；两种空集规则触发场景不同不冲突；
  target 回退规则覆盖 roster 变化与残留非法 tag
- 测试断言清单核对：spec 点名标识符全部在现有测试锁定；node --check
  天然覆盖新 JS；三步标题条无 --clusters 时随簇区隐藏，兼容路径清晰

## 结论

阻断已修订，spec 可进立哥审阅，随后进 plan。
