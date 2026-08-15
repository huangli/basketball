# todo: 场次精彩照片自动挑选（photo-select）

- [x] spec/plan/todo 初稿 + spec-reviewer 第一轮（2 阻断 + 6 建议）
- [x] 按审查修订三件套（B1 比例跟随素材、B2 可执行断言、球 conf≥0.35、±3 帧防抖、apply schema 校验、分桶保底规则）
- [x] 测试先行：test_rank_photos.py + test_gen_photo_page.py（打分/分桶/构图/换算断言/页面）
- [x] rank_photos.py: 缓存打分 + 保底分桶 top200 + 抽帧防抖 + 构图裁切 + candidates json
- [x] rank_photos.py --apply: selections schema 校验 + 落盘 output/<场次>/照片精选/
- [x] gen_photo_page.py: 瀑布流确认页
- [x] video.py photo 子命令 + 使用手册.html + AGENTS.md 同步
- [x] ruff format/check + pytest 全绿（146 测试）
- [x] 实跑 20260805_车百鼎：211 张候选 + 页面，抽查 10 张构图 8 合格（review01.md）
- [x] review01.md 存档
- [x] git commit（只 commit 不 push）
- [ ] 立哥页面点选后跑 `video photo --session ... --apply` 验证落盘链路

## 第二轮调参（2026-08-15，立哥反馈：冲击力不够——要力量感/特写/进球最后一瞬/篮板）

- [x] 失败测试先行：球筐距信号 / 进球锚点 ±0.6s 加成与保底 / 特写构图（55~75%、留白≥5%、切脚允许、>85% 降分）/ hoops-goals 加载 / --force
- [x] rank_photos.py：hoops_batchN 球筐距信号（权重 0.35 主信号）+ goals_batchN confirmed 加成（×1.5 + force_pick 额外保底）+ 权重重排 + 特写构图替换保守外扩 + --force 全量重跑
- [x] ruff format/check + pytest 全绿
- [x] 旧候选指标基线（211 张：筐窗口内 85.3%、进球锚点 ±2s 内 16.1%、±0.6s 覆盖 16/122）
- [x] 实跑 `--force` 重出候选（334 张，模糊丢弃 9）+ 重新生成确认页
- [x] 抽查 12 张新候选：筐附近占比大升（±2s 16.1%→57.2%，±0.6s 覆盖 16/122→119/122），零切头；进球帧构图偏宽为主要不足
- [x] review02.md 存档 + spec-reviewer 文档自审（2 阻断：测试计数失实/spec 留白口径冲突，均已修订）
- [x] git commit 87563dd + 文档修订补交（只 commit 不 push）
