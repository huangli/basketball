# Plan: 照片库认人（photo-roster）

依据 `docs/photo-roster/spec.md`（四轮审查修订定稿）。按依赖序排，每个 Task
留系统于可工作状态，Phase A 达标 checkpoint 由立哥过目后才进 Phase B。

## 架构决策

- **新脚本 photo_match_scorers.py，复用 cluster_scorers 的现成件**：
  `load_clip_cache`/`save_clip_cache`（cluster_scorers.py:238/273）、`file_md5`、
  `build_clip_encoder`（:291）、`merge_candidates`（:204）全部 import 复用，
  不抄代码；照片缓存与裁图缓存同格式（键 = `model_tag:md5`，向量 L2 归一化
  后落盘），余弦相似度 = 归一化向量点积
- **逐批串联**：`build_people_steps`（video.py:385）在 ②聚类 后插 ②.5 照片匹配
  步骤，candidates 与该批 clip_cache.json 配对（该 cache 由 ② 聚类落盘在
  `batch.scorer_clusters.parent`）；产出 `scorers_bK/photo_matches.json`
- **确认页显式传参集成**：video.py 拼确认页参数时探测
  `scorers_bK/photo_matches.json` 存在才拼 `--photo-matches`（与
  --index/--roster-existing 同构，video.py:432-438）；gen_scorer_page 只认
  显式参数、无参数一律旧行为（不自动摸目录——与 spec "无此参数行为不变"
  的兼容性承诺一致）
- **号码→人全靠既有名单机制**：`match_players_by_number`
  （gen_scorer_page.py:1103）与 --players-file 不改造，照片命中只负责产出
  "号码"，占位条目（名单缺号时 `半截篮<号>`）随 players 注入
- **Phase A/B 硬闸**：T4 实跑不达标（<80% 或 >10%）→ 归档 review 停工，
  人脸模型路线经立哥批准再议；Phase B 代码一律不进 main 链

## 前置依赖（立哥侧，非代码任务）

- P1 供照到位：`photos/<号码>/` 每号码正反各 1 张起步
- P2 淳化街道 roster confirmed=true（people 链确认，照片库成员 tag 建议带号码）

T1-T3 不依赖 P1/P2（合成数据 TDD），可先动手；T4 实跑卡 P1+P2。

## Task List

### Phase A：匹配核心 + 对照实验

- [ ] T1 照片库加载 + 照片 embedding 缓存
  - Acceptance: 扫 `photos/<号码>/` 产出 gallery（去零号码 → [照片路径]）；
    非数字名/空文件夹/无合法图 WARNING 跳过、全无效显式报错；号码归一化
    `07`→`7`（原名仅展示）；.photo_cache.json 幂等增量（新增照片只算新图）、
    模型前缀隔离；**`.gitignore` 加 `photos/`（真人照片不入库红线，
    `git check-ignore photos photos/.photo_cache.json` 通过）**
  - Verify: `pytest tests/test_photo_match_scorers.py -k gallery or photo_cache`
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py、.gitignore
- [ ] T2 匹配主链（得分 + 闸 + 产物）
  - Acceptance: --candidates 可重复合并、--cache 可重复并集查询；得分 =
    max(crops × photos) 余弦；并列最高不采纳、单号码库 margin=+∞；
    `score≥THRESHOLD 且 margin≥MARGIN` 才入 photo_matches.json（阈值常量
    占位待 T4 标定）；裁图 md5 不在缓存 WARNING 跳过该球、cache 文件缺失
    显式报错、本模型前缀命中率 0% 显式报错；产物 schema 显式校验
  - Verify: `pytest tests/test_photo_match_scorers.py`
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py
- [ ] T3 --evaluate 评估模式
  - Acceptance: 真值映射（半截篮 tag 取号、无号半截篮 tag 单列"不可判"、
    对方/便服记无号）；入统 = goals confirmed 且 key 在 roster.assignments；
    报告含全部入统球 top-1 号码+score+margin 分布（不过闸）+ 正样本命中率 +
    负样本误命中率 + 按号码混淆矩阵；markdown 报告写到 --out；坏 roster
    SchemaError
  - Verify: `pytest tests/test_photo_match_scorers.py -k evaluate`
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py

