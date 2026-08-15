# Review 01: 审查存档——video build 多批次修复

- 范围：ae162f4..0c330ae（ed7df83 合并合成+零命中跳过 / 93865e6 合并文件改名 / 0c330ae except 补括号）
- 审查方式：spec/plan 预审（Ready=No→吸收 B1-B3）+ 任务级 spec+质量双审查 + 文档同步 spec-reviewer（2026-08-15）
- 结论：**Approved**（修复后无 Critical / 无 Important）

## spec 预审修订（plan 阶段吸收）

- B1：_confirmed_keys 漏捕 ValueError（str anchor_time 走 f"{t:.1f}" 抛 ValueError 而非
  TypeError）——契约级鲁棒缺口，已补三异常捕获
- B2/B3：plan 文档数字错误（预期命令数 3→4 条；RED 预期失败计数 6→实际 5，
  dry-run 防护测试旧代码下天然 PASS）——已改准
- 建议吸收：零命中队伍 WARNING 去重（warned_teams）；单批不变口径写明
  "仅指 goals 路径与调用次数"

## 任务级审查核实要点

- E1-E5 与 plan 逐字一致；单批 else 分支逐字不变；显式 filter 不预检
- 零命中判定 hit_tags / warned_teams 正确；全零 exit 1 且无子进程
- dry-run 不写合并文件（双重防护测试：禁子进程 + 不落盘）
- 合并文件逐字拼接过 build_highlight _validate_goals（真实 goals_batchN 字段齐全）；
  排序 (file, anchor_time) 跨批天然正确（文件名即时间戳）
- 合并文件改名 merged_goals_cli.json 撤出 discover_batches 的 goals*.json glob——
  消除"无法识别的 goals 文件" WARNING 噪音（实现者自首的疑虑，改根因不打补丁）

## 审查插曲（留档）

- 任务审查曾报 "except 缺括号 = 模块级 SyntaxError" Critical——**误报**：PEP 758
  （Python 3.14）允许无括号多异常 except，ast.parse/py_compile/全量测试实证合法。
  但无括号形态易误读（本项目 3.14-only，仍按惯例补括号，0c330ae）。
  教训：审查者用旧版本语法知识下致命结论前，应先跑一次 import/编译验证。
- 另遇并行会话疑似 git restore 把工作区改动冲掉一次（paren 修复首次提交落空），
  重应用后立即提交成功——并行会话同 repo 工作区的已知风险。

## 文档同步

- docs/video-cli/spec.md build 节：多批次合并合成 + 零命中跳过 + 显式不预检
  （spec-reviewer PASS-WITH-WARNINGS，两条手册措辞建议已吸收）
- 使用手册.html 第 4 步：多批自动合并/零命中跳过（含队伍与全零 exit 1）/--batch 单批不合并

## 放行条件

- 立哥实测：`video build --session 20260805_车百鼎 --all`（先 --dry-run 看展开），
  抽查跨批球员（如对7 b1=6/b2=2）合集片段数
