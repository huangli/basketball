# Review 01: opponent-filter spec 审查（2026-09-06）

> 审查员：spec-reviewer 角色子代理（只读审查）。结论：修订后通过（处置如下）。

## 阻断问题与处置

- **B1：`_build_expand_all` 现状不跳过对手队/伪球员**（只跳便服分队；便服个人合集照出，spec"同便服口径"表述错误）→ spec 设计 4 已改为"显式跳过 tag=对手 个人合集 + 对手队分队合集"，并注明与便服口径的差异。
- **B2：`teamOfTag` 会把"对手"误判为便服**（黑/蓝/白前缀匹配，其余归便服；导出兜底走它）→ spec 设计 2 已加"tag=对手 必须特判，team 写入与页面分组不走 teamOfTag 兜底"。
- **B3：伪球员 team 取值与 UI/CLI OPP 不一致风险**（cfg.opponent 空时有效对手名是 opponent_of(session)）→ spec 设计 1 已改为"team = 有效对手名（cfg.opponent 缺省按场次 ID 后缀派生），与 UI OPP 同口径"。

## 遗留

- 新增 O2：黑/白阵营映射与伪球员的关系实施时摸清，并存不冲突即可。
