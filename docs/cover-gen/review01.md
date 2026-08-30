# Review 01：cover-gen spec 审查（agent-evaluator 代行 spec-reviewer，2026-08-30）

**结论：不通过（2 阻断），修订后复审。** 命名复用与口径对齐扎实（通过 7 项）。

## 阻断问题

- **B1. D2 缩放口径自相矛盾**：spec 写"3:4 竖版 1080×1440"，但 D2 写"等比缩放至 1080 高"
  ——那只到 810×1080。正确：`scale=max(1080/W, 1440/H)` 等比充满 + 中心裁；数学上任何源
  都能填满（放大+中心裁），4:3 源若高<1440 只是放大、画质降，非裁剪失败。
- **B2. covers 无过滤缺省行为未定**：裸命令等价 build `--all`（遍历 team+个人），不是
  build 默认的"全员"（`个人_全员_进球合集`）；AGENTS.md 有"不出全员总合集"口径。
  需明示 covers 缺省 = `--all`。

## 建议

- S1. 4:3 路径无实测/无测试（唯一场次全 16:9）——补 4:3 合成用例或收窄 claim
- S2. plan/todo "21 张"与事实不符（实测 20）——改不硬编码，写"=select_goals 命中数"
- S3. 多批次 merge / --batch 未纳入测试
- S4. 无 rawdir 报错路径未测
- S5. `anchor-0.5` 当 anchor<0.5 会 ≤0——需 clamp 或 WARNING
- S6. 字体回退三处表述冲突——统一为"微软雅黑→宋体回退+日志提示；皆无才显式报错"
- S7. 片名含球员名应注明"属主名非进球细节"，消除歧义

## 通过项

命名复用正确（select_goals ④⑤/⑧ 便服口径）；--session/--rawdir 缺省与 build 一致；
需求①③⑤覆盖无 over-engineering（logo/VLM 列为扩展点）；产物隔离规范；
rules.md 合规；Success Criteria 可检验。
