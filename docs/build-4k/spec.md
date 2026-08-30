# Spec: build 4K 输出（半截篮集锦默认 4K + --4k 手动重出）

2026-08-29 立哥定。修订既定剪辑规格（原"输出 1080p"）。v3：按 review01/review02 修订。

## Objective

背景：立哥发抖音，1080p 上传只解锁 1080p 档位，4K 上传才有"超清"选项。
两条需求（已与立哥确认）：

1. **半截篮队伍集锦全局默认 4K**：`video build --all` 或 `--team 半截篮` 时
   `队伍_半截篮_进球集锦.mp4` 出 4K（16:9 场次 3840×2160；4:3 场次 2880×2160），
   其余所有产物（对方集锦、全部个人合集、进球片段）维持 1080p。
2. **手动重出 4K**：`video build` 加 `--4k` 旗标，配合现有选择器
   `--scorer <人>` / `--team <队>` / `--all`（或不带选择器=全员合集），把所选产物
   从原片重切重编码出 4K，产物主名在尾部类型词（进球集锦/进球合集）之前插入
   `_4K`，与 1080p 版并存。
   （不是放大已有 1080p 文件——插值放大无画质收益，明文不做。）

用户：立哥（唯一用户）。成功 = 上述两条在 20260822_citymonkey 场次实测出片、
ffprobe 验证尺寸帧率。

## Tech Stack

- Python 3.14 / ffmpeg 8.1.2（libx264 CRF 体系，无 NVENC 依赖）
- 底层 `build_highlight.py --out WxH` 已支持任意尺寸注入（:125-128 解析，
  :615 scale+pad 随注入尺寸生成，CRF 码率随像素自然放大）——**尺寸注入零改动**。
- 改动点：
  - `scripts/video.py`：4K 尺寸常量、`--4k` 解析、per-filter 尺寸与后缀注入（见 D4）
  - `scripts/build_highlight.py`：**仅加一个可选产物名后缀参数**（review01-B1 放行，
    见 D2），既有命名逻辑与真值表语义不动

## Commands

```powershell
# lint / format / test（提交前必过）
ruff format scripts tests; ruff check --fix scripts tests; pytest -q
# 功能验证
video build --session 20260822_citymonkey --all                  # 半截篮集锦应出 4K 原名
video build --session 20260822_citymonkey --all                  # 连跑第二次：幂等，不回退 1080p
video build --session 20260822_citymonkey --team citymonkey --4k # 出 队伍_citymonkey_4K_进球集锦.mp4
video build --session 20260822_citymonkey --scorer 黄立 --4k      # 出 半截篮_黄立_4K_进球合集.mp4
video build --session 20260822_citymonkey --team 半截篮 --4k      # no-op：仍出原名，无重复文件
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 <产物>
```

## Project Structure

```
scripts/video.py              → 4K 常量、--4k 解析、per-filter 尺寸与后缀注入
scripts/build_highlight.py    → 仅加可选 --name-suffix 参数（默认空=现状）
tests/test_video.py            → 增补用例 1-9（见 Testing Strategy）
tests/test_build_highlight.py → --name-suffix 透传用例
docs/build-4k/                → 四件套（spec.md / plan.md / todo.md / reviewNN.md）
AGENTS.md                     → 剪辑规格段同步（半截篮集锦默认 4K）
使用手册.html                  → build 章节同步 --4k 用法
```

## Code Style

遵守根目录 `rules.md`（鲁棒优先 > 性能 > 简洁），与 `video.py` 现有风格一致：
类型标注、docstring 写契约与 Raises、结构化日志、显式报错不猜。

尺寸分类沿用 `resolve_out_size`（video.py:398-447）**现有相对容差口径**
（`abs(ratio - RATIO_16_9) / RATIO_16_9 <= RATIO_TOLERANCE`），不新造第二套判定；
将其重构为一次分类、返回 `(size_1080p, size_4k)` 对，调用方按步骤取用：

```python
def resolve_out_sizes(session_dir: Path) -> tuple[str, str]:
    """按场次素材比例返回 (1080p 尺寸, 4K 尺寸)。

    16:9 → ("1920x1080", "3840x2160")；4:3 → ("1440x1080", "2880x2160")。

    Raises:
        BasketballPipelineError: 素材比例未知或场次内比例混杂
        （沿用现有相对容差判定与混比例显式报错，video.py:444-447，不猜）。
    """
```

## Testing Strategy

`tests/test_video.py` 增补（沿用现有 tmp_path 造场次目录的模式）：

1. `--all` 展开：半截篮 `--team` 步骤 `--out 3840x2160` 且产物原名无后缀；
   citymonkey 与个人步骤仍 `--out 1920x1080`
