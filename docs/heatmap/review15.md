# review15：v4 spec/plan 复审（2026-08-15）

审查对象：review14 意见落实后的 docs/heatmap/spec.md、plan.md、todo.md
审查员：spec-reviewer（coder 子代理扮演，resume 同一实例）· 结论：**通过**

## 一轮意见落实核对（全部正确落实）

- B1：spec 新增"分母口径（B1 写死）"段，106=侦察时点快照、107=实跑/
  成功标准分母；目标/成功标准/边界全同步（107+15=122 与 hoops 121/122 自洽）
- S1：截断 Track 新建实例、双喂截断轨迹、截断空→无种子落兜底/no_landing；
  与代码事实吻合（晚起轨迹因 anchor−first.sec < 0.8 必落 no_landing，
  侧门关死）
- S2：启动校验写死（缺队伍 WARNING + 该队禁用；键缺失全禁 + WARNING）
- S3：风险表补行（WARNING 兜底 + 待办跟进）
- A1/A3/A4/A5/A6 均落实到 plan/todo/spec

## 遗留建议（不阻断，随 Task 5 顺手修，已当场落实）

1. plan.md Task 3 首行"实跑 106 球"残留 → 已改 107
2. spec 启动校验队伍集合是否含便服有歧义（便服必缺映射会假 WARNING）
   → 已改为"不含便服，便服已在守卫前剔除"，与队别口径节闭环

## 结论

通过。v4 修复口径与 crop_scorers/mot_candidates/goal_heatmap 代码事实
逐点吻合，成功标准三条门（机检队色相反=0 / 覆盖 ≥55% 或立哥裁决 /
目击 ≥10/15）均可机检或可验证。进入 Task 5 实施。
