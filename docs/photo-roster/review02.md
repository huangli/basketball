# Review 02: 照片库认人 plan/todo 审查（2 轮闭环）

日期：2026-08-23
对象：docs/photo-roster/{plan.md, todo.md} 初稿 → 定稿；spec.md 仅"传参约定"
小节随本轮修订（原"缺省自动探测"改为"显式传参"）
审查人：spec-reviewer 子代理（对照 spec.md 定稿与 video.py / gen_scorer_page.py /
cluster_scorers.py 现状代码核查锚点）

## 总结论：无阻断问题，plan/todo 定稿可开工

## 第 4 轮：2 阻断 + 2 建议（全部修订）

| 阻断 | 修订 |
|---|---|
| 确认页"缺省自动探测同目录 photo_matches.json"与 spec "无此参数行为不变"矛盾，且与仓库惯例相反（--index/--roster-existing 均由 video.py 探测存在后显式传参；:1548 同目录校验是约束显式传参合法性，非自动发现机制） | spec/plan/todo 三处统一改"显式传参"：gen_scorer_page 只认 --photo-matches；存在性探测收在 video.py 编排侧（is_file 后拼参） |
| spec Boundaries 写死 photos/ 进 .gitignore，但 T1-T7 无任务承接（自动提交口径下真人照片误入库风险是实的） | T1 Acceptance 加 `.gitignore` 加 `photos/` + `git check-ignore photos photos/.photo_cache.json` 断言，Files 加 .gitignore |

建议吸收：T6 降级范围封口（仅 ②.5 允许失败降级，①②③ 失败语义不变）；
T4 review03.md 预置达标/不达标结论模板。

## 第 5 轮：无阻断，2 建议（已吸收）

- plan.md:3 "三轮审查闭环" → "四轮审查修订定稿"（spec 传参约定小节随第 4 轮改过）
- T1 验收补 `git check-ignore photos/.photo_cache.json` 显式断言（防日后缓存挪出库目录）

## 锚点核查记录（第 4 轮，全部属实）

- cluster_scorers.py:238 load_clip_cache / :273 save_clip_cache / :291
  build_clip_encoder / :204 merge_candidates / :222 file_md5 均为公共函数可
  import 复用；merge_candidates 返回 key→GoalCrops 含 base_dir，正合逐批
  解析裁图路径之需
- video.py:385 build_people_steps ②聚类后插步位置成立；②聚类落 cache 于
  batch.scorer_clusters.parent 与 cluster_scorers.py:753 口径吻合
- gen_scorer_page.py:1103 match_players_by_number / :1548 --clusters 同目录
  校验属实

## review 编号约定（本轮起）

- review01.md = spec 三轮审查闭环（已归档）
- review02.md = plan/todo 审查（本文件）
- review03.md = T4 Phase A 实跑报告（预置达标/不达标模板）
- review04.md = T7 收尾真机验证
