# Plan: 照片库认人 v2.1（免费信号 → 人裁）

依据 `docs/photo-roster/spec.md`（v2.1，2026-08-27 立哥定：零 token 路线）。
真值标尺：`work/20260822_citymonkey/truth_16.json`（16 球机器可读）。

## 架构决策

- **L1 双候选 spike 并行**：号码 OCR（PARSeq 系）与人脸（insightface）互不
  依赖，同一真值标尺评分，spike 后立哥 checkpoint 定选型——不预判哪路赢
- **T5 预填机制复用**：L1 matcher 产出对齐 photo_matches.json 现 schema
  （spec 数据契约写死映射），gen_scorer_page 零改动；video.py 仅换 ②.5 的
  生产者调用
- **spike 与产品代码分离**：spike 一律 work/ 一次性脚本（豁免四件套），
  选型定了才在 scripts/ 建产品 matcher（走完整四件套）
- **crop-quality 是并行专项**（docs/crop-quality/ 自己的四件套）：裁图闸
  修好前，spike 用现有含废图裁图——反映现状上限，废图球按 truth_16 的
  invalid 类不计入成绩分母
- **评测三指标**：覆盖率（机器采纳比例）/采纳误指认率（红线 ≤10%）/
  人裁负担（进确认页比例）；覆盖率不硬卡

## 前置依赖

- D1 truth_16.json 已落盘 ✓（2026-08-27；**58 球分母 = goals_batch1.json
  58 条 confirmed——同目录旧布局 goals_batch.json 为 57 条已弃用，差 1 球
  系标注修订，勿混用旧文件**）
- D2 立哥批准新依赖：PARSeq 系（S1）、insightface（S2）——随 spec v2.1 请批

## Task List

### Phase A.0：spike（work/ 一次性脚本，豁免四件套）

- [ ] T8 S1 号码 OCR spike
  - Acceptance: PARSeq 系管线跑通（安装/权重下载走 HTTPS_PROXY，装不上记录
    原因换备选实现不硬磕）；truth_16 出命中/误指认/漏；58 球出覆盖率
    （有号球占比 + 库外读数率）；报告含"可读帧率"观察；**许可按实际选用
    组件分别核实（PARSeq-B 本体 Apache-2.0 vs 整管线 CC-BY-NC，报告注明）**；
    原始数据归档
  - Verify: work/spike_ocr/ 报告 + truth_16 对账表（**对账表行数=16**：
    我方 8 球正确率、对方 4 球误中率、废图 2 球行为、**未判 2 球单列不进
    分母**；**覆盖率分母=58**；**PARSeq 装不上走"未验证"分支时，以对账表
    缺失+原因记录为验收替代**）
  - Files: work/spike_ocr/（一次性）
- [ ] T9 S2 人脸 spike
  - Acceptance: insightface buffalo_l 跑通（**装不上/权重下载失败记录原因、
    结论记"未验证"，与 T8 失败路径对称**）；truth_16 出命中/误指认/漏
    （多帧质量加权投票 vs 单帧，两口径都记）；小脸检出失败率单列；报告归档
  - Verify: work/spike_face/ 报告 + truth_16 对账表（**行数=16**，未判 2 球
    单列不进分母）
  - Files: work/spike_face/（一次性）

### Checkpoint（立哥过目）

- [ ] T10 选型拍板：L1 = OCR / 人脸 / 双路接力 / 皆弃
  - Acceptance: 两 spike 报告呈阅，立哥结论记 review04.md；皆弃 → 本功能
    终止（todo 余项划掉注明）
  - Files: docs/photo-roster/review04.md

### Phase B：产品化（选型非"皆弃"才动；走四件套修订）

- [ ] T11 L1 matcher 产品化
  - Acceptance: scripts/ 下 matcher（按选型建）——缓存幂等（键=裁图 md5+
    模型版本）、产出对齐 photo_matches.json schema（高置信映射 score、
    margin=0.0 占位）、低置信/无命中不入 matches、名单先验（OCR 库外读数
    不采纳）、**双路启用时接力编排 = OCR 高置信 > 人脸高置信 > 人裁，
    OCR 命中不调人脸（mock 计数断言，仅选型=双路时生效）**、单球失败
    ERROR 不炸批；单测注入假识别器
  - Verify: `pytest tests/test_<matcher>.py` + validate_matches_payload 联调
  - Files: scripts/<ocr|face>_match_scorers.py、tests/test_<matcher>.py
- [ ] T12 video.py people 串联换 L1
  - Acceptance: ②.5 步骤由 CLIP 匹配器换 L1 matcher（条件与降级语义同 T6
    既有口径：photos/ 存在且非 --skip-cluster；仅 ②.5 允许失败降级）；
    **people 链 read_numbers 默认翻转 False（v2.1 零 token 定案；
    --read-numbers 显式开保留兼容，既有手工功能不删）**；单测断言串法
  - Verify: `pytest tests/test_video.py -k people`
  - Files: scripts/video.py、tests/test_video.py

### Phase A：级联评测 + 收尾

- [ ] T13 Phase A 级联评测（卡 T12 + 测试场次 confirmed roster）
  - Acceptance: **photo_match_scorers.py --evaluate 改造为级联评测器**
    （L1 结果对账，spec Project Structure 契约点的实现载体）；测试场次
    真值跑级联，出覆盖率/采纳误指认率/人裁负担三指标；采纳误指认 ≤10%
    达标；高置信阈值按分布定稿（Ask first 立哥确认）；报告归档
    review05.md；不达标 → 评估恢复 K3 兜底（**仅出报告不实施**，
    Open Questions）报立哥
  - Verify: 评测器单测 + 真值场实跑报告
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py、
    work/<测试场次>/cascade_eval_report.md、docs/photo-roster/review05.md
- [ ] T14 文档收尾 + 真机验证
  - Acceptance: 使用手册.html 认人流程改免费信号口径；AGENTS.md 认人链路
    更新；docs/经验教训.md 补"同制服认人级联"条目；**spec/plan 阶段命名
    统一为执行序（spike/选型/产品化/评测/收尾，消除 Phase A/B 倒挂）**；
    真机 people 链重跑肉眼抽验预填；review06.md 归档
  - Verify: 关口全绿 + 真机抽验
  - Files: 使用手册.html、AGENTS.md、docs/经验教训.md、docs/photo-roster/
    （spec/plan 命名统一 + review06.md）

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|---|---|---|
| PARSeq 装不上（Py3.14/torch 2.13 兼容） | 中 | 记录原因换备选实现（其他开源 OCR 或自训小模型），不硬磕；S1 结论记"未验证" |
| 号码可读帧率太低（俯视远景，冰球固定广角仅 5% 帧可读，arXiv:2405.13896，review03.md 归档） | 高 | spike 如实出数；OCR 覆盖率极低 → 选型靠人脸或皆弃，不硬上 |
| 小脸检出失败/误认 | 中 | 检出失败率单列；多帧投票抬上限；人脸只作高置信预填 |
| 废图污染 spike 成绩 | 低 | truth_16 invalid 类不计分母；crop-quality 修好后续场次自然受益 |
| 非商业许可阻碍将来开源 | 中 | Open Questions 挂账；开源时评估替换或声明 |

## Open Questions

- L1 高置信阈值：spike 分布出来后定稿（Ask first）
- Phase A 评测场次：citymonkey 续用 or 新素材，以 roster 确认进度为准
