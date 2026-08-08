# Review 03: spec v3 轨迹法修订 + 四件套一致性

> - 审查对象：docs/scorer/spec.md（v3「投篮者定位算法」节）、plan.md、todo.md（T2b/T4b）
> - 审查日期：2026-08-08
> - 审查人：Kimi Code（spec-reviewer 子代理）
> - 结论：**需修订 → 已按 B1/B2/B3 修完**（纯文档同步，代码不动）

## 已核验通过

- v3 算法描述与 crop_scorers.py 实现逐条一致（窗口 [−4.0,+0.5]、run_mot(min_length=1)、
  端点距 ≤200px、--candidates fid+|t0−anchor|≤0.3s、严格包含无 margin、start_fallback、
  裁图规格不变）
- 批次 1 实测口径（OK 17/17、SKIP 0、裁图 4 对/10 勉强/1 可疑/2 错）与 todo T2b 闭环
- rules.md / AGENTS.md 兼容；review 编号符合规则（本文 = review03）

## 阻断问题与修订（本轮已全部修复）

| # | 问题 | 修法 |
|---|---|---|
| B1 | Testing Strategy 残留 v2 投票法措辞，与 v3 矛盾 | 已改写为轨迹法测试口径（含 SKIP 三分支与 --candidates 退化） |
| B2 | Commands 缺 --candidates/--rawdir，照抄偏离 spec | 已补全两条 crop_scorers 命令 |
| B3 | plan.md AD 仍 v2 算法，四件套不一致 | 已改写为轨迹法摘要 + 风险表口径同步 |

## 非阻断建议（已部分采纳）

1. spec 头部补 v3 changelog —— 已采纳
2. 算法节补三处边界语义（--candidates 未匹配退化、起点无人框仍 SKIP、距离=框中心欧氏）—— 已并入 Testing Strategy 口径
3. T4b 预览片段（clips/ 产物、clip 字段、页面视频优先级）spec 正文未收录 —— 留待 T8 收尾补录
4. 颜色标定基数注释（15 张旧 run vs 17 张新 run）—— 留待 T8
5. SC2 措辞（SKIP 不产图）—— 留待 T8
6. todo T2 原条目加注"已被 T2b 替换" —— 已采纳
