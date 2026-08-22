# Plan: basketball-clip —— 开源 GUI 改造实施计划

> 依据 `docs/basketball-clip/spec.md` v5（立哥已批准）。2026-08-22。
> 阶段关系：SP 先行（打包可行性兜底，不碰 scripts、不受 O4 时间线约束），A→B→C 串行，D 与 C 可部分并行，E 穿插，F 收尾。
> **A 阶段启动前提（O4 定案）**：立哥宣布现工作区在途功能开发完成后才启动；A 启动即取 scripts/tests 最新快照，此后现工作区 scripts 冻结，新功能只进新仓库。

## 组件与依赖图

```
SP 打包spike(3.10+PyInstaller) ──┐
                                 ├→ E 打包与安装器 → F 发布
A 仓库骨架+脱敏迁移 → B scripts豁免改造 → C GUI → D 售后配套 ──┘
```

- **SP（打包 spike）**：不阻塞 A–D（开发在 3.14 进行，ruff py310 拦截新语法），但**必须在 E 之前出结论**；若不通过，E 的打包方案要回头改（备选：换 3.11/3.12/3.13，或退为 pip 安装版——届时需立哥重新拍板）。
- **A → B**：豁免改造直接在新仓库的 scripts/ 上做，不做两遍。
- **C 依赖 B**：GUI 向导的"设置队名""认人无读号"等交互由 B 的配置注入能力支撑；runner 的命令契约以 B 改造后的 CLI 为准。
- **D 依赖 C 雏形**：诊断日志导出按钮挂在 GUI 上；issue 模板/CONTRIBUTING 可在 A 之后随时做。

## 阶段明细

### SP. 打包可行性 spike（最高优先，半天内出结论）
- 干净 venv 装 Python 3.10 + 全量依赖（torch CPU、ultralytics、open_clip、opencv、scikit-learn、fastapi、uvicorn、pyinstaller）。
- 打一个最小可跑包（hello + import torch/ultralytics/cv2），验证 PyInstaller 对 3.10 与各库的收集（hidden imports、torch 数据文件）。
- 产出：可行/不可行结论 + 踩坑清单，记入 review 文档。
- **验证点**：打出的 exe 在无 Python 环境目录能跑通 import 链。

### A. 新仓库骨架 + 脱敏迁移
- 本地新建 `basketball-clip/`（空历史 git init，**不 push**——推送属对外操作，届时先问立哥）。
- 抽取 `scripts/`（剔除 vlm_filter/vlm_judge_events/vlm_trial_ark）、`tests/`、`rules.md`、`ruff.toml`（target-version 降 py310）、`pyproject.toml`（改写打包元数据）。
- tests/ 75 处私人字样替换通用样例（红队/20260801/测试员），scripts/ 注释脱敏。
- LICENSE(MIT)、README.md（中文+英文摘要）、.gitignore、使用手册重写版骨架。
- **查证 abdullahtarek_ball.pt 许可**（O1 收尾），不通过则该模型改首运下载方案。
- **验证点**：新仓库 `pytest -q` 全绿；关键词扫描表零命中（署名豁免除外）。

### B. scripts 豁免清单五类改造（新仓库内）
1. 配置外置：代理/凭证路径 → 环境变量（缺省关闭）。
2. 队名可配置化：roster/gen_scorer_page 队名会话注入；video.py 等零散"半截篮"字样通用化。
3. vlm_* 三脚本剔除（A 已做），**crop_scorers 顶层 import 改延迟导入**（仅 --read-numbers 路径触发），所需常量/函数归属在此定案。
4. 读号默认关闭 + 无凭证显式报错。
5. OSNet/torchreid 下线（cluster_scorers + 对应测试剔除）。
- 每类改造独立 commit，均跑全绿关口。
- **验证点**：CLI 回归——五个子命令与现工作区同输入同产物（豁免项除外）。