2. `--4k` + `--scorer/--team`：所选步骤 `--out 3840x2160` 且命令带 `--name-suffix _4K`
3. `--team 半截篮 --4k`：no-op——`--out 3840x2160`、无后缀、无重复产物
4. `--4k` 不带选择器：全员合集步骤 4K + 后缀（产物 `个人_全员_4K_进球合集.mp4`）
5. 4:3 场次（构造 facts ratio=4/3）：4K 映射 2880x2160
6. 未认人自动模式：`--4k` 被忽略并 WARNING，三件套行为不变
7. 未知比例：`BasketballPipelineError` 显式报错
8. 幂等：同参数连跑两次 `--all`，半截篮步骤命令行两次一致（尺寸 4K、无后缀）
9. `--all --4k`：其余步骤 4K + `--name-suffix _4K`，半截篮步骤 4K 原名无后缀
   （review02-B5：OUR_TEAM no-op 覆盖展开路径）

`tests/test_build_highlight.py` 补一条：`--name-suffix _4K` 时产物主名在尾部
类型词前插入后缀（`队伍_X_4K_进球集锦.mp4` / `{队}_{名}_4K_进球合集.mp4`），
缺省不传与现状逐字节一致。

实机验证：20260822 场次 `--team 半截篮` 出片，ffprobe 核 3840×2160/50fps。

## Boundaries

- **Always**：原片只读；沿用 `--out` 注入与 CRF 体系；手动 `--4k` 产物插入 `_4K`
  与 1080p 共存（防止后续 `--all` 重跑把手动 4K 静默覆盖回 1080p）；
  自动模式颜色队（白/黑）**不视为**半截篮集锦，不出 4K
- **Ask first**：改编码器/加硬件加速（本期不做，继续 libx264 CPU）；新增依赖（不需要）
- **Never**：不插值放大已有 1080p 文件充 4K；不改 `build_highlight.py` 既有命名
  逻辑与真值表语义（新增的可选后缀参数缺省行为必须与现状逐字节一致）；
  不让 4K 规则影响未认人自动模式三件套

## 关键设计决策

- **D1. OUR_TEAM**：`OUR_TEAM = "半截篮"` 常量；`--all` 展开与 `--team 半截篮`
  单点均走 4K 尺寸、产物原名（它本身就是默认产物，重复 `--all` 幂等一致，
  连跑 N 次都是同尺寸同名）
- **D2. 后缀落地方式（review01-B1 + review02-B4 定）**：产物主名由
  build_highlight.py 内部生成（:216 `队伍_{team}_进球集锦` /
  :231 `{team}_{name|tag}_进球合集`），video.py 无法事后可靠改名（姓名回退
  逻辑在底层）。故给 build_highlight.py 加 `--name-suffix` 可选参数，
  在 `select_goals` 返回的 out_stem **尾部类型词（进球集锦/进球合集）之前插入**；
  video.py 仅手动 `--4k` 步骤传 `--name-suffix _4K`。缺省不传 = 现状。
- **D3. OUR_TEAM 的 `--4k` 幂等 no-op（review01-B2 + review02-B5 定）**：
  半截篮本已默认 4K 原名——无论 `--team 半截篮 --4k` 单点还是 `--all --4k`
  展开，该队步骤均为 no-op（4K 原名、无后缀、不产重复文件），INFO 提示
  "半截篮集锦已默认 4K，--4k 为 no-op"
- **D4. per-filter 尺寸注入（review01-B3 定）**：现状全 filters 共用一个 out_size
  （video.py:940 拼进 base）。4K 化需把 `--out` 拼装挪进 filter 循环，按
  (filter 旗标, 值, 是否 --4k) 逐步骤定尺寸与后缀——spec 明写此为结构性改动
- **D5. 命名示例**：手动 4K 产物形如 `队伍_citymonkey_4K_进球集锦.mp4`、
  `半截篮_黄立_4K_进球合集.mp4`、`个人_全员_4K_进球合集.mp4`
- **D6. 性能提示**：每个 4K 步骤执行前 INFO 一条（4K CPU 编码约为 1080p 的
  3~4 倍耗时），不在 build 开头统一刷
- 热图步骤与分辨率无关，不随 4K 改变触发口径

## Success Criteria

1. `video build --all`：半截篮集锦 3840×2160（16:9 场次）原名产物，其余产物
   1920×1080，全程无错；连跑第二次命令行与产物保持一致（幂等，不回退）
2. `--team citymonkey --4k` / `--scorer 黄立 --4k` / 无选择器 `--4k`：出 `_4K`
   4K 产物，1080p 原版保留；`--team 半截篮 --4k` 与 `--all --4k` 的半截篮步骤
   无重复文件
3. 4:3 场次映射 2880×2160；未知比例显式报错
4. 未认人自动模式行为不变（颜色队不出 4K）
5. `ruff format` / `ruff check` / `pytest -q` 全绿；四件套齐；AGENTS.md 与
   使用手册.html 已同步

## Open Questions

无（范围/入口/全局性三点已与立哥确认；review01/review02 阻断均已在本版修订）。
