# plan: 场次精彩照片自动挑选（photo-select）

依据 `docs/photo-select/spec.md`（含 spec-reviewer 第一轮修订）。

## 步骤

1. **测试先行（rules.md：复杂逻辑先写失败测试）**：`tests/test_rank_photos.py`、`tests/test_gen_photo_page.py`
   - 打分：有球有人 > 无人无球；球速快 > 静止；低置信球（<0.35）视为无球
   - 分桶：构造跨时段分布，验证每桶保底 1 张 + 按分补齐至 N
   - 构图：人框+球框联合包围、边界夹取、头顶留白、最小宽度降级、16:9/4:3 两比例
   - 尺度换算：越界坐标抛 SchemaError
   - 页面：JSON → HTML 含全部候选与导出脚本（断言关键片段）

2. **scripts/rank_photos.py**（核心，新文件）
   - 输入：`--session <场次ID>`，读 `work/<场次>/session_facts.json`、`video_cli.json`（srcdir）；
     缓存经 `crop_scorers.load_mot_cache` 读取（schema 校验唯一入口，参照 release_probe.py 复用方式）
   - 纯函数拆分：`score_frame(...)`、`bucket_pick(scored, bucket_sec=10, total=200)`、
     `compose_crop(person_box, ball_box, img_w, img_h, aspect) -> tuple`、`rescale_box(...)`
   - 尺度换算可执行断言：换算后框落 `[0,width]×[0,height]`（容差 1%），缓存 max x ≤ 1920+ε、
     max y ≤ 检测帧高+ε；违反抛 SchemaError
   - top 200 → ffmpeg 抽帧（候选时刻 ±3 原帧 ×7，Laplacian 选清晰，全组模糊则丢弃记日志）→
     按素材比例裁切（16:9→1920×1080 / 4:3→1440×1080）→ jpg
   - 写 `photo_candidates.json`（pipe_common 原子写）
   - 断点续跑：candidates json 已存在且视频清单未变则跳过抽帧，仅重排

3. **scripts/gen_photo_page.py**（页面，新文件）
   - 读 photo_candidates.json 生成独立 HTML（图片相对路径引用，交互参照 gen_scorer_page.py）
   - 瀑布流 + 点选 + 快捷键 + 导出 JSON 下载 + 保存路径说明

4. **确认落盘**：rank_photos.py `--apply [路径]`（可选参数，缺省 `photo_selections.json` 约定路径）：读入先 schema 校验（rules.md §0.2），
   复制确认照片到 `output/<场次>/照片精选/`，文件名 `照片_XXX_视频序号_时刻.jpg`

5. **集成**：`video.py` 增加 `photo` 子命令（薄封装 rank → page），更新 `使用手册.html` 与 AGENTS.md 工作流约定

6. **关口**：`ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿，
   实跑 20260805_车百鼎 场次出 200 张候选 + 页面，人工抽查 10 张构图质量

7. **review01.md**：存档本轮实现与实测结果

## 顺序与依赖

1 → 2 → 3 → 4 → 5 → 6 → 7。全程不改 mot_cache、不动检测链路。
