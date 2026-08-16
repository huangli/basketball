# Review 01: 读号默认开 + 确认页一键全收号码预填（spec/plan/todo 三件套）

> 2026-08-16，独立审查员。审查对象：docs/read-numbers-batch/{spec,plan,todo}.md。
> 只读审查，未改动任何被审文件。

## 整体评价

三件套结构完整、边界声明清晰、成功标准大多可机检，引用的源码行号抽查 10 余处基本全部命中。
但 spec 的「改动契约」对 argparse 同 dest 双开关的默认值解析语义描述**事实错误**（已用本机
Python 实证），照做会导致 Phase 1 功能不生效，需修订后再实施。

## 阻断问题

### B1. argparse 同 dest 双开关：新增 `default=True` 不会生效（契约写错）

- 位置：spec.md §改动契约 video.py（第 86-88 行）、plan.md §Architecture Decisions 第 1 条、
  todo.md Task 1。
- spec 写：「保留既有 `--read-numbers`（store_true，同一 dest）；新增 `--no-read-numbers`
  （store_false, dest=read_numbers, default=True）」。
- 实证（本机 Python 3.14 实跑）：argparse 在 `parse_known_args` 中按注册顺序填默认值，
  且带 `if not hasattr(namespace, action.dest)` 守卫——**先注册者的 default 胜出**。
  既有 `--read-numbers`（store_true 隐式 default False）先注册，后加的
  `--no-read-numbers default=True` 被跳过，缺省仍为 **False**：

  ```
  p.add_argument('--read-numbers', action='store_true')
  p.add_argument('--no-read-numbers', action='store_false', dest='read_numbers', default=True)
  p.parse_args([]).read_numbers  # → False（不是 True）
  ```

- 后果：照契约逐字实施，「读号默认开」静默不生效。spec 的单测（缺省 True）会在
  Checkpoint 1 拦住，但契约本身把实现者引向必然失败的写法。
- 修法：契约改为「两条 add_argument 之后显式 `pp.set_defaults(read_numbers=True)`，
  并在行内注释说明 argparse 默认值取先注册者、set_defaults 兜底」。plan/todo 同步
  把 Task 1 的 Acceptance 补一句「缺省 True 由 set_defaults 保证，非 add_argument
  default 参数」。

## 建议改进

### S1. 「认人链路提效调研」来源未落盘，证伪数据无法复核

- 位置：spec.md 第 3 行（来源）、§非目标（第 35-37 行，跨批聚类 49.5% 纯度、b2 2/29、
  b3 1/25、0.06 阈值 2/6/0/1 等实测数）。
- 全库检索 docs/ 无此调研文档，上述数据无出处可查。且 AGENTS.md 约定「已证伪清单与
  依据见 docs/经验教训.md」，跨批聚类继承预填这条新证伪未计划补记。
- 修法：调研数据归档为 docs/read-numbers-batch/research.md（或并入 spec 附录），并在
  经验教训.md §2 补一条跨批继承证伪记录（可放 Phase 3 收尾任务里）。

### S2. Commands 块混用 bash 语法，与 AGENTS.md 指定 shell 不符，且含伪命令

- 位置：spec.md §Commands（第 70-80 行）。
- `export PYTHONIOENCODING=utf-8` 是 bash 语法；AGENTS.md 明确「Shell 是 Windows
  PowerShell 7+」，PowerShell 下应写 `$env:PYTHONIOENCODING="utf-8"`。
- `node --check <(提取 scorer.html 的 script 段)` 是进程替换（bash-only）且提取步骤
  未定义，属于伪命令，照抄跑不通。node 本身已确认可用（v24.15.0）。
- 修法：拆成两步写实（python 提取 script 段落临时文件 → `node --check tmp.js`），
  或以「生成实页后按 todo 手工清单目检」为准、删掉伪命令；导出语法给 PowerShell 版本。

### S3. 示例命令 `--session 20260722` 在本工作区不存在

