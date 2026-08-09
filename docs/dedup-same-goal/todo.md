# todo：标注页同球双 J 自动识别

## Task 1：分组纯函数 + 单测

**Description：** 在 `scripts/gen_label_page.py` 新增纯函数：输入同 fid 事件列表（anchor_t0 升序），相邻事件窗口 `[anchor_t0 − CLIP_BEFORE_SEC, anchor_t0 + CLIP_AFTER_SEC]`（常量引自 gen_review_clips，写全模块路径）重叠即同组，传递闭包合并；输出每事件组号（无重叠为 None）。

**Acceptance criteria：**
- [x] 无重叠事件各自独立（组号 None）
- [x] 两两重叠归同组；传递闭包三事件（A 叠 B、B 叠 C）同组
- [x] 跨 fid 事件绝不混组；单事件输入正常返回

**Verification：**
- [x] `python -m pytest tests/test_gen_label_page.py -q` 新增 5 用例全过（另加两组编号用例共 6 个，commit dfcf697）

**Dependencies：** None
**Files likely touched：** `scripts/gen_label_page.py`、`tests/test_gen_label_page.py`
**Estimated scope：** S（1-2 文件）

## Task 2：批次 3 回放验证

**Description：** `work/` 下一次性脚本：对 `work/20260722/review_batch3/events_index.json`（全部 234 事件）跑 Task 1 分组函数，对照 `20260722地平线/goals_20260722_3.json`（61 J 原始导出）断言。脚本注释须注明：两条跨文件反例（203918/203928、205204/205158）在"仅同 fid"规则下由构造保证不并，0 误分组的真正考验是同文件 42 个独立球——防二期做跨文件时误读该断言含义。

**Acceptance criteria：**
- [x] 8 组同球对全部命中同组（200730/200854/201604/201718/203946/204746/205942/210152，anchor 差 2.3~4.2s）
- [x] 0 误分组 = 任意两个 confirmed J 不同组（真两球 203918/203928、205204/205158 由仅同 fid 构造保证）；42 独立球中 9 个与非 J 邻事件同组属正确提示（2026-08-09 实测，帧图抽查佐证，口径修订见 spec 成功标准）

**Verification：**
- [x] 回放脚本运行输出两组断言全 PASS（脚本落 `work/`，不入库）：234 事件 → 111 入 48 组；8 组全命中；0 漏网双 J

**Dependencies：** Task 1
**Files likely touched：** `work/dedup_replay_check.py`（一次性，豁免 rules.md）
**Estimated scope：** XS（1 文件）

## Checkpoint：Task 1-2 完成 = 分组规则可信，失败回 Task 1，不进 Phase 2

## Task 3：同组卡片视觉分组

**Description：** gen_label_page.py 生成页面时把 Task 1 的组号内联进事件数据；同组事件加同色标识（组号→4 色轮换）+ 标签"疑似同回合（组 N，共 M 个）"。注意现行标注页是单事件翻页器（show(i) 一次一事件，无卡片网格），标识落点（进度行/verdict 区/video 容器边框）以实现时页面结构为准。不动 J/P/F 按键逻辑与断点续标。

**Acceptance criteria：**
- [x] 同组事件可一眼识别（同色标识 + 组标签，落点不限）——代码完成；页面级验证批次 3 events_index 生成 html 中 200730 两事件均注入 grp=43/grp_size=2、组标签元素在位；**立哥 2026-08-09 无痕窗口验收通过**
- [x] 无组事件页面呈现与现状一致（无回归）——测试覆盖（不成组事件无 grp 字段）
- [x] 断点续标（刷新回到上次位置）功能不受影响——review03 核实该 JS 逻辑未动

**Verification：**
- [x] 批次 3 events_index 生成 html 核对组呈现（元素+数据注入在位；页面观感 2026-08-09 立哥无痕窗口验收通过）
- [x] `pytest -q` 全绿

**Dependencies：** Task 1（Checkpoint 通过后开工）
**Files likely touched：** `scripts/gen_label_page.py`、`tests/test_gen_label_page.py`
**Estimated scope：** M（页面模板 + 测试）

## Task 4：导出前置确认框

**Description：** 导出 goals 的 JS 逻辑（exportGoals）加前置检查：同组 ≥2 个 J 时 confirm() 列出组内事件时间与文件名，"同一球"→ 阻止导出并提示改判；"两个球"→ 放行。选择不持久化，每次导出都问。

**Acceptance criteria：**
- [x] 同组 2 J 弹确认且两条路径行为正确（阻止/放行）——实现经 review03 逐行核对（确定=两个球放行 / 取消=同一球阻止）；**立哥 2026-08-09 验收通过整体页面**（验收主走 label-speedup 的组内 J 确认跳过路径；导出兜底弹窗未单独构造场景，行为有 review03 逐行核对 + 单测兜底）
- [x] 同组 1 J 或无组时不弹窗，导出行为与现状一致——issues 过滤 `length >= 2` 保证
- [x] 导出 JSON 结构与现行 schema 完全一致（file/anchor_time/clip_start/clip_end/status/scorer）——导出字段未动，review03 逐字段核对

**Verification：**
- [x] 人工验收：立哥 2026-08-09 无痕窗口实操通过（组标签可见、组内 J 弹确认、确定后同组标 F 并跳过）
- [x] `pytest -q` 全绿

**Dependencies：** Task 1（Checkpoint 通过后开工；可与 Task 3 并行）
**Files likely touched：** `scripts/gen_label_page.py`
**Estimated scope：** S（页面内 JS）

## Task 5：关口与交付

**Description：** 全量质量关口与提交。

**Acceptance criteria：**
- [x] `ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿（--fix 后复核 diff）
- [x] spec 成功标准逐条核对结果回填 review（review03：1 处口径表述阻断已修订，建议项全采纳）

**Verification：**
- [x] 关口命令输出全绿；commit 完成

**Dependencies：** Task 2、3、4 全部完成
**Files likely touched：** 无新增
**Estimated scope：** XS

## 生产观察（下一批次）

- [ ] 下一生产批次同球双 J ≤1 例，结果回填本文件与 review
