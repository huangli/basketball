# Spec/Plan/Todo 三件套二审：进球人识别

> - **审查对象**：`docs/scorer/spec.md`（v2，162 行）、`docs/scorer/plan.md`（80 行）、`docs/scorer/todo.md`（53 行）
> - **审查日期**：2026-07-31
> - **审查轮次**：第 2 轮（一审见同目录 `review01.md`；spec 头部称已按 review01 修订 B1/B2/M1-M6）
> - **审查范围**：① review01 落实情况核对 ② spec/plan/todo 三者内部一致性 ③ 修订是否引入新问题
> - **审查方法**：逐条对照 review01 的 B/M/m/Q 与 spec v2 修订；交叉核对 spec 节 ↔ plan Task ↔ todo Acceptance 的覆盖与措辞一致
> - **审查人**：opencode（glm-5.2）
> - **结论摘要**：**落实情况良好**——review01 的 2 阻断 + 6 重要 + 5 建议 + 3 疑问基本全部落地，无新阻断。但三件套存在 **3 处重要一致性缺口**（confirmed 字段计算未定义、真值表"全员"行歧义、试点前置数据未作 checkpoint）与若干 Minor，建议 T4 开工前补 N1、T6 开工前确认 N7。**可进实现阶段**。

---

## 0. review01 落实情况核对（逐条）

| 一审项 | 一审要求 | spec v2 落地位置 | 落实 |
|---|---|---|---|
| B1 真值表 | 补 build_highlight 组合真值表 | spec.md L92-102（7 行表） | ✅（残留 N2/N3/N4，见下）|
| B2 定位算法 | 指明 persons 无 ID + 关联方法 + 众数量化 | spec.md L104-115（IoU 链 4 步）| ✅ |
| M1 SKIP 流程 | 确认页呈现 + roster 允许未归属 + 跳过不阻塞 | spec.md L87-88 / plan.md L26-28 / todo T4,T6 | ✅ |
| M2 fid 映射 | 写明 fid=去 .mp4 | spec.md L89-90 / plan.md L13 / todo T1 | ✅ |
| M3 键格式化 | 双端共用 format 函数 | spec.md L85-86 / plan.md L13 / todo T1 | ✅ |
| M4 颜色采样 | 采样区 + 判据 + 阈值来源 | spec.md L117-121 | ✅ |
| M5 批次合并 | --roster-existing 协议 | spec.md L43-45 / todo T4 | ✅（残留 N6 players 合并语义）|
| M6 文件名前缀 | 队伍_/个人_ 分支 | spec.md L60-61,100 | ✅ |
| m1 号码缓存 | number_cache.json 幂等 | spec.md L37,62 / todo T7 | ✅ |
| m2 players 注入 | --players/players.json 优先级 | spec.md L142 提三种，**优先级/schema 仍未定义** | ⚠ 部分 |
| m3 便服 team | 合法值 + 不进分队 | spec.md L76,86,161 | ✅ |
| m4 裁图尺寸 | 短边 ≥400px | spec.md L115 | ✅ |
| m5 SC4 口径 | 覆盖全部非 SKIP confirmed 球 | spec.md L152-153 | ✅ |
| Q1 Boundaries 矛盾 | 授权范围厘清 | spec.md L139-140 | ✅ |
| Q2 颜色阈值来源 | 标定来源 | spec.md L121 | ✅ |
| Q3 无名单退化 | 自由文本 + 颜色预填 | spec.md L159 | ✅ |

**小结**：16 项中 14 项完整落实、1 项部分（m2）、1 项残留语义瑕疵（B1 衍生 N2-N4）。修订质量高。

---

## 1. 阻断级

**无。** B1/B2 已实质解决，二审未发现新阻断。

---

## 2. 重要级（影响正确性，建议对应 Task 开工前补）

### N1. `confirmed` 字段由谁计算、怎么计算未定义

spec.md L87-88：

> `confirmed=true` 的条件：**全部非 SKIP confirmed 球都已归属**；SKIP 球允许未归属。

但三件套都没说 **confirmed 怎么产生**：

- 谁判断"全部非 SKIP 球已归属"？gen_scorer_page 导出时比对 `--goals` 的 confirmed 球集 vs roster.assignments 键集？
- 立哥导出 roster.json 时，confirmed 是页面自动算，还是立哥手动勾？
- todo T4 acceptance（todo.md L23-26）只说"导出 roster.json"，**完全没有 confirmed 字段逻辑**。

