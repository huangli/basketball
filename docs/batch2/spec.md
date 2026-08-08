# Spec: 批次 2 流水线改进（时空聚类 / 排序 / 锚点 / 投篮者定位 / 补标固化）

> 2026-07-30 v2（spec-review 修订）。依据：批次 1 闭环复盘
>（docs/2026-07-26-current-goal-detection-pipeline.md §4）与 AGENTS.md 下批五改进。
> 状态：①②⑤已实现并提交（commit 4abc0c4），批次 2 跑批完成（185 事件待标注）。

## Objective

批次 1 验收暴露了 4 个结构性缺陷，批次 2（20260722 场次第 51~150 个视频，100 个）
开工前必须修掉，否则同样的错误会放大 2 倍：

1. **同球重复**：190354 一个进球被聚类缝隙拆成两事件（2.6s/309px），合集进了两次。
2. **mega-event 锚点错位**：0544 事件链 9 候选跨 8.4s，锚点取 conf 最高成员（4.5s 未中）
   而真进球在 11.5s；1508、1948 同类。合集片段切错时段。
3. **审核顺序无先验**：立哥从头平推 113 事件，真球密度高的没有排前。
4. **补标靠手搓**：39 个候选级 NO 的未覆盖时刻用 heredoc 临时脚本挖的，不可复现。

同时打认人地基：零成本部分（投篮者定位裁图、颜色分队）本轮做完，
球员按钮/号码识别等立哥名单与拍板。

成功 = 批次 2 的审核页里：无同球重复事件、无 mega-event 锚点错位、
真球集中在头部（认真看头部 + 快扫尾部）、补标一条命令可复现。

## Tech Stack

Python 3.14.3（标准库 + numpy/opencv/pillow/ultralytics/httpx，已装）；
ffmpeg 8.1.2；Kimi K3（事件级判定，vlm_judge_events.py 已入库）；
豆包 seed-2.0-pro（可选号码识别试点，ARK_API_KEY 走环境变量，不入文件）。
无新依赖。批次 2 K3 预算外推 ≈170 事件 ≈ 670K 输入 token（84 事件/50 视频口径）。

## Commands

```bash
export PYTHONIOENCODING=utf-8   # Git Bash 下 python 打印中文必须
python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q

# 批次 2 跑批顺序（51~150 视频；各脚本参数缺口列入任务，以 docstring 为准）
python scripts/extract_frames.py "20260722地平线/2026 年 7月22 日 地平线" --limit 100   # 位置参数+--limit（无 --srcdir/--range）
# 检测（YOLO→work/detect/<fid>_mot_cache.json，最重的步骤，100 视频约 2h CPU，现有调用方式不变）
python scripts/pilot_candidates.py <fid...> --out work/20260722/candidates_b2.json      # fid 位置参数（无 --srcdir/--range）
python scripts/detect_hoops.py --candidates work/20260722/candidates_b2.json --out work/20260722/hoops_b2.json
python scripts/gen_review_clips.py --candidates work/20260722/candidates_b2.json --outdir work/20260722/review_b2 --srcdir "20260722地平线/2026 年 7月22 日 地平线" --orig 3840x2160 --hoops work/20260722/hoops_b2.json --keep-clips
python scripts/vlm_judge_events.py --index work/20260722/review_b2/events_index.json --goals work/20260722/goals_b2.json --hoops work/20260722/hoops_b2.json
# K3 NO 排尾重排序（新任务：--resort 读事件级缓存重排 events_index，或 vlm_judge_events 回写）
python scripts/gen_label_page.py --index work/20260722/review_b2/events_index.json
# 补标审计（仅启用候选级剔除时；批次 2 默认 NO 只排序不剔除，本步产出为空属正常）
python scripts/find_uncovered_rejects.py --candidates work/20260722/candidates_b2.json --vlmcache <候选级缓存> --index work/20260722/review_b2/events_index.json
```

## Project Structure

```
scripts/            → 流水线脚本（rules.md 约束）
  gen_review_clips.py   已实现（工作区未提交）：时空聚类 + 末成员锚点 + hoop_dist 排序
  find_uncovered_rejects.py  新：补标清单生成（替代手搓 heredoc）
  crop_scorers.py       新：投篮者定位裁图（认人地基）
tests/              → pytest 单测（纯函数，不碰真帧/网络）
work/20260722/      → 场次产物（批次 1 封存；批次 2 产物用 _b2 / review_b2 区分）
output/20260722/    → 成品合集
docs/               → 方案文档（本 spec 在 docs/batch2/，已完成，无 plan/todo）
```

