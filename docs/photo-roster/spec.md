# Spec: 照片库认人（photo-roster）——半截篮队员照片 1:N 识别预填

## Objective

立哥供照：半截篮队员穿球衣照片，正反各 2 张，按号码建子文件夹
（`photos/<号码>/`）。进球归属时，我方（半截篮）优先用照片库做 1:N 识别
预填确认页，立哥确认页终裁导出 roster（2026-08-23 立哥定：预填+确认页终裁，
不做全自动归属）。对方球队不进库、不识别，走现有聚类+人工流程不变。

背景与明示决策：docs/scorer-reid/review01.md 实跑结论——全身外观聚类
（CLIP/OSNet）在本素材（俯视远景、运动模糊、遮挡）已到纯度天花板，原建议
是"照片库**人脸** embedding 是后续真正值得试的方向"。本 spec 对其做**有意
偏离**：先用零新依赖的 CLIP 全身/半身外观做 1:N 对照（任务从"全员互相区分"
变为"N 选 1"，难度低一个量级），Phase A 不达标再转人脸专用模型（新依赖，
Ask first）。这是明示决策而非引用原文。

成功标准（可执行验证）：

- **Phase A 对照实验先行**：评测真值 = 淳化街道 confirmed roster（立哥先跑
  people 链确认，照片库成员的球重点确认；现存唯一 roster，20260722 产物已随
  archive 清理），按 §数据契约的评估口径出命中率+混淆矩阵报告归档 review；
  **达标线：我方有号球 top-1 命中率 ≥80% 且负样本误命中率 ≤10%**（立哥可改）
  才进入 Phase B 集成；不达标记 review 停工报立哥
- Phase B 集成后：确认页对照片命中球预填归属+置信度展示，未命中球行为不变；
  导出 roster、build 合集全链无回归
- ruff+pytest 全绿；四件套齐全

## Tech Stack

- 复用既有：open_clip_torch（CLIP ViT-B-32 后端，cluster_scorers 既有
  ImageEncoder 抽象与 clip_cache）、scikit-learn、pillow
- **零新依赖**（Phase A/B 内）。人脸专用模型（insightface 等）只在 Phase A
  不达标时作为备选，Ask first
- OSNet 后端不用于本功能（review01 已证与 CLIP 持平且域差距同存）

## Commands

```bash
# 质量门（改动后必跑）
python -m ruff format scripts tests && python -m ruff check --fix scripts tests && \
  python -m pytest -q

# Phase A：照片库 × 淳化街道对照实验（裁图 embedding 复用该场既有合并
# clip_cache，零重复推理；该 cache 由 build 自动模式聚类产出，含该场全部批次裁图；
# 前提：该场已跑过 build 自动模式）
python scripts/photo_match_scorers.py --photos photos --evaluate \
  --candidates work/20260813_淳化街道/scorers_b1/scorer_candidates.json \
  --candidates work/20260813_淳化街道/scorers_b2/scorer_candidates.json \
  --candidates work/20260813_淳化街道/scorers_b3/scorer_candidates.json \
  --roster work/20260813_淳化街道/roster.json \
  --cache work/20260813_淳化街道/scorers_auto/clip_cache.json

# Phase B：people 链路实跑（逐批调用，candidates 与 cache 按批配对；
# 此命令由 video.py people 串联，手工调试验时用）
python scripts/photo_match_scorers.py --photos photos \
  --candidates work/<场次>/scorers_b1/scorer_candidates.json \
  --cache work/<场次>/scorers_b1/clip_cache.json \
  --out work/<场次>/scorers_b1/photo_matches.json
```

## Project Structure

```
photos/<号码>/*.jpg      → 照片库（立哥维护；真人照片 gitignore 不入库，同素材口径）
scripts/
  photo_match_scorers.py 新：照片库加载校验 → embedding（缓存）→ 球-号码得分 →
                          photo_matches.json / 对照评估报告
  gen_scorer_page.py    改：--photo-matches 注入预填（高置信预填+置信度角标，
                          冲突双候选展示）；无此参数行为不变
  video.py              改：people 链路在逐批 cluster 后串逐批 photo_match
                          （照片库缺失整步跳过 INFO，不阻塞认人；
                          --skip-cluster 时同口径跳过）
tests/                  → 纯函数单测（合成 embedding，不碰真模型/真照片）
docs/photo-roster/      → 本四件套
work/<场次>/scorers_bK/photo_matches.json → 匹配产物（逐批，
                          key → {number, score, margin}）
```

