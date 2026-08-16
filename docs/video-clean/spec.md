# Spec: video clean——清空工作区（output + work + 源视频）等待下次视频

## Objective

立哥 2026-08-15 定：加 `video clean` 子命令，一键把工作区恢复到全新状态——
清空 `output/`、`work/`、源视频目录，等待下次视频。

已定口径（AskUserQuestion 确认）：

- **全部清空**（不分场次）：output/ 全部内容 + work/ 全部内容 + 源视频目录
- **列清单 + 输入 yes 确认**；支持 --dry-run 只看清单不动手

安全设计（删源视频不可恢复，鲁棒优先）：

- 源视频目录从各场次 `work/<场次>/video_cli.json` 的 srcdir 收集（**在清 work
  之前先读**）；无 state/srcdir → WARNING 跳过源视频删除（不猜路径）
- 守卫（任一不满足 → 拒绝删该目录并 WARNING，继续其他目标）：
  - srcdir 解析后 ≠ 仓库根，且仓库根不在 srcdir 之下（防指向祖先目录）
  - srcdir ≠ 盘符根（`srcdir.parent == srcdir`）
  - srcdir 必须实际存在且是目录
- output/ 与 work/ **只清空内容、保留目录本身**（CLI 与后续流程假定它们在）
- 只动这三个目标；仓库其他一切（scripts/models/docs/archive/tests/resource/
  .git/根目录文件）不碰
- 非交互环境（stdin 不是 tty）且非 --dry-run → 拒绝执行退出 1（防后台挂起
  在 input()）
- 确认词精确匹配 `yes`；其他任何输入 = 放弃，不动任何文件，退出 0（并提示未动）

输出清单：逐条列 路径 + 总大小（GB 保留两位）+ 文件数；删除后报释放空间。

成功标准：

- `video clean --dry-run` 只列清单不写盘不删文件
- `video clean` 列清单 → 输入 yes → output/work 内容清空（目录保留）+ 源视频
  目录整目录删除 → 报释放空间；输入其他 → 什么都不动
- 守卫生效：srcdir 指向仓库根/盘符根/不存在 → 拒绝且 WARNING，其余目标照常
- pytest 全绿、ruff 干净；四件套齐全

## Tech Stack

只改 `scripts/video.py` + `tests/test_video.py`；标准库 shutil/rmtree；无新依赖。

## 数据契约

- 目标清单结构：三个分组（output 内容 / work 内容 / 源视频目录），每条
  (path, size_bytes, n_files)；size/文件数用 os.scandir 递归统计，
  统计失败（权限等）记 WARNING 并按 0 展示，不中断
- 删除顺序：先 output 内容 → 再 work 内容 → 最后源视频目录（srcdir 已在
  最前收集好）；单个目标删除失败记 ERROR 继续其余，结尾汇总，有失败退出 1

## Code Style

rules.md；video.py 现有编排器风格（argparse 子命令 + logger + 显式失败）。

## Testing Strategy

- 新增 tests/test_video.py TestClean（tmp_path 造 output/work/素材目录 +
  video_cli.json；monkeypatch input/builtins）：
  - dry-run：列清单、零删除（目录与文件原样在）
  - 确认 yes：三分组内容清空、output/work 目录本身保留、源视频目录消失、
    返回 0
  - 确认词非 yes（如回车/"y"）：零删除、返回 0
  - 无 video_cli.json（无 srcdir）：WARNING 跳过源视频，output/work 照常清
  - 守卫：srcdir=仓库根 / srcdir 不存在 → 拒绝该目标 WARNING，其余照常
  - 非 tty 且非 dry-run → 退出 1 不删任何东西
- 不真删仓库文件——所有用例在 tmp_path 内造目录树（chdir + WORK_ROOT 相对
  解析沿用既有 fixture 模式）
- 手工验证（立哥实测）：`video clean --dry-run` 看清单 → 真跑前确认清单内容

## Boundaries

- Always：清单先行、yes 精确确认；删除逐目标容错（单点失败不拖垮其余）；
  质量门全绿后提交
- Ask first：无（立哥已明确范围与确认形式）
- Never：不动 output/work/源视频以外的任何路径；不删 output/work 目录本身；
  无 --yes 免确认开关（本期不做）；不重试已删文件

## Success Criteria

- [ ] clean 子命令（清单 + yes 确认 + dry-run + 守卫 + 容错汇总）
- [ ] 测试 6 条全绿；既有测试不回归
- [ ] 使用手册.html 补 clean 一节；docs/video-cli/spec.md 命令清单同步
- [ ] 立哥 dry-run 实测
- [ ] ruff+pytest 全绿；四件套齐全
