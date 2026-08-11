# review07：triage 扫尾墙功能下线（立哥拍板）

日期：2026-08-11　审查方式：立哥决策 + 主会话执行 + spec-reviewer 复审
判定：**下线完成**

## 决策

立哥实操 triage 墙三轮（全景缩略图 → 筐区裁剪 → 悬停视频墙，见
review05/06）后拍板：**功能下线，"有点重复功能了"**——墙的"快速否垃圾"
与 label.html 的"逐条放视频判"在使用感上重叠，两轮迭代后省时收益
仍不抵多开一个页面的成本。

## 下线范围

- 删除 `scripts/gen_triage_page.py`、`tests/test_gen_triage_page.py`
  （git 历史留档，如需找回查 commit cc4195e 之前）
- `run_session.py` ⑦ 步移除 triage 命令（每批 7→6 条），`_stage_done`
  阶段⑦ 断点判定只查 label.html；文件头同步
- `tests/test_run_session.py` 断言同步（命令数 7→6、⑦ 仅 label 页）
- spec.md F1 节加下线标记（内容留档）；AGENTS.md 流水线描述去掉 triage
- 未落地的"clip_wide 全景优先"改动随删除废弃（立哥选全景后随即拍板下线）

## 保留不受影响的部分

- **F2 编排器（run_session.py）继续服役**：批次 4 起新场次仍一键串联
  至 label.html；F1 配套的 `pipe_common.sec_to_frame_idx` 已随下线删除
  （复审确认无任何生产调用方，纯死代码）
- 已生成的 `work/20260722/review_batch3/triage.html` 与 `thumbs/` 由
  主会话删除（中间产物，防误用旧页）
- 立哥的 dry-run 命令等价性验收项仍有效（F2 范围）

## 教训（供经验教讪文档收录）

- **新交互页面先出最小可用版给立哥试手感，再迭代**——本轮三轮迭代
  （静态全景→裁剪→视频）都是在补"判读可行性"，而根因是墙与标注页的
  分工本身就不成立；若第一版就让立哥对比"墙否 vs 标注页直接否"，
  可省两轮返工
- "只能否不能是"的安全设计同时限制了墙的价值上限：能否的场景在
  标注页也一样快，墙没有独占价值

## 验证

- pytest 全绿（用例数随测试文件删除回落）、ruff format/check 全绿
- `run_session.py --dry-run` 重跑：每批 6 条命令、⑦ 仅 label.html
