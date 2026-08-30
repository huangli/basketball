# Spec: 视频封面生成（cover-gen）——每条输出视频多张候选封面供挑选

2026-08-30 立哥定。背景：视频要发抖音/视频号，需要封面图（小图能看清、带队名/片名）。

## Objective

- 给**每条 confirmed roster 模式的 build 输出视频**（队伍集锦 + 每个个人合集）生成
  **封面候选图**：该合集内每个 confirmed 球都出一张（入网前 0.5s 抽帧），立哥自己挑一张上传
  （自动模式例外见 D4：只出颜色队队伍集锦封面，不出个人合集封面）。
- 封面规格：**3:4 竖版 1080×1440**，等比缩放充满 + 中心裁剪（不拉伸不黑边），叠文字
  （上：队伍名；下：片名 = 产物主名，如 `进球集锦` / `黄立_进球合集`；球员名属主名
  组成部分、非进球细节）。
- 成功标准：`video covers` 在 20260822_citymonkey 场次跑通；每个产物一个目录，
  内含 N 张候选封面（N=select_goals 命中数）+ 一张网格预览图（带编号）；
  grid 与单张均可直接上传。

用户：立哥。产物是图片（JPEG，3:4），不碰原片与既有合集 mp4。

## Tech Stack

- Python 3.14 / ffmpeg 8.1.2（抽帧，任取帧）+ Pillow 12.3（合成文字/裁剪/网格）
- 中文字体：Windows 微软雅黑（`/c/Windows/Fonts/msyh.ttc`），缺则回退系统宋体；
  回退时日志提示所用字体；两者皆无才显式报错（避免成框/乱码字）
- 复用 `scripts/video.py` 的场次发现（discover_batches）、roster 校验
  （validate_roster）、命名（select_goals——与 build_highlight 产物名一一对应）

## Commands

```powershell
# lint / format / test
ruff format scripts tests; ruff check --fix scripts tests; pytest -q
# 生成封面 —— 无过滤缺省 = 等价 build --all（遍历 team + 每个个人，含零命中 skip；
# 非 build 默认的全员合集）。缺省不出一张"个人_全员"总封面（AGENTS.md 不出全员口径）。
video covers --session 20260822_citymonkey
# 限定产物（可选）：--team 半截篮 / --scorer 半截篮6 / --batch 2
video covers --session 20260822_citymonkey --team 半截篮
```

产物落盘：`output/<场次>/covers/<产物主名>/cover_001.jpg ... / sheet.jpg`
（产物主名 = select_goals 输出，与 build_highlight 同名，如 `队伍_半截篮_进球集锦`、
`半截篮_黄立_进球合集`）

## Project Structure

```
scripts/gen_covers.py     → 新增：抽帧+合成封面+网格（核心）
scripts/video.py          → 加 covers 子命令（薄封装：session/roster/rawdir 解析 + 调 gen_covers）
tests/test_gen_covers.py  → 新增用例
tests/test_video.py       → covers 子命令回归用例
docs/cover-gen/           → 四件套（spec.md / plan.md / todo.md / reviewNN.md）
使用手册.html              → 加 covers 说明
```

## Code Style

遵守 `rules.md`（鲁棒>性能>简洁）：类型标注、docstring 写契约与 Raises、
结构化日志、显示报错不猜。ffmpeg 抽帧失败逐球 WARNING 跳过（单帧不阻塞整组），
全部失败显式退出 1。路径用 pathlib，不用反斜杠字面量。

## 关键设计决策

- **D1. 每条输出视频一个目录**：目录名 = 产物主名（select_goals，与 build_highlight
  命名一致），内含 `cover_001..0NN.jpg`（逐一对应该产物 confirmed 球的抽帧）＋
  `sheet.jpg`（网格预览，缩略图带编号，供浏览初选）
- **D2. 裁剪公式（钉死，review01-B1）**：输出 1080×1440（宽×高）。等比缩放充满——
  `scale = max(1080/W, 1440/H)`，将源缩放为 `(round(W*scale), round(H*scale))`，
  再中心裁剪到 1080×1440。任何源都能填满（放大或缩小后中心裁），不拉伸、不黑边。
  **不是**"缩到 1080 高"（那只到 810×1080）。
- **D3. 文字**：PIL 叠加——上缘大号队伍名（如 半截篮），下缘片名（如 进球集锦 /
  黄立_进球合集）；白字+深色描边/底带保证可读；字体加载函数
  `load_font()`：微软雅黑→宋体回退（日志提示所用字体）→皆无显式报错。