### Checkpoint A（立哥过目）

- [ ] T4 Phase A 实跑 + 阈值标定（卡 P1+P2）
  - Acceptance: 淳化街道实跑出报告；按分布定 THRESHOLD/MARGIN 写死常量
    （注释注明标定来源）；达标线双指标判定；报告+结论归档 review03.md
    （**预置达标/不达标两个结论模板，实跑后只填数**，降低立哥过目摩擦）；
    **不达标 → 停工报立哥，不进 Phase B**
  - Verify: 实跑命令见 spec §Commands Phase A；review03.md 立哥确认
  - Files: docs/photo-roster/review03.md、scripts/photo_match_scorers.py（阈值常量）

### Phase B：集成（Phase A 达标才动）

- [ ] T5 gen_scorer_page 照片预填
  - Acceptance: 只认显式 `--photo-matches`（须与 --scorers 同目录），无参数
    行为零变化；优先级 读号>照片>印名>空白；
    读号/照片冲突 → 预填读号 + 条目角标显示照片候选（号码+得分）可点击切换；
    名单缺号 → 占位条目 `半截篮<号>` 随 players 注入（不依赖前缀推队）；
    坏 photo_matches schema SchemaError
  - Verify: `pytest tests/test_gen_scorer_page.py -k photo`
  - Files: scripts/gen_scorer_page.py、tests/test_gen_scorer_page.py
- [ ] T6 video.py people 串联
  - Acceptance: build_people_steps 在 ②聚类 后插 ②.5 照片匹配步骤（条件：
    `photos/` 存在且非 --skip-cluster；缺库 INFO 跳过整步不阻塞）；
    拼确认页参数时探测 photo_matches.json 存在才传 --photo-matches；
    **仅 ②.5 步允许失败降级（ERROR 留痕、确认页照出、降级为无预填），
    ①②③ 失败语义不变（任一步失败中断整链）**；单测用假步骤列表断言串法
  - Verify: `pytest tests/test_video.py -k people`
  - Files: scripts/video.py、tests/test_video.py
- [ ] T7 文档同步 + 真机验证 + 收尾
  - Acceptance: 使用手册.html 加供照说明与流程变化；AGENTS.md 认人链路口径
    更新（照片预填进 people 链）；淳化街道 people 链真机重跑，确认页预填
    肉眼抽验；review04.md 归档；四件套 todo 全勾
  - Verify: 关口全绿 + 真机抽验 + `grep` 无旧口径残留
  - Files: 使用手册.html、AGENTS.md、docs/photo-roster/review04.md

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|---|---|---|
| Phase A 不达标（CLIP 域差距在 1:N 场景仍吃命中率） | 高 | 硬闸停工；备选人脸模型（Ask first）；读号链路不受影响仍是主信号 |
| 照片质量差（模糊/多人/遮脸） | 中 | 供照说明前置给立哥；确认页角标人工兜底；照片可随时后补增量重算 |
| 淳化街道 roster 无号 tag 多 → "不可判"占比高、评估失真 | 中 | P2 操作建议 tag 带号码；不可判单列不计分母 |
| 某批 ② 聚类未跑 → 该批 cache 缺失 | 低 | 契约已写死显式报错；people 链顺序保证聚类先于匹配 |
| 阈值标定过拟合单场次 | 中 | 常量注释注明标定来源；后续场次确认页终裁天然纠偏，观察值记 review |

## Open Questions

- THRESHOLD/MARGIN 具体值：T4 标定后填（Ask first 边界内的立哥确认项）
- 人脸模型备选的具体选型：仅当 Phase A 不达标才展开
