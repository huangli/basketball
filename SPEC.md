# SPEC.md — 篮球视频进球剪辑规格

> 本文件是执行规格；通用约定见 `AGENTS.md`，两者冲突时以用户最新确认为准。
> 素材是流动的：每次会话先重新扫描目录，不硬编码文件清单。

## 1. 概述与目标

从 DJI 篮球录像中检测「球入网」瞬间（进球锚点），剪出片段后按**场次**（拍摄日期，定义见 §2）分别合成两类成品，每场次：

- 每个队伍一个集锦：`output\<场次>\队伍_XX_进球集锦.mp4`
- 每个人一个合集：`output\<场次>\个人_XX_进球合集.mp4`

流程：环境检测 → 进球检测 → 人物/队伍识别 → 片段剪辑 → 分组合成 → 验证。

## 2. 目录与文件约定

```
C:\2. Basketball Video\
├─ 0_raw_videos\         原始素材（*.MP4 / *.LRF，只读不删不改；素材流动，每次先重扫）
├─ work\
│  ├─ frames\           抽帧（LRF 粗扫、原片精抽、接触表）
│  ├─ clips\            单个进球片段（统一 1440×1080@50fps H.264+AAC）
│  └─ roster\           花名册
│     ├─ raw\           每个进球的投篮者原始帧
│     └─ <场次>\        该场次人物代表帧、拼图
├─ output\
│  └─ <场次>\           该场次的队伍集锦与个人合集
├─ goals.json           进球时刻状态
└─ roster.json          人物/队伍花名册（按场次隔离）
```

**场次定义**：场次 ID 有两种来源——

- **自动推导（默认）**：取文件名中的拍摄日期 `YYYYMMDD`；同一天录制多场时，按文件时间间隔 > 2 小时自动建议拆分，场次 ID 为 `YYYYMMDD-a`、`YYYYMMDD-b`。
- **用户声明（优先）**：用户明确指定新场次时，场次 ID 用 `YYYYMMDD_对手名`（如 `20260719_城东队`），声明覆盖自动推导；目录名字符避开 `\/:*?"<>|`。

首次处理积压素材时，先扫描给出检测到的场次清单（日期/时间段/文件数）交用户确认或改名。goals/roster/输出均按场次隔离，跨场次不合并。

### goals.json schema

以视频文件名（含扩展名的完整文件名）为每条的 `file` 主键，每条进球记录：

```json
{
  "version": 2,
  "goals": [
    {
      "file": "DJI_20260705193012_0042_D.MP4",
      "session": "20260705",
      "anchor_time": 187.43,
      "clip_start": 183.43,
      "clip_end": 189.43,
      "slowmo": true,
      "player_label": "红队-7号",
      "team_label": "红队",
      "status": "confirmed"
    }
  ]
}
```

- `anchor_time`：球入网瞬间，秒（相对文件开头，±0.1s 精度）
- `session`：场次 ID，默认由 `file` 文件名日期派生；同一天多场拆分时手工改（见 §9）
- `clip_start = max(0, anchor_time - 4)`，`clip_end = anchor_time + 2`；100fps 素材窗口相同，但入网后 2 秒素材半速慢放实际播放 4 秒，故慢放片段成片长 8 秒、常速片段长 6 秒
- `slowmo`：是否 100fps 素材需做入网后半速慢放
- `status`：`candidate` → `confirmed` → `clipped` → `done`；精抽二次确认未通过标 `rejected`（不进入后续阶段）；源文件缺失时标记 `removed`。所有终态记录均保留不删
- `player_label` / `team_label` 在用户确认花名册前为 `null`

### roster.json schema

```json
{
  "version": 2,
  "sessions": {
    "20260705": {
      "confirmed": false,
      "teams": ["红队", "黄队"],
      "players": [
        {
          "label": "红队-7号",
          "team": "红队",
          "rep_frame": "work\\roster\\20260705\\红队-7号.jpg",
          "appears_in": ["DJI_20260705193012_0042_D.MP4"]
        }
      ]
    }
  }
}
```

