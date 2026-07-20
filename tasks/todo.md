# 任务清单：篮筐 ROI 检测 + 技术统计（v3.1，试点 50 文件）

> 规格以 `docs/superpowers/specs/2026-07-20-hoop-roi-detection-design.md`（v3.1）为准；本清单替代 v2 全部未完成任务（v2 完成情况见 git 历史）。
> **落盘纪律（唯一路径）**：AI 子批只产出批级 JSON，由主控**串行**运行落盘脚本合并 goals.json；禁止子代理并行直接写 goals.json。
> **防降质红线**：所有供 AI 阅读的 tile/拼图 ≤~2000px；3840×2880 原图只给用户看，不用 Read 工具读。
> **防 tile 丢尾**：一切拼图输入序列补齐到 12 的倍数（tpad 克隆末帧或每 12 帧单独一次调用）。
> 试点文件 = `work/pilot_files.json` 中 50 个 MP4（文件名序前 50，含 0005~0010 ground truth）。

## Task 1: 试点初始化

**描述：** 新建 `scripts/pilot_init.py`：① 从 `work/file_inventory.json` 取全部 MP4 按文件名排序，取前 50 写 `work/pilot_files.json`（`{"files":[...]}`）；② 若 `goals.json` 非空且 `work/goals_v2_archive.json` 不存在，把当前 goals.json 复制为归档；③ 重建 `goals.json` 为 `{"version":3,"goals":[]}`。幂等：归档已存在则跳过②。

**验收标准：**
- [ ] `work/pilot_files.json` 恰好 50 个文件，全部 ∈ inventory，含 0005~0010 六个文件
- [ ] `work/goals_v2_archive.json` 存在且含 306 条记录；`goals.json` 为 version 3、goals 为空数组

**验证：** 新建 `scripts/verify_pilot_init.py` 校验上述全部，退出码 0

**依赖：** 无 | **规模：** S

---

## Task 2: 标定帧抽取（build_hoop_calib.py extract）

**描述：** 新建 `scripts/build_hoop_calib.py`（模板 `scripts/build_tiles.py`：ThreadPoolExecutor max_workers=4、幂等跳过、错误汇总）。`extract` 子命令：对 pilot 50 文件各取 50% 时长处 1 帧，**scale=480:360**：

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <dur*0.5> -i "<file>" -map 0:v:0 -frames:v 1 -vf scale=480:360 "work\frames\_calib\<stem>.jpg"
```

拼 sheet：输入帧序列**补齐到 12 的倍数**（tpad=stop_mode=clone 克隆末帧，或每 12 帧单独一次 ffmpeg 调用），tile=4x3 → `work\frames\_calib\sheet_%02d.jpg`（50 文件 → 5 张，50 格全部可溯源）。同时落 `work\frames\_calib\meta.json`：`{"cell":[480,360],"multiplier":8,"order":["<stem1>",...]}`（格序→文件映射，含补齐的克隆格标记）。

**验收标准：**
- [ ] 50 张单帧 + 5 张 sheet，每张 sheet 约 1930×1100（≤2000px）；meta.json 完整
- [ ] 幂等：重跑全部 skip

**验证：** 新建 `scripts/verify_hoop_calib.py`：单帧数=50、sheet 数=5、ffprobe 读 sheet 宽高 ≤2000、meta.json 50 格可溯源

**依赖：** Task 1 | **规模：** S

---

## Task 3: AI 篮筐标定 → hoops.json + 抽验

**描述：** AI 逐张读 5 张 sheet，按 meta.json 的格序对每格标出本场用筐 1~2 个：near（本场近端大筐，必有）/ far（本场远端筐，若在场内使用且可见），给 480×360 图内筐心坐标。写 `work/hoops.json`：

```json
{
  "DJI_20250419163240_0001_D.MP4": {"hoops": [{"id":"near","x":1380,"y":470,"crop":1500},{"id":"far","x":2770,"y":1385,"crop":900}]}
}
```

坐标 = 图内坐标 **×8**（唯一倍率，以 meta.json 为准）；crop 边长 near=1500、far=900（AI 按实际远近 ±200 微调）。场馆是多片场地，结合场地边界/球员朝向区分本场筐与邻场筐。
然后运行 `build_hoop_calib.py check`：对每个 hoop 按标定 crop 取 25% 时长处 1 帧，scale=320 cell 拼 4×3 check sheet（输入同样补 12 倍数）；AI 逐格确认判据 = **筐心在 crop 内且距任一边 ≥10%S**（clamp 贴边的筐天然偏心，不要求居中），不符文件重标后重跑 check 直至全部通过。

**验收标准：**
- [ ] `work/hoops.json` 覆盖 pilot 50 文件；每文件 hoops 1~2 个；id ∈ {near,far}；0≤x≤3840、0≤y≤2880；crop ∈ [700,1700]
- [ ] verify 用 meta.json 倍率反推抽查 3 个 hoop，坐标落在对应格的筐附近
- [ ] check sheet 全部 hoop 通过距边判据

**验证：** 新建 `scripts/verify_hoops.py` 做 schema 校验 + meta 反推抽查；check sheet AI 目检全过

**依赖：** Task 2 | **规模：** M

---

## Task 4: 粗扫 tile（build_roi_scan.py）+ 扩展 goals_append.py

**描述：**
① 新建 `scripts/build_roi_scan.py`（模板 build_tiles.py）。按 hoops.json 对每文件每 hoop（跳过 dropped:true）生成 2fps crop tile：

```powershell
ffmpeg -hide_banner -loglevel error -y -i "<file>" -map 0:v:0 `
  -vf "crop=<S>:<S>:<x0>:<y0>,fps=2,scale=480:480,tile=4x3:padding=2:margin=2" -q:v 4 `
  "work\frames\<stem>\roi_<hoop_id>_%04d.jpg"