### C. GUI（FastAPI 后端 + 原生前端向导）
- `gui/runner.py`：subprocess 任务编排，按"进度协议 v1"（下节定死）解析 logging 行 → 进度事件（SSE），任务状态落盘可断点续查。
- `gui/app.py`：REST（选目录/建场次/启动任务/查状态/取消）+ SSE + 静态页托管；标注/认人/照片确认页直接复用现有生成器产物（GUI 内嵌或新开页）。
- `gui/static/`：中文向导（选素材 → 设队名 → 检测 → 标注 → 认人 → 合集 → 照片），每步进度条 + 失败友好提示。
- 输入校验在后端边界；错误不吞，前端友好提示 + 后端详细日志。
- **验证点**：`tests/gui/` 全绿；浏览器自动化冒烟（向导首页渲染、任务启动到进度推送）通过；小样片全流程手测走通。

## 进度协议 v1（plan 阶段定死，spec 承诺；scripts 侧零改造）

runner 对子进程 stdout 逐行解析，规则全部集中在 `gui/runner.py` 单点：

- **步骤边界**：匹配 `执行: (.+)$`（video.py `run_step` 既有日志格式）→ 发 `step_start`；子进程退出 0 → `step_done`；非 0 → `step_failed`（带 returncode 与末 N 行日志）。
- **进度估算**：`step_index / total_steps`，total_steps 由 runner 在任务启动时按命令链预计算（如 people = 批次数 × 3 段）；无子步骤内细粒度，不定量部分前端转圈。
- **日志透传**：所有行原样以 `log` 事件推 SSE，前端滚动显示（普通用户可折叠）。
- **SSE 事件类型**：`step_start` / `step_done` / `step_failed` / `log` / `task_done` / `task_failed`，共六种。
- **降级规则**：任何解析异常/格式不识别的行只透传 `log`，进度保持上次值，绝不报错中断任务；未来 scripts 日志格式变动最多损失步骤进度精度，不伤主链。

### D. 售后配套
- GUI"导出诊断日志"按钮（版本号+系统信息+后端日志 → zip）。
- `.github/ISSUE_TEMPLATE/`（中文 bug 模板，引导附诊断 zip）、`CONTRIBUTING.md`。
- **验证点**：诊断 zip 内容完整可解；issue 模板在 GitHub 预览渲染正常（push 后验）。

### E. 打包与安装器（SP 通过后启动）
- PyInstaller spec（one-folder）：收齐 torch/ultralytics/open_clip 数据文件、ffmpeg（BtbN LGPL）+ 许可文本、双 YOLO 模型、CLIP 权重。
- Inno Setup 脚本：安装向导、桌面图标、卸载；体积预估 ~1.5GB。
- **验证点**：干净 Windows 环境（沙盒/虚拟机）双击安装 → 全流程小样片跑通（Success Criteria 4）。

### F. 发布（全程先问立哥）
- 创建公开仓库 `github.com/huangli/basketball-clip`、push、开 Issues。
- gitleaks + 关键词扫描终审（署名豁免口径）；Release v0.1.0 挂安装包。
- **验证点**：脱敏验收零命中；立哥过目仓库首页后确认公开。

## 风险与对策

| 风险 | 对策 |
|---|---|
| SP 不通过（PyInstaller/依赖在 3.10 踩死坑） | 备选 3.11/3.12/3.13 逐档试；全不行则降级为 pip 安装版，回头找立哥重定分发方案 |
| abdullahtarek 模型许可不允许再分发 | 改首运下载（HF/Roboflow 直链），GUI 加"下载模型"步骤兜底 |
| B 改造引入 CLI 行为偏差 | 每类改造独立 commit + 回归对照（同输入同产物）；豁免清单之外一律不动 |
| 现工作区在途改动漂移（O4） | A 启动前提 = 立哥宣布在途功能完成；A 取最新快照后现工作区 scripts 冻结，新功能只进新仓库 |
| GUI 进度解析脆（logging 文本变动） | 进度协议集中在 runner 单点；解析失败降级为"运行中"不定量进度，不报错 |
| 干净机器验证环境缺失 | 用 Windows 沙盒或新开用户账户+临时目录模拟；立哥实机协助终验 |

## 并行/串行结论

- 串行主线：A → B → C → E → F。
- SP 立即先行（半天）；D 的 issue 模板/CONTRIBUTING 可在 A 后任意插入；诊断导出随 C 一起做。
- 立哥现工作区的在途功能开发不受阻（O4：完成后再切换主仓库）。
