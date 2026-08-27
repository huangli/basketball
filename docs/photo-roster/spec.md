# Spec: 照片库认人 v2（photo-roster）——级联识别：免费信号 → K3 读号 → K3 照片对照

> **v2 变更记录（2026-08-27）**：v1 的 CLIP embedding 匹配路线经三方调研
> （数据根因/文献/协议实验，结论归档 review03.md）**证伪判死刑**——
> 通用 CLIP 对同款球衣不同人无判别力（跨人对相似度 0.936 超同人对下限，
> 正确/错误号得分带完全重叠无阈值可切）。同小样实测 **K3 照片对照
> 10/13 零误指认**（work/k3_photo_test/）。v2 主路线改为**级联识别**，
> K3 照片对照做兜底裁判。v1 已交付物去向：照片库契约/号码归一化/确认页
> 预填机制（T5）/评估口径**保留**；photo_match_scorers.py（CLIP）标记证伪
> 不推荐，其 --evaluate 评测机制改造复用于级联评测；T6 串联改接 K3 匹配器。

## Objective

进球归属识别改级联（文献标准答案，同制服场景号码是第一信号、外观只配辅助）：

- **L1 免费信号**（离线零成本，视 Phase A.0 spike 结果决定启用哪路）：
  号码 OCR（PARSeq 类）/ 人脸 embedding 多帧投票——高置信命中的球直接定
- **L2 K3 读号**（现成链路 crop_scorers --read-numbers，多帧众数投票）：
  号码可见时一票定身份，~6K token/球
- **L3 K3 照片对照**（v1 小样实测 10/13 零误指认）：裁图+照片库问 K3
  "是几号/不在库/看不清"，~15K token/球，L1/L2 拿不下的球才调——
  节省量待 S1 覆盖率回填（文献估算 50-80%）
- **L4 确认页人裁**：以上全拿不下 → 簇级空白，立哥终裁（架构定位不变：
  机器排序+人裁判；任何一层都不是终裁，确认页导出才算数）

对方球队不进照片库，各层正确行为 = 拒答/无命中，走现有聚类+人工。

成功标准（可执行验证）：

- **Phase A.0 两个 spike 先行**（半天级，work/ 一次性脚本豁免四件套）：
  - S1 号码可读性：citymonkey 58 球跑现成 --read-numbers（新调用 ≤300 闸
    内），出**覆盖率**（有号球占比）+ 对照已终裁 13 球的**准确率**——
    同时回答"PARSeq 离线 OCR 值不值得投"（可读帧率是前提）与 L2 层实力
  - S2 人脸路线：insightface buffalo_l 在已终裁 13 球 + 照片库（14 张）
    上的命中率/误指认率——回答 L1 人脸路值不值得投
- **Phase A 级联评测**：测试场次 confirmed roster 当真值，级联整体
  （L1/L2/L3 各自+接力后总账）出命中率/误指认率/token 成本报告归档；
  **达标线：正样本命中率 ≥80% 且误指认率 ≤10%**（立哥可改）才进 Phase B
- Phase B：K3 匹配器产品化（缓存/逐批串联/确认页预填复用 T5 机制）+
  文档同步 + 真机验证
- ruff+pytest 全绿；四件套齐全

## Tech Stack

- 既有：open_clip（聚类用，认人不用于身份判别）、httpx、K3（api.kimi.com
  /coding/v1，凭证 ~/.kimi-code/credentials/kimi-code.json 900s 临期重读，
  复用 vlm_filter.load_token / crop_to_b64 / 重试口径）
- **spike 新依赖（Ask first，随本 spec 请立哥批准）**：insightface（S2；
  buffalo_l 权重**非商业许可**——个人使用无碍，开源产品化时需另评估，
  见 Open Questions）；PARSeq 管线是否引入由 S1 结果再议（CC-BY-NC 同问题）
- 零新依赖：Phase A.0 的 S1 用现成 --read-numbers 链路

## Commands

```bash
# 质量门（改动后必跑）
python -m ruff format scripts tests && python -m ruff check --fix scripts tests && \
  python -m pytest -q

# S1：citymonkey 全量读号（现成链路，参数签名照 video.py build_crop_argv:373-388
# 实况；58 球 × ≤3 裁图 ≈ 174 次新调用 < 300 闸；缓存幂等）
python scripts/crop_scorers.py \
  --goals work/20260822_citymonkey/goals_batch1.json \
  --candidates work/20260822_citymonkey/candidates_batch1.json \
  --out work/20260822_citymonkey/scorers_b1 \
  --detectdir work/detect --framesdir work/frames \
  --rawdir "C:/2. Basketball Video/20260822_citymonkey" \
  --read-numbers --max-reads 300

# S2/Phase A：spike 与评测命令随 plan 落（work/ 一次性脚本）
```

## Project Structure

```
photos/<号码>/*.jpg      → 照片库（契约同 v1：归一化/校验/gitignore，不重述）
scripts/
  k3_match_scorers.py   新（Phase B）：K3 照片对照产品化——prompt 定稿、
                        按裁图 md5+prompt 版本缓存（number_cache 同模式）、
                        产出对齐 photo_matches.json 现 schema（见数据契约）、
                        逐批
  photo_match_scorers.py 标证伪不推荐（docstring 注明）；--evaluate 机制
                        改造为级联评测器（L1/L2/L3 结果合并对账）
  video.py              改（Phase B）：people 链 ②.5 由 CLIP 匹配器换 K3 匹配器
  gen_scorer_page.py    不改（T5 预填机制零改动消费，见数据契约映射规则）
work/k3_photo_test/     → v1 小样实验存档（本 spec 的证据来源）
docs/photo-roster/      → 本四件套
```

