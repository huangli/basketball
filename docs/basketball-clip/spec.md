# Spec: basketball-clip —— 面向普通用户的开源篮球集锦剪辑工具

> 2026-08-22 立哥定方向；四件套按项目约定放 `docs/basketball-clip/`（spec / plan / todo / reviewNN）。
> v5：按 review01–05 修订闭环；O1–O7 全部定案（2026-08-22 立哥）；售后配套（诊断日志导出/issue 模板/Release 流程）经立哥批准纳入范围；spec 已经立哥批准进入 Phase 2。

## Objective

把现有流水线从个人工作区改造为**面向普通用户的开源程序**，发布到 GitHub 新仓库 `basketball-clip`：

- **保留命令行**：现有 `python scripts/video.py score|people|build|photo|clean` 行为保持兼容，老用法不受影响（特许修改范围见"scripts 豁免清单"）。
- **新增友好界面**：本地网页版 GUI（Python 后端 + 浏览器前端），双击启动后自动开浏览器，一步步引导普通用户走完全流程：
  选素材目录 → 设置队名 → 检测进球 → 网页标注 → 认人 → 出队伍/个人合集 → 照片精选。
- **一键安装包**：Windows 安装器，内嵌 Python 运行时与模型，普通用户零配置（无需装 Python/ffmpeg/模型）。
- **开源**：MIT 许可证，中文为主的界面与文档（README 附英文简介），代码与私人数据彻底脱敏。
- **售后配套**：GUI 内置"导出诊断日志"按钮（版本号/系统信息/后端日志打 zip，供用户附到 issue）；仓库预置中文 GitHub issue 模板与 `CONTRIBUTING.md`；修复经 GitHub Release 发布新版安装包。

**目标用户**：想给自己的篮球视频自动剪进球集锦的普通球友（Windows 用户，不懂命令行）。
**非目标**：移动端、云端服务、多用户协作、实时直播剪辑。

**用户故事**：
1. 普通用户下载安装包 → 双击安装 → 桌面出现"basketball-clip"图标。
2. 打开程序，浏览器出现中文界面 → 选择手机导出的视频文件夹 → 填写我方队名 → 点"开始检测"。
3. 检测完界面提示"发现 N 个疑似进球"→ 点进标注页逐个确认（沿用现有 label 页交互）。
4. 进入认人页确认每个进球是谁（无读号，手动为主）→ 点"生成合集"→ 得到按队伍/个人的集锦视频和精彩照片。

## Tech Stack

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.14（开发）；**打包环境 Python 3.10**（见 O6） | 开发环境与现工作区一致；打包用成熟版本 |
| 流水线 | 现有 `scripts/` 迁移，行为兼容 | GUI 只做编排，不重写检测/合成逻辑 |
| GUI 后端 | FastAPI + uvicorn | 新增依赖；REST + SSE 推送任务进度 |
| GUI 前端 | 原生 HTML/JS/CSS（无框架） | KISS；标注/认人/照片页复用现有生成器产物 |
| 进度协议 | runner 解析子进程 logging 行 → 进度事件（SSE） | 日志格式约定在 plan 阶段定死，scripts 侧不加进度改造 |
| 检测模型 | `abdullahtarek_ball.pt` + `yolov8n.pt`（CPU 推理），随安装包分发 | 见 O1（已定案） |
| Re-ID | 仅 CLIP 后端（权重 350MB 打进安装包，见 O5）；OSNet/torchreid 在新仓库下线（见 O7） | 减少老旧依赖 |
| VLM 读号 | 开源版默认关闭，GUI 不暴露（见"scripts 豁免清单"） | 普通用户无 Kimi 凭证 |
| 视频 | **BtbN FFmpeg LGPL build** 随安装包内嵌（许可文本随包附带） | 见 O2（已定案） |
| 打包 | PyInstaller（one-folder）+ Inno Setup 安装器 | 可行性验证见 O6 |
| 许可证 | MIT | AGPL/LGPL 依赖声明见 O1/O2 |

## scripts 豁免清单（review01-B1 定案）

"行为保持兼容"的**例外**——以下五类修改属本项目特许范围，不算违反边界：

1. **配置外置**：硬编码的本机代理 `127.0.0.1:7897`（`video.py`、`cluster_scorers.py`）、凭证路径等改为环境变量/配置文件读取，缺省关闭。
2. **队名/称呼字样清理与可配置化**：`gen_scorer_page.py`/`roster.py` 中"半截篮"固定队名及阵营映射改为会话级配置注入（GUI 向导"设置队名"步骤写入配置）；`video.py:906` argparse description 等零散"半截篮"字样一并通用化。
3. **已下线脚本剔除**：`vlm_filter.py` / `vlm_judge_events.py` / `vlm_trial_ark.py`（事件级 K3 判定已下线、试验脚本）不迁移进新仓库。
4. **读号降级**：`crop_scorers.py --read-numbers` 在新仓库默认关闭；无凭证时显式报错提示"读号需自行配置 VLM 凭证"，不静默失败；GUI 不暴露读号开关。配套改造：`crop_scorers.py:72-87` 对 `vlm_filter` 的**模块顶层 import 改为延迟导入**（仅 --read-numbers 路径触发），所需常量/函数内联进 crop_scorers 或新的小模块（plan 阶段定归属）——否则剔除 vlm_filter 后认人链 import 即崩。
5. **OSNet/torchreid 下线**：`cluster_scorers.py` 中 OSNet 后端（`build_osnet_encoder`、`--model osnet_x1_0`、MODEL_TAGS 分派）剔除，仅保留 CLIP 后端；`tests/test_cluster_scorers.py` 中对应 OSNet 用例一并剔除。

