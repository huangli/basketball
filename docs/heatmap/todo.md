# todo：进球热区图 · 阶段 0 标定验证（v2 修订）

依据：spec.md v2（review05/06 通过）+ plan.md v2（门禁口径沿用写死）

**v1 状态（2026-08-15 已收尾）**：v1 Task 1 完成，稳定段法 Q2 实测 63.1% < 70%
→ 证伪记档（经验教训 §8）；v1 Task 2/3/4 门禁短路未启动。release_probe.py
留档不删（复算依据）。
**v2 状态（2026-08-15 已收尾）：Task 1 完成，轨迹法新 Q2 实测 68/122 = 55.7%
< 90%（≥110）→ 再次证伪，经验教训 §8 追加记档；Task 2/3/4 门禁短路未启动。
死因：球检测器看不到手上的球——52 球 fallback、56/68"真持球"定位帧在锚点后
（入网后持球），合理出手窗仅 10 球。scorer_landings.py 留档（复算依据）。**

**全局质量门**：每个代码 Task 提交前必过 `ruff format scripts tests &&
ruff check --fix scripts tests && pytest -q`（--fix 后复核 diff）。
**人工门禁**：Task 2 的"立哥点关键点"与 Task 4 的汇总，必须等 Task 1 的
新 Q2 报告出炉且 ≥90% 过关后才启动；机器开发不受此限。

- [x] Task 1：`scripts/scorer_landings.py` + 单测（新 Q2 轨迹法定位成功率，纯只读）
  - 结果：122 球全量跑通；scorer_landings.json 落盘；**成功率 55.7% 未过关**；
    11 新单测 + 全量回归绿
  - Acceptance：122 球全量跑通；scorer_landings.json 落 work/20260805_车百鼎/
    （SKIP 写死 frame_idx=-1/sec=-1.0/null 字段不省略）；控制台报告成功率
    分 reason 分层；start_fallback/SKIP/缺缓存均计未命中入分母
  - Verify：ruff + pytest 绿（合成用例：真持球/fallback/no_track_near_anchor/
    缺缓存/SKIP 形态/锚点超差退化）+ 实跑出报告
  - Files：scripts/scorer_landings.py、tests/test_scorer_landings.py
- [ ] Task 2：`scripts/gen_calib_page.py` + 单测（Q1 标注工具）**未启动（新 Q2 未过关证伪，门禁短路）**
  - Acceptance：从可用落点球（OK 且非 start_fallback）分层抽样 ≥10 事件
    （左右端×远近×片段×变焦档，每档 ≥2）；页面自包含、叠加人框与落点标记、
    ≥5 点位引导（建议 6 点）、localStorage、导出 calib.json（v2 schema：
    event_key/fid/frame_idx/px/py/landmark/court_spec）
  - Verify：pytest 绿 + node --check + 浏览器实点 1 事件
  - Files：scripts/gen_calib_page.py、tests/test_gen_calib_page.py
- [ ] Task 3：`scripts/calib_eval.py` + 单测（Q1 精度评估）**未启动（门禁短路）**
  - Acceptance：image→court 米制单应 + 留一法折内最小二乘逐点评估；
    混合中位 + P90；单点 >2m 记 WARNING；calib_eval.json 落
    work/20260805_车百鼎/
  - Verify：ruff + pytest 绿（合成单应误差≈0 / 扰动上升）+ 合成 fixture 端到端
  - Files：scripts/calib_eval.py、tests/test_calib_eval.py
- [ ] Task 4：双门槛汇总 + `docs/heatmap/calib-report.md` **未启动（Q1 未做）**
  - Acceptance：报告含双判据实测值 vs 阈值、抽样偏差、尺度锚定假设注明
    （FIBA 默认/非标放宽）、米制评估口径溯源、持球帧时间误差声明、
    明确立项/证伪结论
  - Verify：spec-reviewer 审报告通过
- [x] Task 5：文档联动（立项→research.md 状态 + 阶段 1 新四件套；
  证伪→经验教训 §8 追加记档，v1 条目保留）**证伪分支完成：§8 追加三条**
  - Verify：联动文档过 spec-reviewer；全部提交
