# video.py 统一入口 CLI — review01（spec 阶段，两轮）

> 审查对象：docs/video-cli/spec.md、plan.md、todo.md。审查者：spec-reviewer 子代理。2026-08-11。

## 第一轮：需修订（2 阻断 + 5 建议 + 2 可选）

**阻断**：
- B1：`--clusters` 与 `--scorers` 不同目录会被 gen_scorer_page 硬性拒收（scripts/gen_scorer_page.py:927 强制校验 + --help 明文"必须与 --scorers 同目录"）。原 spec 合批聚类落 `work/<S>/scorer_clusters.json` 必炸 → **采纳审查员推荐方案 a：逐批聚类**，clusters 落各批 `scorers[_bK]/`，放弃合批聚类（跨批合并由 roster-existing 链条承担）
- B2：批次 1 配套命名假设滞后于代码——run_session.py:366-370 对所有批次统一 `batch{k}` 标签，产 `candidates_batch1.json`/`review_batch1/`，`candidates.json`/`review/` 是 20260722 历史布局 → **改双轨发现**：配套名从 goals 文件名推导（对照表入 spec），并明写"label.html 导出后人工改名"前提

**建议（全部吸收）**：S1 人工改名前提明写；S2 发现阶段 WARNING/执行阶段跳过口径统一；S3 `--all` 注明 build_highlight 强制 confirmed=true 门槛；S4 todo 前置核对扩为"参数名+help 约束说明"；S5 run_step 统一注入 `PYTHONIOENCODING=utf-8`（Windows 中文日志坑，docs/经验教训.md §6）。
**可选（吸收）**：O1 runs 记录 argv+exit code 照实记；O2 `--max-reads` 缺省 3×confirmed 注明推导自 --best-crops 默认 3。

## 第二轮：通过（0 阻断，1 建议 + 3 可选全部顺手吸收）

- M1（建议，已吸收）：配套检查粒度细化到文件级——旧布局 20260722 批次 1 的 `review/` 下无 `events_index.json`（实证不存在），显式传不存在路径会 read_json 抛 OSError → `--index` 改为**文件存在才传**，缺失 WARNING 降级（页面仅失兜底视频引用）
- O1（已吸收）：同 K 双布局并存（goals.json 与 goals_batch1.json 同在）→ 报错退出 1 不猜
- O2（已吸收）：build 尺寸判定措辞改为"逐文件 width/height 主比例判定"（顶层字段仅首文件值）
- O3（已吸收）：plan 风险表第 3 行同步"参数名+约束"措辞

**核验记录**：people 第 2/3 段 clusters 路径一致性 ✓；crop_scorers 产物即 `<out>/scorer_candidates.json`（:1538）✓；批次对照表与 plan discover_batches 一致 ✓；PYTHONIOENCODING 两处口径一致 ✓。

**结论：通过，四件套冻结，进入实现。**
