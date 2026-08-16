# Review 01: 审查存档——video clean

- 范围：4bf769e..9225bc7（单提交）+ Task 2 文档同步
- 审查方式：spec/plan 预审（Ready=No→修订）+ 任务级 spec+质量双审查 Approved + 文档同步 spec-reviewer PASS-WITH-WARNINGS（2026-08-15）
- 结论：**Approved**（无 Critical / 无 Important）

## spec 预审修订（plan 阶段吸收）

- **B1（阻断，已修）**：srcdir 守卫方向写反——`REPO_ROOT in p.parents` 判的是
  "srcdir 在仓库根之内"（合法子目录被误杀），而要拒的是"srcdir 是仓库根的祖先"
  （rmtree 会连仓库一起删）。已修 `p == REPO_ROOT or p in REPO_ROOT.parents`。
  当前布局下仓库根唯一祖先是盘符根、恰被盘符根守卫兜住，属潜伏洞——鲁棒优先
  原则下预审拦截价值就位
- B2：Self-Review 行数声明过期（并行会话动过文件），改措辞"以当时文件为准"
- 建议吸收：清单统计 OSError 按 0 展示不中断；_tree docstring 与代码对齐

## 任务级审查核实要点

- E1-E4 与 plan 逐字一致（ruff format 折行仅排版）；6 条测试与实现逐条吻合
- 守卫方向/盘符根/不存在三条逐一推演正确；symlink 删除兜底（is_symlink → unlink
  不穿透 rmtree 目标）
- 收集 srcdir 在清 work 之前；plan 列表只含 output/work 子项与过守卫 srcdir
- 测试隔离安全：main(relocate=False) 不 chdir，六用例全部 tmp_path 沙箱
- 非 tty 检查在 input() 之前返回，管道环境不会挂起

## 文档同步

- docs/video-cli/spec.md：命令清单 + §clean 小节（范围/确认/守卫/dry-run/容错）
- 使用手册.html：命令表 clean 行 + .warn 警告框（不分场次、成品一起删、
  发出去前别 clean）+ 素材目录行口径更新——spec-reviewer PASS-WITH-WARNINGS，
  两条措辞建议（全场次口径、警示醒目度）已吸收

## 已知行为（不修，留档）

- 空 plan 早退排在非 tty 检查前：非 tty + 工作区已空时 rc=0 而非 1（plan 原文顺序）
- _dir_stats 对 symlink 漏统计（仅清单展示偏小，spec 允许）
- read_json 的 OSError 重试退避（0.5+1+2s）：state 不可读时 clean 卡顿数秒，可接受

## 放行条件

- 立哥实测 `video clean --dry-run` 看清单；真删由他亲自跑
