# 设计文档：YOLO 球轨迹检测 + 接触表复核（v4 检测阶段）

> 日期：2026-07-23　状态：草案（待 spec-reviewer 审查）
> 范围：**重建进球检测阶段（阶段 1）**，替代 v2/v3/像素法全部失败方案。阶段 2~5（花名册/剪辑/合成/验证）主体沿用 SPEC。
> 试点：0006/0007/0008 三文件（立哥已确认 ground truth：0006@6s、0007@31s、0008@35s），试点达标后再推全量。
> 核心范式转变：**全画面低 conf 球检测 + 轨迹聚类 + 静止点/conf 谷底判定**，废弃筐心标定 + crop。

## 1. 背景与诊断

### 1.1 历史方案失败教训

| 方案 | 失败原因 | 花费 | 教训 |
|---|---|---|---|
| v2（LRF 粗扫 + AI 目检） | LRF 960×720 球仅 3–5px，误报率 95% | token 中 | 分辨率不够 |
| v3（筐 ROI crop + K3 AI） | 烧钱 + 筐标定不准 + ground truth 错 | **¥100+** | AI 每帧过云端 + 筐标定不可靠 |
| 像素法（色度+运动量） | 召回率 33%（3 文件仅命中 1） | ¥0 | 球占比 <1%，信号被淹没 |
| YOLO + COCO（yolov8n） | sports ball 类不认篮球，0 个球检测 | ¥0 | COCO 训练数据是棒球/网球 |

### 1.2 YOLO + 篮球模型验证（2026-07-23，本次）

HuggingFace `Lumos-88/YOLO11-fine-tuned-for-basketball-detection`（best.pt，5.29MB，COCO 80 类微调）全画面检测结果：

| 文件 | 真实进球 | 全画面最高 conf | 球轨迹 | 结果 |
|---|---|---|---|---|
| 0007@31s | 立哥确认 | **0.91** | 高处(184)→下降(429)→静止(462) | ✅ 清晰 |
| 0008@35s | 立哥确认 | **0.81** | 检测到 @(2016,1352) | ✅ 成功 |
| 0006@6s | 立哥确认 | 0.19（表面）→ 真球 0.05（被网遮挡） | 静止点 (940,798) | ⚠️ 入网遮挡 |

### 1.3 0006 调查结论（subagent 深度报告，见 `work/investigate_0006/REPORT.md`）

根因（三个叠加，非模型能力问题）：
1. **筐心标定严重错误（主因）**：立哥标 (1440,1050)，真实入网点 **(940,798)**，水平差 **500px**。筐 crop(x0=1040) 把真球(x=940)挡在左边界外。
2. **入网瞬间球被网遮挡**：6.0s 入网帧真球 conf 跌到 **0.05**（被网完全遮挡），全画面被假阳性压到次位。
3. **拥挤场景假阳性淹没**：20–40 人画面，模型每帧吐 3–4 个假"球"（如 size 59×62 的橙色衣物 conf=0.92），真球(27px)被淹没。

**系统性风险（关键）**：入网遮挡是篮球进球的**固有特性**。"单帧高 conf"策略会系统性漏掉遮挡型进球。0007/0008 成功属于**运气好**（它们的静止球未被遮挡，conf 保持 0.8+）。**不能据 0007/0008 的成功推断方法鲁棒。**

### 1.4 已验证的事实

- 原片 3840×2880 缩到 1920×1440 后，近筐球 30–50px、远筐球 15–25px，篮球模型可检测（conf 0.4–0.91）；
- imgsz=1280 是较优（640 太小漏小球，1920 不提升被遮挡球的 conf）；
- crop 破坏全局上下文，效果**不如全画面**（0006 真筐 crop 反而更差）；
- 篮球模型在 COCO sports ball(id=32) 上微调，输出 sports ball 类；同时保留全部 80 类（可交叉验证 person 等）；
- CPU 推理（AMD Ryzen AI 9 HX 370）单帧 1920×1440 @ imgsz1280 约 2–3 秒。

## 2. 决策（本次拍板）