除以上五类，`scripts/` 逻辑与 CLI 行为零改动；GUI 只能通过 subprocess 调用，不得 import 后改其内部逻辑。

## Commands

```powershell
# 开发（在新仓库根）
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -e . -r requirements-dev.txt   # 网络受限用户可选镜像源

# 质量关口（与现工作区一致，提交前必跑）
ruff format scripts tests gui && ruff check --fix scripts tests gui
pytest -q

# CLI（保持兼容）
python scripts/video.py score <素材目录> --session 20260822
python scripts/video.py people --session 20260822
python scripts/video.py build --session 20260822 --all
python scripts/video.py photo --session 20260822 --apply

# GUI 开发模式
python -m gui            # 起 FastAPI，自动开浏览器

# 打包（O6 验证通过后实施）
python packaging/build_installer.py   # PyInstaller + Inno Setup 一键出安装包
```

## Project Structure

新仓库 `basketball-clip/`（**空历史 `git init` 新建**，不携带现工作区 git 历史）：

```
basketball-clip/
├── scripts/            → 现有流水线脚本（剔除 vlm_* 三个，豁免清单内修改）
├── gui/                → 新增：FastAPI 后端 + 静态前端
│   ├── app.py          → FastAPI 入口，REST/SSE 路由
│   ├── runner.py       → 任务编排（subprocess 调 scripts，进度落盘+推送）
│   └── static/         → index.html / css / js（引导式向导界面）
├── packaging/          → PyInstaller spec、Inno Setup 脚本、图标（新做通用图标）
├── tests/              → 现有测试迁移（私人字样替换为通用样例）+ gui/ 新增测试
├── models/             → 不随仓库分发（.gitignore）；安装包/首运下载，见 O1
├── docs/               → 用户文档（中文 README + 英文摘要 + 使用手册重写版）
├── .github/ISSUE_TEMPLATE/ → 中文 bug 反馈模板（引导附诊断日志 zip）
├── CONTRIBUTING.md     → 参与贡献指南（fork → PR 流程，中文）
├── .gitignore          → work/ output/ 素材 模型 凭证一律排除
├── LICENSE             → MIT
├── README.md           → 中文主文档 + English summary
└── pyproject.toml      → 打包元数据 + pytest 配置
```

## 脱敏扫描清单（review01-B2 定案，可执行口径）

**不进入新仓库**：素材目录、`work/`、`output/`、`archive/`、现 `docs/` 下私人决策记录（四件套含立哥决策上下文，仅提炼通用设计进新 docs）、`resource/logo.png`（球队标识，换新做通用图标）。

**关键词扫描表**（对**新仓库全部已跟踪文件**——scripts/ tests/ gui/ packaging/ docs/ pyproject.toml README 等——全量 Grep，零命中才准发布）：
`立哥`、`半截篮`、`车百鼎`、`淳化`、`huangli`、`7897`、`kimi-code`、`dji_mimo_2026` 及任何真实场次名/真名。
**豁免口径**：开源必需的公开署名除外——README/pyproject 中的仓库 URL（`github.com/huangli/basketball-clip`）与作者署名允许命中 `huangli`；脱敏目标是私人素材、真名、场次数据、本机配置，不是公开身份。

**tests/ 口径**：全量迁移，但私人字样（实测 75 处：立哥 6 + 半截篮 35 + 车百鼎 32 + 7897 2）替换为通用样例（如 `红队`、`20260801`、`测试员`），替换后测试必须保持全绿。

## Code Style

与现工作区一致——`rules.md`（鲁棒优先 > 性能 > 简洁）+ `ruff.toml` 迁移到新仓库，**一处定向修改：新仓库 `target-version` 从 `py314` 降为 `py310`**（打包环境 3.10 的开发期防护：ruff 直接拦截 3.11+ 语法如 `tomllib`/`except*`/`typing.Self`，不留到打包验证才炸）：

```python
def load_state(session: str) -> dict[str, Any]:
    """读取 work/<场次>/video_cli.json；不存在返回默认空状态，版本不符显式失败。

    Raises:
        BasketballPipelineError: state 版本不支持（不静默降级）。
    """
```

要点：类型标注、docstring 说明失败行为、显式失败不静默降级、无魔法值、中文注释按现有密度（注释中的私人称呼一并脱敏）。

## Testing Strategy

- **框架**：pytest（现有 21 个测试文件脱敏迁移，保持全绿）。
- **新增 GUI 测试**：
  - `tests/gui/test_runner.py`：任务编排单测（mock subprocess），覆盖成功/失败/中断。
  - `tests/gui/test_app.py`：FastAPI TestClient 路由测试（状态查询、任务启动、错误响应）。
  - **浏览器自动化冒烟** 1–2 条（本机 Chrome DevTools MCP 环境）：向导首页渲染、检测任务启动到进度推送。
