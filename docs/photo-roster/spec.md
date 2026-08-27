# Spec: 照片库认人 v2.1（photo-roster）——免费信号 → 人裁（零 token 路线）

> **v2.1 变更（2026-08-27 立哥定）**：级联去掉全部 K3 层——**K3 读号不调、
> K3 照片对照不调**，链路简化为 **L1 免费信号 → L4 确认页人裁**，零 token。
> （L 编号沿用 v2 的四级级联——v2 的 L2 K3 读号、L3 K3 照片对照已删，
> 读者找不到 L2/L3 属预期；阶段编号沿用 v1 的 Phase A/B 称谓，
> **执行序以 plan 为准**：spike → 选型 → 产品化 → 评测 → 收尾。）
> K3 照片对照小样 10/13 零误指认的实测记录留档（work/k3_photo_test/），
> 若免费信号实测覆盖率太弱，恢复 K3 兜底经立哥批准即可（Open Questions）。
> crop_scorers 既有 --read-numbers 功能是既有代码不删，级联不再调用；
> **people 链 read_numbers 默认随之翻转 False**（--read-numbers 显式开
> 保留兼容，承接任务见 plan T12）。
>
> **v2 变更记录（2026-08-27）**：v1 CLIP 匹配路线经三方调研证伪判死刑
> （跨人对相似度 0.936 超同人对下限、正确/错误号得分带完全重叠无阈值可切，
> 归档 review03.md）。v1 已交付物去向：照片库契约/号码归一化/确认页预填
> 机制（T5）/评估口径**保留**；photo_match_scorers.py（CLIP）标记证伪
> 不推荐，其 --evaluate 机制改造复用于级联评测。

## Objective

进球归属识别走零成本级联（同制服场景号码是第一信号、外观只配辅助，
文献结论归档 review03.md）：

- **L1 免费信号**（离线零成本，具体启用哪路由 Phase A.0 两个 spike 定）：
  - 候选 a：**号码 OCR**（PARSeq 类开源管线，多帧投票 + 在场名单先验）——
    同制服场景第一信号
  - 候选 b：**人脸 embedding**（insightface buffalo_l，多帧质量加权投票）
  高置信命中的球直接预填，其余球落 L4
- **L4 确认页人裁**：机器拿不下的球 → 簇级空白，立哥终裁（架构定位不变：
  机器排序+人裁判；机器预填永远不是终裁，确认页导出才算数）

对方球队不进照片库/名单，正确行为 = 无命中，走现有聚类+人工。

成功标准（可执行验证）：

- **Phase A.0 两个 spike 先行**（work/ 一次性脚本豁免四件套，真值 =
  `work/20260822_citymonkey/truth_16.json`，16 球：8 我方有号/4 对方/2 废图/
  2 未判）：
  - S1 号码 OCR spike：PARSeq 管线在 truth_16 上的**命中率/误指认率** +
    citymonkey 58 球**覆盖率**（有号球占比）——决定 OCR 路去留
  - S2 人脸 spike：insightface buffalo_l 在 truth_16 上的命中率/误指认率
    ——决定人脸路去留
- **选型 checkpoint**：两 spike 报告立哥过目，定 L1 = OCR / 人脸 / 双路接力 /
  皆弃（皆弃则 Phase B 不做，认人维持纯人工确认页，本功能到此为止）
- **Phase B**：L1 matcher 产品化（缓存/逐批串联/确认页预填复用 T5 机制）——
  评测需要产品化 matcher 才能跑，故产品化先行
- **Phase A 级联评测**（产品化后）：测试场次 confirmed roster 当真值，
  出**机器高置信采纳率（覆盖率）+ 采纳部分误指认率 + 人裁负担**（进确认页
  比例）三指标报告归档；**达标线：采纳部分误指认率 ≤10%**（红线，立哥可改）；
  不达标 → 回退报立哥（评估恢复 K3 兜底或调阈值），覆盖率不硬卡
  （低覆盖率 = 人裁多干活，不是事故）
- 文档同步 + 真机验证
- ruff+pytest 全绿；四件套齐全

## Tech Stack

- 既有：torch 2.13 CPU、opencv、pillow、numpy、scikit-learn
- **spike 新依赖（Ask first，随本 spec 请立哥批准）**：
  - S1：PARSeq 号码识别（**许可按实际选用组件分别核实**：PARSeq-B 本体
    Apache-2.0，整管线参考实现 mkoshkina/jersey-number-pipeline 为
    CC-BY-NC 非商业——spike 报告注明实际用了哪个）
  - S2：insightface + buffalo_l 权重（**非商业许可**）
  许可口径：个人剪辑自用无碍；basketball-clip 开源产品化时需另评估
  （Open Questions）
- 明确不用：K3（本链路零 token）、CLIP 整图匹配（证伪）、OSNet（证伪）

## Commands

```bash
# 质量门（改动后必跑）
python -m ruff format scripts tests && python -m ruff check --fix scripts tests && \
  python -m pytest -q

# S1/S2 spike：work/ 一次性脚本，命令随 plan 落
# Phase A/B：产品化后命令随 plan 落
```

## Project Structure

