# 设计文档：篮筐 ROI 检测 + 技术统计（v3 检测阶段重建）

> 日期：2026-07-20　状态：用户已批准设计；v3.1 已按 spec-reviewer 审查修订（B1/M1~M8 全部修复）
> 范围：重建 SPEC 阶段 1（进球检测 → **出手检测**），并新增技术统计产出：得分、助攻、命中率、出手次数。阶段 2~5（花名册/剪辑/合成/验证）主体沿用。
> **不做**：抢断、正负值（用户已排除）。
> 试点：文件名序前 50 个 MP4（含 ground truth 文件 0005~0010），试点达标后再推全量。

## 1. 背景与诊断

v2 方案（LRF 2fps 全画面 tile 粗扫 → 原片 10fps 960×720 精抽 → 高清复看）实测失败：

- 306 候选中试点 20 个仅 1 个真进球（用户终审确认），误报率 ~95%；
- 精抽级 55% 候选「过网不可辨」，高清复看后子代理仍产生幻觉误报（用户否决 2/3 confirmed）；
- 根因是**分辨率**：原片 3840×2880 缩到 960×720 后球仅 3~5px；结构（两级扫描）本身无问题。

已验证的事实（2026-07-20 实测）：

- 原片篮筐 crop（1500×1500）下球 60~80px、网清晰，过网瞬间一眼可判（work/roi_test/crop_sheet.jpg）；
- 远端筐在原片 900~1200 crop 下球 15~25px，配合 10fps 连续帧轨迹可判；个别遮挡仍不可判的交用户，不允许 AI 硬猜；
- 场馆为多片场地球馆，画面内可见多个篮架，必须按文件逐筐标定；机位跨文件会变，文件内假定不动（需抽验）。

## 2. 决策（用户拍板）

方案一（双层级 crop 扫描）+ 方案三音频佐证，统计范围 = 得分/助攻/命中率/出手次数：

1. 每文件标定 1~2 个篮筐 → `work/hoops.json`；
2. 原片 crop 2fps 粗扫全段 → **出手候选窗口**（candidate）；
3. 窗口原片 crop 10fps 精判，一次定音：**confirmed（投进）/ attempt（出手未中）/ rejected（非出手）/ uncertain**；
4. **uncertain 门禁**：全部 uncertain 经用户定夺改判（或用户确认放弃）后才进入投篮者帧/花名册；
5. 所有 confirmed+attempt 抽投篮者全画帧（供认人、判 2/3 分、判助攻）；
6. 花名册归并（沿用阶段 2，覆盖全部出手者 + 投篮者帧中可辨识的传球者）→ 用户门禁 G1；
7. 标注：每条记录填 `points`（1/2/3），每条 confirmed 填 `assist_label`；
8. 音频峰值兜底进球召回：峰值 ±5s 无记录 → 补精判；
9. 统计产出：`output\<场次>\技术统计.csv`（个人+队伍）；
10. 旧 306 候选归档 `work/goals_v2_archive.json`，goals.json 重建为 v3（v2 字段全保留 + 扩展，见 §3.6）。

不采用：运动门控（方案二，试点实测成本后再议）；纯音频优先（召回不可控）。

## 3. 组件设计

### 3.1 篮筐标定（build_hoop_calib.py + AI 目检）

- 每文件取 50% 时长处 1 帧，**scale=480:360**，拼 4×3 sheet（cell 480×360 → 约 1930×1100，满足 ≤2000px 红线）；**输入帧序列须补齐到 12 的倍数**（tpad 克隆末帧或每 12 帧单独一次 ffmpeg 调用），因为 tile 滤镜丢弃不足一格的尾部——不补齐则尾部文件静默丢失（v3.1 修复 B1）。50 文件 → 5 张 sheet，50 格全部可溯源到文件；
- 生成 sheet 时落 `work/frames/_calib/meta.json`：cell 尺寸、**坐标倍率（×8）**、格序→文件名映射；verify 与后续换算一律读 meta，不靠口头传递（v3.1 修复 M3）；
- AI 逐格标注筐心坐标（480×360 图内坐标）与 near/far → `work/hoops.json`（存**原片坐标** = 图内坐标 ×8）：
  ```json
  { "DJI_xxx_D.MP4": { "hoops": [ {"id":"near","x":1380,"y":470,"crop":1500}, {"id":"far","x":2770,"y":1385,"crop":900} ] } }
  ```
  crop 边长：near=1500，far=900（可按实际远近距离由 AI 标定时微调 ±200）；
