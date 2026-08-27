# Todo: 照片库认人 v2.1（免费信号 → 人裁）

依据 `docs/photo-roster/spec.md`（v2.1）+ `plan.md`。按依赖序执行，逐项验收。
真值标尺：`work/20260822_citymonkey/truth_16.json`（我方 8 / 对方 4 / 废图 2 /
未判 2，废图不计分母）。

- [x] T0-T6 v1 已交付（匹配核心/页面预填/串联；CLIP 路线已证伪归档 review03）
- [x] T7 spec v2.1 修订（去 K3 层，零 token 路线，2026-08-27 立哥定）
- [x] T8 S1 号码 OCR spike（PARSeq 系，work/ 一次性）
  - Acceptance: 管线跑通（装不上记录原因换备选不硬磕）；truth_16 命中/
    误指认/漏对账表；58 球覆盖率+库外读数率；可读帧率观察；**许可按实际
    选用组件分别核实（PARSeq-B 本体 Apache-2.0 vs 整管线 CC-BY-NC，报告
    注明）**；报告归档
  - Verify: work/spike_ocr/ 报告
  - Files: work/spike_ocr/
- [x] T9 S2 人脸 spike（insightface buffalo_l，work/ 一次性）
  - Acceptance: 管线跑通（装不上/权重下载失败记录原因记"未验证"）；
    truth_16 命中/误指认/漏（多帧投票+单帧双口径）；小脸检出失败率单列；
    报告归档
  - Verify: work/spike_face/ 报告
  - Files: work/spike_face/
- [x] T10 【checkpoint】立哥选型：OCR / 人脸 / 双路 / 皆弃
  - Acceptance: 两报告呈阅，结论记 review04.md；皆弃 → 余项划掉注明
  - Files: docs/photo-roster/review04.md
- [ ] T11 L1 matcher 产品化（卡 T10 选型）
  - Acceptance: 缓存幂等（裁图 md5+模型版本）；产出对齐 photo_matches.json
    schema（高置信映射 score、margin=0.0 占位）；低置信/无命中不入 matches；
    OCR 库外读数不采纳（名单先验）；**双路启用时接力编排 = OCR 高置信 >
    人脸高置信 > 人裁，OCR 命中不调人脸（mock 计数断言，仅选型=双路时
    生效）**；单球失败 ERROR 不炸批；单测注入假识别器
  - Verify: `pytest tests/test_<matcher>.py` + validate 联调
  - Files: scripts/<ocr|face>_match_scorers.py、tests/test_<matcher>.py
- [ ] T12 video.py people 串联换 L1（卡 T11）
  - Acceptance: ②.5 换 L1 matcher（条件/降级语义同 T6 既有口径）；
    **people 链 read_numbers 默认翻转 False（v2.1 零 token 定案；
    --read-numbers 显式开保留兼容）**；单测断言
  - Verify: `pytest tests/test_video.py -k people`
  - Files: scripts/video.py、tests/test_video.py
- [ ] T13 Phase A 级联评测（卡 T12 + 测试场次 confirmed roster）
  - Acceptance: **photo_match_scorers.py --evaluate 改造为级联评测器**
    （L1 结果对账，spec Project Structure 契约点的实现载体）；覆盖率/
    采纳误指认率/人裁负担三指标；采纳误指认 ≤10% 达标；高置信阈值定稿
    （Ask first）；报告归档 review05.md；不达标评估恢复 K3 兜底
    （**仅出报告不实施**）报立哥
  - Verify: 评测器单测 + 真值场实跑报告
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py、
    work/<测试场次>/cascade_eval_report.md、docs/photo-roster/review05.md
- [ ] T14 文档收尾 + 真机验证
  - Acceptance: 使用手册.html / AGENTS.md / docs/经验教训.md 同步免费信号
    口径；**spec/plan 阶段命名统一为执行序（spike/选型/产品化/评测/收尾，
    消除 Phase A/B 倒挂）**；真机 people 链重跑肉眼抽验；review06.md 归档
  - Verify: 关口全绿 + 真机抽验
  - Files: 使用手册.html、AGENTS.md、docs/经验教训.md、docs/photo-roster/
    （spec/plan 命名统一 + review06.md）
