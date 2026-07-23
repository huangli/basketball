# 实施计划：篮筐 ROI 检测 + 技术统计（v3.1，试点 50 文件）

## 概述

按设计文档 `docs/superpowers/specs/2026-07-20-hoop-roi-detection-design.md`（v3.1，已过 spec-reviewer 审查修订）重建检测阶段：每文件标定篮筐（`work/hoops.json`）→ 原片 crop 2fps 粗扫 → 候选窗口 10fps crop 精判（confirmed/attempt/rejected/uncertain 四选一）→ **uncertain 用户定夺门禁** → 全画投篮者帧 → 花名册（G1 门禁）→ 标注 points/assist → 技术统计.csv。试点 = 文件名序前 50 个 MP4（含 ground truth 0005~0010），验收达标后推全量 115。**attempt（出手未中）是一等事件**：不进成片，但是命中率/出手数的数据源。抢断、正负值不做（用户已排除）。

## 架构决策

- **一切看图均在原片篮筐 crop**（near S=1500 / far S=900）；tile/拼图一律 ≤~2000px（标定 cell 480×360=×8 倍率，唯一口径，meta.json 落盘防漂移）
- **tile 滤镜丢尾防线**：所有拼图输入补齐 12 的倍数；精判窗 t±2.7s=54 帧整除 + `-frames:v 6` 强制恰 6 张（win_end clamp 到文件时长，win_start 文件名 round 0.1s）
- **唯一落盘路径**：AI 子批只产批级 JSON，主控串行运行落盘脚本合并，禁止并行直接写 goals.json；同 file+hoop 候选 |Δt|<3s 合并防多窗一球双计，统计前 anchor<2s 报警复核
- 旧 goals.json 归档 `work/goals_v2_archive.json`；新 goals.json 为 v3（v2 字段保留 + `result`/`points`/`assist_label`/`hoop_id`/`source`/`note`）
- **投篮者帧 1600×1200×3**（anchor-3/-2/-1），一帧三用：认人 / 判 1·2·3 分 / 判助攻；快攻长传盲区为已知口径下限，报告 assist null 占比
- **花名册覆盖出手者 + 可辨识传球者**（否则助攻无处可记）
- **音频峰值只兜底进球召回**（峰值 ±5s 无任何记录 → 对全部未 dropped hoop 补精判，`source=audio`），不单独产生记录
- AI 目检子批执行（粗扫 ≤10 文件/批、精判 ≤50 候选/批），子代理并行（仅目检与产 JSON），429 限流则串行重试
- 阶段 3~5（剪辑/合成/验证）规格不动；编码器取 `work/file_inventory.json` 头部决策（本次 libx264）；试点不执行阶段 3 剪辑

## 依赖图

```
T1 试点初始化（归档+50清单）
└→ T2 标定帧脚本 → T3 AI标定 hoops.json【含抽验复标】
    ├→ T4 粗扫脚本(+落盘脚本扩展) → T5 AI粗扫候选（5子批）→ T7 精判脚本(+判定落盘脚本) → T8 AI精判（分批）
    │                                                                                        └→ T8.5 uncertain 用户定夺【门禁】
    └→ T6 音频峰值（与 T4/T5 并行）→ T9 音频兜底补判（T8 后）─────────────────────────────┐
T8.5 + T9 ─→ T10 投篮者帧 → T11 花名册【G1】→ T12 标注 → T14 统计+报告
T13 召回金标准（T8 后，与 T9~T12 并行；gold 用户确认后生效）→ T14
```

T14 内 SPEC.md/AGENTS.md 更新后必须派 spec-reviewer 子代理审查（AGENTS.md 强制）。

## 任务清单（详见 tasks/todo.md）

| # | 任务 | 规模 |
|---|------|------|
| T1 | 试点初始化：归档旧 goals.json、生成 `work/pilot_files.json` | S |
| T2 | `build_hoop_calib.py`：标定帧 + sheet（补 12 倍数 + meta.json） | S |
| T3 | AI 标定 `work/hoops.json` + 抽验复标 | M |
| T4 | `build_roi_scan.py` + 扩展 `goals_append.py`（v3 字段、串行合并、去重） | S |
| T5 | AI 粗扫锁候选（5 子批，子代理产 JSON，主控串行落盘） | M |
| T6 | `build_audio_peaks.py`：音频峰值 + 阈值标定（0007+1~2 对照） | S |
| T7 | `build_roi_fine.py`（三模式）+ 新建 `goals_judge.py` | S |
| T8 | AI 精判四选一（分批，子代理） | L |
| T8.5 | 【门禁】uncertain 全部经用户定夺改判 | S |
| T9 | 音频兜底补判（`build_audio_recheck.py` + 复用 T7/T8） | S |
| T10 | `build_shooter_frames.py`：投篮者帧 1600×1200 | S |
| T11 | 花名册归并（含传球者）→【G1 用户确认】→ 回填 | M |
| T12 | AI 标注 `points` / `assist_label` | M |
| T13 | 出手召回金标准（2 个长文件，gold 用户确认） | M |
| T14 | `build_stats.py` + 试点报告 + SPEC/AGENTS 更新 | M |

## 风险与对策

（检测层风险沿用设计文档 §5，此处为执行层补充）

| 风险 | 对策 |
|---|---|
| 子代理 429 限流 | 串行重试、缩小子批；已有批级 JSON 落盘可续 |
| 并行写 goals.json 竞态 | 唯一落盘路径（主控串行合并），子代理禁写 |
| 标定倍率用错（×6/×8 漂移） | 唯一口径 480×360 ×8 + meta.json 落盘 + verify 反推抽查 |
| tile 丢尾吞尾部内容 | 拼图输入补 12 倍数；精判 `-frames:v 6` 强制 |
| 标定误差（图内 ±15px ≈ 原片 ±120px） | T3 抽验门禁：筐心在 crop 内且距边 ≥10%S，不符重标 |
| 峰值不知球进在哪端筐 | T9 对全部未 dropped hoop 补窗，AI 看哪端有球，按展开计数对账 |
| 召回金标准 AI 自证 | gold 清单（附 tile 索引）用户全量确认后才生效 |
| 试点文件边界（anchor<3s、win 超文件时长） | clamp + 按实际张数出片并列清单 |

## 待确认问题

- 门禁 1（T8.5）：uncertain 清单定夺
- 门禁 2（T11/G1）：试点场次 20250419 花名册确认
- 门禁 3（T13）：召回 gold 清单确认