- 粗扫阶段确认邻场筐（无本队活动）时，写回该 hoop `"dropped": true` + reason，后续任务一律跳过（v3.1 修复 m6）；
- crop 原点计算时 clamp：`x0=min(max(0, cx-S/2), 3840-S)`，y 同理（2880-S）；
- 抽验：按 25% 时长处再抽 1 帧，用标定 crop 拼 check sheet（同样补齐 12 倍数）；判据 = **筐心在 crop 内且距任一边 ≥10%S**（clamp 贴边的筐天然偏心，不按居中判，v3.1 修复 m8）；不符的文件重新标定。

### 3.2 crop 粗扫（build_roi_scan.py + AI 目检）

- 命令原型（每文件每 hoop）：
  ```powershell
  ffmpeg -hide_banner -loglevel error -y -i "<file>.MP4" -map 0:v:0 `
    -vf "crop=<S>:<S>:<x0>:<y0>,fps=2,scale=480:480,tile=4x3:padding=2:margin=2" -q:v 4 `
    "work\frames\<base>\roi_<hoop>_%04d.jpg"
  ```
- cell=480（near 球 19~26px、far 球 8~13px，粗扫只需识别「攻筐/出手事件」不需确认结果）；tile 4×3=12 帧=6s（约 1930×1450，Read 不降质）。时间换算：`t=(tile序号-1)*6 + 格内序号(0~11)*0.5`；
- AI 逐 tile 锁「球朝筐飞行/篮下攻筐/出手动作」窗口（候选 t，±3s 窗），写 goals.json（status=candidate，含 file/session/window_start/window_end/hoop_id/source=tile）；
- **落盘方式（唯一）**：AI 子批只产出批级 JSON，由主控**串行**运行落盘脚本合并，禁止并行直接写 goals.json（v3.1 修复 M1 竞态）；
- **去重合并（v3.1 修复 M7）**：同 file+hoop 新候选与既有候选 |Δt|<3s 时合并（取中点），防相邻 tile 各锁一次导致同一次出手双计；
- 子批 ≤10 文件；估算 50 文件约 350~400 张 tile。

### 3.3 crop 精判（build_roi_fine.py + AI 目检）

- 窗口 = 候选 t±2.7s（54 帧 @10fps，恰为 6 张完整 3×3 tile——目的是 tile 数确定、幂等可校验；win_start=max(0, t-2.7) 且 **win_end clamp 到文件时长**，文件名中 win_start 一律 round 到 0.1s），命令加 **`-frames:v 6`** 强制恰 6 张（帧数 ±1 抖动时幂等仍命中，v3.1 修复 M4）：
  ```powershell
  ffmpeg -hide_banner -loglevel error -y -ss <win_start> -to <win_end> -i "<file>.MP4" -map 0:v:0 `
    -vf "crop=<S>:<S>:<x0>:<y0>,fps=10,scale=640:640,tile=3x3:padding=2:margin=2" -q:v 3 `
    -frames:v 6 "work\frames\<base>\roifine_<hoop>_<win_start>_%03d.jpg"
  ```
  时间换算：`t=win_start + (tile序号-1)*0.9 + 格内序号(0~8)*0.1`；
- 判定四选一，每条立即经主控串行落盘：
  - **confirmed（投进）**：球整体过网瞬间为 anchor_time（±0.1s）；`result=made`；写 clip_start/clip_end/slowmo（按 inventory avg_frame_rate，50/1→false，100/1→true，其他报警交用户）；
  - **attempt（出手未中）**：投篮动作成立但未进——打铁/三不沾/被盖（被盖记 `note=blocked`）。anchor_time = 球触筐/最接近筐瞬间（被盖则为封盖瞬间）；`result=miss`；**记录保留，是命中率/出手数的数据源**；不写 clip_start/clip_end/slowmo；
  - **rejected（非出手）**：传导/运球/邻场活动等假候选，注明原因；
  - **uncertain**：仍不可判 → 抽 1 张原分辨率单帧存 `work\frames\<base>\review_*.jpg` **供用户查看**（3840×2880 原图不给 AI 读），另存一份 ≤2000px 缩样供 agent 侧留档（v3.1 修复 n7）；**进入 §2.4 的用户定夺门禁**，禁止 AI 硬猜（幻觉教训）；