## 数据契约

### 照片库（photos/）

- 结构：`photos/<号码>/` 子文件夹，号码 = 文件夹名（纯数字 str）；每号码预期
  4 张（正反各 2），**至少 1 张**，不足记 WARNING 不阻塞
- **号码归一化（写死）**：匹配主键统一 `str(int(文件夹名))` 去前导零
  （`07`→`7`，与 K3 读号归一 `crop_scorers.py:193` 及名单 tag 找号
  `gen_scorer_page.py:1124` 同口径）；文件夹原名仅作展示，不参与 join
- 校验：非数字文件夹名 / 空文件夹 / 无合法图片（.jpg/.jpeg/.png）→ WARNING
  跳过该条目；全部无效 → 显式报错退出（整个库无效属配置错误，不静默空跑）
- 照片内容机器无法校验（照片里多人、混进别人照片）：此类污染靠确认页角标
  人工兜底，供照说明写明"每张照片只含本人"
- 照片 embedding 缓存：`photos/.photo_cache.json`，键 = 文件 md5，幂等增量；
  模型 tag 前缀隔离（同 clip_cache 口径，防后端切换互冲——review01 教训）

### photo_match_scorers.py

- 输入：--photos 库目录 + --candidates（可重复，并集后者覆盖，对齐
  cluster_scorers 口径）+ **--cache（可重复，跨文件并集查询；键 = crop md5
  天然不冲）**；--evaluate 模式另加 --roster 出对照报告
- 串联口径（写死）：video.py people **逐批调用**——每批 candidates 与该批
  clip_cache.json 配对，产出逐批 `scorers_bK/photo_matches.json`，供逐批
  确认页消费（与 people 逐批出页布局对齐）；--evaluate 模式可传合并 cache
  （如 scorers_auto/clip_cache.json）一次评全部批次
- 球-号码得分（写死）：`score(球, 号码) = max over (该球 crops × 该号码 photos)`
  的余弦相似度；球级归属 = 得分最高号码，附带次高分差（margin）
- 退化路径（写死）：**两号码并列最高分 → 不采纳记未匹配**（保守，交人裁判）；
  **库内仅 1 个号码时 margin 视为 +∞**（过闸只看 threshold）
- 采纳闸（写死）：`score ≥ THRESHOLD 且 margin ≥ MARGIN` 才算命中，否则未匹配；
  THRESHOLD/MARGIN 常量由 Phase A 分布标定后写死（带注释注明标定来源）
- 缓存口径：candidates 缺 entry / 裁图 md5 不在缓存 → 该球 WARNING 跳过不阻塞；
  缓存文件缺失 → 显式报错（提示先跑 cluster）；**本模型前缀命中率 0% →
  显式报错**（提示 cluster 用了别的 --model 后端，防静默零产出）
- 输出 photo_matches.json：`{version, model, threshold, margin, matches:
  {goal_key: {number, score, margin}}}`（仅含命中球，number 为去零主键），
  schema 显式校验；**--evaluate 报告则含全部入统球的 top-1 号码+得分+margin
  分布（不过闸）**——标定与混淆矩阵以此为准，photo_matches.json 仍只落过闸命中球

### 评估口径（--evaluate，写死）

- 真值映射：roster.players 中 `team=半截篮` 的 tag → 号码 = tag 内首个数字串
  （去零）；对方/便服 tag 的球真值记"无号"
- **无号的半截篮 tag（如"白色中锋"）的球单列"不可判"，不进正/负样本分母**
  （他可能是照片库成员，正确命中不该计误）；真值确认环节操作建议立哥给
  照片库成员的 tag 补号码（减少不可判占比）