- `confirmed` 按场次独立：某场次必须为 `true`（用户确认）后才允许执行**该场次**的阶段 3 及以后。
- 不同场次允许同名标签对应不同人，互不合并；跨场次个人总合集需另行跨场次人脸归并，属可选扩展（见 §10）。

## 3. 阶段 0 环境检测

每次会话执行一次，结果写入会话变量 `$ENC`（下文统一以 `$ENC` 引用编码器）。

```powershell
ffmpeg -version        # 确认 8.x 在 PATH
ffmpeg -hwaccels       # 查看可用硬解
nvidia-smi             # 有输出且有 NVIDIA 卡 → 用 NVENC
```

决策逻辑：

- `nvidia-smi` 成功且列出物理 NVIDIA 卡（型号含 GeForce/RTX/Quadro/Tesla 等，非 vGPU/虚拟实例）→ `$ENC="h264_nvenc"`，质量参数 `-cq 20 -preset p5`
- 否则 → `$ENC="libx264"`，质量参数 `-crf 20 -preset medium`

逐文件探测（帧率/位深混存，禁止假设）：

```powershell
ffprobe -v error -select_streams v:0 `
  -show_entries stream=width,height,r_frame_rate,avg_frame_rate,pix_fmt,codec_name `
  -of json "DJI_xxx_D.MP4"
```

`avg_frame_rate` 为 `100/1` → 走慢放路径；`50/1` → 走常速路径。

## 4. 阶段 1 进球检测

原则：用 LRF 粗扫（960×720@25fps，快），用原片精定帧。全程 `-map 0:v:0` 显式选流。

### 4.1 LRF 2fps 抽帧

```powershell
New-Item -ItemType Directory -Force "work\frames\<basename>" | Out-Null
ffmpeg -hide_banner -loglevel error -y -i "<name>.LRF" -map 0:v:0 `
  -vf "fps=2,scale=480:360" -q:v 4 "work\frames\<basename>\f_%05d.jpg"
```

单帧产物供逐帧翻看、局部复看备用；常规判读直接用 §4.2 接触表，为省时间可跳过本节。（LRF 无对应文件时退回原片低分辨率抽帧，加 `-ss`/全段按需；§4.2 退回规则相同。）

### 4.2 5×4 tile 接触表

每 20 帧（10 秒）拼一张 5×4 接触表，文件名带起始帧号便于换算时间：

```powershell
ffmpeg -hide_banner -loglevel error -y -i "<name>.LRF" -map 0:v:0 `
  -vf "fps=2,scale=320:240,tile=5x4:padding=2:margin=2" -q:v 4 `
  "work\frames\<basename>\tile_%04d.jpg"
```

时间换算：`t ≈ (tile序号-1)*10 + 格内序号(0~19)*0.5` 秒。

### 4.3 人工/AI 看图锁候选

逐张看接触表，锁定「球接近篮筐并疑似穿网」的时间窗（±5 秒），写入 goals.json（status=`candidate`）。球在 960×720 下太小看不清时，对该窗口直接用原片缩样复看。

### 4.4 原片 10fps 精抽定帧（±0.1s）

对每个候选窗口（`win_start = max(0, 候选时间 - 5)`，`win_end = 候选时间 + 5`），原片抽 10fps 帧并拼接触表二次确认（防误判入网）：

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <win_start> -to <win_end> `
  -i "<name>.MP4" -map 0:v:0 `
  -vf "fps=10,scale=960:720,tile=5x4:padding=2:margin=2" -q:v 3 `
  "work\frames\<basename>\fine_<win_start>_%03d.jpg"