`confirmed` 是 roster schema 核心字段——build_highlight 据它决定拒收/放行（todo T5⑧"未 confirmed=true 拒收退出 1"）。计算规则缺失会让"立哥确认→导出→合成"闭环在 T4 行为不确定。

**建议**：plan.md AD + todo T4 补一条——"gen_scorer_page 导出时自动算 confirmed：比对 `--goals` 中 status=confirmed 的球集，扣掉 SKIP 球后，若全部出现在 assignments 键中则 confirmed=true，否则 confirmed=false 并列出未归属球"；spec Testing 补对应单测（N10）。

### N2. 真值表"全员"行（spec L98）歧义，与 plan L28 解释不一致

spec.md L98：

> 有 roster 无 scorer 无 team → 全员（roster 仅作 confirmed 校验）

"全员"指什么未写清：goals.json 全部 confirmed 球？还是 roster.assignments 全部归属球？两者在 SKIP 未归属时**结果不同**。plan.md L28 试图澄清：

> 有 roster 无过滤参数的"全员"行——该行实际=全归属球

但 spec 没同步。这直接关系到 SKIP 球命运：未归属 SKIP 球进不进"全员"合集？spec.md L88 只说"WARNING 跳过不阻塞"，没说"全员合集是否含它"。

**建议**：spec.md L98 改措辞为"全归属球（assignments.values 去重）；未归属球（含 SKIP）WARNING 跳过、不进任何合集"，与 plan L28 对齐。

### N7. 试点前置数据就绪未作 checkpoint（实操风险）

review01 §0 已核实：工作区当前 `work/20260722/goals.json`（17 confirmed）、`work/detect/*_mot_cache.json`、`work/frames/<fid>/` **均不存在**（根目录 goals.json 为空）。但三件套全程假设这批数据已就绪：

- spec.md L10/L35 "批次 1 已验收 17 个 confirmed"
- plan.md Overview "批次 1 的 17 个 confirmed 进球做试点"
- todo T2/T3/T6 的 Verify 都依赖实跑

T6（端到端试点）若数据未就绪会直接失败，且失败点会很晚才暴露（前面 T1-T5 都是合成数据单测，不碰真数据）。

**建议**：plan.md Phase 3 / todo T6 加一条前置检查——"试点前确认 goals.json + mot_cache + frames 齐备（review01 §0 已示当前缺失）；缺失则先重跑 extract_frames→mot_candidates→gen_label_page 标注链"。

---

## 3. 建议级（一致性瑕疵，不阻断）

### N3. 真值表分支计数三处不一致

- spec.md L132 Testing："**七个**组合分支"
- plan.md L48："真值表改造（**7** 分支）"
- plan.md L52 Checkpoint："真值表 **8** 分支测试全过"
- todo.md T5：列了 ①-⑧（且 ⑧ 含"便服退出1"和"confirmed拒收退出1"两条），实际 9 个断言点

口径打架。真相：真值表本体 7 行 + 2 个横切校验（便服、confirmed）。

**建议**：统一表述为"真值表 7 组合 + 2 横切校验（便服/confirmed）= 9 断言"，三处同步。

### N4. spec 真值表未含"便服"例外

spec.md L100：

> 有 roster 无 scorer 有 team → 按 team 取 players.tags → 反查 assignments

未注明 `team=便服` 例外。plan.md L25 与 todo T5⑧ 都说"便服报错退出 1"，但真值表 L100 把 team 当泛指，会让实现者以为"便服也按 team 反查"。真值表与横切校验脱节。

**建议**：spec.md L100 末尾加注"`team` 取值限于黑/白；`--team 便服` 见横切校验（退出 1）"。

### N5. plan.md AD 漏记两项决策

plan.md Architecture Decisions 覆盖了便服/SKIP/号码/输出 tag，但两项决策只在 spec/todo 出现、没进 plan AD：
- **confirmed 校验语义**（N1）——plan AD 应记录"confirmed 由 gen_scorer_page 导出时计算"；
- **--team 的"队伍_"前缀**（spec L100）——plan AD 只说了 --scorer 用 tag（L23-24），没说 --team 前缀分支。

**建议**：plan.md AD 补两条，保持"决策集中"（plan 自身定位）。

### N6. players 合并语义三件套不一致

