# Review 02: 读号默认开 + 确认页一键全收号码预填（复审）

> 2026-08-16，独立审查员。复审对象：docs/read-numbers-batch/{spec,plan,todo,research}.md
> （review01.md 之后的主代理修订版）。只读审查，未改动任何被审文件。

## 整体评价

review01 的 1 条阻断与 5 条建议改进全部正确闭环，O1/O2 两条可选优化也已吸收；
修订未引入新的阻断或一致性问题。四件套可进入实施。

## review01 问题闭环核对

### B1. argparse 同 dest 默认值语义 —— ✅ 已闭环

- spec.md:87-93：契约改为「两条 add_argument 之后显式 `pp.set_defaults(read_numbers=True)`」，
  并完整说明 hasattr 守卫 / 先注册者胜出 / add_argument `default=True` 会被压住的语义，
  要求 set_defaults 行内注释。修法与本机实证结论一致，表述准确。
- plan.md:11-15（Architecture Decisions 第 1 条）、todo.md Task 1 Acceptance 同步收口，
  三处口径一致；Testing Strategy（spec.md:126）保留「缺省 True」单测锁定，双保险到位。

### S1. 调研来源归档 —— ✅ 已闭环

- research.md 已创建：跨批聚类继承证伪实测数（49.5% / b2 2/29 / b3 1/25 / 0.06 阈值
  2/6、0/1）完整归档，方法与对账口径写明；另附读号通路闲置现状与批内纯度回测，超出
  最低要求。
- spec.md:3-4 来源行已指向 research.md；plan Task 6 / todo Task 6 均含「经验教训.md §2
  补记该条证伪」。当前 经验教训.md 尚无该条（Grep 验证无匹配）——属正常，Task 6 未执行，
  不算未闭环。

### S2. Commands 块 shell 语法 —— ✅ 已闭环

- 改 PowerShell 代码 fence + `$env:PYTHONIOENCODING="utf-8"`（spec.md:71-72）；
  `;` 串接在 PowerShell 7+ 合法；`python -m ruff` 本机实测可用（ruff 0.16.0，
  比裸 `ruff` 更稳——裸命令在 Git Bash PATH 下不存在）。
- 伪命令 `node --check <(...)` 已删除，改为「python 提取生成页 script 段落临时文件后
  node --check tmp.js；或生成实页后按 todo 手工清单目检」（spec.md:79-80）——
  描述性两步 + 兜底路径，可执行性达标。

### S3. 示例命令场次不存在 —— ✅ 已闭环

- spec.md:76/78 改用真实场次 `20260805_车百鼎 --batch 2`（`work/20260805_车百鼎/`
  存在，`--batch` 参数见 video.py:753）。

### S4. 预算口径数值 —— ✅ 已闭环

- spec.md:94-95 改「confirmed×3（按场次实测，车百鼎三批 = 87/147/132 张）」，
  与 confirmed 29/49/44 ×3 一致；plan Task 5 手册口径同步（每批 = confirmed×3 张）。

### S5. 跨 session 边界补全 —— ✅ 已闭环

- spec.md:103-105 红线补「使用手册.html 仅动 people/认人相关小节，build 小节不碰；
  tests/test_video.py 只新增 people parser 用例，不改既有 build 用例」；
  plan Task 5、todo Task 1/Task 5 同步复述，三处一致。

### 可选优化吸收情况

- O1（alert X/Y 口径写死）：✅ spec.md:116-118 写死 X = `prefill_note="ambiguous"`
  球数、Y = `prefill_tag` 非空且 touched 球数。
- O2（无号场次 INFO 提示收口）：✅ spec.md:160-162 Open Questions 1 划线收口为决策；
  plan.md 新增「已收口决策」一节（:73-76），不再双重悬置。
- O3（行号引用改函数名锚点）：未采纳，spec 仍用裸行号（如 :781-788 实际到 :786）。
  可选优化不强制，维持 review01 定级；行号已在 review01 全部验证命中，当前不影响实施。

## 修订新引入问题排查

- plan/todo 任务数从 6 调整为 7（拆出 research/经验教训归档为 Task 6、四件套收尾为
  Task 7），两文件编号与内容一致，无错位。
- plan Task 6 措辞「调研依据归档 research.md」——该文件已随本轮修订落盘，执行时直接
  勾选即可；纯措辞时序问题，不阻塞（可选优化级，不另立条）。
- 经验教训.md 改动已声明在 Task 6，不在另一 session 声明的改动面（docs/heatmap/ 等）
  内，无新冲突面。
- research.md 新增批内纯度数据（b1 0:6 / b2 1:8 / b3 2:9，纯度 55~59%）为 spec 未引用
  的补充材料，与 spec 非目标 P3 的取舍方向一致，无矛盾。

## 与 AGENTS.md 冲突对照表

无冲突。review01 指出的边角项（证伪补记 经验教训.md）已排入 Task 6，闭环路径明确。

## 结论

**通过**。review01 全部问题闭环，可实施。