```

时间换算（每张 tile 为 5×4=20 帧、10fps，即每张覆盖 2 秒）：`t = win_start + (tile序号-1)*2 + 格内序号(0~19)*0.1` 秒。

逐帧确认球整体过网瞬间，记下帧号换算精确时间（精度 ±0.1s），更新 goals.json：`anchor_time`、`clip_start`、`clip_end`、`slowmo`（按该文件 avg_frame_rate 判定），status → `confirmed`；二次确认未通过（打铁/三不沾/被盖）则 status → `rejected`，不进入后续阶段。

## 5. 阶段 2 人物/队伍识别

### 5.1 抽投篮者帧

每个 `confirmed` 进球，取入网前 1~3 秒内 3 帧（投篮者最清晰）。`$a` 即该条 `anchor_time`；`<goal_id>` 为该进球的唯一标识，统一取 `<basename>_<anchor_time>`（与 §6 片段命名一致）。若 `$a-3 < 0`（进球发生在文件开头 3 秒内），按实际可用范围少取：

```powershell
foreach ($t in @($a-3, $a-2, $a-1)) {
  if ($t -lt 0) { continue }
  ffmpeg -hide_banner -loglevel error -y -ss $t -i "<file>" -map 0:v:0 `
    -frames:v 1 -q:v 3 "work\roster\raw\<goal_id>_$t.jpg"
}
```

### 5.2 归并与命名

- 分队：按服装颜色/款式（如红/黄队服、黑 T 恤便装）。
- 归并个人：以人脸为主、服装为辅；人脸模糊时以服装+体型+发型归并。
- 命名只用标签：`红队-7号`、`黑T恤-A` 风格，不用真名。
- 便装/无统一队服人员的 `team_label` 用其服装组名（如 `黑T恤`），队伍集锦同样按该 `team_label` 生成；归属存疑的在用户确认时定夺。
- 每个人存一张代表帧到 `work\roster\<场次>\<label>.jpg`，写入 roster.json 对应场次的 `players`（label/team/rep_frame/appears_in）。

### 5.3 花名册拼图 → 用户确认门禁

把该场次全部代表帧拼成一张总图供用户过目：

```powershell
ffmpeg -hide_banner -loglevel error -y -framerate 1 -pattern_type glob -i "work\roster\<场次>\*.jpg" `
  -vf "scale=320:240,tile=5x4:padding=4:margin=4" -frames:v 1 "work\roster\<场次>\roster_sheet.png"
```

（Windows 无 shell 通配展开，必须 `-pattern_type glob`；输出用 `.png` 避免重跑时被 glob 自匹配。人数超过 20（5×4 上限）时加大 tile 行列，如 6×5。）

**必须用户确认后**才把该场次的 `confirmed` 置 `true`，并回填 goals.json 中该场次记录的 `player_label`/`team_label`。未确认前该场次禁止进入阶段 3；其他已确认场次不受影响。

## 6. 阶段 3 片段剪辑

统一输出：1440×1080（4:3）、50fps、H.264（NVENC cq20 或 x264 CRF20）+ AAC 48kHz。片段命名：`work\clips\<basename>_<anchor>.mp4`。

### 6.1 50fps 素材（常速单段）

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <clip_start> -to <clip_end> -i "<file>" `
  -map 0:v:0 -map 0:a:0 `
  -vf "scale=1440:1080,fps=50" -c:v $ENC <质量参数> -pix_fmt yuv420p `
  -c:a aac -ar 48000 -b:a 160k -movflags +faststart "work\clips\<clip>.mp4"
```

### 6.2 100fps 素材（两段拼接：常速段 + 半速慢放段）

A 段（入网前 4s，常速，100→50 降采样）：

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <clip_start> -to <anchor> -i "<file>" `
  -map 0:v:0 -map 0:a:0 `
  -vf "scale=1440:1080,fps=50" -c:v $ENC <质量参数> -pix_fmt yuv420p `
  -c:a aac -ar 48000 -b:a 160k "work\clips\<clip>_A.mp4"
```

B 段（入网瞬间起 2s 素材，半速慢放：100fps 原样读出按 50fps 播放，实际播放 4s；用 `setpts=2.0*PTS` + `fps=50`，音频 `atempo=0.5`）：

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <anchor> -to <anchor+2> -i "<file>" `
  -map 0:v:0 -map 0:a:0 `
  -vf "scale=1440:1080,setpts=2.0*PTS,fps=50" -af "atempo=0.5" `
  -c:v $ENC <质量参数> -pix_fmt yuv420p `
  -c:a aac -ar 48000 -b:a 160k "work\clips\<clip>_B.mp4"
```

两段 concat（同参数直接重封装）：

```powershell
"file '<clip>_A.mp4'", "file '<clip>_B.mp4'" |
  Set-Content -Encoding ascii "work\clips\<clip>.txt"
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "work\clips\<clip>.txt" `
  -c copy -movflags +faststart "work\clips\<clip>.mp4"
```

（concat 列表条目一律用纯文件名：demuxer 的相对路径相对于列表文件所在目录解析，与运行时 cwd 无关，且避免 Windows 反斜杠被当作转义符。列表与片段同放 `work\clips\`。）

完成后 goals.json 该条 status → `clipped`。

## 7. 阶段 4 合成

1. 从 goals.json 取 `clipped` 和 `done` 状态的记录（排除 `candidate`/`rejected`/`removed`），先按 `session` 分场次，场次内再按 `team_label` / `player_label` 分组；并以 `work\clips\` 中片段文件实际存在为准，缺失片段跳过并告警。
2. 组内按拍摄时间排序——文件名 `DJI_YYYYMMDDHHMMSS_...` 即时间，直接按文件名字符串排序，同文件内按 `anchor_time` 排序。
3. 每组生成 concat 列表并用 demuxer 重封装（不重编码），条目用纯文件名（同 §6.2 的路径规则）：

```powershell
$list | ForEach-Object { "file '$_'" } |
  Set-Content -Encoding ascii "work\clips\concat_<场次>_<组名>.txt"
New-Item -ItemType Directory -Force "output\<场次>" | Out-Null
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "work\clips\concat_<场次>_<组名>.txt" `
  -c copy -movflags +faststart "output\<场次>\队伍_<组名>_进球集锦.mp4"
# 个人同理：output\<场次>\个人_<label>_进球合集.mp4
```

合成后相关记录 status → `done`。

## 8. 阶段 5 验证

每个成品：

```powershell
# 时长/帧数/参数校验：应为 1440x1080、50fps、h264+aac、48kHz
ffprobe -v error -show_entries stream=codec_name,width,height,avg_frame_rate,sample_rate `
  -show_entries format=duration -of json "output\<场次>\<成品>.mp4"
```

- 时长应 ≈ 片段数 × 6 秒（其中每个慢放片段按 8 秒计）。
- 抽首/中/尾 3 帧拼图目检（帧文件顺序命名，保证 image2 序列连续可读）：

```powershell
$dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 "output\<场次>\<f>.mp4")
$ts = @(1, [int]($dur/2), [int]($dur-2))
for ($i = 0; $i -lt 3; $i++) {
  ffmpeg -hide_banner -loglevel error -y -ss $ts[$i] -i "output\<场次>\<f>.mp4" -map 0:v:0 `
    -frames:v 1 "work\frames\chk_$($i+1).jpg"
}
ffmpeg -hide_banner -loglevel error -y -i "work\frames\chk_%d.jpg" -vf "tile=3x1" -frames:v 1 "work\frames\chk_sheet.jpg"
```

## 9. 增量处理规则

- 每次会话先递归重新扫描（MP4 与 LRF 都扫），与 goals.json 主键比对：

```powershell
Get-ChildItem "0_raw_videos" -Recurse -File -Include *.MP4,*.LRF
```

- **新文件**：只跑未处理文件的 阶段 1–3，不重做已有记录。按文件名日期归入场次，出现新日期即产生新场次；若用户已声明该批文件所属场次（`YYYYMMDD_对手名`），以声明为准。
- **缺失文件**：对应 goals.json 记录 status 改 `removed`，记录保留不删；对应片段若已存在于 `work\clips` 且属受影响分组，从 concat 列表剔除。若某组（场次+队伍/个人）全部进球均为 `removed`，删除该组已生成的 output 成品（场次目录空了则一并删除）。
- **受影响分组**：只要组内任一进球增删，该组（场次+队伍/个人成品）整组重新执行阶段 4 合成（阶段 4 取 `clipped`+`done` 记录，旧片段不会丢失）。不同场次互不影响。
- **新场次**：roster 按场次独立，新场次必须完整执行阶段 2 并经用户确认（该场次 `confirmed` 置 `true`）后才进入阶段 3；其余场次不受影响。
- **同场次新球员/新队伍**：若该场次新进球涉及 roster 中不存在的球员或队伍，对新增部分重新执行阶段 2 归并与拼图，新增 label 经用户确认后才回填并进入阶段 3（该场次 `confirmed` 维持 `true`，既有 label 无需重确认）。
- **同一天多场**：扫描后若文件时间间隔 > 2 小时，提示拆分为 `YYYYMMDD-a`/`YYYYMMDD-b` 场次（或用户手工指定），相应记录改 `session` 字段。
- **场次改名/归并**：用户可随时把自动推导的场次改名（如 `20260719` → `20260719_城东队`）或调整文件归属；相应更新 goals.json 的 `session`、roster.json 的场次 key，并重命名 `output\`/`work\roster\` 下对应该场次的目录后按 §9 重合成受影响分组。
- MP4/LRF 配对每次重新按同名匹配，容忍单边缺失（LRF 缺失时用原片低清抽帧代替粗扫）。

## 10. 方案决策记录（2026-07-19，用户已拍板）

进球检测方式三选一，对比后**选定方案 A（agent 目检接触表），不压缩 token 成本**：

| 方案 | 成本 | 效果 | 结论 |
|---|---|---|---|
| A. Agent 看图（ffmpeg 抽帧 + 逐张目检） | 零开发；约 90-110 万 tokens/全量 | 语义判断最强，能区分入网/打铁/被盖，顺带完成阶段 2 识人 | ✅ 采用 |
| B. OpenCV 传统算法（霍夫圆+轨迹规则） | 开发调参 2-4h 起 | 全景球场球仅 10-20px 且有拖影，误报率高，基本不可行 | ❌ 否决 |
| C. 训练/微调检测模型（YOLO 类） | 标注数百帧 + 无 GPU 只能 CPU 训练，成本为 A 的 10 倍+ | 微调后可用，长期大批量才划算 | 暂不采用 |

Token 估算（不压缩，按 320×240 单元、2fps 全量执行）：粗扫 60-70 万 + 精抽 15-25 万 + 花名册 8-15 万 + 验证 <5 万 ≈ **90-110 万**。

迁移路径：方案 A 产出的 `goals.json`（进球精确时刻）即高质量标注数据；未来素材量若持续大增，可据此微调检测模型迁移到方案 C。曾讨论运动预筛/降采样省 token，用户明确**不需要**。

场次组织（2026-07-19，用户拍板）：输出按场次（拍摄日期）隔离，不同场次的同名标签不合并；跨场次个人总合集需另行跨场次人脸归并，列为可选扩展，现阶段不做。

## 11. 风险与对策

| 风险 | 对策 |
|---|---|
| LRF 中球太小看不清 | 对该窗口用原片缩样（scale=1920:1440 或更高）复看 |
| 人脸模糊无法归并 | 以服装颜色/款式为主，体型发型为辅；仍不确定则用 `<队>-待定X` 标签，留给用户确认时定夺 |
| 误判入网（打铁/三不沾/被盖） | 阶段 1.4 原片 10fps 精抽必须二次确认球整体过网才置 `confirmed` |
| 50/100fps、8/10-bit 混存 | 每个文件先 ffprobe，按 `avg_frame_rate` 选 6.1/6.2 路径，输出统一 `yuv420p` |
| DJI 附带 data/MJPEG 流混入 | 所有转码命令显式 `-map 0:v:0 -map 0:a:0` |
| NVENC 不可用/报错 | 回退 `libx264 -crf 20`，其余参数不变 |
| 素材增删导致状态漂移 | goals.json/roster.json 以文件名为主键，缺失标 `removed`，见第 9 节 |
