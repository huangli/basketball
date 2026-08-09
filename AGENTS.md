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
- Python 3.14.3 已装；已装 ultralytics 8.4.104 + torch 2.13.0 (CPU) + opencv 5.0.0 + numpy 2.4.3 + pillow 12.3 + open_clip_torch 3.3.0 + scikit-learn 1.9.0 + transformers + timm 1.0.28 + httpx + torchreid 0.2.5 + tensorboard（pip 清华镜像源；torchreid 的 PyPI 名是 torchreid 非 deep-person-reid）
- **硬件**：AMD Ryzen AI 9 HX 370 + Radeon 890M 核显（**无独立 N 卡**），32GB 内存；YOLO CPU 推理约 1.1s/帧（1920 宽 @ imgsz1280，双模型）
- **模型**：`models/` 目录下 `abdullahtarek_ball.pt`（球检测主力）+ `yolov8n.pt`（人物，持球排除用）；`osnet_x1_0_market1501.pth`（行人 Re-ID，认人聚类备用后端，Market1501 训练，官方 MODEL_ZOO Google Drive 链接下载）；`basketball_yolo11.pt`（Lumos-88，已证假阳性爆炸）、`446f6e6e79_yolo11m.pt`（已证不可用）留档
- 网络：代理在 `127.0.0.1:7897`（Clash）；pip 用清华镜像；HF 下载需 `HTTPS_PROXY=http://127.0.0.1:7897`
- Shell 是 Windows PowerShell 7+；本机 Kimi Code CLI（Kimi Code 托管订阅，凭证 `~/.kimi-code/credentials/kimi-code.json`，**token 有效期仅 900s**，脚本每次调用前重读）
- **VLM**：Kimi K3（经 Kimi Code 订阅 `api.kimi.com/coding/v1`，支持图片输入）；**生产流水线已不用**（2026-08-01 起下线，见工作流约定），留作未来多模型试验；用法与坑见方案文档 §2/§3.5/§5

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
- 成品分两类、按场次分目录：`output\<场次>\队伍_XX_进球集锦.mp4` 和 `output\<场次>\<队伍>_<姓名>_进球合集.mp4`（2026-08-09 起新命名，姓名为空回退标签），片段按拍摄时间排序，同参数 concat 直接重封装不重编码；若同场次混入不同比例素材，须按比例分别合成或统一缩放重编码后拼接
- 审核视频 2 倍速（立哥实测可稳判，声音保留）

## 代码规范（强制，勿再询问）

- **所有 `scripts/` 下的 Python 代码必须遵守根目录 `rules.md`**（鲁棒优先 ＞ 性能 ＞ 简洁）。
- **spec/plan/todo/review 四件套先行（2026-07-30 立哥定，07-31 定目录）**：`scripts/`、`tests/` 的新功能、多文件改动等非小修小补的代码工作，动手前必须先产出四件套——spec（目标/边界/成功标准）、plan（执行步骤）、todo（勾选清单）、review（审查报告存档），**每一个 spec 一个子文件夹，四件套同放 `docs/<功能名>/`**（spec.md / plan.md / todo.md / reviewNN.md；不再使用 tasks/ 目录）；**review 按轮次编号**（review01.md、review02.md……每轮审查一份，递增不覆盖），按本文档自审要求过 spec-reviewer；`docs/` 根下只放长期方案文档（pipeline 主文档、对外需求文档等）。小修 bug、单点参数调整、`work/` 下一次性探索脚本可豁免。直接开写容易出错，禁止。
- **lint/format/test**：Ruff 为唯一权威（`ruff.toml`），格式化 `ruff format`，检查 `ruff check`，测试 `pytest`。提交前跑 `ruff format scripts tests && ruff check --fix scripts tests && pytest -q`（`--fix` 后须复核 diff）。
- **自动提交（2026-08-01 立哥定）**：修改完成即 git commit，不再等立哥口令——按逻辑改动为单位提交；代码改动须先过上条 lint/format/test 关口全绿，文档改动须先过 spec-reviewer；提交信息用中文 conventional 风格（参照 `git log`）；**只 commit 不 push**；素材、中间产物、模型权重等 `.gitignore` 排除项及敏感/凭证文件一律不 add。
- `archive/` 下已冻结代码不受 `rules.md` 约束，不要回头改。

## 工作流约定

