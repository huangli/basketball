# review14：v4 spec/plan 一轮审查（2026-08-15）

审查对象：docs/heatmap/spec.md、plan.md、todo.md 的 v4 修订
（v3 目击证伪后修复：持球点限出手前窗口 + 队色硬守卫）
审查员：spec-reviewer（coder 子代理扮演）· 结论：**需修订**

## 阻断

- **B1 分母 106/107 口径分裂**：spec 多处写死 106（侦察时点快照），
  v3 实跑与 v4 重跑分母实为 107（并行会话又认 1 球，半截篮 51→52，
  roster confirmed=true）；成功标准"K1 写死"的分母与运行输入矛盾。
  → 修订：侦察节保留 106 快照并注明时点，实跑/成功标准统一 107

## 严重

- **S1 截断空轨迹的 start_nearest_box 回退歧义 + 侧门**：喂截断空 Track
  会 IndexError；喂原轨迹则晚起轨迹（起点 ∈ (anchor−0.5, anchor]）仍能从
  回退链到筐下人。→ 写死：find_held_box 与 start_nearest_box 均喂截断
  轨迹，截断空 → 无种子直接落兜底/no_landing
- **S2 team_color 缺失分两层**：键整体缺失已写 WARNING；键存在但某队伍
  不在映射内则该队守卫静默禁用。→ 启动校验队伍集合 ⊆ team_color 键，
  缺队伍一次性 WARNING
- **S3 session_facts 重建丢键未声明**：run_session --force 重探测用
  build_facts 整体重写 facts 不含 team_color → 守卫静默退化。
  → 风险表补行：启动 WARNING 兜底 + run_session 写入列待办跟进

## 建议（落实见 plan/todo）

- A1 plan 写明截断 Track 构造方式（列表推导新建实例，不改原对象）
- A2 常量关系自洽已核实（HELD_SEARCH_BEFORE_SEC=0.5 vs
  RELEASE_BEFORE_SEC=1.0 / TRACK_START_MIN_SEC=0.8 / trace 窗 ±2.0s）
- A3 补两守卫分工对照句（串人守卫保链不漂 vs 硬守卫保人对）
- A4 HeatLanding.reason docstring 同步 team_mismatch
- A5 机检复核载体写死（work/color_recheck.py 一次性脚本）+ 共模盲区声明
- A6 便服在守卫前剔除，team_color 不含便服
