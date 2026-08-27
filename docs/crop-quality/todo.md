# Todo: 裁图质量闸（crop-quality）

依据 `docs/crop-quality/spec.md` + `plan.md`。先标定后写码，逐项验收。

- [ ] C1 标定：58 球裁图分布
  - Acceptance: 全部候选帧宽高比分布 + yolov8n 框内复检置信度分布；
    t550.0/t480.1/t34.1/t186.6/t264.4 落点标注；MIN_RATIO/MAX_RATIO/
    PERSON_CONF 建议值（宁漏拦不错杀）；归档 review01.md 标定章
  - Verify: work/crop_quality_calibration/ 分布报告
  - Files: work/（一次性分析脚本）
- [ ] C2 宽高比闸实施
  - Acceptance: 选帧循环内几何闸（C1 定稿常量）；废帧 INFO 留痕；补位
    语义；全废球 SKIP+reason、预览片段保留、SKIP 条目不落 crops/crop_scores；
    单测边界值
  - Verify: `pytest tests/test_crop_scorers.py -k ratio`
  - Files: scripts/crop_scorers.py、tests/test_crop_scorers.py
- [ ] C3 框内人物复检闸实施
  - Acceptance: yolov8n 复检（conf<PERSON_CONF 判无人）；惰性加载+可注入；
    留痕/补位/SKIP 同 C2；单测注入假检测器三分支
  - Verify: `pytest tests/test_crop_scorers.py -k recheck`
  - Files: scripts/crop_scorers.py、tests/test_crop_scorers.py
- [ ] C4 citymonkey 重跑真机验证
  - Acceptance: 操作步骤：① `mv work/20260822_citymonkey/scorers_b1
    work/20260822_citymonkey/scorers_b1.bak`（备份不删）；②
    `python scripts/video.py people --session 20260822_citymonkey --no-read-numbers`
    （**--no-read-numbers 必带**——number_cache 随 scorers_b1 移走，不带会
    全量重调 K3 读号烧额度；②.5 产物顺带刷新——现为 CLIP 匹配产物、非终态，
    以 photo-roster T12 换 L1 后为准，本次仅核对裁图闸；该场次 roster
    未确认导出，确认页刷新无确认态可冲）；③ 核对：
    t480.1/t550.0 被拦留痕（t550.0 属预期拦截不计误杀，补位失败归 SKIP
    亦不算）；truth_16 我方 8 球中除 t550.0 外的 7 球有效裁图零误杀逐球
    核对表；归档 review01.md 验证章
  - Verify: 真机重跑 + 逐球核对表
  - Files: work/20260822_citymonkey/、docs/crop-quality/review01.md
- [ ] C5 文档同步 + 收尾
  - Acceptance: AGENTS.md / docs/经验教训.md 同步；todo 全勾；review01.md
    完整归档
  - Verify: `python -m ruff format scripts tests && python -m ruff check --fix
    scripts tests && python -m pytest -q` 全绿
  - Files: AGENTS.md、docs/经验教训.md
