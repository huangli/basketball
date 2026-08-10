# review01：batch-speedup spec 第 1 轮（spec-reviewer）

日期：2026-08-10　审查方式：spec-reviewer 子代理（plan 型，只读）
判定：**有阻断问题（4 条）** → 已全部修订

## 阻断与处置

### B1. F2 阶段⑥漏 --keep-clips → 已修
- 问题：不带 --keep-clips 时 gen_review_clips 只产拼接视频、不产
  events_index.json 与单事件 clips（gen_review_clips.py:802、844-853），
  下游页面全断粮；dry-run 对照的历史命令均带该参数。
- 处置：阶段⑥清单补上 `--keep-clips` 并加粗后果说明。

### B2. F1 未规定"墙不得覆盖已有标注" → 已修
- 问题：只写"只能否"，没说已标事件（尤其历史 J）在墙侧的行为；误点 F
  会把 confirmed 球改写成 {r:"no"}，导出只收 goal/practice → 静默丢球。
- 处置：F1 硬规定 2——渲染/点击以 localStorage 实时值为准，已标事件
  展示标注 + F 按钮禁用，只允许对未标事件写 {r:"no"}。

### B3. F1 未规定合并写语义 → 已修
- 问题：label.html 的 save() 是刻意的先读合并再写（防多页互覆盖，
  gen_label_page.py:155-160）；triage 朴素回写会用旧快照覆盖 label 侧。
- 处置：F1 硬规定 3——合并写复刻 + 绝不写 LSKEY_pos 位置键。

### B4. 成功标准 4"尺寸不匹配检测"无设计支撑 → 已修
- 问题：探测结果不落盘，续跑时无基准可比对，标准成死条款。
- 处置：阶段①落盘 work/<session>/session_facts.json，续跑重探测比对，
  不一致即 WARNING 终止（--force 除外）；成功标准 4 改为篡改 facts 表注入。

## 建议项（8 条全部采纳）

降级口径（大疆尾截短合法降级）、映射单点公共函数、extract_frames 粒度
如实呈现、阶段⑦显式 --index/--session、④ fid 覆盖核对、残次事件
跳过+WARNING 对齐、成功标准 2 机检口径、--fids → adhoc 固定命名。

## 核对通过的关键前提（审查方核实，plan 采信）

- 帧号映射成立：f_00001 ↔ t=0（mot_candidates.parse_sec: `sec=(idx-1)/5`），
  spec 反函数 `round(t×5)+1` 正确；anchor_t0 按 0.1s 存储的 ±1 帧舍入
  误差在 ±2 帧窗口内可吸收
- marks 结构兼容：{r:"no"} 与 label.html 的 show/stats/jumpUnmarked/export
  全部兼容
- 老脚本 CLI 默认值坑均可显式传参绕过（mot 默认旧测试 fid、pilot 默认
  work/pilot 旧路径、detect_hoops 无默认、gen_review_clips --srcdir/--orig/--hoops）