- spec.md L45 / todo T4："同键冲突退出 1"——**指 assignments 键**；
- plan.md L80 Open Questions："players 以新名单为准"；
- spec.md L133 Testing："players 缺 tag WARNING"——又引入第三种 players 校验语义（缺 tag 是 WARNING 而非 SchemaError，与 L131"tag 重复→SchemaError"的严格度不一致）。

三处对 players 合并/校验各说各话：assignments 冲突退出、players 整体覆盖、players 缺 tag 仅 WARNING。

**建议**：spec.md schema 节统一 players 校验口径——"tag 缺失/重复均 SchemaError（与 L131 一致），不要 WARNING"；并明确 --roster-existing 时 players 合并策略（整体覆盖 or 并集，plan L80 倾向覆盖，spec 应写死）。

### N8. roster schema `name` 空串边界未定义

spec.md L76 示例 `{tag:"灰T恤-A", name:"", team:"便服"}` 合法（name 空）。但真值表 L99"解析 tag 或 name 任一命中"——若 `--scorer ""` 或多人 name 空，会误匹配。应明确"name 空串不参与匹配，仅 tag 命中"。

### N9. todo T2 漏"代表帧=离球最近帧"规则

spec.md L114 明确"代表帧（离球最近帧）"，但 todo T2 acceptance（todo.md L11-12）裁图规格只写了"外扩 20%、短边 ≥400px"，漏代表帧选取规则。实现者可能取错帧（如窗口首帧/中间帧）。

**建议**：todo T2 补"代表帧=窗口内离球最近帧"。

---

## 4. 疑问 / 内部一致性

- **N10.** 测试策略（spec.md L131-133）覆盖 schema/真值表/合并，但**未列 confirmed 计算的单测**（N1）。补一条"导出时 goals.confirmed 球集 ⊆ assignments 键（扣 SKIP）→ confirmed=true；否则 false 并列未归属球"。
- **N11.** spec.md L142 提到"`--players`/`--players-file`/`players.json`"三种注入，但 m2（一审部分落实）仍未定义优先级与 players.json schema。建议 spec 给一行优先级声明（如"CLI > file > 同目录 players.json"）。
- **N12.** plan.md L70 Risk 表"SKIP 率 >30% 返工"，返工方向含"取球最后离开人框的帧"——这与 spec.md L114"代表帧=离球最近帧"是不同策略，plan 把它列作返工备选 OK，但建议 spec 注明"返工时代表帧策略可切换"，避免实现者以为写死。

---

## 5. 结论与修订优先级

1. **可进实现阶段**——无新阻断，review01 落实率 14/16 完整。
2. **T4 开工前必修**：N1（confirmed 计算）——否则认人页导出行为不定，闭环断。
3. **T6 开工前必修**：N7（前置数据就绪检查）——否则试点跑不起来。
4. **建议本轮一并消化**（措辞性，改 spec 即可）：N2（全员行）、N3（分支计数）、N4（便服例外）、N6（players 校验统一）。
5. **可在实现时顺手**：N5/N8/N9/N10/N11/N12。

整体评价：三件套结构清晰、spec v2 修订扎实、plan 的 Architecture Decisions + Checkpoint 设计合理（人工/机器 checkpoint 分层、风险表到位）。上述问题以一致性措辞为主，不涉及架构返工。修完 N1/N7 即可放心进 T1。

---

## 附：三件套交叉覆盖核对（spec 节 ↔ plan Task ↔ todo）

| spec 节 | plan 对应 | todo 对应 | 覆盖 |
|---|---|---|---|
| Objective | Overview | – | ✅ |
| roster schema | AD L13-15 | T1 | ✅ |
| 真值表 | AD + Task L48 | T5 | ✅（N2-N4 措辞）|
| 定位算法 | AD L16-18 | T2 | ✅（N9 代表帧）|
| 颜色判据 | AD L20-22 | T3 | ✅ |
| 认人页合并 | Task L47 | T4 | ✅（N1 confirmed）|
| 号码识别 | AD L29-30 | T7 | ✅ |
| SKIP 处理 | AD L26-28 | T4,T6 | ✅ |
| Boundaries | AD + Checkpoint 2 | T5 Verify | ✅ |
| Success Criteria | Checkpoint 1/2/3 | 各 Verify | ✅（N7 前置数据）|
| Open Questions | Open Questions | – | ✅ |
