# Plan: 裁图质量闸（crop-quality）

依据 `docs/crop-quality/spec.md`。先标定后写码：阈值来自 citymonkey 58 球
实测分布，不拍脑袋。

## 架构决策

- **闸插选帧循环内（补位语义，spec 写死）**：候选帧逐帧过闸，废帧丢弃继续
  取次优帧，凑够 best_crops 或帧池耗尽；全废才 SKIP
- **两道闸顺序：宽高比先行、人物复检殿后**——宽高比是纯几何计算零成本，
  先筛掉畸形框；yolov8n 复检只对过了几何闸的帧跑，省 CPU
- **yolov8n 惰性加载**：仅裁图路径用到；测试注入假检测器不碰真模型
  （models/yolov8n.pt 现成，持球排除用同款）
- **先标定后写码**：C1 出分布报告，阈值建议值立哥过目后写死常量
  （Ask first）

## Task List

- [ ] C1 标定：58 球裁图分布
  - Acceptance: citymonkey 58 球全部候选帧（含未入选帧，从检测缓存取框）
    的宽高比分布 + yolov8n 框内复检置信度分布（**spec 引用的 16 张样本
    分布仅作先期参考，阈值以本任务 58 球全量分布为准**）；重点标注
    t550.0（畸形）、t480.1（瓶子）、t34.1/t186.6/t264.4（错人框）落在
    分布哪里；给出
    MIN_RATIO/MAX_RATIO/PERSON_CONF 建议值（宁漏拦不错杀）；归档
    review01.md 标定章
  - Verify: work/crop_quality_calibration/ 分布报告
  - Files: work/（一次性分析脚本）
- [ ] C2 宽高比闸实施
  - Acceptance: 选帧循环内几何闸（阈值= C1 定稿常量）；废帧 INFO 留痕
    （时刻+原因）；补位语义；全废球 SKIP+reason 且预览片段保留、SKIP 条目
    不落 crops/crop_scores；单测边界值（恰好等于/略超/正常不误杀）
  - Verify: `pytest tests/test_crop_scorers.py -k ratio`
  - Files: scripts/crop_scorers.py、tests/test_crop_scorers.py
- [ ] C3 框内人物复检闸实施
  - Acceptance: 几何闸通过的帧跑 yolov8n 复检，无可信 person（conf<
    PERSON_CONF）判无人废帧；检测器惰性加载+可注入；留痕/补位/SKIP 语义
    同 C2；单测注入假检测器（有框放行/无框拦截/低置信拦截）
  - Verify: `pytest tests/test_crop_scorers.py -k recheck`
  - Files: scripts/crop_scorers.py、tests/test_crop_scorers.py
- [ ] C4 citymonkey 重跑真机验证
  - Acceptance: **操作步骤（写死）**：① 移走旧产物
    `mv work/20260822_citymonkey/scorers_b1 work/20260822_citymonkey/scorers_b1.bak`
    （备份不删，验证无误后由立哥决定清理）；② 重跑裁图段
    `python scripts/video.py people --session 20260822_citymonkey --no-read-numbers`
    （**--no-read-numbers 必带**——number_cache 随 scorers_b1 移走，不带会对
    58 球全量重调 K3 读号烧额度，违反 v2.1 零 token 定案；**photo-roster
    T12 落地后 read_numbers 默认翻 False，该旗标从必带降为可选，届时回填
    本文档**；
    ②.5 匹配与确认页产物顺带刷新——**②.5 现为 CLIP 匹配产物、非终态，
    以 photo-roster T12 换 L1 后为准，本次仅核对裁图闸**；该场次 roster
    未确认导出，确认页刷新无确认态可冲**）；③ 核对：
    t480.1 瓶子帧、t550.0 细条帧被拦且留痕（**t550.0 被拦属预期拦截不计
    误杀；补位失败归 SKIP 亦不算**）；**truth_16 我方 8 球中除 t550.0 外的
    7 球有效裁图零误杀**
    逐球核对表；结果归档 review01.md 验证章
  - Verify: 真机重跑 + 逐球核对表
  - Files: work/20260822_citymonkey/、docs/crop-quality/review01.md
- [ ] C5 文档同步 + 收尾
  - Acceptance: AGENTS.md 认人链路行补质量闸；docs/经验教训.md 补"废框三
    类型+两道闸"条目；todo 全勾；review01.md 完整归档
  - Verify: 关口全绿
  - Files: AGENTS.md、docs/经验教训.md

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|---|---|---|
| yolov8n 对小人/遮挡框置信度天然低 → 误杀好帧 | 高 | C1 标定看正常球置信度分布下限再定阈；宁漏拦不错杀；误杀核对进 C4 |
| 框来源口径变化（检测缓存缺框） | 中 | 缺框帧跳过复检不拦截（不静默丢弃，记 INFO） |
| 旧场次产物口径不一致 | 低 | 只对新跑生效（spec 幂等写死）；citymonkey 验证走删产物重跑 |

## Open Questions

- 阈值定稿值：C1 报告后立哥确认（Ask first）
- 错人框（裁到对手）：边界外，后续与 team_guess 不可靠一起单独立项
