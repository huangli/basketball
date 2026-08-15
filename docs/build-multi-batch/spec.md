# Spec: video build 多批次修复——合并合成 + --all 零命中跳过

## Objective

问题（2026-08-15 立哥实测 `video build --session 20260805_车百鼎 --all`）：

1. **零球批次中止整轮**：_cmd_build 逐批×逐 filter 调 build_highlight；球员某批
   零进球 → build_highlight "无可合成记录" exit 1 → 整个 build 中止
   （黑后卫 b1 零球/b2 六球，第一步即停）。
2. **次生：逐批同名输出互相覆盖**：build_highlight 输出名由 session+filter 决定、
   不含批次——即使不中止，后批会合集会盖掉前批的（多批次 build 从未真正跑通过，
   之前都是单批或手工跑）。

方案（合集口径 = 每球员/队伍每场一个合集、片段按拍摄时间排序）：

- **多批次合并合成**：选中批次 >1 时，先把各批 goals 全记录逐字合并，原子写
  `work/<场次>/goals_merged_cli.json`（`{"session": ..., "goals": [...]}`），
  每个 filter 只调一次 build_highlight。片段由 build_highlight 内部按
  (file, anchor_time) 排序——文件名即拍摄时间戳，跨批排序天然正确。
  选中批次 ==1（含 --batch K）时现状不变。
- **--all 零命中跳过**：展开前预算各球员/队伍在选定批次 confirmed 键集
  （format_key）与 roster.assignments 的交集——零命中 → WARNING 跳过不调用；
  全部零命中 → 报错退出 1。显式 --scorer/--team/无过滤**不预检**（零记录错误
  自下而上冒出，保留 typo 防呆）。
- --dry-run：不写合并文件（命令引用其路径，只打印）。
- 合并文件每次 build 重写（素材流动、goals 会变）；它是 work/ 下中间产物。

成功标准：

- 立哥实测命令 `video build --session 20260805_车百鼎 --all` 跑通：每球员/队伍
  一个合集，含全部三批片段；零命中球员/队伍（如有）WARNING 跳过不中止
- 单批 goals 路径与每 filter 调用次数同现状；--all 零命中跳过对单批同样生效
  （修复意图）；显式 --scorer/--team/无过滤不预检（错误自下而上）
- pytest 全绿（含更新的既有 build 测试）、ruff 干净；四件套齐全

## Tech Stack

只改 `scripts/video.py`（编排层）+ `tests/test_video.py`；build_highlight /
roster.py 零改动；无新依赖。

## 数据契约

- 合并文件 `goals_merged_cli.json`：`{"session": <场次ID>, "goals": [各批全记录
  逐字拼接]}`——不过滤不校验（confirmed 过滤与结构校验是 build_highlight 职责，
  单一校验点不复制）。原子写（pipe_common.atomic_write_json）。
- 命中预算：`_confirmed_keys(goals_path)` 返回 confirmed 记录的 format_key 集合；
  缺 file/anchor_time 的坏记录跳过（留给 build_highlight 报错），不提前炸。
- 零命中判定：tag→keys 映射来自 roster.assignments；球员 = 其 tag 的键 ∩
  known_keys 非空；队伍 = 队内任一球员命中。assignments 里有但 players 里没有的
  tag 不参与逐人展开（现状如此，不动）。

## Code Style

rules.md；video.py 现有编排器风格（Step/run_step/logger.warning）。

## Testing Strategy

- 新增（tests/test_video.py，run_recorder 拦截 subprocess 既有模式）：
  - 多批 --all：两批 goals + roster 全命中 → 每 filter 只调一次、--goals 指向
    goals_merged_cli.json、合并文件已写盘且内容 = 两批逐字拼接 + session 字段
  - --all 零命中跳过：assignments 只给部分球员 → 零命中球员/队伍 WARNING 跳过，
    命令数 = 命中数；caplog 含跳过提示
  - --all 全零命中 → exit 1 且无子进程
  - 单批（--batch K 或只有一批）→ 仍用原批次 goals 路径（现状不变）
- 更新既有：`_goals_payload` 补 anchor_time（命中预算需要）；
  test_all_expands_players_and_teams / test_all_skips_casual_team /
  test_nonzero_stops_exit1 / test_dry_run_executes_nothing 的 roster 夹具补
  assignments（键用 roster.format_key 现算，与 goals 夹具对齐）
- 单批行为不变由未改动的 test_command_verbatim_default / test_batch_filter
  覆盖（"单批不变"仅指 goals 路径与每 filter 调用次数口径；--all 零命中跳过
  对单批同样生效，属修复意图）
- 手工验证（立哥实测）：`video build --session 20260805_车百鼎 --all` 全跑通；
  抽查一个两批都有球的球员（如对7 b1=6/b2=2）合集含 8+ 片段

## Boundaries

- Always：质量门全绿后提交；合并文件原子写；素材/goals 只读
- Ask first：无（零新依赖、零新 CLI 参数；改动限编排层）
- Never：不改 build_highlight / roster.py；不改单批与显式过滤行为；
  不动 output/ 已有产物

## Success Criteria

- [ ] 多批合并合成（每 filter 一次调用、合并文件原子写、dry-run 不写盘）
- [ ] --all 零命中跳过（球员/队伍 WARNING、全零 exit 1）
- [ ] 单批行为不变；既有测试更新后全绿
- [ ] 立哥实测 --all 跑通 + 抽查合集片段数
- [ ] docs/video-cli/spec.md build 节同步 + 使用手册补一句
- [ ] ruff+pytest 全绿；四件套齐全