```
photos/<号码>/*.jpg      → 照片库（契约同 v1：归一化/校验/gitignore，不重述）
scripts/
  ocr_match_scorers.py / face_match_scorers.py  新（Phase B，按选型建其一或全）：
                        缓存幂等、产出对齐 photo_matches.json 现 schema
                        （复用 T5 页面预填）、逐批
  photo_match_scorers.py 标证伪不推荐（docstring 注明）；--evaluate 机制
                        改造为级联评测器（L1 结果对账）
  video.py              改（Phase B）：people 链 ②.5 由 CLIP 匹配器换 L1 匹配器
  gen_scorer_page.py    不改（T5 预填机制零改动消费）
work/                   → S1/S2 spike 一次性脚本与报告（豁免四件套）
docs/photo-roster/      → 本四件套
docs/crop-quality/      → 裁图质量闸专项（并行，互为上下游）
```

## 数据契约

### L1 接力与采纳规则（写死）

- 双路都启用时顺序：**OCR 高置信命中 > 人脸高置信命中 > 人裁**
  （号码是离散直接证据，人脸是相似度证据，文献级联口径）
- **误指认是红线指标**：答错号/认错人（不是漏）单列统计——漏可以人补，
  错会静默污染；"不在库/无命中"**不算错算漏**（v1 实测口径）
- 对方球（不在库）：正确行为 = 无命中；任何路误命中即误指认
- **名单先验**：OCR 候选限定在场名单号码集合、**库外读数不采纳**——名单 =
  确认页 `--players-file` 同源的用户提供名单（players.json 为用户运行时
  输入、不入库）；**缺省时退化为照片库号码集合**（Vats CVPRW2022 实证
  +4.4%，review03.md 归档）

### L1 输出 schema（写死，同 v2 K3 映射思路）

- 产出保持 photo_matches.json 现 schema 不变（version=photo-match-v1、
  model/threshold/margin 顶层数值占位、matches:{key:{number,score,margin}}）
  ——T5 页面机制与 validate_matches_payload 零改动消费
- 映射：高置信命中 → 入 matches（**score=best sim 实测、margin=top1-top2
  分差实测**——2026-08-28 T11 落地口径，比 v2 的占位方案信息更富、消费端
  无感）；低置信/无命中 → 不入 matches（确认页全量列球天然进页面）
- 原始结果（置信度/票数/各帧明细）写 matcher 自有缓存（幂等，重跑零重算）

### 照片库 / 评估口径 / 确认页预填

- 照片库契约（结构/归一化 `str(int())` 去零/校验/gitignore）：**同 v1，不变**
- 评估口径（真值映射/无号半截篮 tag 单列"不可判"/入统 = goals confirmed
  ∩ assignments/正负样本/混淆矩阵）：**同 v1，不变**；指标改三指标
  （覆盖率/采纳误指认率/人裁负担）
- 确认页预填（读号>照片>印名>空白、显式传参、冲突角标、占位注入）：
  **同 v1，不变**（T5 已交付，生产者换人它无感；读号预填因级联不调 K3
  读号而自然空缺，页面逻辑不受影响）

## Code Style

遵守根目录 rules.md；模型加载惰性（测试注入假检测器/假识别器，不碰真模型
 真权重）；单球失败记 ERROR 不炸批。

## Testing Strategy

- spike（Phase A.0）：work/ 一次性脚本，豁免四件套，结果归档 review
- Phase B 产品代码：pytest 单测不碰真模型/真权重/网络：
  - 接力规则：OCR 命中不调人脸（mock 计数断言）、单路失败降级
  - 名单先验：库外读数不采纳
  - schema 映射与 validate_matches_payload 联调断言
  - 缓存：幂等、版本变更作废
  - 输出与 T5 消费端联调（假数据端到端）

## Boundaries

- Always：质量门全绿后提交；spike/评测原始数据归档 review
- Ask first：S1/S2 新依赖与非商业许可（本 spec 已请批）；L1 选型（spike 后
  立哥 checkpoint）；达标线数值调整；恢复 K3 兜底
- Never：任何层不是终裁（确认页导出才算）；不删 T5 预填机制与照片库契约；
  不在本链路调 K3（零 token 是立哥定案）

## Success Criteria

- [ ] S1：PARSeq truth_16 命中/误指认 + 58 球覆盖率（有号球占比+库外读数率）
  报告归档；OCR 路去留结论
- [ ] S2：insightface truth_16 命中/误指认报告归档；人脸路去留结论
- [ ] 选型 checkpoint 立哥拍板（OCR/人脸/双路/皆弃）
- [ ] Phase B：L1 matcher 产品化 + video.py 串联（评测的前置：评测用产品化
  matcher 跑）
- [ ] Phase A：级联评测三指标达标（采纳误指认 ≤10%），报告归档；
  不达标回退报立哥
- [ ] 真机验证 + 文档同步
- [ ] ruff+pytest 全绿；四件套齐全（review 按轮次编号）

## Open Questions

- **许可风险**：PARSeq/insightface 均非商业许可——个人自用无碍；
  basketball-clip 开源且含认人功能时需评估替换或声明依赖许可
- **K3 兜底恢复阀**：若 L1 采纳率过低（人裁负担过重），可经立哥批准恢复
  K3 照片对照兜底（v1 小样 10/13 零误指认留档 work/k3_photo_test/，
  prompt 与实验脚本现成）
- 测试场次：citymonkey（truth_16 已机器可读）+ 立哥新素材；Phase A 正式
  评测场次以 roster 确认进度为准
- 裁图质量分工：无人框/畸形框由 docs/crop-quality/ 专项处理；错人框
  （裁到对手）两边均边界外，后续单独立项
