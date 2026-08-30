# Plan: 视频封面生成（cover-gen，docs/cover-gen/spec.md v2）

## 组件与依赖

```
gen_covers.py 抽帧+合成+网格（核心，无依赖，最先做）
        ↓
video.py covers 子命令（解析 session/roster/rawdir + 组装 filters + 调 gen_covers）
        ↓
测试 → 实机验证 → 使用手册.html 同步 → 提交
```

## 步骤

1. **gen_covers.py 核心**
   - 输入解析：--session/--rawdir；读 goals_batch（多批时 merge）+ roster
     （validate_roster）
   - 复用 select_goals 命名 + filters（--scorer/--team/--batch/--all；无过滤=--all）+ 自动模式判定
   - 抽帧：`clamp(anchor-0.5, 0)` → ffmpeg 单帧 → 等比充满缩放 + 中心裁 1080×1440
     → PIL 叠文字（队伍名/片名，load_font 微软雅黑→宋体→报错）→ cover_NNN.jpg
   - 网格预览 sheet.jpg（PIL 拼缩略图+编号）
   - 单球抽帧失败 WARNING 跳过；全败退出 1；无 rawdir 复用 resolve_rawdir 报错
   - 验收：tests/test_gen_covers.py 用例 1-10

2. **video.py `covers` 子命令**
   - argparse 加 covers（--session/--rawdir/--scorer/--team/--batch/--all）
   - 解析 session_dir + rawdir + roster/自动模式 → 组装 filters（复用 _build_expand_all
     逻辑，无过滤走 --all）→ 调 gen_covers
   - 验收：test_video.py 增 covers 回归（covers 无过滤等价 --all、自动模式只出颜色队）

3. **关口**：ruff format/check + pytest -q 全绿（--fix 后复核 diff）

4. **实机验证**（20260822_citymonkey）：
   - `video covers --team 半截篮` 出 队伍_半截篮_进球集锦 目录（候选数 = select_goals 命中数
     ≈20，sheet 带编号）
   - `video covers --scorer 半截篮6` 出 半截篮_黄立_进球合集 目录
   - 抽查封面 1080×1440、文字可见、无黑边

5. **文档同步**：使用手册.html 加 covers；docs/cover-gen/ 四件套完

6. **提交**：`feat: video covers 生成视频封面（3:4 候选多张供挑选）`，不 push

## 风险与缓解

- **R1. 中文字体缺失/乱码** → load_font 探测（微软雅黑→宋体→显式报错），日志提示所用字体
- **R2. 产物名与 build 不一致** → 直接复用 select_goals，不复制一套命名
- **R3. 抽帧失败单点阻塞** → 单球 WARNING 跳过，全败才退出 1
- **R4. 候选过多** → 不硬编码张数；sheet 网格快速浏览
- **R5. covers 缺省误做成"全员"** → 无过滤明确走 --all 展开（D4/B2），测试锁定

## 并行/顺序

步骤 1 先（gen_covers 独立）；2 依赖 1；3-6 严格顺序。
