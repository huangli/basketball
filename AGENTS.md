# AGENTS.md

## 背景

- 永远称呼用户为**立哥**；球队：**半截篮**；愿景：**玩到60岁**

这不是代码仓库，而是一个篮球视频剪辑工作区。任务：检测进球（球入网）→ 按队伍和个人分别合成集锦。

**素材是流动的**：会不断加入新视频、删除旧视频。因此——
- 不要硬编码文件清单/数量，每次会话先重新扫描素材目录（递归）
- `goals.json` / `roster.json` 以文件名为主键，处理前检查文件是否仍存在，容忍缺失

## 环境（已验证）

- `ffmpeg` / `ffprobe` 8.1.2（gyan.dev 完整版）在 PATH 中，含 NVENC/x264，直接可用
- Python 3.14.3 已装：ultralytics 8.4.104 + torch 2.13.0 (CPU) + opencv 5.0.0 + numpy 2.4.3 + pillow 12.3 + open_clip_torch 3.3.0 + scikit-learn 1.9.0 + transformers + timm 1.0.28 + httpx + torchreid 0.2.5 + tensorboard（pip 清华镜像源）
- **硬件**：AMD Ryzen AI 9 HX 370 + Radeon 890M 核显（**无独立 N 卡**），32GB 内存；YOLO CPU 推理约 1.1s/帧（1920 宽 @ imgsz1280，双模型）
- **模型**：`models/` 下 `abdullahtarek_ball.pt`（球检测主力）+ `yolov8n.pt`（人物，持球排除用）；`osnet_x1_0_market1501.pth`（Re-ID 备用后端）；`basketball_yolo11.pt`、`446f6e6e79_yolo11m.pt` 已证不可用，留档
- 网络：代理 `127.0.0.1:7897`（Clash）；pip 用清华镜像；HF 下载需 `HTTPS_PROXY=http://127.0.0.1:7897`
- Shell 是 Windows PowerShell 7+
- **VLM**：Kimi K3（经 Kimi Code 订阅 `api.kimi.com/coding/v1`，支持图片输入）；**生产流水线已下线**（2026-08-01 起，见工作流约定），留作未来多模型试验；用法与坑见方案文档 §2/§3.5/§5；凭证 `~/.kimi-code/credentials/kimi-code.json` 的 **token 有效期仅 900s**，脚本每次调用前重读

## 素材关键事实（已验证）

- **素材规格不假设**：已验证过两种形态——HEVC 3840×2160 (16:9) 10-bit 59.94fps（dji_mimo 命名）与 4:3 8-bit 50/100fps；处理前必须 ffprobe 确认，脚本尺寸参数需按场次注入
- 文件名即拍摄时间；大疆文件带 data 流和缩略图流，转码用 `-map 0:v:0 -map 0:a:0` 显式选流
- 不删除/不修改任何原始视频文件；素材目录的增删由立哥自己操作

## 已和用户确认的剪辑规格（勿再询问）

- 进球锚点 = 球入网瞬间；片段窗口 = 前 4 秒 + 后 2 秒
- 输出 1080p、50fps、H.264 + AAC；**输出比例跟随素材，等比缩放不裁不切**：16:9 素材出 1920×1080（2 倍整缩放），4:3 素材出 1440×1080（8/3 倍等比）
- 100fps 素材：入网前常速（降 50fps），入网后 2 秒做半速慢放（100→50fps），两段拼接；其他帧率不慢放
- 命名用标签不用真名：`红队-7号`、`黑T恤-A` 风格；花名册生成后需给用户确认
- 按**场次**组织：场次默认 = 文件名日期（YYYYMMDD），同一天多场按时间间隔拆分；用户可明确声明新场次（ID 用 `YYYYMMDD_对手名`），声明优先；roster 按场次隔离、各自需用户确认，跨场次不合并
- 成品分两类、按场次分目录：`output\<场次>\队伍_XX_进球集锦.mp4` 和 `output\<场次>\<队伍>_<姓名>_进球合集.mp4`（2026-08-09 起新命名，姓名为空回退标签），片段按拍摄时间排序，同参数 concat 直接重封装不重编码；若同场次混入不同比例素材，须按比例分别合成或统一缩放重编码后拼接
- **合集口径（2026-08-08 立哥定）**：不出全员总合集；分队合集按队伍出但依赖认人——要分队合集时先跑认人流程
- 审核视频 2 倍速（立哥实测可稳判，声音保留）

## 代码规范（强制，勿再询问）

