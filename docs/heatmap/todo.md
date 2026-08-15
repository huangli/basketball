# todo：进球热区图 · 阶段 0 标定验证

依据：spec.md（review01/02 通过）+ plan.md（P1-P4 决策点写死）

**状态（2026-08-15 收尾）：Task 1 完成，Q2 实测 77/122 = 63.1% < 70% 门槛
→ 按 spec 预先写死的判据功能证伪。Task 2/3/4 未启动（Q2 未过关 → 整体搁置，
立哥人工点位按门禁短路省去），Task 5 证伪分支已记档（docs/经验教训.md §8）。**
实测细节：`work/20260805_车百鼎/release_probe.json`（未命中 45 = 无稳定段 43
+ 球心不落人框 2；一致性抽查 5/10；P3 任一 39% 超提示线；另发现逐帧
max-conf 取球会被场边静止闲置球抢走的假命中，已记经验教训）。

**全局质量门**：每个代码 Task 提交前必过 `ruff format scripts tests &&
ruff check --fix scripts tests && pytest -q`（--fix 后复核 diff）。
**人工门禁**：Task 2 的"立哥点关键点"与 Task 4 的汇总，必须等 Task 1 的
Q2 报告出炉且 ≥70% 过关后才启动；机器开发不受此限。

- [x] Task 1：`scripts/release_probe.py` + 单测（Q2 回溯成功率，纯只读）
  - 结果：122 球全量跑通；release_probe.json 落盘；**覆盖率 63.1% 未过关**；
    一致性抽查 5/10 ≤100px；质量门全绿（27 新单测 + 全量回归）
  - Acceptance：122 球全量跑通；release_probe.json 落 work/20260805_车百鼎/；
    控制台报告覆盖率/断帧分布/P3 分层；缺缓存与球心不落人框均计未命中入分母；
    一致性抽查 10 球 ≤100px
  - Verify：ruff + pytest 绿（合成轨迹：稳定/瞬移/断帧/多段取末段/缺缓存）+ 实跑出报告
  - Files：scripts/release_probe.py、tests/test_release_probe.py
- [ ] Task 2：`scripts/gen_calib_page.py` + 单测（Q1 标注工具）**未启动（Q2 未过关证伪，门禁短路）**
  - Acceptance：分层抽样 ≥10 事件（左右端×远近×片段×变焦档）；页面自包含、
    ≥5 点位引导、localStorage、导出 calib.json（P4 schema）
  - Verify：pytest 绿 + node --check + 浏览器实点 1 事件
  - Files：scripts/gen_calib_page.py、tests/test_gen_calib_page.py
- [ ] Task 3：`scripts/calib_eval.py` + 单测（Q1 精度评估）**未启动（门禁短路）**
  - Acceptance：image→court 米制单应 + 留一法折内最小二乘逐点评估；
    混合中位 + P90；单点 >2m 记 WARNING；calib_eval.json 落
    work/20260805_车百鼎/
  - Verify：ruff + pytest 绿（合成单应误差≈0 / 扰动上升）+ 合成 fixture 端到端
  - Files：scripts/calib_eval.py、tests/test_calib_eval.py
- [ ] Task 4：双门槛汇总 + `docs/heatmap/calib-report.md` **未启动（Q1 未做，无双门槛可汇总；结论以经验教训 §8 记档）**
  - Acceptance：报告含双判据实测值 vs 阈值、P3 分层、抽样偏差、尺度锚定
    假设注明（FIBA 默认/非标放宽）、米制评估口径溯源、明确立项/证伪结论
  - Verify：spec-reviewer 审报告通过
- [x] Task 5：文档联动（立项→research.md 状态 + 阶段 1 新四件套；
  证伪→经验教训.md 记档）**证伪分支完成：`docs/经验教训.md` §8 两条记档**
  - Verify：联动文档过 spec-reviewer；全部提交