## 数据契约

### 级联接力规则（写死）

- 每球按 L1→L2→L3 顺序求值，**高层命中即停**（省钱核心）：L1 高置信命中
  → 不调 L2/L3；L2 读号采纳 → 不调 L3
- L2 采纳 = 现成投票规则全分支（crop_scorers.py:246-276）：同号 ≥2 张采纳；
  有效票 =1 时 conf=high 采纳、low 归 None；有效票 ≥2 且全不同取唯一
  conf=high（多个 high 不采）；None 票不参与计数
- **误指认是红线指标**：各层分开统计"答错号"（不是漏）——漏可以人补，
  错会静默污染；L3 的"不在库/看不清"拒答**不算错算漏**（v1 实测口径）
- 对方球（不在库）：正确行为 = 各层无命中/拒答；任何层误命中即误指认

### K3 照片对照（L3，v1 实验口径产品化）

- 输入：该球最优裁图 + 照片库全部照片（7 号码 × 2，顺序 prompt 声明）；
  prompt 定稿存仓库（版本化，同 NUMBER_PROMPT_VERSION 模式，改版本缓存作废）
- **输出 schema（写死）：保持 photo_matches.json 现 schema 不变**
  （version=photo-match-v1、model/threshold/margin 顶层数值占位、
  matches:{key:{number,score,margin}}）——T5 页面机制与
  validate_matches_payload 零改动消费；映射规则：
  - K3 答 high → 入 matches：`score=1.0`、`margin=0.0`（**固定占位，
    注释注明语义=置信度映射、非余弦分**，页面角标得分列对 K3 来源显示
    固定 1.000 属预期）
  - K3 答 low / null（不在库/看不清）/ 解析失败 → **不入 matches**；
    该球由确认页全量列球天然进页面（簇级空白），"low 进确认页"由此满足
  - K3 原始回复（含 confidence/reason/拒答）写入 k3_match 自有缓存
    （键 = 裁图 md5 + prompt 版本；拒答也缓存，重跑零新调用）
- 缓存：K3 调用不免费，幂等落盘（同 number_cache 模式）

### 照片库 / 评估口径 / 确认页预填

- 照片库契约（结构/归一化 `str(int())` 去零/校验/gitignore）：**同 v1，不变**
- 评估口径（真值映射/无号半截篮 tag 单列"不可判"/入统 = goals confirmed
  ∩ assignments/正负样本双指标/混淆矩阵）：**同 v1，不变**；级联评测按层
  出分 + 接力总账
- 确认页预填（读号>照片>印名>空白、显式传参、冲突角标、占位注入）：
  **同 v1，不变**（T5 已交付，生产者从 CLIP 换 K3 它无感）

## Code Style

遵守根目录 rules.md；K3 调用失败不炸批（单球失败记 ERROR 跳过该层进下一层，
同 vlm_filter 口径）；token 消耗逐场统计落日志。

## Testing Strategy

- spike（Phase A.0）：work/ 一次性脚本，豁免四件套，结果归档 review
- Phase B 产品代码：pytest 单测不碰网络/凭证（注入假 K3 reader，同
  crop_scorers NumberReader 注入模式）：
  - 接力规则：高层命中不调低层（mock 计数断言）、各层失败降级
  - K3 回复解析：合法 JSON/号码不在库归 null/无法解析/幻觉硬答的处理
  - schema 映射：high → score=1.0/margin=0.0 入 matches；low/null/解析失败
    不入；validate_matches_payload 对产物校验通过（联调断言）
  - 缓存：幂等、prompt 版本变更作废、拒答缓存
  - 输出 schema 与 T5 消费端联调（假数据端到端）

## Boundaries

- Always：质量门全绿后提交；spike/评测原始数据归档 review；token 成本记账
- Ask first：insightface/PARSeq 等新依赖与非商业许可（本 spec 已请批 S2）；
  prompt 定稿变更；级联层顺序调整；达标线数值调整
- Never：任何层不是终裁（确认页导出才算）；不删 v1 已交付的 T5 预填机制与
  照片库契约；不调 K3 做事件级进球判定（2026-08-01 已下线，场景不同勿混）

## Success Criteria

- [ ] S1：citymonkey 58 球读号覆盖率 + 13 球准确率报告归档；PARSeq 去留结论
- [ ] S2：insightface 13 球命中率/误指认率报告归档；人脸路去留结论
- [ ] Phase A：级联接力评测（测试场次真值）双指标达标，token 成本账归档
- [ ] Phase B：k3_match_scorers.py 产品化 + video.py 串联 + 真机验证
- [ ] ruff+pytest 全绿；四件套齐全（review 按轮次编号）

## Open Questions

- **许可风险**：insightface/buffalo_l 与 PARSeq 均为非商业许可——个人剪辑
  自用无碍；若 basketball-clip 开源（docs/basketball-clip/）且含认人功能，
  需评估替换（自训/换许可友好模型）或在开源文档中声明依赖许可
- 测试场次：立哥新下载的素材（citymonkey 已承担 v1 小样+S1，Phase A 正式
  评测是否续用 citymonkey 取决于其 roster 确认进度）
- 库外球员：t471.7 已澄清为对方蓝 15（无需补照）；后续我方新队员入库走
  正常供照
- 裁图质量分工：无人框/畸形框由 docs/crop-quality/ 专项处理；**错人框
  （裁到对手）两边均边界外**，与 team_guess 不可靠是同坑两侧，后续单独立项
