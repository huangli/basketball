# Spec 审查报告：进球人识别（投篮者定位 / 分队 / 认人确认页 / roster.json）

> - **审查对象**：`docs/scorer/spec.md`（v1，137 行；现与本文同目录）
> - **审查日期**：2026-07-31
> - **审查范围**：投篮者定位、颜色分队、号码识别、roster.json schema、认人确认页、build_highlight 的 `--roster/--team` 扩展
> - **审查方法**：用真实代码与数据反验判据与可行性——`rules.md`、`docs/2026-07-26-current-goal-detection-pipeline.md`、`scripts/build_highlight.py`（当前 `--scorer` 实现）、`scripts/mot_candidates.py`（mot_cache 实际结构）、`scripts/extract_frames.py`（帧/fid 约定）、`scripts/gen_label_page.py`（导出键格式）、`AGENTS.md`（已确认规格）
> - **审查人**：opencode（glm-5.2）
> - **结论摘要**：方向正确、与 AGENTS.md 规格（命名标签 / 场次隔离 / 输出比例跟随素材）一致，roster schema 草案可用。但有 **2 处阻断**（build_highlight 语义真值表缺失、投篮者定位核心算法描述不充分）与 **6 处重要**，不足以直接进 `tasks/plan.md`。建议先修 B1/B2 再写 plan。

---

## 0. 现场核对事实（审查依据）

工作区当前为干净状态——以下 spec 引用的输入产物**均不存在**（不影响设计评审，但试点前须重跑流水线生成）：

- `work/20260722/goals.json` —— 缺（根目录 `goals.json` 为空 `{"version":3,"goals":[]}`）
- `work/detect/*_mot_cache.json` —— 缺
- `work/frames/<fid>/f_*.jpg` —— 缺

已坐实的契约（spec 依赖项）：

| 事实 | 来源 | spec 是否对齐 |
|---|---|---|
| 帧命名 `f_%05d.jpg`（1 起，5 位零填充） | `extract_frames.py:169` | ✅ spec L93 映射 `f_{frame_idx+1:05d}.jpg` 正确 |
| `fid = os.path.splitext(file)[0]`（去 `.mp4`） | `extract_frames.py:204` | ❌ spec 全程用 file 全名，未写 fid 映射（M2）|
| mot_cache 结构 `{frames, balls:[[{conf,box,cx,cy,sec,frame_idx}]], persons:[[[x1,y1,x2,y2]]]}` | `mot_candidates.py:241-258` | ⚠ persons 框**无 track ID**（M1）|
| `run_mot` 只对 ball 做 MOT，不对 persons | `mot_candidates.py:300-351` | ⚠ 投篮者定位需自行关联 persons（M1）|
| build_highlight 当前 `--scorer` = `g.get("scorer")==scorer`（精确匹配 goals 字段）| `build_highlight.py:316` | ❌ 与 spec 语义②冲突（B1）|
| label 页导出 `anchor_time: e.anchor_t0` **未 round** | `gen_label_page.py:144` | ⚠ roster 键精度脆弱（M4）|

---

## 1. 阻断级（进 plan 前必须修订）

### B1. build_highlight 的 `--scorer/--team/--roster` 组合真值表缺失

spec L85-89 定义了三条语义（① 给 `--roster` 只认 assignments；② `--scorer` 匹配 tag/name；③ `--team` 匹配 team），但未覆盖完整组合，而当前实现是另一套逻辑：

```python
# build_highlight.py:316（现状）
goals = [g for g in goals if not scorer or g.get("scorer") == scorer]
```

当前 `--scorer` 直接精确匹配 goals.json 的 `scorer` 字段。spec 把这整套改写，但以下组合未定义：

| `--roster` | `--scorer` | `--team` | 期望行为 | spec 是否定义 |
|---|---|---|---|---|
| 无 | 有 | – | ？ | ❌（旧逻辑按 goals.scorer；但 spec L86 称"批次1该字段全空"→ 命中 0 条）|
| 无 | – | – | 全员 | ✅（旧逻辑）|
| 有 | 有 | – | roster 内解析 scorer→tag，反查 assignments | ⚠ 推断 |
| 有 | – | 有 | 按 team 取 players，反查 assignments | ⚠ 推断 |
| 有 | 有 | 有 | 互斥报错？ | ❌ |

**根因**：spec 用"语义①②③"分别陈述，但没给组合后的完整真值表，实现者会对"无 roster 给 `--scorer`""`--scorer`/`--team` 同给"自由发挥。

**建议**：在 roster schema 小节补一张组合真值表，明确：
- 无 `--roster` 给 `--scorer` 是否仍走旧 goals.scorer 兼容路径（决定是否破坏旧用法 / 是否需要 deprecation 警告）；
- `--scorer` 与 `--team` 同给时报错退出 1；
- `--roster` 与无 `--roster` 两条代码路径的隔离方式。

