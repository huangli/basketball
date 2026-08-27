# Review 04: T10 选型 checkpoint（2026-08-28 立哥拍板）

## 拍板结论

- **L1 = 人脸单路高置信档**（insightface buffalo_l，sim 高置信档，观察值 ~0.40，
  Phase A 评测分布后定稿，Ask first）
- **OCR 不投**：我方 2/8 命中、置信度不可切（正确 0.52 vs 噪声 0.985 重叠）、
  对方同号红线 1/4（blue6→6，名单先验挡不住双方同号）、有效采纳仅 6.9%
- **crop-quality 三阈值定稿**：MIN_RATIO=0.15 / MAX_RATIO=1.2 / PERSON_CONF=0.25

## 呈阅材料（双 PASS 归档）

- `work/spike_ocr/report.md`（PARSeq-B 18 窗滑窗；可读帧率真号口径 28.6%；
  PARSeq-B 本体 Apache-2.0 已核 LICENSE，未引入 CC-BY-NC 整管线）
- `work/spike_face/report.md` + `registration_audit.json`（raw top-1 4/8 对 4 误
  不可用；**sim≥0.40 档 2/8 采纳全对、0 误指认、对方 0/4 误中**——16 球小样
  观察值非定稿；小脸检出失败 25%；注册净化必需：背景路人曾注册成 57）
- `work/crop_quality_calibration/report.md`（643 候选帧分布；三阈值断层/双峰
  支撑充分；truth 我方 7 球帧级零误杀；6 废球全灭归 SKIP 均属预期拦截；
  复现校验 135/135 字节一致）

## Santa 过程记录

- 开发产物双独立审查 R1：B PASS / C FAIL（4 处文档级硬伤：18 窗误写 22、
  t34.1 帧一致性口径、sim 区间指代、注册审计未落盘）→ 全部修正
- R2：双 PASS 零阻断（对账表逐球复算一致；T9 小样口径如实标注）

## 后续路线（按 plan）

- crop-quality：C2/C3 闸实施（阈值已定稿）→ C4 真机验证 → C5 文档
- photo-roster：T11 人脸 matcher 产品化（face_match_scorers.py；注册净化
  口径产品化：单人正脸+最大脸+尺寸闸）→ T12 video.py 串联（②.5 换人脸
  matcher + read_numbers 默认翻 False）→ T13 级联评测（阈值定稿）→ T14 收尾
- 前置条件（立哥侧，随 T11 落地提示）：照片库补/换**单人正脸照**——
  14 张现照 4 张背面无脸、3 张背景小人脸污染，净化后 7 号各仅剩 1 张合格