- **当前方案文档**：`docs/2026-07-26-current-goal-detection-pipeline.md`（流水线、实测指标、已证伪清单、素材适配、生产计划，先读它再动手）
- 中间产物放 `work\`（frames / detect / review / label / pilot），成品放 `output\<场次>\`
- 状态存 JSON：`goals.json`（进球时刻）、`roster.json`（进球→人物→队伍），便于断点续做
- **检测流水线**（详见方案文档）：抽帧 5fps → abdullahtarek+yolov8n 检测 → MOT 静止段+断轨重连候选 → 筐轨迹补检 → 事件合并+筐距排序 → label.html 标注页（J/P/F；片段自带 2x 烘焙，页面默认 1x = 有效 2x，S 键加至有效 4x；同文件审核窗口重叠事件标"疑似同回合"组标签，组内新判 J 可一键把同组未标注成员标 F 跳过，导出时同组多 J 弹确认框兜底）→ goals.json → build_highlight.py 合成（--out 按场次注入尺寸）；**事件级 K3 判定已下线**（2026-08-01 立哥定：批次 2 实测 7 次 YES 仅 6 真 1 误、仅覆盖 6/35 球，NO 误杀真球 4 起、排尾险致漏球，排序性价比过低，批次 3 起不跑）
- **文档自审（强制）**：创建或修改 `docs/` 下文档（含各功能子文件夹的 spec/plan/todo/review）、`AGENTS.md`、`rules.md` 后，必须通过 Task 工具调用 `spec-reviewer` 子代理审查；有阻断问题须修订后再交付，禁止跳过
- 进球归属：个人合集需标进球者；立哥人工标注（当前），照片库自动认人（待立哥供照）

## 当前状态（2026-08-09；20260722 场次全量闭环）

- **三批次总账：300 视频全量跑完，103 confirmed 进球**（17 + 35 + 51），全部经立哥合集验收
- **批次 1（首批 50 视频）全链路闭环（含认人）**：17 球 → 12 个个人合集 + 2 个分队集锦（黑 3 / 白 6；便服 8 球只进个人合集）→ `output/20260722/`；`roster.json` 已生成并经立哥两轮修正（黑21 拆分 大斌/王敏龙、白22 并入小朱、蓝27 归黑队）
- **批次 2（第 51–150 视频）**：100 视频 → 684 候选 → 185 事件 → **35 球** → `output/20260722_2/`；审核片段含 +4s 结局尾巴、默认全景、跨文件续接；批次 2 为 K3 事件级判定末次运行（对照账见主文档 §4，性价比不成立而下线）
- **批次 3（第 151–300 视频）**：151 视频 → 913 候选 → 234 事件 → 标 61 J → 去重鉴定 **51 球** → `output/20260722_3/`；K3 下线后首个纯"机器排序+人裁判"批次；去重明细与系统性发现（同球双 J、大疆尾截短特性、文件名时间戳重叠）见主文档 §4 批次 3 节
- **合集口径（2026-08-08 立哥定）**：不出全员总合集；分队合集按队伍出，但依赖认人（批次 2/3 均未标 scorer），立哥暂不认人——要分队合集时先跑认人流程
- **标注页提效已交付（2026-08-09 立哥验收通过）**：dedup-same-goal（疑似同回合组标签 + 导出多 J 确认兜底，批次 3 回放 8 组同球双 J 全命中）+ label-speedup（组内新判 J 一键跳过同组、页面倍速控制——默认有效 2x，S 键加 4x；回放自动跳过 15 条、51 球零误标）；四件套在 `docs/dedup-same-goal/`、`docs/label-speedup/`
- **认人流程（已固化）**：crop_scorers.py（轨迹法定位+多裁选帧+串人守卫+颜色分队预填；--read-numbers 读号已升级为多帧众数投票，旧数据回填用 --numbers-cache-only 零新调用，新场次全量模式 --max-reads 按球数×3 估）→（可选）cluster_scorers.py（聚类仅作分组预填不终裁；**CLIP complete@0.15 为定稿**，需显式传 `--linkage complete --threshold 0.15`；OSNet Re-ID 后端 --model osnet_x1_0 已接入但 20260722 标定未超 CLIP——51.5% vs 62.6%，备用不推荐；曲线见 docs/scorer-reid/review01）→ gen_scorer_page.py（确认页，--clusters 簇级一次选人+逐球覆盖，--players-file 注入号码→姓名名单如 work/20260722/players.json，裁图仅辅助、视频为终裁）→ 立哥确认导出 roster.json → build_highlight.py --roster/--scorer/--team 出合集（命名见剪辑规格）；四件套在 `docs/scorer/`、`docs/scorer-cluster/`、`docs/scorer-reid/`
- **机器裁判方向终结（已证伪）**：K3 事件级判定、豆包视频模型慢放判定均撞"盲区像素证据弱"同一堵墙；**架构定位 = 机器排序 + 人裁判**；K3 判定 2026-08-01 起下线
- **自动剔除长期关闭**：0 漏检宣称 99% 召回需 299 独立正样本 ≈15 场次；NO 只排序不剔除
- 球员照片库待立哥新增（到手后可上人脸识别预填）；新比赛素材待立哥加入（干完他会删旧素材）
- 文档：`docs/2026-07-26-current-goal-detection-pipeline.md`（方案主文档）、`docs/2026-07-28-goal-autotriage-requirements.md`（对外需求文档）