**全画面 YOLO 球检测 + 轨迹聚类 + 静止点/conf 谷底判定 + 接触表复核**：

1. 全画面降采样 5fps → 篮球模型检测球（**conf=0.04** 低阈值捕获遮挡期弱信号）；
2. 假阳性过滤（轨迹连续性 + size/双模型交叉验证）；
3. 球轨迹聚类（最近邻关联，连续帧位移 < 物理上限）；
4. 入网点判定（**静止点 + conf 谷底 + 恢复**三特征，§3.4）；
5. 候选时刻 ±3s 抽原片帧拼接触表 → **立哥人工确认**（每场约 10 分钟）；
6. 确认进球写入 goals.json（status=confirmed）。

**不采用**：
- ❌ 筐心标定 + crop（已证明标定不可靠，偏 500px；crop 破坏全局上下文）；
- ❌ 单帧高 conf 判定（系统性漏遮挡型进球）；
- ❌ 云端 VLM 精判（虽然 qwen3-vl-flash 全量 <¥10，但本次先走纯本地方案，VLM 留作 uncertain 兜底的可选扩展）；
- ❌ 音频优先（已证伪，空心入网无人欢呼时音频反而最安静）。

**用户核心约束（优先级）**：不花钱/少花钱 > 时间长可接受 > 每场立哥 ≤10 分钟 > 可靠性（召回优先，假阳性靠接触表剔除）。

## 3. 组件设计

> **通用约定**：所有脚本第一步 `New-Item -ItemType Directory -Force "<输出目录>" | Out-Null` 确保目录存在（ffmpeg 不自动建目录）。**v4 全程基于原片 MP4 降采样检测**——LRF 960×720 分辨率不足以支撑 YOLO 球检测（见 §1.1），不再使用 LRF。抽帧/检测阶段只取视频流（`-map 0:v:0`，无音频需求）；音频在阶段 3 剪辑时按 SPEC §6 选流。

### 3.1 全画面球检测（build_ball_detect.py）

