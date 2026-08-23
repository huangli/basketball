# Todo: 照片库认人（photo-roster）

依据 `docs/photo-roster/spec.md` + `plan.md`（第 4 轮审查修订稿）。按依赖序执行，
逐项验收。前置（立哥侧）：P1 供照 `photos/<号码>/`（✓ 已到 7 人 14 张）；
P2 测试场次 roster confirmed=true（立哥另下载测试视频，淳化街道将删除不作
评测依据）。T1-T3 不卡前置（合成数据 TDD）；T4 实跑卡 P1+P2；
Phase B 卡 Checkpoint A 达标。

- [x] T1 照片库加载 + 照片 embedding 缓存
  - Acceptance: 扫 `photos/<号码>/` 产 gallery（去零号码 → [照片路径]）；
    非数字名/空文件夹/无合法图 WARNING 跳过、全无效显式报错；`07`→`7`
    归一化（原名仅展示）；.photo_cache.json 幂等增量、模型前缀隔离；
    `.gitignore` 加 `photos/`（`git check-ignore photos photos/.photo_cache.json`
    通过）
  - Verify: `pytest tests/test_photo_match_scorers.py -k gallery or photo_cache`
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py、.gitignore
- [x] T2 匹配主链（得分 + 闸 + 产物）
  - Acceptance: --candidates 可重复合并、--cache 可重复并集查询；得分 =
    max(crops × photos) 余弦；并列最高不采纳、单号码库 margin=+∞；
    `score≥THRESHOLD 且 margin≥MARGIN` 才入 photo_matches.json（阈值占位
    待 T4 标定）；裁图 md5 不在缓存 WARNING 跳过该球、cache 缺失显式报错、
    前缀命中率 0% 显式报错；产物 schema 显式校验
  - Verify: `pytest tests/test_photo_match_scorers.py`
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py
- [x] T3 --evaluate 评估模式
  - Acceptance: 真值映射（半截篮 tag 取号；无号半截篮 tag 单列"不可判"；
    对方/便服记无号）；入统 = --goals 的 confirmed 球且 key ∈ roster.assignments
    （--evaluate 必须同时给 --roster 与 --goals，缺一 parser 报错）；
    报告含全部入统球 top-1+score+margin 分布（不过闸）+ 正样本命中率 +
    负样本误命中率 + 按号码混淆矩阵；markdown 报告写 --out；坏 roster
    SchemaError
  - Verify: `pytest tests/test_photo_match_scorers.py -k evaluate`
  - Files: scripts/photo_match_scorers.py、tests/test_photo_match_scorers.py
- [ ] T4 【Checkpoint A，卡 P1+P2】Phase A 实跑 + 阈值标定
  - Acceptance: 测试场次实跑出报告；按分布定 THRESHOLD/MARGIN 写死常量
    （注释注明标定来源）；双指标达标判定（≥80% 且 ≤10%）；报告+结论归档
    review03.md（预置达标/不达标结论模板，实跑后只填数）；
    **不达标 → 停工报立哥，不进 Phase B**
  - Verify: spec §Commands Phase A 实跑命令；review03.md 立哥确认
  - Files: docs/photo-roster/review03.md、scripts/photo_match_scorers.py（阈值常量）
- [x] T5 gen_scorer_page 照片预填
  - Acceptance: 只认显式 `--photo-matches`（须与 --scorers 同目录），无参数
    行为零变化；优先级 读号>照片>印名>空白；读号/照片冲突 → 预填读号 +
    角标显示照片候选（号码+得分）可点击切换；名单缺号 → 占位条目
    `半截篮<号>` 随 players 注入；坏 schema SchemaError
  - Verify: `pytest tests/test_gen_scorer_page.py -k photo`
  - Files: scripts/gen_scorer_page.py、tests/test_gen_scorer_page.py
- [x] T6 video.py people 串联
  - Acceptance: build_people_steps 在 ②聚类 后插 ②.5 照片匹配（条件：
    `photos/` 存在且非 --skip-cluster；缺库 INFO 跳过不阻塞）；拼确认页
    参数时按计划预传 --photo-matches，**执行 ③ 前探测产物存在性，缺失则
    剥旗标、确认页照出**（拼装时探测会死锁：首跑产物未落盘）；仅 ②.5 步允许
    失败降级（ERROR 留痕、确认页照出、降级为无预填），①②③ 失败语义不变；
    单测断言串法
  - Verify: `pytest tests/test_video.py -k people`
  - Files: scripts/video.py、tests/test_video.py
- [ ] T7 文档同步 + 真机验证 + 收尾
  - Acceptance: 使用手册.html 供照说明+流程变化；AGENTS.md 认人链路口径更新；
    测试场次 people 链真机重跑、确认页预填肉眼抽验；review04.md 归档；
    本 todo 全勾
  - Verify: `ruff format scripts tests && ruff check --fix scripts tests &&
    pytest -q` 全绿 + 真机抽验 + 无旧口径残留
  - Files: 使用手册.html、AGENTS.md、docs/photo-roster/review04.md
