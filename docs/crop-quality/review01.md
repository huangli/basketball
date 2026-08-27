# Review 01: 裁图质量闸——标定 + 真机验证（2026-08-28）

## C1 标定章（work/crop_quality_calibration/）

- 口径：完全复现 crop_scorers 生产链（locate → trace → score → pick），框取
  mot 缓存；**58/58 球入选帧质量分一致 + 135/135 入选裁图字节级一致**
  （verify_crops.json，帧身份物证）
- 643 候选帧分布：宽高比（外扩）p1=0.2254、min=0.0898（t550.0 细条）；复检
  置信度完美双峰（18 帧无 person=0.0，其余 625 帧全部 ≥0.5）
- **三阈值定稿（2026-08-28 立哥批，review04）**：
  - MIN_RATIO=0.15：仅拦 t550.0 细条帧（0.0898），次低帧 0.1988 无误杀
  - MAX_RATIO=1.2：超上限 10 帧全属 t44.2（镜头前挥臂特写，新废帧类型），
    该球补位存活
  - PERSON_CONF=0.25：距 truth 我方入选帧最低置信 0.6111 有 2.4 倍余量
- 建议阈值下拦 29/643 帧；6 球全灭归 SKIP（目检全废：广告牌酒瓶×4、
  无人特写×1、瓶子×1）

## C4 真机验证章（citymonkey 重跑，带闸）

操作：`mv scorers_b1 → scorers_b1.bak` → `video people --session
20260822_citymonkey --no-read-numbers`（EXIT=0；②.5 已随 T12 为人脸匹配器，
顺带产出 9 球高置信命中）。

| 核对项 | 结果 |
|---|---|
| t480.1 瓶子球被拦 | ✓ status=SKIP、reason=quality_gate |
| t550.0 细条帧被拦 | ✓ 细条帧（ratio 0.09）被拦，补位存活 status=OK（1 张 ratio 0.21）——预期拦截不计误杀 |
| 全灭 SKIP 6 球 | ✓ 与标定预测的 6 个废球一致（均非 truth 我方球；t480.1 为 truth invalid，废图球全灭正是设计意图） |
| **truth_16 我方 7 球零误杀** | ✓ 全部 status=OK；裁图数与旧版逐一相同（t10.9 旧版即 1 张、ratio 0.567 健康，非被拦） |

逐球核对表（我方 7 球，新 candidates vs .bak）：t10.9（1=1）、t34.1（3=3）、
t173.8（3=3）、t264.4（3=3）、t529.8（3=3）、t608.2（3=3）、t692.4（3=3）——
帧级零误杀成立。

## 附带验证（人脸匹配器真机首跑）

- 注册净化实跑：6 张照片弃用留痕（22/57/77 小脸 w<120、6/8/9 无脸），
  7/7 号码各剩 1 张合格正脸可用（审计 photos/face_registration_audit.json）
- 52 球出分、**9 球高置信命中**（24 张无脸裁图跳过）、确认页预填生效
  （占位条目 半截篮<号> 注入 6 个）
- 印证 review04 前置条件：立哥补单人正脸照可提升注册张数与命中率

## Santa 记录

- C2/C3 代码双独立审查 PASS（两条 MEDIUM 经 T11 车道修复：中文路径读图、
  detector 批级单例）；T12 双审 PASS（argparse 三态实证）
- 遗留 suggestions（下轮评估）：spec 测试策略"旧产物幂等"条目与"移走重跑"
  行为口径自相矛盾建议删除；SKIP×rawdir 组合断言可补
