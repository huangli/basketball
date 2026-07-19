# 任务清单：篮球进球视频剪辑（v2，对齐 SPEC v2）

> 规格以 `SPEC.md` 为准；场次（session）贯穿全流程。文件/批次数量一律以当次扫描为准，不硬编码。
> **落盘纪律**：所有目检/判定任务，每判定一条立即写 goals.json，保证任意时刻中断可续。
> **候选期扩展字段**（SPEC schema 之外，plan 已声明）：`window_start`/`window_end`。

## Task 0.1: 全量扫描与文件清单 ✅ 已完成（2026-07-19，commit 见 git log）

**描述：** 递归扫描 `0_raw_videos\*.MP4/*.LRF`，同名配对（容忍单边缺失），逐 MP4 用 ffprobe 记录 width/height/avg_frame_rate/pix_fmt/duration，写 `work\file_inventory.json`（以文件名为主键），头部写编码器决策（本次探测无 NVIDIA 卡 → `encoder: libx264`；后续会话重探）。

**验收标准：**
- [x] inventory 条目数 = 当次扫描 MP4 数（115），每条含 fps/pix_fmt/duration
- [x] LRF 缺失的 MP4 列出清单（本次 0 个缺失）
- [x] inventory 头部含 `encoder` 字段（libx264）

**验证：** `python scripts\verify_inventory.py` 全部通过（9 项）；实现 `scripts\build_inventory.py`（8 线程并行 ffprobe）

**依赖：** 无 | **规模：** S

---

## Task 0.2a: 场次清单草案与派生规则

**描述：** 按文件名 `DJI_YYYYMMDDHHMMSS` 分组：先按日期分，同日内相邻文件间隔 >2h 处建议拆分 `YYYYMMDD-a/-b`。产出**草案**落盘 `work\sessions.json`：每场含 session_id/时间范围/文件清单 + 派生规则（文件名 → session 的映射逻辑）。

**验收标准：**
- [ ] `work\sessions.json` 存在，每个扫描到的文件恰好属于一个场次
- [ ] 含拆分建议说明（哪些间隔 >2h）

**验证：** 脚本校验"文件 → 场次"映射全覆盖且无重叠

**依赖：** Task 0.1 | **规模：** S

---

## Task 0.2b: 场次确认门禁【G0】

