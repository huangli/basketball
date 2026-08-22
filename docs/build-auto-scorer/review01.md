# Review 01: build 认人可选化 文档审查

**审查日期**：2026-08-22　**审查角色**：spec-reviewer（子代理）
**审查对象**：`docs/build-auto-scorer/`（spec.md / plan.md / todo.md）、`AGENTS.md`（合集口径行、CLI build 行）、`使用手册.html`、`docs/2026-07-26-current-goal-detection-pipeline.md:86` 注记
**抽查代码**：`scripts/build_highlight.py`（docstring 真值表）、`scripts/video.py`（`_cmd_build` / `_cmd_build_auto`）、`scripts/auto_roster.py`（docstring/映射逻辑）

## verdict: PASS（首轮 FAIL，阻断修订后复核通过）

### 首轮阻断问题与修订记录

1. **todo.md 全部 6 项未勾选，与实际状态矛盾**（仓库惯例完成项勾 `[x]`，参照
   `docs/batch-speedup/todo.md`）。
   修订：T1–T5 已勾 `[x]`；T6 待真机抽验与提交完成后勾选。

### 首轮非阻断建议与采纳记录

1. 手册页脚"最后更新：2026-08-16"过期 → 已改 2026-08-22。
2. FAQ 标题"build 报 roster 不存在 / 未 confirmed"易误导（新口径不再报错）→
   改题"想出实名合集但 roster 未确认"。
3. 手册"三、文件都放哪"未列新中间产物 → work 行补 `scorers_auto/`、`auto_roster.json`；
   output 行补 `进球片段/` 子目录与热图仅认人后触发。
4. 手册"四、成品规格"命名行 → 补未认人自动合集的 `球员_X` 簇标签口径。
5. spec 幂等跳过与成功标准 1 的交叉引用（纯可读性）→ 语义自洽，不改。

### 首轮逐项核对通过项（复核仍成立）

- 产物命名口径（全员_进球集锦.mp4 / 进球片段/ / 球员_X_进球合集.mp4）在 spec、
  AGENTS.md、手册三处一致；`球员_A_…` 与 `auto_roster.py` cluster_tag 映射吻合。
- 真值表⑨⑩ 语义与 `build_highlight.py` docstring 逐条吻合；①改名/③保旧名一致。
- video.py 分派（confirmed → 现状路径；缺失/未确认 → 自动模式）、无条件 WARNING、
  热图仅 confirmed 路径触发，与 spec/plan/AGENTS.md/手册一致。
- 认人可选语义贯穿手册（流程图/命令卡/第 3 步可选标注/第 4 步/FAQ），无过时残留。
- 主文档 :86 ①产物名注记已加；旧名残留仅限 ③ 路径代码/测试与历史文档（T5 允许范围）。
- plan 风险表"素材/goals 变更后须删 scorers* 重跑"已在手册第 4 步兑现。

## 另：实施前的双评审收敛（santa-method，三轮）

spec/plan/todo 动手前经两位独立评审员逐轮对抗审查（上下文隔离、同一 rubric）：

- 第一轮（B/C）：双双 FAIL。阻断项：spec 真值表⑩ 伪码与 plan 逐 tag 循环实现矛盾；
  build_people_steps 不可整函数复用（namespace AttributeError）；未确认 roster 下热图
  行为未定义；spec"覆盖 WARNING"Never 条款无实现步骤。已全部修订。
- 第二轮（D/E）：双双 FAIL。阻断项：簇数异常 INFO 留痕链条在 plan/todo 断裂；
  todo T5 grep 验收与"③保留旧名"设计自相矛盾。已全部修订。
- 第三轮（F/G）：**双双 PASS**，无阻断项。低成本建议（真值表块加①改行、②标注不传
  --roster、NNN 跳号口径、批次缺 candidates 守卫、>15 簇量化、热图措辞）已采纳回填。
- 附带核实：video.py:512 `except KeyError, TypeError, ValueError:` 无括号写法经实测
  py_compile/import 通过（PEP 758，Python 3.14 起合法），非问题。
