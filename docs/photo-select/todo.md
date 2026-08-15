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
- [ ] git commit（只 commit 不 push）
- [ ] 立哥页面点选后跑 `video photo --session ... --apply` 验证落盘链路
