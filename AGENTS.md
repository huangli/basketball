# AGENTS.md

## 背景

- 永远称呼用户为**立哥**
- 球队名字：**半截篮**
- 愿景：**玩到60岁**

这不是代码仓库，而是一个篮球视频剪辑工作区。任务：检测进球（球入网）→ 按队伍和个人分别合成集锦。

**素材是流动的**：会不断加入新视频、删除旧视频。因此——
- 不要硬编码文件清单/数量，每次会话先重新扫描素材目录（递归）
- `goals.json` / `roster.json` 以文件名为主键，处理前检查文件是否仍存在，容忍缺失

## 环境（已验证）

- `ffmpeg` / `ffprobe` 8.1.2（gyan.dev 完整版）在 PATH 中，含 NVENC/x264，直接可用
- Python 3.14.3 已装；已装 ultralytics 8.4.104 + torch 2.13.0 (CPU) + opencv 5.0.0 + numpy 2.4.3 + pillow 12.3 + open_clip_torch 3.3.0 + scikit-learn 1.9.0 + transformers + timm 1.0.28 + httpx（pip 清华镜像源）
- **硬件**：AMD Ryzen AI 9 HX 370 + Radeon 890M 核显（**无独立 N 卡**），32GB 内存；YOLO CPU 推理约 1.1s/帧（1920 宽 @ imgsz1280，双模型）
- **模型**：`models/` 目录下 `abdullahtarek_ball.pt`（球检测主力）+ `yolov8n.pt`（人物，持球排除用）；`basketball_yolo11.pt`（Lumos-88，已证假阳性爆炸）、`446f6e6e79_yolo11m.pt`（已证不可用）留档
- 网络：代理在 `127.0.0.1:7897`（Clash）；pip 用清华镜像；HF 下载需 `HTTPS_PROXY=http://127.0.0.1:7897`
- Shell 是 Windows PowerShell 7+；本机 Kimi Code CLI（Kimi Code 托管订阅，凭证 `~/.kimi-code/credentials/kimi-code.json`，**token 有效期仅 900s**，脚本每次调用前重读）
- **VLM**：Kimi K3（经 Kimi Code 订阅 `api.kimi.com/coding/v1`，支持图片输入）用于候选精筛；用法与坑见方案文档 §2/§3.5/§5

## 素材关键事实（已验证）

- **当前真实素材**：`20260722地平线/2026 年 7月22 日 地平线/`（300 文件 / 71 分钟，dji_mimo 命名）；**HEVC 3840×2160 (16:9)、10-bit、59.94fps**——与旧测试素材（4:3，详见下条）不同，处理前必须 ffprobe 确认，脚本尺寸参数需按场次注入
- 旧测试素材（20250419，114 文件 4:3：109 个 8-bit 50fps + 5 个 100fps）已归档到 `archive/0_raw_videos_test/`，仅作回归用
- 文件名即拍摄时间；大疆文件还带 data 流和缩略图流，转码用 `-map 0:v:0 -map 0:a:0` 显式选流
- 不删除/不修改任何原始视频文件；素材目录的增删由立哥自己操作

## 已和用户确认的剪辑规格（勿再询问）

- 进球锚点 = 球入网瞬间；片段窗口 = 前 4 秒 + 后 2 秒
- 输出 1080p、50fps、H.264 + AAC；**输出比例跟随素材，等比缩放不裁不切**：16:9 素材出 1920×1080（2 倍整缩放），4:3 素材出 1440×1080（8/3 倍等比）
- 100fps 素材：入网前常速（降 50fps），入网后 2 秒做半速慢放（100→50fps），两段拼接；其他帧率不慢放
- 命名用标签不用真名：`红队-7号`、`黑T恤-A` 风格；花名册生成后需给用户确认
- 按**场次**组织：场次默认 = 文件名日期（YYYYMMDD），同一天多场按时间间隔拆分；用户可明确声明新场次（ID 用 `YYYYMMDD_对手名`），声明优先；roster 按场次隔离、各自需用户确认，跨场次不合并
- 成品分两类、按场次分目录：`output\<场次>\队伍_XX_进球集锦.mp4` 和 `output\<场次>\个人_XX_进球合集.mp4`，片段按拍摄时间排序，同参数 concat 直接重封装不重编码；若同场次混入不同比例素材，须按比例分别合成或统一缩放重编码后拼接
- 审核视频 2 倍速（立哥实测可稳判，声音保留）

## 代码规范（强制，勿再询问）

- **所有 `scripts/` 下的 Python 代码必须遵守根目录 `rules.md`**（鲁棒优先 ＞ 性能 ＞ 简洁）。
- **lint/format/test**：Ruff 为唯一权威（`ruff.toml`），格式化 `ruff format`，检查 `ruff check`，测试 `pytest`。提交前跑 `ruff format scripts tests && ruff check --fix scripts tests && pytest -q`（`--fix` 后须复核 diff）。
- `archive/` 下已冻结代码不受 `rules.md` 约束，不要回头改。

## 工作流约定

- **当前方案文档**：`docs/2026-07-26-current-goal-detection-pipeline.md`（流水线、实测指标、已证伪清单、素材适配、生产计划，先读它再动手）
- 中间产物放 `work\`（frames / detect / review / label / pilot），成品放 `output\<场次>\`
- 状态存 JSON：`goals.json`（进球时刻）、`roster.json`（进球→人物→队伍），便于断点续做
- **检测流水线**（详见方案文档）：抽帧 5fps → abdullahtarek+yolov8n 检测 → MOT 静止段+断轨重连候选 → 筐轨迹补检 → 事件级 K3 判定（排序信号，不当裁判）→ 事件合并+筐距排序 → label.html 标注页（J/P/F）→ goals.json → build_highlight.py 合成（--out 按场次注入尺寸）
- **文档自审（强制）**：创建或修改 `docs/` 下 spec 文档、`AGENTS.md`、`rules.md`、`tasks\*.md` 后，必须通过 Task 工具调用 `spec-reviewer` 子代理审查；有阻断问题须修订后再交付，禁止跳过
- 进球归属：个人合集需标进球者；立哥人工标注（当前），照片库自动认人（待立哥供照）

## 当前状态（2026-07-28）

- **批次 1（20260722 首批 50 视频）端到端闭环**：365 候选 → 113 事件 → 人工标注 20 球 + 1 训练球 → 去重（190354 同球拆两次）→ **19 球合集已出** `output/20260722/个人_全员_进球合集.mp4`（1920×1080 50fps）；补标 16 事件（覆盖 20 个未覆盖时刻）0 进球，候选级召回账目闭环
- **机器裁判方向终结（已证伪）**：K3 事件级判定（token÷2.4 但 YES=0、NO 精度 95%）、豆包视频模型慢放判定（真球 2/10 YES）均撞"盲区像素证据弱"同一堵墙；**架构定位 = 机器排序 + 人裁判**（筐距排序、K3 NO 排尾、时空聚类去重）
- **自动剔除长期关闭**：0 漏检宣称 99% 召回需 299 独立正样本 ≈15 场次；当前 NO 只排序不剔除
- 下批（全量 300）四改进：筐距排序写入 events_index、事件聚类改时间+空间、事件级 K3 为默认判定协议、自动剔除必配补标机制
- 文档：`docs/2026-07-26-current-goal-detection-pipeline.md`（方案主文档）、`docs/2026-07-28-goal-autotriage-requirements.md`（对外需求文档）
- 全量推进**暂缓**（新旧素材都暂缓），等立哥指令；球员照片库待立哥新增；`roster.json` 尚未生成（待花名册确认）