```

x0/y0 = clamp(cx-S/2, 0, 3840-S) / clamp(cy-S/2, 0, 2880-S)。幂等：按 `roi_<hoop_id>_*.jpg` glob 计数，达 floor(round(dur*2)/12) 张则 skip（verify 容忍 N 或 N+1 张，fps 滤镜帧数有 ±1 抖动）。
② 扩展 `scripts/goals_append.py` 至 v3：candidate 窗口 t±3（clamp≥0）；新字段 `hoop_id`、`source`（默认 tile）；幂等键不变（file+window_start）；**去重合并**：同 file+hoop_id 新候选与既有 candidate |Δt|<3s 时合并取中点不新增；脚本仅由主控串行调用。

**验收标准：**
- [ ] 每 (文件, hoop) 目录张数 ∈ {floor(round(duration×2)/12), +1}（时长 <6s 的文件 tile 数为 0 属预期，列出清单）
- [ ] goals_append.py 扩展字段与合并规则有自测（构造 3 条含 1 条重叠候选，合并后 2 条）

**验证：** 新建 `scripts/verify_roi_scan.py` 按 inventory 时长逐目录核对；goals_append 自测输出

**依赖：** Task 3 | **规模：** S

---

## Task 5: AI 粗扫锁候选（5 子批 × ~10 文件，子代理产 JSON）

**描述：** 子批按文件名序切分 pilot 50 文件。子代理逐张读 `roi_<hoop>_*.jpg`，锁「球朝筐飞行/篮下攻筐/出手动作」的候选时刻 t（换算：`t=(tile序号-1)*6 + 格内序号(0~11)*0.5`，格内序号含 0）。**子代理只产出批级 JSON**（`work\cands_batch_<i>.json`：`[{"file","t","hoop_id","note?"}]`），不直接写 goals.json；**主控串行**运行 goals_append.py 合并（自动去重合并）。粗扫只锁「出手事件」，不判断进没进；确认邻场筐（全程无本队活动）时，由主控写回 hoops.json 该 hoop `"dropped": true` + reason，后续任务跳过。

**验收标准：**
- [ ] 该子批每张 tile 均被查看；批级 JSON 字段完整（file/t/hoop_id）
- [ ] 合并后 goals.json candidate 字段完整（file/session/window_start/window_end/hoop_id/source/status）；session ∈ sessions.json
- [ ] 无 |Δt|<3s 的同 file+hoop 重复候选（合并规则生效）

**验证：** goals.json 解析通过；子批文件数与批报一致；抽查 3 条候选时间换算

**依赖：** Task 4 | **规模：** M（每子批）

---

## Task 6: 音频峰值（build_audio_peaks.py）

**描述：** 新建 `scripts/build_audio_peaks.py`：对 pilot 50 文件运行 `ffmpeg -i <file> -af ebur128=peak=true -f null -`，解析 stderr 中各秒峰值；以 **0007 为主 + 1~2 个对照文件**打印全段峰值分布定阈值（已知 0007@4.5s 进球应有峰；阈值写进 JSON header）。产出 `work/audio_peaks.json`：`{"threshold":<值>, "files":{"<file>":[t1,t2,...]}}`（3s 内相邻峰合并取峰尖时刻）。

**验收标准：**
- [ ] 50 文件全部有条目（无峰文件为空数组）
- [ ] 0007 在 4.5±2s 内有峰；阈值与标定依据记录在 header

**验证：** 新建 `scripts/verify_audio_peaks.py` 校验上述

**依赖：** Task 1（与 Task 3~5 并行） | **规模：** S

---

## Task 7: 精判 tile（build_roi_fine.py 三模式）+ 新建 goals_judge.py

**描述：**
① 新建 `scripts/build_roi_fine.py`，三种模式：
- 默认：goals.json 全部 candidate；窗口 win = t±2.7（t=窗口中点，win_start=max(0,t-2.7) 且 win_end clamp 到 inventory duration，文件名 win_start round 到 0.1s）
- `--from <json>`：读 audio_recheck.json 条目（对该文件全部未 dropped hoop 各开一窗，窗口 t±3 的中点 t）
- `--full <file>`：全段模式（窗口=整文件时长，连续 tile），输出命名 `roifull_<hoop>_%03d.jpg`（Task 13 用）

命令（窗口模式）：

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <win_start> -to <win_end> -i "<file>" -map 0:v:0 `
  -vf "crop=<S>:<S>:<x0>:<y0>,fps=10,scale=640:640,tile=3x3:padding=2:margin=2" -q:v 3 `
  -frames:v 6 "work\frames\<stem>\roifine_<hoop>_<win_start>_%03d.jpg"
```