- **输入**：MP4 文件路径；
- **抽帧**：ffmpeg 全画面降采样到 5fps + scale=1920:1440（4K→1/2，球 30–50px 可辨），JPEG q=4；
  ```powershell
  New-Item -ItemType Directory -Force "work\frames\<base>" | Out-Null
  ffmpeg -hide_banner -loglevel error -y -i "<file>.MP4" -map 0:v:0 `
    -vf "fps=5,scale=1920:1440" -q:v 4 "work\frames\<base>\f_%05d.jpg"
  ```
  时间换算：`t = (帧序号-1) / 5`；
- **检测**：YOLO 篮球模型（`basketball_yolo11.pt`），`conf=0.04, imgsz=1280, classes=[32]`（只取 sports ball）；
- **输出**：`work/detect/<base>.jsonl`，每行一条检测：`{"t":12.4,"conf":0.78,"cx":968,"cy":184,"w":38,"h":42}`（cx/cy 为 1920×1440 图中心坐标，w/h 为检测框宽高）；
- **幂等**：输出 jsonl 存在且帧数匹配则 skip；
- **性能**：40s 文件 = 200 帧 × 2.5s ≈ 8 分钟（CPU）；115 文件全量 ≈ 15 小时（全自动，立哥无需值守）；
- **坐标换算**：原片坐标 = img 坐标 × 2（用于后续抽帧/剪辑）。

### 3.2 假阳性过滤（build_ball_filter.py）

> §3.1 对每帧**同时跑两个模型**：basketball_yolo11.pt（classes=[32] 球）+ yolov8n.pt（classes=[0] person），分别产出球检测 jsonl 和 person 框 jsonl（**全画面一次性，不逐候选跑**，否则成本爆炸）。本节读取两份 jsonl 做交叉过滤：

- **size 上限交叉验证**：`max(w,h) > 55` 的球检测，与同帧 person 框做 IoU 匹配，IoU > 0.3 且 person conf > 0.5 → 判为衣物/标志假阳性，丢弃；
- **size 下限**：`max(w,h) < 8` 的检测丢弃（噪声）；
- **低 conf 保留**：**不按 conf 绝对值过滤**（入网遮挡期 conf 可低至 0.05），conf 过滤交给 §3.3 轨迹连续性处理；
- **输出**：`work/detect/<base>_filtered.jsonl`（保留的球检测，含 cross_val 标记）。

### 3.3 球轨迹聚类（build_ball_track.py）

将过滤后的逐帧检测关联成轨迹（多目标跟踪简化版）：

- **关联规则**：相邻帧（Δt=0.2s）两检测中心位移 < **120px** 则视为同一球（此阈值适用于**静止段附近**的帧间关联，入网减速段实测 <120px；**飞行段球速可达 1200+px/s 会断轨，但断轨不影响静止点判定**——静止段独立判定，不依赖飞行段连续。试点前置用 0007 飞行段数据标定真实速度，必要时改用速度预测关联：线性外推 + 余量）；
- **最小轨迹长度**：连续 ≥ **4 帧**（0.8s）才算有效轨迹，丢弃孤立短检测（滤除突现突灭的假阳性）；
- **断线重连**：允许中间缺失 1 帧（被瞬时遮挡），用前后帧位置线性插值；
- **输出**：`work/track/<base>.json`，每条轨迹：`{"track_id":1,"points":[{"t":5.8,"cx":881,"cy":796,"conf":0.17},...]}`。

### 3.4 入网点判定（build_goal_candidates.py）⭐ 核心

对每条轨迹分析，找"入网点"（进球锚点候选）。判据分两层：

**必要条件 = 静止点**（必须满足）：
- 轨迹中存在连续 ≥ 4 帧（0.8s）位置静止段，**各点到段几何中心位移 < 40px**（img 系，≈一个球径；用 0006 标杆标定：6.0s(929)↔6.4s(961)=32px 在网中晃动属物理常态，30px 会误杀此标杆）；段的几何中心 = 候选 ball_position（**img 系坐标，§3.6 落盘时 ×2 转原片系**）；

**充分条件 = conf 谷底 + 恢复**（区分 occlusion 标记，不满足走兜底）：
1. **conf 谷底**：静止段内 conf 出现明显谷底（段内最低 conf < **谷底帧两侧非谷底帧** conf 均值 × 0.5；"两侧"= 谷底帧的前一帧与后一帧，避免把谷底自身算进分母），对应"入网瞬间被网遮挡"；
2. **恢复**：谷底后 conf 回升（谷底后 2 帧内出现 conf > 谷底 × 2），对应"球从网中露出"；
- 满足充分条件 → `occlusion=true`（如 0006@6s，conf 谷底 0.05→恢复 0.79）；
- **不满足但有静止点 → `occlusion=false` 兜底**（如 0007 球未被遮挡，conf 持续高位 0.8+），仍判为候选交接触表确认。

**空心入网快速穿网兜底**（静止段 < 4 帧时）：球空心穿网在网中停留可能 <0.8s（4帧@5fps），主判据会漏。增设兜底——轨迹末端位移单调减小（连续 ≥3 帧位移递减，末帧位移 <60px）**且**出现 conf 谷底（< 前帧 conf×0.5），即使无 ≥4 帧静止段也判为候选（`occlusion=true, note=fast_swindle`）。**此兜底需试点验证后启用**（§5 验收 7：空心球占比 >20% 时为必须项）。

**入网点 anchor_time** = 静止段起始时刻（球刚到达停留点的瞬间）。

**trajectory_conf 计算口径** = 该轨迹所有点 conf 的**算术均值**（反映整条轨迹的检测置信度，用于接触表排序/候选优先级）。

**输出**：`work/candidates/<base>.json`（坐标为 **img 系**，1920×1440）：
```json
[{"anchor_time":6.0,"ball_position":[940,798],"rest_duration":1.2,
  "conf_min":0.05,"conf_recover":0.79,"occlusion":true,"trajectory_conf":0.55}]
