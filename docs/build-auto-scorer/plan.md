# Plan: build 认人可选化（颜色分队集锦 + 自动个人合集）

依据 `docs/build-auto-scorer/spec.md`（2026-08-22 定稿；同日立哥改定：
默认产物不要全员集锦，要按球衣颜色分队的队伍集锦——①改名撤销，改动面缩小）。

## 关键代码事实（已核实）

- `roster.py`：team 合法值 = strip 后非空的 str → auto roster 用 `team=<簇内颜色多数票>`、
  `name=""`、`tag=<簇字母>`，build_highlight 真值表④现有命名逻辑
  `f"{team}_{name or tag}_进球合集"` 天然产出 `黑_A_进球合集.mp4`，**④ 命名逻辑零改动**。
- `crop_scorers.py`：每个 status=OK 的球已写 `team_guess`（黑/白/便服，HSV 躯干
  主色判据，:1420）——颜色分队数据现成，auto_roster 只需读 candidates 多数票。
- `video.py` `_cmd_build`：`roster_path.is_file()` 即传 `--roster`（未确认也传 → 被拒收，
  即 2026-08-22 事故根因）；`build_people_steps` 的 crop/cluster 段可拆解复用
  （cluster 步骤已带 HTTPS_PROXY env 与定稿参数 complete/0.15）。
- `cluster_scorers.py`：`--candidates` 可重复传参合并多批（同 key 后者覆盖）；
  输出 clusters 内簇用 int cluster_id；unclustered 球不入簇。
- `build_highlight.py`：cut_normal/cut_slowmo 可复用为"直接出最终 mp4"（不经 concat）；
  真值表⑤ `--team` 过滤逻辑现成（便服拒收⑧，自动模式便服队不出集锦属预期）。

## 组件与实施顺序（全部串行，后项依赖前项契约）

### 1. build_highlight.py：真值表⑨ `--per-goal`

- 新旗标 `--per-goal`：每个 confirmed 球独立出片到 `output/<场次>/进球片段/`
  （main 需自建该目录，现仅建 out_dir 与 _clips_tmp），
  命名 `NNN_<file主名>@<anchor:.1f>s.mp4`（NNN 按时序 001 起；锚点保留一位小数），
  不 concat、不进 `_clips_tmp`，直接 cut_normal/cut_slowmo 到最终路径。
- 与 --scorer/--team/--roster 组合：⑨ 是独立模式，与过滤旗标互斥报错（防歧义）。
- 退出码口径同主流程：部分原片缺失 → 出完能出的、exit 1 并 ERROR 清单。
- 断点：已存在的同名产物跳过（幂等，build 重跑不重复转码）。
- 验证：`pytest tests/test_build_highlight.py`（新用例 mock run_ffmpeg）。

### 2. build_highlight.py：真值表⑩ `--allow-unconfirmed`

- 新旗标 `--allow-unconfirmed`：跳过 `require_confirmed`；未给 `--roster` 时给该旗标
  → 报错（无意义组合，显式失败）。
- 显式 `--roster` 无此旗标仍拒收（旧契约不变，回归测试证明）。
- ~~① stem 改名~~（初稿方案，已随 2026-08-22 口径变更撤销）：① 输出名维持
  `个人_全员_进球合集` 不动，自动模式不调①，无改名需求。
- 验证：`pytest tests/test_build_highlight.py` 全绿。

### 3. scripts/auto_roster.py（新模块，纯函数 + 薄 CLI）

- 输入：一个或多个 scorer_clusters.json（可重复 `--clusters`，跨批合并，
  同 goal key 后者覆盖前者——与 cluster_scorers 合并口径一致）；
  一个或多个 scorer_candidates.json（可重复 `--candidates`，读每球 `team_guess`）；
  `--session`；`--out`。
- 输出 auto_roster.json：`confirmed=false`、`session`、
  `players=[{tag: <字母>, name: "", team: <簇内 team_guess 多数票>}]`
  （簇按 cluster_id 升序映射 A/B/…/Z/AA…；多数票平票取簇内首球队别；
  球缺 team_guess（status!=OK/旧数据）不计票，全簇无票归"便服"）、
  `assignments={<goal key>: <字母>}`；unclustered 不进 assignments。
- 簇数异常（0/1/>15 簇）：INFO 留痕一行、不 WARNING、不阻塞（2026-08-22 立哥定）；
  0 簇写出空 players/assignments 的合法 roster（validate_roster 可通过），exit 0，
  由 video.py 跳过队伍/个人合集步骤。
- schema 校验：clusters/candidates 文件损坏走 SchemaError 显式失败（rules.md §0.2）。
- 验证：`pytest tests/test_auto_roster.py`（新文件：映射/合并/多数票/平票/无票/0 簇/坏 schema）。

### 4. video.py：build 默认自动模式编排

roster 状态判定（`_cmd_build` 入口；roster.json schema 损坏时 validate_roster
抛 SchemaError → 显式报错退出 1，不降级不静默，rules.md §0.2）：
- `roster.json` 存在且 `confirmed=true` → **现状路径零改动**（含 --all/--scorer/--team）。
- 缺失或 `confirmed=false` → 自动模式：无条件 WARNING 一行"按未认人处理"；
  用户给了 --scorer/--team/--all 时另 WARNING 说明过滤被忽略。