### B2. 投篮者定位核心算法描述不充分（persons 框无 ID）

spec L90-91：

> 窗口多帧投票（anchor−2.5s~−0.3s 内每帧取离球最近人框，众数胜出）

但 mot_cache 的 `persons` 是**无 track ID 的框列表**（`mot_candidates.py:257` 仅存 `[x1,y1,x2,y2]`），且 `run_mot`（`mot_candidates.py:300-351`）只对 ball 做 MOT，**不对 persons 做**。连续坐标无天然"众数"——必须先做 persons 的帧间关联（简易 IoU 链）或空间聚类，才能投票。

spec L91 自己实证"191948 两采样点选到不同人"，正是这层缺失的症候，却用"窗口多帧投票"一笔带过。投篮者定位是 Objective 三件事之首、且成功标准 2 直接依赖它，描述不足会导致实现质量不可控、SKIP 率无法预测。

**建议**：spec 至少指明：
- persons 框无 ID 的事实；
- 帧间关联方法（IoU 链 vs 中心点聚类，二选一在 plan 定）；
- "众数"的量化口径（按中心点分桶取众数 vs 聚类取最大簇），而非裸用"众数"一词。

---

## 2. 重要级（影响正确性 / 可落地，建议 plan 前定）

### M1. SKIP 球的认人 / 归属流程断裂

spec L92：窗口有效帧 <2 → SKIP。成功标准 2 称"SKIP 不计入分母"。但 **SKIP 球仍是 confirmed 进球，仍需归属才能进个人 / 分队合集**。spec 未定义：

- SKIP 球在确认页如何呈现（无裁图，立哥怎么认人？）；
- roster 怎么填（assignments 留空？那 build_highlight --roster 怎么处理？）；
- 成功标准 4"个人合集进球数与 roster 归属数一致"在 SKIP>0 时口径为何。

流程在 SKIP 处断链。

**建议**：补 SKIP 球处理——确认页标"无法定位、无预填"，保留进球时间让立哥凭视频/记忆手动选；roster 允许该球 assignments 留空且仍计 `confirmed=true`；build_highlight 对未归属球按"未识别"桶处理或跳过并 WARNING。

### M2. `file → fid` 映射未写明

crop_scorers 要读 `work/detect/<fid>_mot_cache.json` 和 `work/frames/<fid>/`，而 `fid = os.path.splitext(file)[0]`（`extract_frames.py:204`，去 `.mp4`）。spec 的 assignments 键用 file 全名（L77 含 `.mp4`），定位读数据却要 fid——这层转换 spec 全程未提，实现者会踩坑（拿 file 全名拼缓存路径找不到文件）。

**建议**：在帧映射注记（L93 附近）补一句"fid = 文件主名（去 `.mp4`），与 extract_frames / mot_candidates 一致；assignments 键保留 file 全名以便人工可读"。

### M3. roster 键 `file#anchor_time` 精度脆弱

spec L77/L82 锚定键 = `<file>#<anchor_time>`，"anchor_time 保留 1 位小数，与 goals.json 一致"。但 label 页导出时（`gen_label_page.py:144`）：

```javascript
anchor_time: e.anchor_t0   // 未 round
```

`e.anchor_t0` 来自 events_index，精度取决于上游。spec"1 位小数"是**假设** goals.json 实际值都恰好 1 位——若带更多小数（如 4.1234），roster 键与 goals.json 对不上，build_highlight --roster 匹配 0 条 → 合集空，且**静默**（看不出错）。

**建议**：写死键格式化规则——认人页导出 `f"{file}#{t:.1f}"`，build_highlight 匹配时同样 `f"{anchor_time:.1f}"`，两端共用同一 format 函数（rules.md §0.2 显式建模，禁止裸拼字符串）。

### M4. 颜色采样区域与判据未定义

mot persons 是**全身框**，含背景（球场 / 地板 / 观众）。spec L16 称"投篮者躯干主色 → 黑 / 白 / 便服"，但未定义：
- 采样区（框上 1/3？中间带？）——不取躯干区会被背景色污染分类；
- 判据（HSV 色相 vs 灰度 vs k-means 主色）；
- 阈值数值（rules.md §5 要求常量带来源注释）。

**建议**：spec 指定采样区（如"框宽 × 框高上 25%~60% 中间带，排除上下 1/5"）+ 判据方向；阈值数值进 `config.py` 并标注标定来源（实测 or 经验）。

### M5. 批次 1 / 批次 2 roster 合并机制未定义

spec L49-50 命令注释：

> 批次 2 的认人与批次 1 共用 roster——…assignments 合并进同一 roster.json