- 位置：spec.md §Commands 第 75 行。
- `work/` 下仅 `20260805_车百鼎`，无 20260722 场次 state，照跑会报错。
- 修法：改用真实场次或明确标注「示意，场次 ID 按实际替换」。

### S4. 预算口径「约 120~150 张/批」与既有实测不符

- 位置：spec.md 第 89 行。
- 车百鼎三批 confirmed = 29/49/44（docs/heatmap/research.md 等已锁定该口径），
  ×3 = 87/147/132，b1 的 87 落在「120~150」区间外。
- 修法：改为「约 90~150 张/批」或直接写「= 该批 confirmed×3，按场次实测」。

### S5. 跨 session 边界未覆盖 使用手册.html 与 tests/

- 位置：spec.md 第 94-97 行（边界红线）、§Boundaries Never 清单。
- 红线只列 video.py build 段 / build_highlight.py / goal_heatmap.py / docs/heatmap/。
  但本功能还要改 使用手册.html（Task 5）与 tests/test_video.py——前者另一 session
  的 build 链路历史上也改（docs/build-multi-batch/plan.md:465 有同类手册任务），
  后者与 build 段测试同文件，均有撞车面。
- 修法：红线补一句「使用手册.html 仅动 people/认人相关小节，build 小节不碰；
  test_video.py 只新增 people parser 用例，不改既有 build 用例」。

## 可选优化

- O1. spec.md 第 108 行 alert 文案「已手改 Y 跳过」的 Y 定义可写死（`prefill_tag` 非空
  且 touched 的计数），避免实现时口径漂移。
- O2. spec Open Questions 1 倾向已明确（INFO 一行、不加分支），plan §Open Questions 又
  原样列出，可直接收口为决策写进 Task，少一处悬而未决。
- O3. 行号引用抽查全部命中（见下），但行号易随代码漂移失效；后续文档建议改用
  「函数名 + 锚点串」引用（如 `match_players_by_number` / `prefill_note = "ambiguous"`）。

## 行号引用抽查记录（10 处全过）

| 引用 | 实际 | 结果 |
|------|------|------|
| video.py:755 `--read-numbers` 默认关 | :755 确为 store_true 无 default | ✓ |
| video.py:48 MAX_READS_PER_GOAL | :48 = 3 | ✓ |
| video.py:357-364 预算注入 | :357-364 if args.read_numbers → --read-numbers + --max-reads | ✓ |
| crop_scorers.py:131 MAX_NUMBER_READS_PER_RUN=20 | :131 = 20 | ✓ |
| crop_scorers.py:394-471 read_number | :394 def read_number | ✓ |
| crop_scorers.py:487-628 apply_number_reading | :487 def；:505 跳票模式注释；:1461 --numbers-cache-only | ✓ |
| gen_scorer_page.py:781-788 按钮 / :895-898 E 键 | :781-786 按钮、:895-898 按键 | ✓（区间微差，可接受） |
| gen_scorer_page.py:1081-1110 match_players_by_number | :1081 def | ✓ |
| gen_scorer_page.py:1432-1435 build_entries 歧义写入 | :1432-1435 len==1 命中 / >1 ambiguous | ✓ |
| JS 侧 ITEMS / save() / show() / exportRoster / clusterAssign | :164 / :398 / :742 / :831 / :730 均存在且语义与 spec 描述一致 | ✓ |

## 与 AGENTS.md 冲突对照表

无硬性冲突。一项边角（未达冲突级，已列入 S1）：AGENTS.md 约定已证伪方向集中记
docs/经验教训.md，本 spec 新增的跨批聚类继承证伪未安排补记。

其余核对均一致：四件套同目录 ✓；只 commit 不 push 且质量门先行 ✓；批量接受走按钮
不走自动执行，符合「机器排序 + 人裁判」✓；CLI 行为变更同步使用手册.html ✓（Task 5）；
review 由独立审查员产出 ✓（即本文档）。

## 结论

**需修订**（存在阻断问题 B1）。修订 B1 后，S1-S5 建议同轮一并吸收。