- **所有 `scripts/` 下的 Python 代码必须遵守根目录 `rules.md`**（鲁棒优先 ＞ 性能 ＞ 简洁）。
- **spec/plan/todo/review 四件套先行（2026-07-30 立哥定）**：`scripts/`、`tests/` 的新功能、多文件改动等非小修小补的代码工作，动手前必须先产出四件套——spec（目标/边界/成功标准）、plan（执行步骤）、todo（勾选清单）、review（审查报告存档），**每一个 spec 一个子文件夹，四件套同放 `docs/<功能名>/`**（spec.md / plan.md / todo.md / reviewNN.md，review 按轮次编号递增不覆盖）；`docs/` 根下只放长期方案文档。小修 bug、单点参数调整、`work/` 下一次性探索脚本可豁免。直接开写容易出错，禁止。
- **lint/format/test**：Ruff 为唯一权威（`ruff.toml`）。提交前跑 `ruff format scripts tests && ruff check --fix scripts tests && pytest -q`（`--fix` 后须复核 diff）。
- **自动提交（2026-08-01 立哥定）**：修改完成即 git commit，不再等立哥口令——按逻辑改动为单位提交；代码改动须先过 lint/format/test 关口全绿，文档改动须先过 spec-reviewer；提交信息用中文 conventional 风格（参照 `git log`）；**只 commit 不 push**；素材、中间产物、模型权重等 `.gitignore` 排除项及敏感/凭证文件一律不 add。
- `archive/` 下已冻结代码不受 `rules.md` 约束，不要回头改。

## 工作流约定

- **方案主文档**：`docs/2026-07-26-current-goal-detection-pipeline.md`（流水线、实测指标、已证伪清单、素材适配，先读它再动手）；对外需求文档 `docs/2026-07-28-goal-autotriage-requirements.md`；**经验教训速查 `docs/经验教训.md`**（历次实测结论与已证伪方向集中索引，动手新方向前先查）
- 中间产物放 `work\`（frames / detect / <场次>/），成品放 `output\<场次>\`；旧 v1 中间产物与旧测试原片已随 archive 清理删除（2026-08-11，释放 33G），`archive/` 现仅存 git 跟踪的冻结代码与文档
- 状态存 JSON：`goals.json`（进球时刻）、`roster.json`（进球→人物→队伍），便于断点续做
- **检测流水线**（详见主文档）：抽帧 5fps → abdullahtarek+yolov8n 检测 → MOT 静止段+断轨重连候选 → 筐轨迹补检 → 事件合并+筐距排序 → label.html 标注页（J/P/F；片段自带 2x 烘焙，疑似同回合分组与倍速控制等提效功能见 `docs/dedup-same-goal/`、`docs/label-speedup/`）→ goals.json → build_highlight.py 合成（--out 按场次注入尺寸）；**新场次用 `run_session.py <素材目录> --session <场次ID>` 一键串联至标注页生成（切批/断点续跑/尺寸探测注入；标注与合集合成仍手工），见 `docs/batch-speedup/`**；triage 缩略图墙已下线（2026-08-11 立哥定，与标注页功能重复，见 `docs/batch-speedup/review07.md`）；**事件级 K3 判定已下线**（2026-08-01 立哥定，对照账见主文档 §4 批次 2）
- **统一入口 CLI**：`python scripts/video.py jinqiu|people|build`——薄封装上述链路（jinqiu=run_session 检测串联、people=认人三段链、build=合集合成；批次自动发现、尺寸按 facts 换算、srcdir 记 `work/<场次>/video_cli.json`），四件套见 `docs/video-cli/`
- **文档自审（强制）**：创建或修改 `docs/` 下文档（含各功能子文件夹四件套）、`AGENTS.md`、`rules.md` 后，必须通过 Task 工具调用 `spec-reviewer` 子代理审查；有阻断问题须修订后再交付，禁止跳过
- 进球归属：个人合集需标进球者；立哥人工标注（当前），照片库自动认人（待立哥供照）
- **认人流程（已固化）**：crop_scorers.py（轨迹法定位+多裁选帧+串人守卫+颜色分队预填；--read-numbers 多帧众数投票读号）→（可选）cluster_scorers.py（聚类仅分组预填不终裁，定稿 **CLIP `--linkage complete --threshold 0.15`**；OSNet 后端备用不推荐）→ gen_scorer_page.py（确认页，--clusters 簇级选人+逐球覆盖，--players-file 注入名单，裁图仅辅助、视频为终裁）→ 立哥确认导出 roster.json → build_highlight.py --roster/--scorer/--team 出合集；参数与标定细节见 `docs/scorer/`、`docs/scorer-cluster/`、`docs/scorer-reid/`
- **架构定位 = 机器排序 + 人裁判**：机器裁判（K3 事件级判定、豆包视频模型）已证伪下线，自动剔除长期关闭；已证伪清单与依据见 `docs/经验教训.md` §2
