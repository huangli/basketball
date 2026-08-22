# Review 07: plan.md + todo.md 审查（2026-08-22）

> 审查员：spec-reviewer 角色子代理（只读审查）。

## 阻断问题与处置

- **B1（进度协议未在 plan 阶段定死，与 spec 矛盾）**：spec 承诺"日志格式约定在 plan 阶段定死"，plan 却留到 C 阶段。
  → 已修：plan.md 新增"进度协议 v1"一节（步骤边界匹配 `执行:` 行 / step_index÷total_steps 估算 / 六种 SSE 事件 / 解析失败降级不定量进度，scripts 侧零改造）。
- **B2（O4 时间线矛盾）**：A 阶段立即迁移 vs spec"在途功能完成后再整体迁移"。
  → 已修：plan 文头写明 A 启动前提 = 立哥宣布在途功能完成（SP 不碰 scripts 不受约束）；风险表新增漂移对策（A 取最新快照后现工作区 scripts 冻结，新功能只进新仓库）。

## 非阻断建议（已吸收）

- A-2 拆为 A-2a（scripts 迁移）/ A-2b（tests 脱敏）两任务。
- SP-2 Verify 报告落盘位置明确为现工作区 `docs/basketball-clip/spike-report.md`（spike 先于新仓库存在）。

## 已核对无问题项

spec 承诺全覆盖无漏项；依赖顺序合理；todo 任务带 Acceptance/Verify/Files。