- 同窗口多次出手（连续补篮）：逐个记 anchor 分别落记录（同 file+window 追加记录的 window_start 加 +0.1 偏移防幂等键冲突，并 note 注明）。

### 3.4 音频佐证（build_audio_peaks.py）

- 全量跑音量峰值：`ffmpeg -i <file> -af ebur128=peak=true -f null -` 解析峰值时刻；阈值以 0007 为主（4.5s 进球应有峰）+ 1~2 个对照文件标定（v3.1 修复 n3）；
- 产出 `work/audio_peaks.json`：file → [peak_times]（3s 内相邻峰合并取峰尖）；
- 比对：峰值 ±5s 内无任何记录 → 对该时刻该文件**全部未 dropped 的 hoop** 各补一组精判 tile，AI 判定后落盘（`source=audio`，window=t±3，hoop_id=判定端，无球端标 rejected+note=no_ball）；按展开后计数对账（v3.1 修复 m1）；
- 只兜底**进球**召回（打铁通常无欢呼，见 §5 风险表）；音频命中也必须经图像精判确认，不单独产生记录。

### 3.5 投篮者帧、花名册与标注（沿用阶段 2 扩展）

- **投篮者帧**（build_shooter_frames.py）：对每条 confirmed/attempt，取 anchor 前 1~3s 全画帧 3 张（`$a-3/$a-2/$a-1`，<0 跳过），**scale=1600:1200** 存 `work\roster\raw\<goal_id>_<t>.jpg`。用途三合一：认人、判 2/3 分、判助攻——一次抽取全部复用；
- **花名册**：按场次归并全部出手者，**并把投篮者帧中可辨识的传球者也纳入 roster**（appears_in 记来源文件；否则只传不投的队友助攻无处可记，v3.1 修复 M5）；代表帧 + roster_sheet.png（输入同样补齐 12 倍数，超出 12 人多拼几张）；用户门禁 G1 确认后回填全部 confirmed/attempt 的 player_label/team_label；
- **标注**（annotation pass，G1 后执行，看投篮者帧+精判序列）：
  - `points`：每条 confirmed/attempt 必填，按出手位置/情形判 **1（罚球）/ 2 / 3（三分线外）**；站位存疑按 2 计并 note=points_uncertain；
  - `assist_label`：仅 confirmed。进球前约 3 秒内最后触球的**队友**传球直接创造该得分 → 填其 label；单打、快攻自备、自抢自补 → null；存疑 → null 且 note=assist_uncertain，不硬猜；
  - **已知口径下限（诚实披露，v3.1 修复 m4）**：快攻长传等发生在 anchor-3s 之前的传球不在投篮者帧内 → 一律记 null，快攻助攻系统性漏记；试点报告须给出 assist null 占比供用户判断是否要扩大回看窗口。

### 3.6 goals.json schema（v3：v2 字段全保留 + 扩展）

`version: 3`。每条记录字段：`file`、`session`、`anchor_time`、`clip_start`、`clip_end`、`slowmo`、`player_label`、`team_label`、`status`，新增：

- `result`：`made` | `miss`（candidate/rejected/uncertain 期无此字段）；
- `points`：1 | 2 | 3（标注后必填，含 attempt）；
- `assist_label`：string | null（仅 confirmed，标注后填写；null=无助攻）；
- `hoop_id`：near | far；`source`：tile | audio；`note`：可选（如 blocked/no_ball/points_uncertain/assist_uncertain）。

status 流转：`candidate → confirmed | attempt | rejected | uncertain`；uncertain 经用户定夺门禁改判 confirmed/attempt（或用户确认放弃后保留 uncertain 但不进统计）；confirmed 经剪辑 `clipped → done`；attempt 在标注完成后为终态（不进剪辑）；removed 规则沿用 SPEC §9。