**描述：** 把场次清单（ID/时间段/文件数/拆分建议）交用户确认、改名或声明对手名；结果回写 `work\sessions.json`。**变更时四处同步**（SPEC §9）：sessions.json、goals.json 既有记录 session、roster.json 场次 key、`output\`/`work\roster\` 对应目录名。G0 只门禁阶段 2 花名册及以后，阶段 1 目检按草案先行。

**验收标准：**
- [ ] 用户明确确认或修改；最终场次表落盘
- [ ] 若有变更，五处同步完成（含 roster.json 该场次 players 的 rep_frame 路径批量改写）且 goals.json 中无指向旧场次 ID 的记录

**验证：** goals.json 的 session 值集合 ⊆ sessions.json 的 session 集合

**依赖：** Task 0.2a | **规模：** S

---

## Task 1.1: 补全全部视频 tile 接触表

**描述：** 按 SPEC §4.2 命令对全部 LRF 生成 2fps、5×4、320×240 单元 tile 到 `work\frames\<basename>\tile_%04d.jpg`，幂等跳过已有非空目录；LRF 缺失的 MP4 退回原片低清抽帧。

**验收标准：**
- [ ] tile 目录数 = 可粗扫文件数；无空目录（时长 <10s 的文件 tile 数为 0 属预期，除外）
- [ ] 每个目录 tile 数 = floor(时长×2/20)（tile 滤镜丢弃不足 20 帧的尾部；时长取 inventory）

**验证：** 统计脚本输出目录/tile 总数；抽查 3 个目录张数与 floor 公式一致

**依赖：** Task 0.1 | **规模：** S

---

## Task 1.2.x: 目检子批锁候选（每个子批一个任务）

**描述：** 子批 ≤10 个文件或 ≤150 张 tile（子批清单按文件名序从 sessions.json 文件全集切分）。逐张查看 tile（Read 工具），锁定「球接近篮筐疑似入网」±5s 时间窗。**看不清的窗口当场闭环**：立即对该窗口用原片高清缩样（scale≥1920:1440）抽帧复看，复看完才决定记 candidate 或放弃。每条判定后立即写 goals.json v2：`file`、`session`（按 sessions.json 草案派生）、`window_start/window_end`、`status=candidate`。

**验收标准：**
- [ ] 该子批每张 tile 均被查看，goals.json 中该子批文件对应的 candidate 记录完整
- [ ] 时间窗换算正确：`t=(tile序号-1)*10+格内序号*0.5`
- [ ] 每条 candidate 的 `session` 值均在 sessions.json 中
- [ ] 无遗留"看不清未复看"的窗口

**验证：** goals.json 解析通过；该子批文件数与目检日志覆盖一致；session 值集合 ⊆ sessions.json

**依赖：** Task 1.1、Task 0.2a（草案派生规则） | **规模：** M（每子批）

---

## ⛔ 检查点 1：候选全量

- [ ] 全部视频目检完毕，候选字段完整，向用户通报量级

---

## Task 2.1: 候选窗口原片 10fps 精抽

**描述：** 对每个 candidate 按 SPEC §4.4 执行（`win_start=max(0,t-5)`，`win_end=t+5`），输出 `work\frames\<basename>\fine_<win_start>_<候选t>_%03d.jpg`（10fps、960×720、5×4 tile；文件名带候选估值防同文件多候选 win_start 碰撞）。

**验收标准：** 每个 candidate 有精抽图；张数 = floor(窗口长×10/20)（尾部不足 20 帧被丢弃属预期）

**验证：** 脚本比对 candidate 数与精抽批次数；抽查 3 个窗口张数

**依赖：** 检查点 1 | **规模：** S

---

## Task 2.2: 精抽目检定帧

**描述：** 逐候选看精抽 tile，确认球整体过网瞬间（否决打铁/三不沾/被盖→`rejected`），按 `t=win_start+(tile序号-1)*2+格内序号*0.1` 换算 anchor_time（±0.1s）；按 inventory 的 avg_frame_rate 定 `slowmo`（100/1→true，50/1→false，**其他值报警并交用户定夺**）；写 clip_start=`max(0,anchor-4)`、clip_end=`anchor+2`、`player_label=null`、`team_label=null`，status→`confirmed`。每条判定后立即落盘。按 ≤50 个候选/批分段执行。

**验收标准：**
- [ ] 每条记录落为 confirmed 或 rejected，字段符合 SPEC §2 v2 schema（confirmed 记录 player/team 显式为 null）
- [ ] slowmo 判定与 inventory 帧率一致，异常帧率已报警

**验证：** schema 校验；随机抽 5 条复查时间换算与 slowmo

**依赖：** Task 2.1 | **规模：** M（分子批执行）

---

## Task 2.3: 抽投篮者帧

**描述：** 每 confirmed 进球在入网前 1–3s 抽 3 帧（`$a-3/$a-2/$a-1`，<0 则跳过），存 `work\roster\raw\<basename>_<anchor>_<t>.jpg`。

**验收标准：** 每进球 1–3 张、可辨认投篮者服装体态

**验证：** 抽查 10 个进球的帧

**依赖：** Task 2.2 | **规模：** S

---

## Task 2.4: 按场次归并花名册

**描述：** 按场次分别归并：服装颜色分队（便装人员 team_label 用服装组名如 `黑T恤`）、人脸+服装归并个人、标签命名（`红队-7号`/`黑T恤-A`）；代表帧存 `work\roster\<场次>\<label>.jpg`；用 `-pattern_type glob` 拼 `roster_sheet.png`（>20 人 6×5 tile）；写 roster.json v2（每场次 confirmed=false）。

**验收标准：**
- [ ] roster.json 符合 SPEC §2 v2 schema，每 confirmed 进球有 player/team 候选归属
- [ ] 每场次一张 roster_sheet.png 含全部人物，可供用户过目

**验证：** json 解析通过；逐场次目检拼图无缺漏

**依赖：** Task 2.3、Task 0.2b（G0 已确认场次表） | **规模：** M

---

## ⛔ 检查点 2：用户确认门禁 G1（按场次，硬性）

- [ ] 用户确认某场次花名册 → roster.json 该场次 `confirmed=true`，回填 goals.json 该场次全部 `player_label/team_label`；未确认场次禁止进入阶段 3，已确认场次不受影响

---

## Task 3.x: 剪辑各场次进球片段（每场一个任务，G1 解锁）

**描述：** 按 SPEC §6 执行该场次全部 confirmed 进球：50fps 走 §6.1 单段；100fps 走 §6.2（A 常速段 + B 慢放段 `setpts=2.0*PTS,fps=50` + `atempo=0.5`，concat 纯文件名列表重封装）。统一 1440×1080/50fps/AAC 48kHz 160k；**编码器与质量参数取 `work\file_inventory.json` 头部 encoder 决策**（本次 libx264 `-crf 20 -preset medium`）。输出 `work\clips\<basename>_<anchor>.mp4`，完成 status→`clipped`。**片源不足边界**：clip_start 触 0（anchor<4s）或 clip_end 超文件时长时按实际时长出片，时长偏差在交付报告标注，不算验收失败。

**验收标准：**
- [ ] clips 数 = 该场次 confirmed 数
- [ ] 每片段时长 6s（slowmo 8s）±0.2s；片源不足的例外已记录
- [ ] 批量 ffprobe 参数全部达标（1440×1080/50fps/h264/aac/48kHz）

**验证：** 脚本批量 ffprobe；随机抽 5% 抽帧目检无黑屏/错段

**依赖：** 检查点 2（对应场次） | **规模：** M（每场）

---

## Task 4.1/4.2: 按场次分组 concat 合成

**描述：** 取该场次 `clipped`+`done` 记录（排除 candidate/rejected/removed），按 team_label / player_label 分组；组内按文件名字符串序 + anchor_time 排序；以 `work\clips\` 片段实际存在为准、缺失跳过并告警；`New-Item -ItemType Directory -Force "output\<场次>"` 后用 concat demuxer 纯文件名列表重封装输出 `output\<场次>\队伍_XX_进球集锦.mp4` / `个人_XX_进球合集.mp4`。合成后该组记录 status→`done`（状态迁移只在此处做）。

**验收标准：**
- [ ] 每场次每队/每人各一个成品，命名与目录符合 SPEC §7
- [ ] 成品时长 = 组内片段时长之和（slowmo 按 8s 计，片源不足按记录扣减）±0.5s
- [ ] `output\<场次>\` 目录已显式创建

**验证：** ffprobe 时长比对；concat 列表与 goals.json 记录数一致

**依赖：** 对应场次 Task 3.x 完成 | **规模：** S

---

## Task 5.1/5.2: 成品验证与交付

**描述：** 全部成品 ffprobe 校验（1440×1080/50fps/h264+aac/48kHz）+ 首中尾 3 帧拼图目检（SPEC §8 命令）；校验 goals.json 无 clipped 残留；交付报告。

**验收标准：**
- [ ] 所有成品参数达标、拼图无黑帧/错拼
- [ ] goals.json 中全部场次无 `clipped` 状态残留（状态迁移已在 4.x 完成）
- [ ] 交付报告含：场次清单、每场队伍数/人数/进球总数、各成品时长、片源不足片段清单

**验证：** 按 SPEC §8 逐项执行并留记录

**依赖：** Task 4.x 全部完成 | **规模：** S
