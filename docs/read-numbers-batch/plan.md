# Plan: 读号默认开 + 确认页一键全收号码预填

## Overview

按 spec（docs/read-numbers-batch/spec.md）实施。两个改动点相互独立、各自
可验，外加手册同步与四件套收尾。Phase 1 / Phase 2 可互换顺序；Phase 3
依赖前两阶段行为定稿。

## Architecture Decisions

- **argparse 双开关同 dest + set_defaults 兜底**：`--read-numbers`（store_true）
  与 `--no-read-numbers`（store_false）共用一个 dest，老命令幂等不炸；
  **缺省 True 用两条 add_argument 之后的 `pp.set_defaults(read_numbers=True)`
  保证**——argparse 默认值带 hasattr 守卫、先注册者胜出，add_argument 的
  `default=True` 会被压住（review01 B1，本机实证）；不引入 env 变量或配置项。
- **批量接受走按钮不走自动执行**：页面加载即批量预填等于机器替人做决定，
  违背"机器排序 + 人裁判"；立哥点一次按钮的成本可忽略，安全性完全不同。
- **批量写入不标 touched**：与簇级选人预填（`clusterAssign`）同语义——
  预填可被后续预填覆盖，终裁靠第三步逐球核对与导出前目检；不新增第三类
  标记态（marks/touched 两集合已够，加状态只会增加互踩面）。
- **零 Python 逻辑改动在 gen_scorer_page**：按钮行为纯前端 JS，Python 侧
  只加按钮 HTML 与 JS 函数；导出契约、build_entries、roster schema 一律不动。

## Task List

### Phase 1: video.py 读号默认开

- [ ] Task 1: people parser 加 `--no-read-numbers`（store_false / 同 dest），
  `--read-numbers` 保留，两条之后 `pp.set_defaults(read_numbers=True)`（行内
  注释说明 argparse 先注册者胜出语义）；改动仅限 parser 参数区
- [ ] Task 2: 单测（缺省 True / --no-read-numbers False / 显式
  --read-numbers True / build_people_steps argv 断言）+ 质量门

### Checkpoint 1

- [ ] ruff+pytest 全绿；`git diff` 复核 video.py 改动仅限 people parser 区域；
  `video people --dry-run` 不带参数输出含 --read-numbers，带
  --no-read-numbers 则不含；**提交 Phase 1**

### Phase 2: 确认页一键全收

- [ ] Task 3: `_HTML` 顶栏加 `#acceptall` 按钮 + JS 函数（prefill_tag 非空
  且未 touched → 写 marks 不标 touched → alert 计数 → save+show）
- [ ] Task 4: 单测（_HTML 关键串断言）+ 质量门 + 实页 `node --check`

### Checkpoint 2

- [ ] 实页手工清单（构造四类球：号码预填 / 歧义 / SKIP / 已逐球手改）：
  点一次按钮仅第一类写入 marks；localStorage touched 无新增；导出 roster
  归属数与 confirmed 正确；**提交 Phase 2**

### Phase 3: 手册同步 + 收尾

- [ ] Task 5: 使用手册.html 更新——`video people` 读号默认开、适用前提
  （球衣有号场次）、token 成本（每批 = confirmed×3 张、缓存幂等）、
  确认页新按钮说明、更新日期（仅动 people/认人小节，build 小节不碰）
- [ ] Task 6: 调研依据归档 `docs/read-numbers-batch/research.md`（跨批聚类
  继承证伪实测数：纯度 49.5%、继承符合率 b2 2/29、b3 1/25、阈值 0.06 仍
  2/6、0/1），并在 `docs/经验教训.md` 补记该条证伪（AGENTS.md 约定证伪
  集中索引）
- [ ] Task 7: 四件套核对（todo 勾完、review 由独立 spec-reviewer 产出后
  归档）；**提交 Phase 3**

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| K3 系统性误读（如球衣互换场次） | 批量错填 | 误读率有 5/5 实测；歧义不预填；批量不标 touched，第三步翻检可改；导出前 alert 计数可目检 |
| 无号场次默认开浪费 token | 额度消耗 | 手册写明适用前提 + `--no-read-numbers`；缓存 md5 幂等，误跑一次只扣一次 |
| 与另一 session 的 video.py 改动冲突 | 合并冲突 | 本功能 diff 限定 people parser 参数区；提交前 git diff 复核 |
| 按钮误触批量写入 | 误归属 | alert 报计数；预填非 touched 可翻检；roster 导出前 confirmed 计数可见 |

## 已收口决策

- 无号场次：读号结果全 None 时打一行 INFO 提示，不加分支逻辑
  （原 spec Open Questions 1，review01 O2 收口）