- **打包验证**：安装包在干净 Windows 虚拟机/沙盒安装 → 跑通 1 段小样片的完整流程。
- **覆盖率**：不设数字门槛——新逻辑必须有测试，旧行为不回归。

## Boundaries

**Always：**
- 提交前跑 `ruff format && ruff check --fix && pytest -q` 全绿（并复核 --fix 的 diff）。
- `scripts/` 改动仅限"豁免清单"所列类别，其余行为零改动；GUI 只能 subprocess 调用。
- 所有外部输入（用户选的路径、表单参数）在后端边界校验。
- 文档（docs/、README）改动后过 spec-reviewer 审查。

**Ask first（先问立哥）：**
- 新增依赖（FastAPI/uvicorn/PyInstaller 等已声明，之外的新依赖）。
- 豁免清单之外修改 `scripts/` 的任何行为（哪怕看似 bug）。
- 模型权重、ffmpeg 的分发方式定案（O1/O2）。
- 推送 GitHub、创建公开仓库的任何操作。

**Never：**
- 私人素材、roster 真名、场次数据、凭证、本机代理配置进入新仓库或其 git 历史。
- 删除/修改原始视频文件。
- 静默吞异常；GUI 错误必须给用户友好提示且后端留详细日志。

## Success Criteria

1. `git clone` 新仓库 → 按 README 装好依赖 → `pytest -q` 全绿（不含任何机器特定路径）。
2. `python -m gui` 启动后浏览器打开中文向导，普通用户不看命令行能走完：
   选目录 → 设队名 → 检测 → 标注 → 认人 → 出合集 → 照片精选，每步有进度与失败提示。
3. CLI 回归：现有 `video.py` 五个子命令在新仓库行为与现工作区逐项一致（同输入同产物；豁免清单内的配置项除外）。
4. 安装包在干净 Windows 环境双击安装后，上述第 2 条全流程跑通（小样片验证）。
5. **脱敏验收**：新仓库为空历史 `git init`；gitleaks + 关键词扫描表全量零命中（公开署名豁免除外，见脱敏扫描清单）；无私人素材/数据/凭证。
6. 现工作区继续可用，不被本次改造破坏。
7. **售后验收**：向导页"导出诊断日志"按钮产出含版本号+系统信息+后端日志的有效 zip；中文 issue 模板在 GitHub 预览渲染正常。

## Open Questions

| # | 问题 | 背景与选项 | 状态 |
|---|---|---|---|
| O1 | 模型与依赖许可 | ultralytics/yolov8n 是 AGPL：**主代码 MIT 完全开源**（立哥定），AGPL 依赖随包并在 README 显式声明，YOLO 权重允许随安装包分发；`abdullahtarek_ball.pt`（Roboflow 来源）许可发布前必须核实，不通过则该模型改首运下载 | **已定案**（2026-08-22 立哥） |
| O2 | ffmpeg 分发 | gyan.dev 完整版的 nonfree 组件编译在二进制内**无法删除**；定案换 **BtbN FFmpeg LGPL build** 内嵌安装包（功能覆盖转码/缩放/拼接，许可文本随包）。体积口径：torch CPU ~200MB / ffmpeg ~80MB / 双 YOLO ~150MB / CLIP ~350MB | **已定案**（2026-08-22 立哥） |
| O3 | GitHub 仓库归属 | 账号 huangli（ekinasm@gmail.com），目标地址 `github.com/huangli/basketball-clip`，个人公开仓库；协作者/分支保护暂不设，后续需要再加 | **已定案**（2026-08-22 立哥） |
| O4 | 现工作区与新仓库同步策略 | **立哥定案：现工作区先把在途功能开发完成，随后整体迁移，后期只在新仓库开发**（新仓库是主仓库，非旁支拷贝）；迁移完成前现工作区照常自用 | **已定案**（2026-08-22 立哥） |
| O5 | CLIP 权重首跑下载 | 普通用户无代理下 HF 必卡；定案 **CLIP 权重（~350MB）打进安装包**，开箱即用 | **已定案**（2026-08-22 立哥） |
| O6 | 打包 Python 版本 | 立哥改问 3.10 可行性——**方向定案：打包环境用 Python 3.10**（PyInstaller/torch/ultralytics 对 3.10 支持成熟；实证：现 scripts/ 无 3.11+ 专属语法，当前兼容）。防护链：新仓库 ruff `target-version=py310` 开发期拦截 + plan 阶段第一任务 spike 实包验证（3.10 + 全依赖 + PyInstaller） | **决策闭环，spike 验证遗留至 plan 阶段** |
| O7 | torchreid/OSNet 去留 | torchreid 0.2.5 老旧，普通用户 pip 安装易翻车；OSNet 本就"备用不推荐"。**定案：新仓库下线 OSNet 后端**，仅保留 CLIP | 已定案，落地依赖豁免清单第 5 类 |