### 3.7 技术统计产出（build_stats.py）

- 输入：goals.json 中该场次全部 confirmed+attempt（已回填标签、已标注、**无残留 uncertain**）；
- 个人表：得分（Σpoints of made）、出手 FGA（points∈{2,3} 的 confirmed+attempt 数）、命中 FGM、命中率 FGM/FGA、三分 3PA/3PM（points=3）、罚球 FTA（points=1）、助攻（Σassist_label 计数）；
- 队伍表：按 team_label 汇总；
- 输出 `output\<场次>\技术统计.csv`（个人+队伍两段），并在交付报告中附 Markdown 表；
- 校验：Σ个人 = Σ队伍；FGA ≥ FGM；与 goals.json 记录数对账；**同 file 同 hoop anchor 两两差 <2s 的记录报警人工核（多窗一球双计防线，v3.1 修复 M7）；统计前 goals.json 无残留 uncertain**（v3.1 修复 M6）。

## 4. 试点验收标准

1. 检出已知进球 0007@4.5s（±0.5s 内）；
2. 两个已知误报（0007@12.6、0008@2.4）不得进入 confirmed；
3. uncertain 率 < 15%（v2 试点为 55%），且统计前 uncertain 全部经用户定夺；
4. **出手召回抽查**：选 **2 个出手密度高的长文件**（热身碎片文件不选），AI 全段 10fps 数出手生成 gold 清单（附 tile 索引），**gold 经用户全量过目确认后生效**（v3.1 修复 M8：禁止被测系统自证召回）；与检出数对账，召回 ≥ 90%，同时报告绝对数（检出/实际）；
5. 统计对账通过（Σ个人=Σ队伍、FGA≥FGM、记录数一致、无双计报警）；
6. 音频兜底补检数、各类状态计数、tile 总数与实测 token 消耗、assist null 占比写入试点报告，供全量 115 文件决策（含是否叠加运动门控）。

## 5. 风险与对策

| 风险 | 对策 |
|---|---|
| 文件内机位漂移 | §3.1 抽验（距边 ≥10%S 判据）；漂移文件分段标定 |
| 远筐仍不可判 | uncertain 交用户，不硬猜；必要时该窗 1:1 原像素单帧复看 |
| 多片场地球馆误标邻场筐 | 标定时结合场地边界/球员朝向；粗扫确认后写回 dropped:true |
| 音频阈值不准 | 0007 为主 + 1~2 对照文件标定；音频只触发补判不直接确认 |
| 快攻 2fps 漏检 | crop 内球大，0.5s 间隔仍可见；音频兜底再兜一层（仅进球） |
| 打铁/安静出手漏检（无欢呼） | §4.4 用户确认 gold 抽查实测召回；不达标则粗扫升 3fps 重跑该批并复盘 |
| 出手者在 hoop crop 外（三分球） | §3.5 全画投篮者帧覆盖认人+判分，crop 只管球的结果 |
| 助攻判定主观 + 快攻长传盲区 | §3.5 明确定义与口径下限；存疑一律 null；报告 assist null 占比 |
| tile 滤镜丢尾吞内容 | 所有拼图输入补齐 12 倍数；精判窗 54 帧整除 + `-frames:v 6` 强制 |
| 并行写 goals.json 竞态 | AI 只产批级 JSON，主控串行合并（唯一落盘路径） |
| 多窗一球双计 | §3.2 落盘合并（|Δt|<3s）+ §3.7 统计前 anchor<2s 报警 |
| token 超估（新增投篮者帧成本） | 投篮者帧限 1600×1200、3 张/条；子批执行每批实测记录 |

## 6. 不做的事（YAGNI）

- 不做抢断、正负值（用户已排除）；不做在场阵容自动识别；
- 不训练/微调检测模型；不装 OpenCV 等新库（纯 ffmpeg + Python 读写 JSON）；
- 不改输出成片规格（阶段 3~5 剪辑/合成参数不动，attempt 不进成片）；
- 不做跨场次人脸归并；不做运动门控（试点后再议）；
- v2 旧检测脚本（build_fine.py / build_zoom.py / apply_adjudication.py 等）随 v3 上线废弃，SPEC 更新时注明。