`-frames:v 6` 强制恰 6 张（帧数 ±1 抖动时幂等仍命中）。幂等：已有 6 张（边界窗按实际张数）则 skip。
② 新建 `scripts/goals_judge.py`：按 (file, window_start) 定位记录更新判定字段——confirmed（anchor_time/result=made/clip_start/clip_end/slowmo）、attempt（anchor_time/result=miss/note）、rejected（note）、uncertain（review 帧路径）；同窗口多次出手用 window_start +0.1 偏移追加新记录并 note=multi_shot；内置 schema 校验（result/slowmo 与 inventory 一致、attempt 无 clip 字段）；仅主控串行调用。

**验收标准：**
- [ ] 每 candidate 恰好 6 张 roifine tile（触文件头/尾边界按实际张数，列出清单）
- [ ] goals_judge.py 四种判定路径自测各 1 条通过；非法输入被拒

**验证：** 新建 `scripts/verify_roi_fine.py`：candidate 数 ×6 与实际张数对账（豁免清单内除外）；goals_judge 自测输出

**依赖：** Task 5（全部子批完成）、Task 3 | **规模：** S

---

## Task 8: AI 精判定（分批 ≤50 候选，子代理产 JSON）

**描述：** 子代理逐候选读 6 张 roifine tile（换算：`t=win_start+(tile序号-1)*0.9+格内序号(0~8)*0.1`），四选一判定产批级 JSON，**主控串行**运行 goals_judge.py 落盘：

- **confirmed**：球整体过网。anchor_time（±0.1s）、result=made、clip_start=max(0,anchor-4)、clip_end=anchor+2、slowmo（inventory avg_frame_rate：50/1→false、100/1→true、其他报警停批交用户）
- **attempt**：出手未中（打铁/三不沾/被盖）。anchor_time=球触筐/最接近筐瞬间（被盖=封盖瞬间）、result=miss、note=airball/blocked/rim（可选）；不写 clip_start/clip_end/slowmo
- **rejected**：非出手（传导/运球/邻场）。note 原因
- **uncertain**：仍不可判。抽 1 张原分辨率单帧存 `work\frames\<stem>\review_<hoop>_<win_start>_<t>.jpg`（**供用户查看，AI 不得用 Read 读 3840×2880 原图**），另存 ≤2000px 缩样 `review_*_small.jpg` 供 agent 留档