但确认页导出是**整文件覆盖**（类比 `gen_label_page.py:151` 的 payload 重建）。未定义：
- 合并方式（gen_scorer_page 支持 `--merge-existing`？还是立哥手改 JSON？）；
- 两批 players 列表不一致时（球衣互换、人员变动）的冲突处理；
- assignments 并集如何保证批次 2 导出不覆盖批次 1。

**建议**：明确合并协议——gen_scorer_page 支持 `--roster-existing`（读已有 roster，合并 assignments，players 以新名单为准或冲突报错退出 1），或 spec 显式声明"立哥手动合并"并在文档给合并示例。

### M6. 输出文件名前缀分支未在实现侧落实

spec L89 语义③要求 `--team` 产出 `队伍_{team}_进球集锦.mp4`。但当前 build_highlight（`build_highlight.py:360-361`）只有：

```python
tag: str = scorer or "全员"
out_path = os.path.join(out_dir, f"个人_{tag}_进球合集.mp4")
```

无 `队伍_` 前缀分支。spec 提了语义但实现要改的部分（按 `--team`/`--scorer` 分支取名、过滤逻辑分叉）未点出，易漏。

**建议**：spec 在 Project Structure 的 build_highlight 条目补"按 `--team`/`--scorer` 分支取名（队伍_ / 个人_ 前缀）+ 过滤逻辑分叉"。

---

## 3. 建议级（需澄清，不阻断）

- **m1. 号码识别无缓存**：crop_scorers `--read-numbers` 每球 1 次豆包调用（spec L38），重跑重复扣费。对照 `vlm_judge_events.py` 有 vlm_cache，spec 应要求号码识别结果落盘缓存（如 `work/<场次>/scorers/number_cache.json`，按 assignments 键索引）。
- **m2. `--players` vs `players.json` 优先级 / 位置 / schema 未定义**：spec L41 注释提到两者，但 gen_scorer_page 命令示例（L42-43）没带 `--players`，且 players.json 放哪、schema 为何、与 `--players` 同给时谁优先均未说。
- **m3. 便服球员的 `team` 字段值未定义**：players.team 仅示例"黑 / 白"（L73-74）。便服球员 team 填什么？是否合法 team 值？`--team 便服` 要否支持？（与 Open Question 3 相关，但 schema 侧须落定，否则 SchemaError 校验范围不清。）
- **m4. 投篮者裁图尺寸未定义**：号码识别要读背号，应给最小像素（如短边 ≥400px），否则背号糊掉号码识别必失败。spec 未提裁图规格。
- **m5. 成功标准 4 口径不清**："个人合集进球数与 roster 归属数一致"——SKIP 球归属数 <17 时怎么算"一致"？应改为"roster.assignments 覆盖全部非 SKIP confirmed 球"。

---

## 4. 疑问 / 内部一致性

- **Q1.** Boundaries（L115）把"给 build_highlight 加参数之外的语义改动"列为 **Ask first**，但 spec 语义①②③本身就在改 build_highlight 核心过滤语义——条款自相矛盾。应厘清"本 spec 已授权的语义改动范围"，否则条款会被误读为"还要再问一次"。
- **Q2.** 颜色分队"接近阈值归便服"未给阈值数值（rules.md §5 要求常量带来源注释），spec 应点出判据来源（实测标定 or 经验值）。
- **Q3.** Open Question 1 的退化方案③"代号按钮 + 聚类"在 Project Structure / Boundaries 里无对应实现入口——无名单时 gen_scorer_page 怎么跑？退化路径未落地，Open Question 与实现脱节。

---

## 5. 修订建议优先级

1. **先修 B1、B2**（补 build_highlight 真值表 + 投篮者定位算法描述）——否则 plan 无法起步。
2. **再修 M1-M5**（SKIP 流程、fid 映射、键精度、颜色采样区、批次合并）——影响正确性。
3. M6、m1-m5、Q1-Q3 可在 plan / 实现阶段一并消化，不阻塞 spec 定稿。

修完 B1/B2 后，建议本 review 文档随 spec 一起过 `spec-reviewer` 子代理二审（AGENTS.md 文档自审要求）。

---

## 附：已对齐项（无需改动，备查）

- 命名用标签不用真名（L10/L73）✅ 符合 AGENTS.md
- roster 按场次隔离、跨场次不合并（L11）✅
- 输出 1080p/50fps、比例跟随素材、`--out` 按场次注入（L46-48）✅ 符合 build_highlight 现状
- 帧映射 `f_{frame_idx+1:05d}.jpg`（L93）✅ 与 extract_frames.py 一致
- 不改 gen_label_page.py / gen_review_clips.py（L118）✅ gen_scorer_page 输出 scorer.html 与 label.html 不撞名
- API key 走环境变量不入文件（L27/L119）✅
- 技术栈无新依赖（L26）✅