- **D4. 命名与过滤**：复用 video.py 现有 filters（--scorer/--team/--batch/--all）与
  roster 判定。**covers 无过滤旗标 = 等价 `--all`**（遍历 team + 每个个人，零命中
  skip），不是 build 默认的"全员"；自动模式（无 confirmed roster）只出颜色队队伍
  集锦封面（便服队不出，同 build 口径），个人合集不出，并以 WARNING"自动模式仅出
  颜色队队伍集锦封面"留痕。
- **D5. 输入**：`--session` 缺省读当前场次指针（同 build）；`--rawdir` 缺省读
  video_cli.json srcdir；取不到显式报错（复用 resolve_rawdir）。
- **D6. 多批次**：多批场次与 build 同口径——经 discover_batches +（多批时）
  `_merge_goals_for_build` 合并后每 filter 只处理一次，防互相覆盖/零球批 exit 1；
  `--batch` 经 `_select_batches` 限定。
- **D7. 抽帧边界（review01-S5）**：`anchor_time - 0.5` 若 ≤0，clamp 到 0 并 WARNING
  提示（该球可能开篇即进）；负值不传给 ffmpeg。

## Testing Strategy

`tests/test_gen_covers.py`（沿用 tmp_path 造场次目录模式）：

1. 抽帧时间点：输入 anchor_time=10.0 → 抽帧时间 = `clamp(10.0-0.5)` = 9.5
2. 裁剪公式（缩小分支）：3840×2160 源 → 输出 1080×1440 无拉伸（scale=max(1080/3840,1440/2160)=2/3，
  缩放为 2560×1440，中心裁宽至 1080）
3. 裁剪公式（放大分支）：更窄源（如 1080×1920 竖源，scale=max(1080/1080,1440/1920)=0.75→实为缩小；
  用 720×1280 源，scale=max(1080/720,1440/1280)=1.5 → 放大至 1080×1920 中心裁）——锁死"放大后
  中心裁也能填满 1080×1440 无黑边"
3. 4:3 源（如 2880×2160）同样填满 1080×1440 无黑边
4. 文字：队名 + 片名均出现在图上（PIL 粗验像素/维度；不做 OCR）
5. roster confirmed：每产物（队伍集锦+个人合集）都出候选；无 roster（自动模式）
   只出颜色队队伍集锦封面，个人合集不出
6. 网格预览：sheet.jpg 尺寸正确且含全部候选缩略图
7. 抽帧失败：单球 ffmpeg 非零 → WARNING 跳过不阻塞；全部失败退出 1
8. `anchor_time` < 0.5：clamp 到 0 且 WARNING，不传负值
9. 无 rawdir / srcdir：取不到 → 显式 error（复用 resolve_rawdir 口径）
10. 多批次 merge：多批场次合并后每产物只处理一次；`--batch 2` 只处理批次 2

实机验证：20260822 场次 `video covers --team 半截篮` 跑通，抽查一张 cover（1080×1440、
文字可见）与 sheet；`video covers --scorer 半截篮6` 出个人合集封面目录。

## Boundaries

- **Always**：原片只读；封面独立目录 `output/<场次>/covers/`，不覆盖/不混入既有
  mp4 产物；抽帧时间 = clamp(anchor_time - 0.5)；等比充满+中心裁剪；文字 = 队伍名 +
  片名（产物主名）；无过滤缺省 = 等价 `--all`（不出"全员"总封面）
- **Ask first**：叠队伍 logo（resource/logo.png，本期不叠，留扩展）；改封面比例/抽帧
  偏移；接 VLM 自动选最"有张力"的一帧（本期不接）
- **Never**：不修改 goals.json / roster.json / 既有合集 mp4；不拉伸变形；字体
  微软雅黑/宋体皆缺时不静默回退成乱码（显式报错）

## Success Criteria

1. `video covers --session 20260822_citymonkey` 跑通 rc 0；每产物目录含候选图 + sheet
2. 封面为 1080×1440、3:4 无拉伸无黑边；含队伍名与片名文字
3. 抽帧时间 = clamp(anchor-0.5)；单球抽帧失败 WARNING 跳过不阻塞
4. 自动模式只出颜色队队伍集锦封面；便服队不出；无过滤缺省 = --all（不出全员总封面）
5. `ruff format/check` 全绿、`pytest -q` 通过；四件套齐；使用手册.html 同步

## Open Questions

- 候选张数不硬编码（= select_goals 命中数）。队伍集锦可能 20+ 张，sheet 网格足够
  浏览；接 VLM 自动选帧后再收紧候选上限。
- 字体回退默认接受（微软雅黑→宋体，日志提示）；若立哥反馈宋体太细可再换。
