# 实施计划：篮球进球视频剪辑流水线（v2，对齐 SPEC v2）

## 概述

从 `0_raw_videos\`（MP4 + LRF，数量以当次扫描为准，素材流动增删）检测「球入网」进球时刻，按 SPEC v2 剪辑（前4s+后2s、1440×1080/50fps、100fps 素材入网后 2s 半速慢放成片 8s），**按场次隔离**输出：每场次每队一个集锦 + 每人一个合集，均落 `output\<场次>\`。检测 = 方案 A（ffmpeg 抽帧 + agent 目检），不压缩 token。

## 架构决策

- **纯 ffmpeg + 目检**；Python 仅读写 JSON。编码器决策存 `work\file_inventory.json` 头部（本次探测：无 NVIDIA 卡 → libx264），下游任务一律引用该决策，不硬编码
- **场次（session）为一等公民**：goals.json v2 每条带 `session`；roster.json v2 按场次 key 隔离、`confirmed` 按场次独立置门；输出 `output\<场次>\`
- **场次两级确认**：0.2a 先计算场次清单与派生规则并落盘 `work\sessions.json` 草案（阶段 1 目检据此预填 session）；0.2b 是用户确认门禁 G0，只门禁 2.4 花名册及以后（精抽定帧 2.1/2.2 不依赖场次终表，可先行）。G0 若改名/拆分，须同步五处：sessions.json、goals.json 既有记录 session、roster.json 场次 key 及其 players 的 rep_frame 路径、`output\`/`work\roster\` 对应目录名（SPEC §9）
- **状态机**：`candidate → confirmed → clipped → done`，分支 `rejected` / `removed`，终态记录保留不删
- **两级检测**：LRF 2fps tile 接触表锁候选（±5s 窗）→ 原片 10fps 精抽定帧（±0.1s）
- **concat 列表一律纯文件名**，列表文件与片段同放 `work\clips\`
- **候选期扩展字段**（SPEC schema 之外，本计划声明）：candidate 阶段允许 `window_start`/`window_end`；confirmed 后这些字段可保留，player_label/team_label 在花名册确认前一律显式为 `null`

## 依赖图

```
0.1 扫描+inventory → 0.2a 场次清单草案(sessions.json) ──┐
    │                                                    │
    ├── 接触表生成（幂等）→ 目检锁候选（子批，预填 session）   │ 0.2b 用户确认场次【G0】
    │       │（看不清的窗口当场用原片高清缩样复看后定夺）      │（只门禁 2.4 花名册及以后；
    │       └── goals.json candidate                       │  改名/拆分→五处同步）
    │               └── 原片精抽定帧 → confirmed/rejected
    │                       └── 抽投篮者帧 → 按场次归并花名册 ◄─┘
    │                               └──【G1：用户按场次确认 roster】
    │                                       └── 该场次片段剪辑 → clipped
    │                                               └── 该场次分组 concat → output\<场次>\
    │                                                       └── 成品验证
```

G1 按场次独立：先确认的场次先进入阶段 3，不等其他场次。

## 任务清单

### 阶段 0：扫描与场次

- [ ] Task 0.1：全量扫描 + `work\file_inventory.json`（MP4/LRF 配对、逐文件 fps/位深/时长、编码器决策）
- [ ] Task 0.2a：计算场次清单（日期分组 + >2h 间隔拆分建议）与派生规则，落盘 `work\sessions.json` 草案
- [ ] Task 0.2b：场次清单交用户确认/改名【门禁 G0】；变更时四处同步

### 阶段 1：接触表与候选检测（子批 ≤10 文件或 ≤150 张 tile）

- [ ] Task 1.1：补全全部视频 2fps 5×4 tile 接触表（幂等跳过已有）
- [ ] Task 1.2.x：逐子批目检锁候选 → goals.json candidate（每条判定后立即落盘，可中断续做）

### 检查点 1：候选全量

- [ ] 全部 tile 已目检；goals.json 候选字段完整（file/session/window_start/window_end）；向用户通报候选量级

### 阶段 2：精确定帧与花名册（按场次组织）

- [ ] Task 2.1：全部候选窗口原片 10fps 精抽拼 tile（文件名含 win_start+候选估值防碰撞）
- [ ] Task 2.2：精抽目检定 anchor_time ±0.1s、slowmo 判定（50/100 以外帧率报警交用户）→ confirmed/rejected
- [ ] Task 2.3：每 confirmed 进球抽投篮者 3 帧 → `work\roster\raw\`
- [ ] Task 2.4：按场次归并人物/队伍 → 代表帧 + roster_sheet.png + roster.json（confirmed=false）

### 检查点 2：用户确认门禁 G1（硬性，按场次）

- [ ] 用户确认某场次花名册 → 该场次 confirmed=true 并回填 goals.json 标签

### 阶段 3：片段剪辑（按场次切片，各场次独立解锁）

- [ ] Task 3.x：每个已确认场次一个任务：剪辑该场次全部进球（50fps 单段 / 100fps 两段慢放），编码器取 inventory 决策

### 检查点 3：片段校验

- [ ] 批量 ffprobe 参数达标；时长 6s（slowmo 8s）±0.2s，片源不足按实际时长并记录；抽 5% 目检

### 阶段 4：分组合成（按场次）

- [ ] Task 4.1：各场次按 team_label 分组 concat → `output\<场次>\队伍_XX_进球集锦.mp4`
- [ ] Task 4.2：各场次按 player_label 分组 concat → `output\<场次>\个人_XX_进球合集.mp4`

### 阶段 5：验证与交付

- [ ] Task 5.1：全部成品 ffprobe 校验 + 首中尾 3 帧拼图目检
- [ ] Task 5.2：校验无 clipped 残留（状态迁移只在 4.x 做）+ 交付报告（场次/队伍/人数/进球数/时长）

## 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 场次拆分误判（>2h 间隔不一定是两场） | 中 | G0 由用户拍板；改名/归并按四处同步规则执行 |
| LRF 球太小漏检 | 高 | 目检阶段当场用原片高清缩样（≥1920×1440）复看后定夺 |
| 误判入网 | 中 | 阶段 2.2 精抽二次确认 |
| 人脸模糊归并错 | 中 | 服装为主，存疑标 `待定X` 交用户定夺 |
| 会话中断 | 中 | 每条判定立即落盘 goals.json，任意点可续 |
| 素材增删 | 低 | 每会话重扫，SPEC §9 增量规则 |
| concat 路径出错（Windows 反斜杠/相对路径） | 低 | 列表一律纯文件名，与片段同目录 |
| 片尾进球窗口超文件时长 | 低 | 按实际时长出片，交付报告标注 |

## 待确认问题

- G0：场次清单待用户确认或改名 —— Task 0.2a 产出后即提出（确认后本条由主 agent 标记已决）
