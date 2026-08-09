# Review 01: 认人提效三件套 spec-reviewer 审查（第 1 轮）

日期：2026-08-09
对象：docs/scorer-cluster/{spec,plan,todo}.md（初版）
审查人：spec-reviewer 子代理（对照 scripts/ 现有代码与 work/20260722 真实数据核查）

## 审查结论：4 个阻断问题，已全部修订

### 阻断 1：crop/crops[0] 定义自相矛盾（spec ↔ plan）

- 问题：spec 契约写 crops[0]=质量最佳帧，plan 风险表写 crops[0] 仍是定位帧，不可兼得
- 修订：**写死 crops[0]=质量最佳帧**（spec 数据契约）；plan 风险表改为
  "不保证是定位帧，由页面预览片段视频终裁兜底"

### 阻断 2：成功标准 104 球口径与只跑 scorers_b3 不自洽

- 问题：三批次 candidates 分散在 scorers/scorers_b2/scorers_b3（17+37+61 条，
  其中 confirmed 104），原命令只跑 b3，成功标准不可达不可验
- 修订：`--candidates` 改为可重复传参、键集取并集（同 key 后者覆盖前者）；
  spec 全部命令改为三批次合并；--evaluate 只统计 roster assignments 里的
  104 键，removed/去重球剔除

### 阻断 3：多裁命令丢 number_guess，number_cache 语义漂移

- 问题：原多裁命令没带 --read-numbers，重跑落盘会丢现有号码预填；
  且多裁后 crop 图内容变化，goal key 缓存的号码结论与新图脱节
- 修订：命令补 `--read-numbers --max-reads 80`（缓存命中零新调用直接回填）；
  spec 数据契约写明口径：number_cache 键仍为 goal key、已知漂移可接受
  （号码只是预填提示，终裁在页面）

### 阻断 4：选帧窗口未定义

- 修订：spec 数据契约补"窗口 = 定位帧前后各 min(2s, mot_cache 覆盖边界)，
  5fps 即各 ≤10 帧，越界即停；帧间 IoU ≥ 0.3 链上，链断即停"

## 非阻断建议的处理

| 建议 | 处理 |
|------|------|
| embedding 缓存键含 threshold 会导致标定调档重复推理 | 采纳：缓存键 = model + 裁图 md5，threshold 不入键 |
| 三档阈值均不达标无降级出口 | 采纳：spec 成功标准 + plan Checkpoint 2 写明降级出口（指标记 review、功能照上、纯度转观察值） |
| 号码只用 crops[0]，质量最佳帧未必露号码 | 采纳：记 Open Questions（多帧多数投票留作后续增强） |
| crops[1..] 命名规则未定义 | 采纳：主名保持兼容，rank≥2 追加 `_q2`/`_q3` 后缀 |
| 认人页命令示例以 `...` 结尾 | 采纳：补全 --roster-existing/--index/--out 实参 |
| cluster 输入顶层结构未写 | 采纳：契约注明 `{"session", "candidates": [...]}` |
| 提交粒度应分 Phase | 采纳：plan/todo 改为三个 Checkpoint 各提交一次 |

## 核查通过项（审查代理确认）

- 真值成立：roster.json = 104 assignments / 20 players / confirmed=true；
  三批次 candidates 并集全覆盖 104 球
- 技术路线可行：mot_cache persons 按帧对齐存 Box，IoU 链有数据源；帧图全量留存
- 聚类键 format_key 与 roster assignments 键格式一致；SKIP 球进 unclustered、
  旧数据回退单 crop，均有覆盖
- todo 与 plan Task 1–8 一一对应；四件套目录符合 AGENTS.md 约定

## 结论

阻断问题全部修订完毕，三件套可进入实施（Phase 1）。