```


**去重**：同文件 anchor_time 两两差 < 2s 的候选合并（取 conf 更高者）。

### 3.5 接触表生成 + 立哥确认（build_review_sheet.py + 人工）

- 对每个候选，抽 `anchor_time ± 3s` 的原片帧（10fps，scale=960:720），拼 **5×4 接触表**（每张覆盖 2s，共 3 张覆盖 6s 窗口）；**窗口左端 clamp 到 0**（anchor<3s 时窗口短于 6s，右端不变）；
  ```powershell
  New-Item -ItemType Directory -Force "work\review" | Out-Null
  ffmpeg -hide_banner -loglevel error -y -ss <max(0,anchor-3)> -to <anchor+3> -i "<file>.MP4" -map 0:v:0 `
    -vf "fps=10,scale=960:720,tile=5x4:padding=2:margin=2" -q:v 3 `
    "work\review\<base>_<anchor>_%03d.jpg"
  ```
- 文件名带 anchor_time 便于定位；
- **立哥看接触表**：每张 3–5 秒扫一眼，判断"进球/未进/不确定"，回报时间戳列表；
- **工作量**：假设每场 150 进球 + 50–100 假阳性 = 200–250 候选 × 3 秒 ≈ **10–12 分钟/场**（达标）。

**全段概览接触表（召回兜底，必做）**：对每个文件额外生成**低清全段 tile**（原片 2fps，scale=480:360，tile=5×4，每张覆盖 10s），让立哥通览整段找漏检——这是召回率的兜底测量手段（上述候选窗口接触表只覆盖候选 anchor±3s，**YOLO/聚类漏掉的进球不会出候选表，立哥无法发现漏检**）：
  ```powershell
  ffmpeg -hide_banner -loglevel error -y -i "<file>.MP4" -map 0:v:0 `
    -vf "fps=2,scale=480:360,tile=5x4:padding=2:margin=2" -q:v 4 `
    "work\review\<base>_overview_%04d.jpg"
  ```
立哥先扫概览表标记疑似进球时刻，再对照候选表确认是否被检出；概览表上发现但候选表没有的 = **漏检**，记入试点报告（§5 验收 4）。

### 3.6 立哥回报 → goals.json 落盘（goals_confirm.py）

- 立哥回报格式：`<base> <anchor> <confirmed|rejected|uncertain>`；
- 主控串行调用 goals_confirm.py 更新 goals.json；
- confirmed：填 anchor_time/clip_start=max(0,anchor-4)/clip_end=anchor+2/slowmo（按 inventory avg_frame_rate：50/1→false，100/1→true）/ball_position/status=confirmed；
- rejected：status=rejected + note；
- uncertain：保留 status=uncertain，进入 §3.7 兜底。

### 3.7 uncertain 兜底（可选扩展，本期不实现）

uncertain 候选可后续接入 qwen3-vl-flash 云端精判（全量 <¥10），或立哥看原片 4K 单帧定夺。**本期 uncertain 一律交立哥看接触表二次确认或放弃**，不接 VLM。

### 3.8 goals.json schema（v4）

`version: 4`。每条记录：
```json
{
  "file": "DJI_xxx_D.MP4",
  "session": "20250419",
  "anchor_time": 6.0,
  "clip_start": 2.0,
  "clip_end": 8.0,
  "slowmo": false,
  "ball_position": [1880, 1596],
  "trajectory_conf": 0.55,
  "player_label": null,
  "team_label": null,
  "status": "confirmed",
  "source": "yolo_trajectory",
  "note": null
}
```

status 流转：`candidate → confirmed | rejected | uncertain → (uncertain 经二次确认) → confirmed | rejected`；confirmed 经剪辑 `clipped → done`。

**与 v3 的差异**：移除 `hoop_id`（不标筐）；新增 `ball_position`（**入网点原片坐标** = img×2，由 §3.6 落盘换算）、`trajectory_conf`（轨迹所有点 conf 算术均值，见 §3.4）、`source`（固定 `yolo_trajectory`）；`result/points/assist_label` 留到阶段 2 标注（本期不做技术统计）。`removed` 状态沿用 SPEC §9（源文件缺失），本设计不重复定义。

## 4. 数据流

```
0_raw_videos\<file>.MP4
    ↓ ffmpeg 5fps scale=1920:1440
