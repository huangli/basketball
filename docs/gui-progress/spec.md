# Spec: GUI 检测百分比进度（进度协议 v1.1）

> 2026-09-05 立哥批准。小功能，四件套从轻。代码改动在新仓库 `C:\Code\basketball_clip`。

## Objective

检测（score）任务在 GUI 向导里从"不定态转圈"升级为**近似百分比进度**。
普通用户跑几小时的检测时，能看到"跑到哪了"，而不是干等。

依据：底层检测脚本本就每 200 帧输出帧级进度日志（`mot_candidates.py:690`
`检测进度: <fid> 第x/y帧`），分子分母齐全，runner 只需加解析规则，**scripts 零改动**。

## 设计（进度协议 v1.1，在 v1 上增量，六种事件不变）

- runner 新增帧进度解析：匹配 `第(\d+)/(\d+)帧` 行 → 发新事件 `frame_progress`
  （字段：fid / frame / total_frames / overall_pct）。
- **分母注册（续跑/缓存命中口径，review01 修订）**：`mot_candidates.py:669` 对每个
  fid（含命中缓存的）都输出 `=== <fid> (<N>帧) ===`，runner 解析该行**提前注册全部
  分母**（总帧数求和）；`:675` 的"命中缓存"行 → 该 fid 瞬时计入分子（视为完成）。
  如此断点续跑时已缓存 fid 进分子也进分母，百分比不失真。
- overall_pct 计算口径：各 fid 总帧数求和为分母，已完成（含缓存命中）fid 的总帧 +
  当前 fid 当前帧为分子；**展示值单调不减**。已知近似：多 fid 并发未注册完前首个
  fid 阶段百分比按已知分母计，可能虚高，属"近似"既定口径。
- 未见任何帧进度行时行为与 v1 完全一致（降级转圈）。
- 前端：检测步进度区显示"约 N%" + 当前 fid 的 x/y 帧；无帧进度时维持原不定态。

## Commands

```powershell
C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m pytest -q   # 全绿
python -m ruff format scripts tests gui && python -m ruff check --fix scripts tests gui
C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m gui          # 冒烟
```

## Project Structure

- `gui/runner.py`：帧进度解析 + frame_progress 事件（协议 v1.1）
- `gui/static/app.js`：进度区渲染百分比
- `tests/gui/test_runner.py`：帧进度事件用例
- 文档：本目录四件套（旧工作区，私人决策记录不进新仓）

## Code Style

同仓库 rules.md：类型标注、docstring 说明失败行为、显式失败不静默、无魔法值
（帧进度正则与间隔常量为具名常量）。

## Testing Strategy

- runner 单测（FakeProcess）：喂 `检测进度: 0030 第1200/3600帧` 等行序列 →
  断言 frame_progress 事件字段与 overall_pct 计算、单调不减、无帧行时不发该事件
- 浏览器冒烟 1 条：真实页面注入帧进度日志，百分比正常渲染
- 存量 pytest/ruff 全绿不破

## Boundaries

- Always：质量关口全绿；协议 v1 六种事件与字段契约不破坏
- Ask first：改 scripts/ 任何行为（本功能不需要）
- Never：为进度给 scripts 加改造；静默吞解析异常（解析失败=不发事件，不报错）

## Success Criteria

1. 检测任务运行时前端显示近似百分比，随帧推进单调不减；**续跑（缓存命中）场景下
   已缓存 fid 计入分子与分母，百分比不因此失真**；首 fid 阶段按已知分母计的虚高
   属既定近似口径
2. 非检测任务（people/build/photo）进度行为不变
3. 新增测试全绿（含"缓存命中 fid + 新检 fid 混合"用例），存量 1088 不破
