# AGENTS.md

## 背景

- 永远称呼用户为**立哥**
- 球队名字：**半截篮**
- 愿景：**玩到60岁**

这不是代码仓库，而是一个篮球视频剪辑工作区。任务：检测进球（球入网）→ 按队伍和个人分别合成集锦。

**素材是流动的**：会不断加入新视频、删除旧视频。因此——
- 不要硬编码文件清单/数量，每次会话先重新扫描 `0_raw_videos\`（递归）
- `goals.json` / `roster.json` 以文件名为主键，处理前检查文件是否仍存在，容忍缺失

## 环境（已验证）

- `ffmpeg` / `ffprobe` 8.1.2（gyan.dev 完整版）在 PATH 中，含 NVENC/x264，直接可用
- Python 3.14.3 已装；**已装 ultralytics 8.4.104 + torch 2.13.0 (CPU) + opencv 5.0.0 + numpy 2.4.3 + pillow 12.3**（pip 清华镜像源）；无 moviepy/PyAV
- **硬件**：AMD Ryzen AI 9 HX 370 + Radeon 890M 核显（**无独立 N 卡**，nvidia-smi 不存在），32GB 内存；YOLO CPU 推理约 2.5s/帧（1920×1440 @ imgsz1280）
- **模型**：`basketball_yolo11.pt`（HuggingFace Lumos-88 篮球检测，5.29MB）+ `yolov8n.pt`（COCO 通用，交叉验证 person 用），在工作目录根
- 网络：用户已配代理（rule 模式），GitHub/HuggingFace 可直连；pip 用清华镜像源
- Shell 是 Windows PowerShell 7+

## 素材关键事实（已验证）

- `.LRF` 实为 MP4 容器（H.264 960×720@25fps），可被 ffmpeg 直接读取；但 **LRF 960×720 分辨率不足以支撑 YOLO 球检测（球仅 3-5px，已实测验证）**，v4 检测全程用原片 1920×1440 降采样；LRF 仅用于全段概览接触表（快速预览找漏检）
- 原片统一 HEVC 3840×2880（4:3）+ AAC 48kHz，但**帧率 50/100fps、位深 8/10-bit 混存**——处理每个文件前必须 ffprobe 确认，不要假设一致
- 文件名即拍摄时间：`DJI_YYYYMMDDHHMMSS_序号_D.MP4`，序号有跳号（0001–0136 中缺 0072–0083 等）
- 大疆文件还带 data 流（遥测）和 MJPEG 缩略图流，转码时用 `-map 0:v:0 -map 0:a:0` 显式选流，避免混入
- MP4 与 LRF 通常同名配对，但因素材增删需每次重新配对，不要假设一一对应

## 已和用户确认的剪辑规格（勿再询问）

- 进球锚点 = 球入网瞬间；片段窗口 = 前 4 秒 + 后 2 秒
- 输出 1080p（1440×1080，保持 4:3）、50fps、H.264 + AAC
- 100fps 素材：入网前常速（降 50fps），入网后 2 秒做半速慢放（100→50fps），两段拼接
- 编码器：先探测 GPU（`ffmpeg -hwaccels` / nvidia-smi），有 N 卡用 h264_nvenc，否则 x264
- 命名用标签不用真名：`红队-7号`、`黑T恤-A` 风格；花名册生成后需给用户确认
- 按**场次**组织：场次默认 = 文件名日期（YYYYMMDD），同一天多场按时间间隔拆分；用户可明确声明新场次（ID 用 `YYYYMMDD_对手名`），声明优先；roster 按场次隔离、各自需用户确认，跨场次不合并
- 成品分两类、按场次分目录：`output\<场次>\队伍_XX_进球集锦.mp4` 和 `output\<场次>\个人_XX_进球合集.mp4`，片段按拍摄时间排序，同参数 concat 直接重封装不重编码

## 工作流约定

- 中间产物放 `work\`（v4：frames / detect / track / candidates / review / clips / roster），成品放 `output\`
- 状态存 JSON：`goals.json`（进球时刻）、`roster.json`（进球→人物→队伍），便于断点续做
- **文档自审（强制）**：创建或修改 `docs/` 下 spec 文档、`AGENTS.md`、`tasks\*.md` 后，必须通过 Task 工具调用 `spec-reviewer` 子代理审查；有阻断问题须修订后再交付，禁止跳过
- 进球检测流程（v4，详见 `docs/superpowers/specs/2026-07-23-yolo-ball-trajectory-detection.md`，**试点中**）：原片全画面 5fps 降采样 → YOLO 篮球模型检测球（conf=0.04）→ 假阳性过滤（size/双模型交叉验证）→ 球轨迹聚类 → 入网点判定（静止点+conf 谷底+恢复）→ 候选+全段概览接触表 → 立哥人工确认（≤10 分钟/场）→ goals.json
- 不删除/不修改任何原始 MP4/LRF 文件
- v2/v3 旧方案已归档到 `archive\`（v2=LRF+目检/95%误报，v3=筐ROI+K3 AI/烧¥100+）；当前活跃方案为 v4（YOLO 球轨迹），设计文档在 `docs/superpowers/specs/`；原始整体规格归档在 `docs/SPEC_2026-07-19.md`
