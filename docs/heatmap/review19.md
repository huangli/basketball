# review19：v4.2 实施后文档增量复核（2026-08-16）

审查对象：spec.md 打样 bug 修正段 + 文档联动三处（使用手册.html /
docs/video-cli/spec.md §build / AGENTS.md 统一入口行）
审查员：spec-reviewer（agent-65，resume 同一实例）· 结论：**通过**

## 核对结论

- 打样 bug 修正段：spec 对打样原式的描述逐字吻合（work/heatmap_style_zones.py:153）；
  死代码论证成立（角条区被 inside3=True 吞进 mid 分支，corner 分支永假）；
  生产版 `inside3 = (|x|≤6.6 且 r≤6.75)` 与 spec 修正式一致；
  "当前数据无影响"自洽（corner_y≈1.415 < 实测 dy 下限 1.9）；
  test_zone_of_known 的 (±7.0, 0.5)→corner 用例构成有效回归保护
- video-cli spec §build 收尾热图条：与 _run_heatmap_step 实现逐条吻合
  （触发点/懒 import/只传 session_dir/INFO 跳过/异常不阻塞/dry-run 计入步数）
- AGENTS.md 统一入口行：与 plan Task 7 写死改动一字不差
- 使用手册.html：双图文件名与实际产物一致；INFO 跳过/异常不阻塞转述准确；
  耗时注记（十几秒）与 spec J2 量级吻合

## 建议（2 条，不阻断）

1. "符号反了"→ 严格说是条件分支取值写反（已顺手修订）
2. dry-run 的 Step 以 subprocess 形式展示而实际 in-process——与
   "goal_heatmap CLI 保留作单独重跑入口"呼应，属合理设计，记录备查