work\frames\<base>\f_00001.jpg  （抽帧，幂等 skip）
    ↓ YOLO basketball_yolo11.pt conf=0.04 classes=[32]
work\detect\<base>.jsonl        （逐帧球检测）
    ↓ size/双模型过滤
work\detect\<base>_filtered.jsonl
    ↓ 最近邻关联 ≥4帧
work\track\<base>.json          （球轨迹）
    ↓ 静止点+conf谷底+恢复 三特征
work\candidates\<base>.json     （入网点候选）
    ↓ ffmpeg 10fps 接触表
work\review\<base>_<anchor>_%03d.jpg
    ↓ 立哥人工确认（每场 ~10 分钟）
goals.json                      （confirmed/rejected/uncertain）
    ↓ 阶段 2~5（花名册/剪辑/合成/验证，沿用 SPEC）
output\<场次>\
```

## 5. 试点验收标准

> **精度口径说明**：本节 anchor_time 容差（±0.4–0.5s）是**检测阶段候选 anchor 的中间精度**；最终 anchor_time 经 §3.5 接触表人工精定帧到 **±0.1s** 后落盘（符合 SPEC §2）。

**试点前置**：立哥对 0006/0007/0008 给出**全部进球 ground truth 清单**（不止 1 个/文件；含每个进球精确时刻 + 是否空心球）。同时对 0007/0008 跑 conf=0.04 全画面精细抽帧，记录其 conf 曲线是否真无谷底（验证 occlusion=false 兜底合理性）。

1. **0006@6s**：检测到入网点 (940,798) img 系 / (1880,1596) 原片，anchor_time ∈ [5.6, 6.4]；轨迹呈现静止点+conf 谷底(≤0.1)+恢复(≥0.4)；
2. **0007@31s**：检测到入网点，anchor_time ∈ [30.5, 31.5]；轨迹有静止点（conf 持续高位，occlusion=false 也算）；
3. **0008@35s**：检测到入网点，anchor_time ∈ [34.5, 35.5]；
4. **召回率**（通过 §3.5 全段概览接触表测量）：**未遮挡进球召回 100%**（漏检任一即不通过）；**遮挡/远筐小球类记录漏检率**并在试点报告量化（不作为否决门槛——§6 已承认此类会漏）；概览表上发现但候选表没有的 = 漏检；
5. **假阳性可控**：三文件总候选数 ≤ 15（真进球 + 假阳性 ≤ 12），立哥看接触表 ≤ 5 分钟完成三文件确认；
6. **uncertain 率 < 20%**；**occlusion=false 候选数 / 总候选数** 记入试点报告（评估兜底分支假阳性占比）；**注意：三文件样本太少，occlusion=false 的 precision 估不准**（需覆盖"非进球静止球"反例：训练球放地上/死球/被人抱着），全量铺开后再下 precision 结论；
7. **空心入网**：试点报告标注 3 文件中是否有空心球及其轨迹特征（静止段是否 <4 帧）；**若空心球占比 >20%，§3.4 快速穿网兜底为必须项**（必须实现并测过，否则不推全量）；同时评估 5fps 采样是否够（采样定理：快速穿网可能采不到"球在网中"帧，必要时候选窗口局部加密 fps）；
8. **性能**：单文件检测+跟踪+判定全程 ≤ 12 分钟（40s 文件；按平均 40s 估算，实际视文件总时长，jsonl 幂等可断点续跑）。

试点不达标则回到 §6 风险对策调整，不推全量。

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| **入网遮挡导致 conf 谷底漏检** | §3.1 conf=0.04 低阈值；§3.4 谷底是判据而非过滤项；§3.3 断线重连容忍 1 帧缺失 |
| 假阳性淹没真球 | §3.2 size/双模型过滤；§3.3 轨迹连续性 ≥4 帧；§3.4 静止点判据（假阳性不会持续静止） |
| 球太小（远筐 15px） | imgsz=1280；远筐球若仍漏，接受漏检（接触表无法覆盖所有情况），靠召回抽查量化 |
| 多球同框（训练球+比赛球） | 轨迹聚类自然分离；接触表上立哥可辨 |
| 筐标定难题（已三次翻车） | **彻底废弃标定**，全画面检测不依赖筐位置；ball_position 由轨迹自动定位 |
| CPU 慢（15 小时全量） | 用户已确认"时间长不要紧"；可后台跑，断点续做（jsonl 幂等） |
| 立哥看接触表超 10 分钟 | 候选数失控时升级 §3.2 过滤（提高轨迹长度门槛到 6 帧）；或接入 VLM 精判（§3.7） |
| 模型泛化（球场不固定） | 篮球模型在多场景微调（Lumos-88）；球场不固定无影响（检测球不检测筐）；试点覆盖 0006/0007/0008 三种机位验证 |
| 球被球员完全遮挡（非网遮挡） | 接受漏检；§3.3 断线重连只容忍 1 帧；接触表上立哥可补 |
| **occlusion=false 兜底导致假阳性占比过高** | 试点报告分开统计 occlusion=true/false 两分支的 precision；若 false 分支 precision<50% 则收紧为"静止点+轨迹长度≥6 帧"或仅保留 occlusion=true（见 §5 验收 6）|
| **空心入网快速落地（静止段<4 帧）** | 试点中观察此类进球占比（§5 验收 7）；§3.4 已增设"位移单调减小+conf 谷底"快速穿网兜底；若占比 >20% 则为必须项 |
| **5fps 采样定理：快速穿网采不到"球在网中"帧** | 候选窗口内局部加密 fps（如对该窗 15fps 重抽）；§3.4 快速穿网兜底用"位移单调减小"替代"静止段"；试点量化此类进球占比 |

## 7. 不做的事（YAGNI）

- 不标筐（hoops.json 废弃，不读不写）；
- 不做筐区域 crop（已证明破坏全局上下文）；
- 不做音频检测（已证伪）；
- 不做像素色度/运动量法（已证召回率 33%）；
- 不接云端 VLM 精判（uncertain 兜底留作可选扩展，本期不实现）；
- 不做技术统计（result/points/assist_label 留到阶段 2，不在本期检测阶段）；
- 不训练/微调新模型（先用现成 Lumos-88，试点不达标再议）；
- 不装 onnxruntime-directml GPU 加速（CPU 够用，15 小时可接受；GPU 留作优化）；
- v3 旧产物（goals.json v3、hoops.json、work/frames/_calib、build_roi_*.py 等）归档不删除，新流程不依赖。

## 8. 与 SPEC.md 的关系（上线同步清单）

- 本设计**替代 SPEC §4 阶段 1（进球检测）全部内容**（§4.1 LRF 抽帧 / §4.2 接触表 / §4.3 锁候选 / §4.4 精抽定帧）；
- **SPEC §2 schema**：goals.json 升级为 v4（§3.8）；示例补顶层 `{"version":4,"goals":[...]}` 结构；version 号从当前 2 更新到 4；
- **SPEC §2 目录约定补充**：新增 `work\detect\`、`work\track\`、`work\candidates\`、`work\review\` 子目录；`work\frames\` 语义从 v3 的"LRF 480×360"改为 v4 的"原片 1920×1440"（与归档的 `archive/v3/work/frames/` 区分）；
- SPEC §5~§9（花名册/剪辑/合成/验证/增量）沿用不变；
- SPEC §10 决策记录追加 v4；
- **AGENTS.md 同步**（整段替换，非一行）：① 检测流程从"LRF 2fps→接触表→人工→原片精抽"改为"全画面 YOLO 球检测→轨迹聚类→静止点判定→接触表复核"；② 环境段更新"已装 ultralytics 8.4.104 + torch 2.13.0 + opencv 5.0.0"；③ LRF 那句"用它抽帧扫描进球比读原片快得多"改为"v4 全程用原片，LRF 分辨率不足以支撑 YOLO 球检测"；
- 试点达标后执行上述同步，并经 spec-reviewer 审查。