- 入统：goals.json `status=confirmed` 且 key 在 roster.assignments 里的球
- 指标：**正样本命中率** = 半截篮有号球 top-1 命中正确率（分母 = 半截篮
  有号球数）；**负样本误命中率** = 真值无号球被命中任意号码的比例（命中即错）；
  混淆矩阵按号码展开归档

### gen_scorer_page.py --photo-matches 预填

- 路径约定（写死）：--photo-matches 缺省取 `--scorers` 同目录的
  `photo_matches.json`（与 --clusters 同目录约定同构）；文件缺失时 INFO
  跳过预填，页面行为同无此参数
- 预填优先级（写死）：**读号命中 > 照片命中 > 印名匹配 > 簇级空白**
  （印名兜底为现状机制 gen_scorer_page.py:1445，本次不动）；读号与照片冲突时
  预填读号结果，照片候选在条目上显示角标（号码+得分）供人工切换——不静默覆盖
- 号码 → 人：复用 players.json 名单（--players-file 既有机制）；名单缺该
  号码 → 预填占位条目 `tag=半截篮<去零号码>, name="", team=半截篮`，
  **占位条目必须随 players 名单注入页面，不得依赖前缀推队**（`半截篮7` 不以
  黑/蓝/白开头，teamOfTag 会误归便服）
- 仅命中球预填；未命中球页面行为与现状完全一致

## Code Style

遵守根目录 rules.md（鲁棒优先 ＞ 性能 ＞ 简洁）；与现有 scripts 一致的
dataclass 契约 + 显式校验 + SchemaError 分层；阈值/边距常量化带标定注释。

## Testing Strategy

- pytest 纯函数单测，不碰真模型/真照片/网络：
  - 照片库扫描校验：合法结构 / 非数字名 / 空文件夹 / 全无效显式失败 /
    前导零归一化（`07`→`7`）
  - 得分聚合：max 规则、多裁多照片矩阵、**并列同分不采纳**、**单号码库
    margin=+∞**
  - 采纳闸：阈值/边距边界值（恰好等于、低于）、未匹配路径
  - 缓存：键规则、增量幂等、模型前缀隔离、前缀命中率 0% 显式报错、
    多 cache 并集查询
  - 评估口径：tag→号码映射（含无号 tag 单列"不可判"）、正/负样本指标、
    坏 roster SchemaError
  - 预填优先级：读号>照片>印名、冲突角标、名单缺号占位注入、
    无 --photo-matches 零影响
- Phase A 对照实验走 --evaluate 实跑，报告归档 review，不进 pytest

## Boundaries

- Always：质量门全绿后分 Phase 提交；embedding 缓存幂等落盘；photos/ 与
  .photo_cache.json 进 .gitignore（真人照片不入库）
- Ask first：任何新依赖（人脸模型路线）；THRESHOLD/MARGIN 定稿值；未来
  "高置信直接自动归属"（本轮明确不做）
- Never：匹配结果不是终裁（确认页导出才算数）；不动 goals/label 流程与
  roster.json schema；不改聚类参数；不删除旧缓存

## Success Criteria

- [ ] Phase A：淳化街道 confirmed roster 对照，正样本命中率 ≥80% 且负样本
  误命中率 ≤10%（或立哥改定值），报告+混淆矩阵归档 review
- [ ] photo_match_scorers.py + 缓存 + 闸逻辑 + 评估口径，单测覆盖上述契约
- [ ] gen_scorer_page --photo-matches 预填集成（含冲突角标与名单缺号回退）
- [ ] video people 链路串联（逐批），照片库缺失 / --skip-cluster 时整步跳过不阻塞
- [ ] ruff+pytest 全绿；四件套齐全（review 按轮次编号）

## Open Questions

- Phase A 双重前置（plan 排依赖注意）：①淳化街道 roster confirmed=true
  （立哥跑 people 链确认，照片库成员的 tag 建议补号码）；②该场已跑过 build
  自动模式聚类（scorers_auto/clip_cache.json 已存在，2026-08-22 已产出 ✓）
- 我方多人同号（不同年份球衣）暂按不存在处理；出现再议
- 供照说明（随 plan 交付给立哥）：每张照片只含本人、清晰正面半身+正面
  全身+背面号码×2、光线均匀、不戴帽遮脸