- `--batch K` 交互：自动模式同样只作用于选定批次（goals 合并、crop/cluster 的
  candidates 均按选定批次注入，cluster 跨批合并在单批时自然退化为单批）。

```
① build_highlight --goals <goals> --rawdir <rawdir> --out <尺寸> --per-goal → 进球片段/（不传 --roster）
② 逐批 crop_scorers：**不整函数复用 build_people_steps**（其访问
   args.read_numbers/max_reads/skip_cluster/players_file，build namespace 无这些属性，
   直接调用必 AttributeError）——抽出独立 crop argv 构造函数（参数逐项显式拼装，
   与 people 链路同参），build/people 两侧共用；
   自动模式**不带 --read-numbers**（读号走 K3 烧 token，自动合集允许有误，不开）；
   scorer_candidates.json 已存在且 JSON 可读则跳过——幂等，仿 run_session 断点口径
③ cluster_scorers --candidates <各批>… --out work/<场次>/scorers_auto/scorer_clusters.json
   --linkage complete --threshold 0.15（env HTTPS_PROXY，复用现常量）；
   每次重跑、靠 clip_cache.json（落 scorers_auto/）免重复 CLIP 推理——
   缓存与 people 各批目录隔离不互串，仅首次 auto 全量付费（见风险表）
④ auto_roster.py --clusters … --candidates <各批 scorer_candidates.json>…
   --session <场次> --out work/<场次>/auto_roster.json
⑤ 逐队：build_highlight --roster auto_roster.json --team <队> --allow-unconfirmed
   → 队伍_<队>_进球集锦.mp4（仅黑/白等颜色队；便服不在循环内——真值表⑧口径；
   零命中队预算跳过，仿 _build_expand_all 口径防 exit 1 中止整轮）
⑥ 逐 tag：build_highlight --roster auto_roster.json --scorer <tag> --allow-unconfirmed
   → <队>_<tag>_进球合集.mp4（零命中 tag 预算跳过，同⑤口径）
⑦ 热图：自动模式**跳过**（goal_heatmap 无 confirmed 检查，未确认 roster 上不新触发；
   仅 confirmed=true 现状路径照现行逻辑调 _run_heatmap_step）
```

- 自动识别链失败口径：②-⑥ 任一步子进程失败 → 记 ERROR 留痕、跳过剩余识别步骤，
  已产出的 ① 保留，build 退出 1（有失败即非 0，同 run_session 口径；不静默降级）。
- 批次守卫：某批缺 candidates.json → WARNING 跳过该批（同 _cmd_people 口径，
  video.py 现有先例），不因单批缺产物中止整轮。
- 单批/多批：goals 合并逻辑（`_merge_goals_for_build`）原样复用。
- dry-run：全链路只打印（现有 `_log_dry_step` 模式）。
- 验证：`pytest tests/test_video.py`（三种 roster 状态的命令序列断言，mock run_step）。

### 5. 文档同步与审查

- `AGENTS.md`：合集口径行修订（2026-08-22：认人可选、默认三产物=队伍集锦（颜色分队）+
  进球片段+自动个人合集；8-08"不出全员总合集"口径维持）。
- `使用手册.html`：build 章节改为"标注完直接 build，认人可选"。
- spec-reviewer 子代理审查本目录四件套 → reviewNN.md 归档（review01=初稿全员口径，
  本轮变更为 review02）。
- 关口：`ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿后提交。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| crop_scorers 重跑慢（重复 build） | 产物存在且可读即跳过（步骤②） |
| ② 幂等跳过与"素材是流动的"张力（goals 变更后 candidates 过期） | 已接受：仿 run_session 断点口径；素材/goals 变更后须人工删 scorers 目录重跑（手册注明） |
| CLIP 权重首跑需代理下载 | cluster 步骤沿用现成 HTTPS_PROXY env 注入 |
| 首次 auto cluster 全量 CLIP 推理（缓存与 people 各批目录隔离） | --out 固定 scorers_auto/，重复 build 复用本目录缓存，仅首次付费 |
| 多批簇标跨批不一致（同一人两批聚成两簇） | 步骤③ 单次 cluster 合并全部 candidates，天然跨批一致 |
| 颜色分队分错（撞色/灯光暗/全员便服场次） | 允许有误（立哥定）；全员便服 → 不出队伍集锦只有个人合集，INFO 留痕；要准走认人流程 |
| per-goal 产物与合集重复占盘（~1 球 6s ≈ 15MB） | 可接受；文档注明删除安全（output/ 产物可再生） |
| video.py:512 `except KeyError, TypeError, ValueError:` 无括号写法 | 已实测 py_compile/import 通过——PEP 758（Python 3.14 起合法）；环境钉死 3.14，不改 |
| 未确认 roster 上误触发热图（goal_heatmap 无 confirmed 检查） | 自动模式跳过热图步骤（⑦），仅 confirmed 路径触发 |

## 验证检查点

1. 步骤 1+2 后：`pytest tests/test_build_highlight.py` 绿
2. 步骤 3 后：`pytest tests/test_auto_roster.py` 绿
3. 步骤 4 后：`pytest tests/test_video.py` 绿
4. 收尾：全量 `pytest -q` + ruff 双关口绿；真机抽验一场（20260813_淳化街道，
   roster 未确认）`video build` 出齐三类产物 exit 0