**验收标准：**
- [ ] 全部 candidate 落为 confirmed/attempt/rejected/uncertain 之一；confirmed 字段符合 schema（result=made、slowmo 与 inventory 一致）
- [ ] 检出已知进球 0007@4.5s（±0.5s）；0007@12.6、0008@2.4 不得为 confirmed
- [ ] uncertain 率 < 15%，uncertain 清单汇总交 Task 8.5

**验证：** goals_judge.py 内置校验；随机抽 5 条 confirmed 复查 anchor 换算

**依赖：** Task 7 | **规模：** L（分批）

---

## Task 8.5:【门禁】uncertain 用户定夺

**描述：** 把 Task 8/9 全部 uncertain 记录（review 原图）交用户逐条定夺：改判 confirmed/attempt（补 anchor_time 等字段，主控用 goals_judge.py 更新），或用户确认放弃（保留 uncertain，不进统计）。**全部定夺完毕才解锁 Task 10**。

**验收标准：**
- [ ] goals.json 中 uncertain 或已改判、或经用户确认放弃；无「待定」悬挂记录

**验证：** 脚本列出全部 uncertain 及其终态，用户确认

**依赖：** Task 8、Task 9 | **规模：** S

---

## Task 9: 音频兜底补判

**描述：** 新建 `scripts/build_audio_recheck.py`：比对 audio_peaks.json 与 goals.json——峰值 ±5s 内该文件无任何记录（含 rejected）→ 写 `work/audio_recheck.json`（`[{"file","t"}]`）。对每条用 `build_roi_fine.py --from work/audio_recheck.json` 对该文件**全部未 dropped hoop** 各抽一组精判 tile，AI 按 Task 8 流程判定，主控串行落盘（source=audio，window=t±3，hoop_id=判定端，无球端 rejected+note=no_ball）。

**验收标准：**
- [ ] audio_recheck 每条 × 该文件未 dropped hoop 数 = source=audio 判定落盘数（按展开后计数对账）
- [ ] 补判新增 confirmed 数记录（供试点报告）

**验证：** 对账脚本输出展开计数与落盘数一致

**依赖：** Task 6、Task 8 | **规模：** S

---

## Task 10: 投篮者帧（build_shooter_frames.py）

**描述：** 新建 `scripts/build_shooter_frames.py`：对每条 confirmed/attempt（含 Task 8.5 改判的），取 anchor 前 3/2/1 秒全画帧（t<0 跳过），goal_id=`<stem>_<anchor>`：

```powershell
ffmpeg -hide_banner -loglevel error -y -ss <t> -i "<file>" -map 0:v:0 -frames:v 1 -vf scale=1600:1200 -q:v 3 "work\roster\raw\<goal_id>_<t>.jpg"
```

**验收标准：**
- [ ] 每条 confirmed/attempt 有 1~3 张；1600×1200 可辨认投篮者服装/体态/站位

**验证：** 新建 `scripts/verify_shooter_frames.py` 对账张数；抽查 10 条目检

**依赖：** Task 8.5、Task 9 | **规模：** S

---

## Task 11: 花名册归并（含传球者）→【G1】→ 回填

**描述：** 沿用 SPEC §5 流程但覆盖**全部出手者 + 投篮者帧中可辨识的传球者**（传球者 appears_in 记来源文件，否则只传不投的队友助攻无处可记）：按投篮者帧归并个人（人脸为主服装为辅）、分队（服装色），命名 `红队-7号`/`黑T恤-A` 风格；代表帧存 `work\roster\20250419\<label>.jpg`，拼 roster_sheet.png（输入补 12 倍数，超 12 人多拼几张，每张 ≤2000px），写 roster.json（该场次 confirmed=false）。**【G1 用户确认】**后置 confirmed=true，并回填 goals.json 全部 confirmed/attempt 的 player_label/team_label。

**验收标准：**
- [ ] 每条 confirmed/attempt 的 player_label/team_label 非空且 ∈ roster.json
- [ ] roster 含可辨识传球者；roster_sheet.png 经用户过目确认

**验证：** 脚本校验回填完整性（无 null 残留）

**依赖：** Task 10 | **规模：** M

---

## Task 12: AI 标注 points / assist_label

**描述：** 新建 `scripts/goals_annotate.py`（主控串行批量 update）。AI 看投篮者帧 + 精判序列逐条标注：

