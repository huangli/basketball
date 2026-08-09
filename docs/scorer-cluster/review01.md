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

---

## 附：实跑标定记录（2026-08-09，Phase 1/2 实跑后补记）

### 多裁串人守卫效果（批次 3，51 球）

- 守卫前：40 个多裁球中 15 个跨队混裁，其中**明确黑↔白混人 7 个**
- 守卫后（drop_opposite_team）：**明确混人 0/40**；余 10 个为便服边界噪声
  （同人不同光线属可接受）；号码缓存回填零新调用

### 聚类纯度标定（三批次合并 104 球，对照已确认 roster，99 键入统）

| linkage | threshold | 簇数 | 纯度 |
|---------|-----------|------|------|
| average | 0.25 | 7 | 21.2% |
| average | 0.20 | 20 | 32.3% |
| average | 0.15 | 42 | 48.5% |
| average | 0.10 | 77 | 82.8% |
| complete | 0.25 | 18 | 33.3% |
| complete | 0.20 | 30 | 42.4% |
| complete | 0.15 | 52 | 62.6% |
| complete | 0.10 | 81 | 85.9% |

**结论：纯度目标（15~25 簇 ≥85%）未达成**——CLIP ViT-B-32 全身裁图
embedding 被场景/球衣颜色主导，同队不同人分不开；85% 纯度要 81 簇
（20 个人），失去批量确认意义。按 spec 预设降级出口执行：**簇级功能照上
（opt-in via --clusters），纯度转为观察值**；定稿 deliverable 用
complete@0.15（52 簇/62.6%，偏紧偏安全，批量错指派代价 > 多点的几下）。

后续增强方向（按预期收益排序）：
1. 专用 Re-ID 模型（OSNet/torchreid）——新依赖，须先问立哥
2. 照片库人脸 embedding 比对——等立哥供照
3. 队伍颜色先分桶再桶内聚类（零新依赖，可小幅提纯度）