## Code Style

遵守 rules.md（鲁棒优先 ＞ 性能 ＞ 简洁）：全类型注解、Google docstring（Args/Returns）、
SchemaError 显式失败、atomic_write_json 落盘、run_id 日志。函数签名延续现状
（`dict[str, Any]` 记录风格，不引入新建模）。

## Testing Strategy

pytest，纯函数单测（不碰真帧/网络/API），fixture 用 tmp_path。
聚类语义（与已落地实现一致，OR 双条件）：

> 相邻候选满足任一即同事件：**gap ≤2s**（纯时间链），或 **gap ≤6s 且 dist ≤400px**（时空放宽）。
> dist 阈值取 400px 而非 300px：190354 同球对实测 308.6px，需 ≥23% 余量；
> 6s/400px 下 30 个新增合并对逐一核查无误合并（191240 补篮类合并正确）。

回归基准（批次 1 真实数据的可复算断言）：

- 时空聚类：326 候选重聚类 → 190354@16.5/19.1 合并为同事件；
  时空放宽**不得**合并远距离对（0544 #1→#2：2.1s/1024px 不合并）；
  总事件数 113 → 84（批次 1 重放值）
- 锚点：0544=11.5 / 1508=12.4 / 1948=4.1（末成员 t0）；190428 弹出案例末成员 10.4s 亦正确
- 排序：events_index 含 hoop_dist；重排序步骤生效后 K3 NO 全部排尾；层内 hoop_dist 升序
- find_uncovered_rejects：批次 1 三件套（candidates_review_v3.json + vlm_cache_v2.json
  （候选级缓存，键 fid#N@尺度）+ review_v3/events_index.json）复现 20 时刻，
  与基准 `work/20260722/candidates_addendum.json` diff 为空
- crop_scorers：合成 mot_cache + goals → 离球最近人框选中正确；无人框显式 SKIP 不炸

## Boundaries

- Always：改动过 ruff+pytest 再交付；rules.md；日志含 run_id；写 JSON 用原子写；
  复用 vlm_filter / vlm_judge_events 现成函数；gen_review_clips.py 与
  test_gen_review_clips.py 现有未提交改动先确认归属再动（另一会话产物）
- Ask first：新增 pip 依赖；改 goals.json / events_index.json 已发布 schema（加字段可以，
  改语义/删字段必须先问）；回刷批次 1 产物；豆包 API 超 20 次调用的花费
- Never：删/改原始视频；硬编码文件清单；碰 archive/；API key 入文件或日志；
  绕过 normalize_verdict 降级规则；修改批次 1 已封存的 review_v3 / goals.json / 合集

## Success Criteria

1. ruff + pytest 全绿（测试数 ≥ 115 + 新增）
2. 时空聚类回归：190354 对合并、远距离对不合并、113→84，全部有测试断言（已实现，验收）
3. 锚点回归：0544=11.5 / 1508=12.4 / 1948=4.1（测试断言）；
   且 17 个 confirmed 的入网时刻全部落在 [锚−4, 锚+2] 成片窗口内（批次 1 重放实测）
4. 排序：批次 1 数据重放（dry-run），排序后前 13 事件含 ≥2 个真进球（实测基线 4 个）；
   K3 缓存键 fid#eN 绑定旧聚类编号，重放时 K3 排尾无数据、退化为纯 hoop_dist 属预期
5. find_uncovered_rejects 一条命令复现批次 1 的 20 时刻（与 candidates_addendum.json diff 为空）；
   定位 = "启用候选级剔除时的配套/审计工具"（批次 2 默认不剔除，产出为空属正常）
6. crop_scorers 对批次 1 的 17 个 confirmed 各产出投篮者裁图，立哥抽查 3 张认可
7. gen_review_clips/gen_label_page 输出 schema 向后兼容（label.html 无需改动能开）

## Open Questions

1. 另一会话的未提交改动（gen_review_clips + 其测试）由谁提交、后续改动归口哪个会话
2. 本场球员名单（号码/特征 → 称呼）——阻塞认人按钮与照片库认人
3. 批次 2 验收节奏是否照批次 1（标注 → 合集 → 立哥过一遍 → 修锚点/误标 → 封存）
4. 号码识别预填是否值得花豆包 API（~20 球 × 1 次/球 < ¥1）——可先免费做颜色分队