- `points`（全部 confirmed+attempt 必填）：1=罚球（罚球线站位、无防守）、2=两分、3=三分线外出手；以 anchor 前 1~3s 投篮者帧站位为准，存疑按 2 计并 note=points_uncertain
- `assist_label`（仅 confirmed）：进球前约 3 秒内最后触球的**队友**传球直接创造该得分 → 其 label（∈ roster）；单打/快攻自备/自抢自补 → null；存疑 → null 且 note=assist_uncertain，不硬猜
- **已知口径下限**：快攻长传（传球早于 anchor-3s）不在投篮者帧内 → 一律 null；统计 assist null 占比写入试点报告

**验收标准：**
- [ ] confirmed/attempt 全部有 points ∈ {1,2,3}；assist_label ∈ roster labels ∪ {null}（仅 confirmed 有此字段）
- [ ] points_uncertain / assist_uncertain 计数与 null 占比记录

**验证：** goals_annotate.py 内置校验；抽 5 条复查

**依赖：** Task 11（G1） | **规模：** M

---

## Task 13: 出手召回金标准（2 个长文件）

**描述：** 选 **2 个出手密度高的长文件**（从 pilot 中按时长+粗扫事件密度选，热身碎片不选；尽量一早一晚），对其全部未 dropped hoop 用 `build_roi_fine.py --full` 做全段 10fps crop，AI 逐张数真实出手（含未中）写 `work/recall_gold.json`（`{"<file>":[{"t":..,"tile":..},...]}`，每条附 tile 索引）。**gold 清单交用户全量过目确认后才生效**（禁止被测系统自证召回）。对账：goals.json 该 2 文件的 confirmed+attempt vs gold（±1.0s 容差配对）→ 召回率与绝对数（检出/实际）。

**验收标准：**
- [ ] gold 经用户确认；召回率 ≥ 90% 且报告绝对数；不达标则粗扫升 3fps 重跑对应子批并复盘漏检模式（漏检 ≥2 次即触发）

**验证：** 对账脚本输出召回率、漏检时刻清单；用户确认记录

**依赖：** Task 8（与 Task 9~12 并行） | **规模：** M

---

## Task 14: 技术统计 + 试点报告 + SPEC/AGENTS 更新

**描述：**
① 新建 `scripts/build_stats.py`：取该场次全部 confirmed+attempt（前置校验：**goals.json 无残留未定夺 uncertain**；**同 file 同 hoop anchor 两两差 <2s 的记录报警人工核**防多窗一球双计），输出 `output\20250419\技术统计.csv`（个人表 label,PTS,FGA,FGM,FG%,3PA,3PM,FTA,AST；队伍表按 team 汇总）。口径：PTS=Σpoints(made)；FGA=points∈{2,3} 的 confirmed+attempt 数；FGM=其中 made 数；FTA=points=1 数；3PA/3PM=points=3 数/made 数；AST=assist_label 计数。对账：Σ个人=Σ队伍、FGA≥FGM、记录数一致，不通过退出码 1。
② 写 `work/pilot_report.md`：验收对照（0007@4.5 检出 / 两误报非 confirmed / uncertain 率 / 召回率绝对数）、状态计数、音频补检新增数、assist null 占比、tile 与实测 token 消耗、全量 115 文件建议（是否叠加运动门控）。
③ 更新 SPEC.md 与 AGENTS.md，范围包括：§2 schema 升 v3（示例补 window_start/window_end/result/points/assist_label/hoop_id/source/note，status 状态机加 attempt/uncertain 分支）、§4 阶段 1 重写为 v3 ROI 流程、§5.1 投篮者帧改 1600×1200 且覆盖 attempt、§5.3 roster_sheet 补 12 倍数规则、§5 花名册含传球者与回填措辞、新增音频兜底与技术统计两节、§9 增量规则对 attempt/uncertain 的适用、§10 追加 v3 决策记录、§11 风险表更新、v2 旧检测脚本（build_fine.py/build_zoom.py/apply_adjudication.py 等）注明废弃；AGENTS.md 检测流程一行同步。随后**必须派 spec-reviewer 子代理审查**（AGENTS.md 强制），阻断问题修订后交付。

**验收标准：**
- [ ] 技术统计.csv 对账通过、无双计报警、无残留 uncertain
- [ ] 试点报告各项验收全部有结论；SPEC/AGENTS 更新通过 spec-reviewer 审查

**验证：** build_stats.py 退出码 0；spec-reviewer 报告无 blocking

**依赖：** Task 9、Task 12、Task 13 | **规模：** M
