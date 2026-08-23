# Review 01: 照片库认人 spec 审查（3 轮闭环）

日期：2026-08-23
对象：docs/photo-roster/spec.md（初稿 → 第 3 轮定稿）
审查人：spec-reviewer 子代理（对照 cluster_scorers/crop_scorers/gen_scorer_page/
roster.py/video.py 现状代码与 docs/scorer-reid/review01.md 实跑结论核查；
并对 work/20260813_淳化街道/ 实产物做了验证）

## 总结论：无阻断问题，spec 可进入 plan 阶段

## 第 1 轮：3 阻断 + 8 建议（全部修订）

| 阻断 | 修订 |
|---|---|
| Phase A 评估口径未定义（tag↔号码映射/入统分母/负样本口径），"top-1 ≥80%" 不可计算 | spec 新增"评估口径（写死）"小节：真值=半截篮 tag 内首个数字串（去零）、入统=goals confirmed 且在 roster.assignments、双指标（正样本命中率 ≥80% 且负样本误命中率 ≤10%）+混淆矩阵 |
| 号码前导零口径自相矛盾（照片库保留 `07`，下游读号/名单全是去零口径） | 写死匹配主键 `str(int())` 去零，文件夹原名仅展示；占位 tag 同步改 `半截篮<去零号码>` |
| tie 与 margin 退化路径无契约，与测试清单不自洽 | 写死：并列最高不采纳记未匹配（保守交人裁判）；单号码库 margin=+∞ |

8 条建议全部吸收：明示偏离人脸建议（有意决策非引用）、cache 前缀命中率 0%
显式报错、--skip-cluster 同口径跳过、占位条目必须随名单注入（不得依赖前缀
推队）、预填优先级补印名档、字段统一 {number, score, margin}、供照说明
"每张只含本人"、Commands 按真实路径写全。

## 第 2 轮：1 新阻断 + 4 建议（全部修订）

| 阻断 | 修订 |
|---|---|
| Phase B `--cache` 指向 scorers_auto/（build 自动模式才有），与 people 链路逐批 cache 布局矛盾，Phase B 第一步即炸 | 定案：`--cache` 可重复跨文件并集查询（键=model_tag:md5 天然不冲）；people **逐批调用**（candidates 与该批 cache 配对，产出逐批 scorers_bK/photo_matches.json 供逐批确认页消费）；--evaluate 可传合并 cache |

4 条建议全部吸收：入统措辞消除 confirmed 歧义、无号半截篮 tag 单列"不可判"
（实证：淳化街道 roster 有"白色中锋"）、Phase A 双重前置写进 Open Questions、
去掉 58 球硬编码。

## 第 3 轮：无阻断，2 建议（随 spec 吸收）

- --evaluate 报告含全部入统球 top-1 分布（不过闸），标定/混淆矩阵以此为准 →
  已补进数据契约
- --photo-matches 缺省取 --scorers 同目录 photo_matches.json（与 --clusters
  同目录约定同构）→ 已补进 gen_scorer_page 小节

## 实产物验证记录（第 2 轮）

- 淳化街道 scorers_b1/b2/b3 scorer_candidates.json 与 scorers_auto/clip_cache.json
  均存在；cache `_meta.model=ViT-B-32/laion2b_s34b_b79k`（CLIP 前缀正确，
  前缀 0% 报错不会误触发）
- roster.json 确为 confirmed=false，与 Open Questions 依赖声明一致

## 遗留（转 plan/todo）

- Phase A 前置：立哥确认淳化街道 roster（照片库成员 tag 建议补号码）+
  立哥供照（photos/<号码>/ 每号码正反各 2 张）
- Phase A 不达标出口：记 review 停工报立哥，人脸模型路线（insightface 等
  新依赖）须经批准
