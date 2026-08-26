# spec：标注页 J 键人工锚点（goal-anchor）

## 背景与问题

成品片段窗口 = 锚点前 4s 后 2s，在标注页导出 goals.json 时写死（`gen_label_page.py` `CLIP_BEFORE_SEC=4.0 / CLIP_AFTER_SEC=2.0`），build 直接吃 `clip_start/clip_end` 不另算。锚点本身是机器定的（事件末候选 t0，`gen_review_clips.py event_anchor`），而**审核片段窗口 = 事件成员跨度（首候选 −2s ~ 末候选 +4s），比成品窗口长**——两个口径不一致导致两类漏切：

- **末尾类**：同一回合被聚类切成多个碎片事件，真实入网落在后一碎片，但前一碎片的审核片段尾部（锚点 +4s）带到了入网画面，立哥据此判 J；成品按该碎片锚点 +2s 下刀，球还没投就出画。
  - 实录（20260822_citymonkey 0248）：一回合碎成 e16/e17/e18/e19 四事件，入网 ~190.5s 落在 e17；e16 审核片段放到 190.6s 立哥见球进判 J，成品窗口 182.6~188.6s 在出手前 2s 结束
- **前段类**：长事件（>6s）入网发生在前段、锚点在末尾候选，成品前 4s 切不到审核前段看到的入网。批次 1 实证少见（末成员锚点全中），但不为零

已否决方案：**导出窗口 +2→+4（A 方案）**——立哥定：不想让片段变长；且只要锚点本身错，调窗口是在赌偏移量，前段类照样漏。

## 目标

标注页加**人工锚点**：立哥看审核片段时，在球入网瞬间按 J——**J = 判进球 + 按下时刻即锚点**（一键合一）；**T = 判进球但用机器锚**（兜底，入网瞬间被挡/出画指不准时用）。导出 goals 时人工锚优先，成品窗口围绕真实入网时刻下刀，锚点偏移类漏切连根拔掉。

键位表（变更后）：

| 键 | 语义 | 锚点 |
|---|---|---|
| J | 进球 | **人工**：按下时刻换算原片时间 |
| T | 进球（兜底） | 机器：事件末候选 t0 |
| P | 不收（练习球） | —（不产出片段） |
| F | 不是 | — |

## 非目标（边界）

- **不动检测/候选/聚类/筐轨迹任何上游环节**；事件合并拆碎片的问题不在此治（dedup-same-goal 的提示机制继续兜底）
- **不改剪辑规格**：仍是锚点前 4s 后 2s，片段不变长
- **不改 `build_highlight.py`**：它已消费 goals.json 的 `clip_start/clip_end/anchor_time`，人工锚经导出自然流入
- **不改 P/F 语义与导出口径**；同回合分组提示（dedup-same-goal）对 J/T 一视同仁（都是 goal）
- 不追溯修改已封存的历史 goals.json

## 方案

1. **events_index 带片段原点与续接标志**（`gen_review_clips.py`）：每条事件加两个字段——
   - `clip_src_start` = `max(0, 首成员t0 − CLIP_BEFORE_SEC)`（审核片段的原片起点，round 0.1s）。裁剪视角与全景视角同窗口（两处同公式），一个字段两视角共用
   - `continued` = 是否跨文件续接（`plan_clip_segments` 已知，由 `cut_cluster_clip`/`cut_wide_clip` 透出返回值）：事件窗口越出本文件末尾时片段是两文件拼接，段 2 时间轴归零，linear 换算不成立，必须让页面感知
2. **标注页 J 捕锚**（`gen_label_page.py`）：
   - 模板注入 `__SPEED__`（= `gen_review_clips.SPEED`，模块引用不硬编码；片段已烘焙 2x）
   - J 键与"进球 (J)"按钮同一路径：`source_t = clip_src_start + video.currentTime × SPEED`，**存入 marks 时即 round 0.1s**（`Math.round(a*10)/10`，进度行显示与导出值一致），判定为 goal
   - T 键：判定为 goal，不存 `anchor`
   - **退化路径**（J 静默退化为 T 行为即机器锚，不报错不阻断）：事件缺 `clip_src_start`（旧 events_index）**或 `continued` 为真**（跨文件续接，换算不成立）；continued 事件在进度行提示"跨文件续接，锚点用机器值"
3. **导出换算**：`marks[key].anchor` 存在 → `anchor_time = anchor`，`clip_start/clip_end = anchor ∓ 4/2`（round 0.1s）；不存在 → 照旧用事件 `anchor_t0`。build 校验 `clip_start ≤ anchor ≤ clip_end` 天然满足。同组多 J 确认框文案优先显示人工锚（无则机器锚），避免核对困惑。
4. **页面呈现**：已标人工锚的事件在进度行显示锚点时刻（如 `锚 t=190.5s`）；按键帮助区补 T 键说明。重复按 J 改锚（覆盖）；按 F 清除标记（连带锚）。
5. **localStorage 兼容**：`marks` 合并写逻辑不变，`anchor` 字段随车保存；旧进度（无 anchor 的 goal 标记）导出时走机器锚路径，行为与现状一致。

## 成功标准

- 新生成的 events_index.json 每条事件含 `clip_src_start`（值 = `max(0, 首成员t0 − 2)`，round 0.1s）与 `continued`（布尔，与 `plan_clip_segments` 判定一致）
- 回放验证（20260822_citymonkey 0248 e16）：审核片段放到 ~190.5s 按 J → 导出该球 `anchor_time≈190.5`、`clip_start≈186.5`、`clip_end≈192.5`；按 T → `anchor_time=186.6`（机器锚）与现状一致
- continued 事件验证：跨文件续接事件按 J → 退化为机器锚，导出 `anchor_time` = 事件 `anchor_t0`，进度行有"跨文件续接"提示
- 旧 events_index（无 `clip_src_start`/`continued`）生成的页面：J/T/P/F 全部可用，导出与现状逐字一致
- `ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿；新增单测覆盖：events_index 新字段（含 <2s 钳 0、continued 透出）、build_html 注入/透传、旧事件兼容（JS 侧以模板注入常量断言为主）
- `使用手册.html` 快捷键表同步；100fps 素材慢放分段点随人工锚变准（顺带收益，注明即可）

## 依赖与输入

- `scripts/gen_review_clips.py`（events_index 生成、SPEED/CLIP_BEFORE_SEC 常量来源）
- `scripts/gen_label_page.py`（标注页模板与导出逻辑）
- `scripts/build_highlight.py`（消费方，不改，仅确认校验口径兼容）
- 回放素材：`work/20260822_citymonkey/review_batch1/events_index.json`（0248 e16 实录案例）
