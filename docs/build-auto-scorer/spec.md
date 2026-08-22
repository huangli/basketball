# Spec: build 认人可选化（自动个人合集）

2026-08-22 立哥定：认人从必选项改为可选项。默认（无 confirmed roster）时
`video build` 一键出齐三类产物；认人确认后仍能出实名队伍/个人合集（现状不变）。

## 目标（Objective）

- **用户**：立哥（唯一用户）；动机：进球标注完成后想直接出片，不愿被认人确认页阻塞
  （2026-08-22 实录：`video build --all` 因 roster 未 confirmed 拒收，流程卡死）。
- **默认产物（roster 缺失或未 confirmed=true）**，`video build --session <场次>` 一条命令出：
  1. **队伍集锦（按球衣颜色分队）**：`output/<场次>/队伍_<黑|白>_进球集锦.mp4`——
     分队依据 = crop_scorers 现成的颜色分队判据（HSV 躯干主色，`team_guess` 字段，
     黑/白/便服三值），簇内多数票定队别；便服队不出集锦（真值表⑧口径沿用）；
     **允许有误**（2026-08-22 立哥定；本条取代初稿的全员集锦——2026-08-08
     "不出全员总合集"口径维持有效）
  2. **独立进球视频**：`output/<场次>/进球片段/` 下每个 confirmed 球一个 mp4，
     命名 `进球片段/NNN_<file主名>@<anchor:.1f>s.mp4`（NNN 按时序 001 起，锚点一位
     小数带 s 后缀，如 `001_dji_mimo_xxx_video@42.0s.mp4`；
     剪辑参数与合集片段一致：前4后2、50fps、慢放规则同）
  3. **自动个人合集**：自动串联 crop_scorers（裁人）+ cluster_scorers
     （CLIP `--linkage complete --threshold 0.15` 定稿口径），按聚类簇出
     `output/<场次>/<队伍>_<簇标>_进球合集.mp4`（如 `黑_A_进球合集.mp4`，
     队伍=簇内颜色多数票）；**不经确认页、允许有误**（立哥明示）
- 注意：裁图失败（unclustered）的球不进队伍/个人合集（无归属依据），
  但仍在 `进球片段/` 中有独立视频，不丢球。
- **认人后产物（roster confirmed=true，现状回归）**：`--all`/`--scorer`/`--team`
  出实名个人合集与队伍集锦，行为与当前完全一致。
- 成功标准见文末，均为可执行验证。

## 边界（Boundaries）

- **不改**：认人链路本身（crop/cluster/确认页/导出 roster）的行为与参数；
  build_highlight 的剪辑参数（窗口/慢放/尺寸/concat 重封装）；
  显式 `--roster` 传入未确认文件时 build_highlight 仍拒收（契约不动，防误用）。
- **改**：`video.py` build 命令的编排（默认模式串联三产物）；
  `build_highlight.py` 增加"每球独立输出"与"未确认 roster 按 tag 分组出合集"能力；
  输出命名按本 spec（`队伍_<黑|白>_进球集锦.mp4` / `进球片段/NNN_<主名>@<anchor>s.mp4` / `<队>_<字母>_进球合集.mp4`）。
- **不做**：跨机位、GUI、手机端；自动合集的准确率优化（聚类参数不动）；
  热图统一为"未认人不出热图"——自动模式（无 confirmed roster）跳过热图，
  仅 roster confirmed=true 的现状路径触发（goal_heatmap 无 confirmed 检查，不新触发热图）。
- **Always**：提交前 `ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿；
  四件套同目录（本文件夹）；AGENTS.md 口径行与 使用手册.html 同步更新。
- **Ask first**：聚类参数调整；新增第三方依赖（预期无）。
- **Never**：改动原始素材；output/ 产物属可再生，重跑覆盖为预期行为
  （现状 run_ffmpeg 恒 `-y`，本次不新增覆盖提示；per-goal 模式幂等跳过已存在产物）。

## 技术现状（真值表依据）

`build_highlight.py` 组合真值表（§docstring，写死）①-⑧ + roster 未 confirmed 拒收。
本次新增两行（不改旧行）：

| 新行 | 条件 | 行为 |
|---|---|---|
| ⑨ | `--per-goal`（新旗标） | 每球独立 mp4 输出到 `进球片段/`，不 concat；与 --scorer/--team/--roster 互斥报错 |
| ⑩ | `--roster` + `--allow-unconfirmed`（新旗标） | 仅豁免 require_confirmed 检查（闸门旗标），其余真值表语义不变——逐簇/逐队分组由 video.py 编排层循环 `--scorer <tag>` / `--team <队>` 调用实现，单次调用走真值表④/⑤产 `<队>_<tag>_进球合集.mp4` / `队伍_<队>_进球集锦.mp4`；无 `--roster` 给此旗标报错（无意义组合，显式失败） |

（初稿的"①改名全员_进球集锦"随 2026-08-22 立哥改定口径撤销：自动模式不出全员集锦，
① 输出名维持 `个人_全员_进球合集` 不动——改动面进一步缩小。）

`video.py build` 编排（无 confirmed roster 时）：

```
build_highlight --goals <合并goals> --rawdir <rawdir> --out <尺寸> --per-goal  # 独立进球视频
crop_scorers（产物幂等跳过）→ cluster_scorers（定稿口径，每次重跑、
    靠 clip_cache 免重复 CLIP 推理）                                   # 自动识别
auto_roster.py --clusters … --candidates … → work/<场次>/auto_roster.json
                                                                     # 聚类+颜色分队 → roster
对每个颜色队（黑/白，便服除外）循环：
  build_highlight --roster <auto_roster.json> --allow-unconfirmed \
      --team <队>                                                    # 真值表⑤ → 队伍_<队>_进球集锦.mp4
对每个 tag 循环：
  build_highlight --roster <auto_roster.json> --allow-unconfirmed \
      --scorer <tag>                                                 # 真值表④ → <队>_<tag>_进球合集.mp4
```

- auto roster：由聚类+颜色分队结果生成 `work/<场次>/auto_roster.json`，`confirmed=false`
  保留语义（与立哥确认的 roster.json 区分；确认页导出仍写 roster.json，两份文件不互相覆盖）。
- 分队：crop_scorers 每个 OK 球已写 `team_guess`（黑/白/便服，HSV 躯干主色判据，
  crop_scorers.py:1420）；auto_roster.py 需加 `--candidates`（可重复）读各批
  scorer_candidates.json，簇内球队多数票定队别（平票取簇内最早有票球的队别，便服照算）。
- 命名：cluster_scorers 簇的 cluster_id 为 int 自 1 起（确认页显示"簇#N"）；
  字母标号 A/B/… 是 auto_roster.py 的新映射产物（cluster_id 升序 → A/B/…/Z/AA…），
  tag=字母、team=簇内多数票队别、name=""，经真值表④命名逻辑产出 `<队>_<字母>_进球合集.mp4`。
- 聚类簇数异常（0 簇/1 簇/>15 簇）：INFO 留痕、不 WARNING、不阻塞（2026-08-22 立哥定）；
  0 簇时队伍/个人合集步骤跳过（auto_roster 产空 players/assignments 的合法 roster，exit 0）。
- 尺寸：`--out` 按 session_facts 主比例换算（video.py 现状逻辑复用）。

## 项目结构与代码风格

- 改动文件：`scripts/video.py`、`scripts/build_highlight.py`，可能新增
  `scripts/auto_roster.py`（聚类结果 → auto_roster.json 转换，纯函数便于测试）。
- 测试：`tests/test_video.py`、`tests/test_build_highlight.py` 增补；新模块配新测试文件。
- 风格：遵守 `rules.md`（鲁棒优先＞性能＞简洁）、`ruff.toml`；中文注释口径同邻域代码。

## 测试策略（Testing）

- pytest 单测为主，不跑真实 ffmpeg 长转码（沿用现有测试的 fake/monkeypatch 模式）：
  - 真值表⑨⑩：per-goal 产物清单、allow-unconfirmed 的拒收豁免与逐簇分组
  - video.py build 编排：无 roster / 未 confirmed / 已 confirmed 三种 roster 状态下的命令序列
  - auto_roster 转换：簇 → players/assignments 的键格式（format_key 契约）
- 回归：现有 test_build_highlight / test_video 全绿（旧真值表①-⑧行为不变）。

## 成功标准（Success Criteria）

1. 无 roster 的场次跑 `video build --session X` 退出 0，且
   `output/X/进球片段/*.mp4`（含全部当前 confirmed 球；goals 收缩后重跑可能残留旧文件，
   数量 ≥ 当前球数属预期）、`output/X/队伍_*_进球集锦.mp4`（每个非便服颜色队一个）、
   `output/X/<队>_*_进球合集.mp4`（数量=聚类簇数）三类产物齐全；**不出全员集锦**。
2. roster 存在但 `confirmed=false`：同样退出 0 出三类产物，日志 WARNING 说明按未认人处理。
3. 全部批次缺 candidates（无可聚类候选）：WARNING 留痕、跳过整条识别链，
   仅出 `进球片段/` 亦属 exit 0 合法态（video.py `_cmd_build_auto` 有意设计）。
4. roster `confirmed=true`：`--all`/`--scorer`/`--team` 行为与改动前完全一致（回归测试证明）。
5. `ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿。
6. AGENTS.md 合集口径行、使用手册.html 流程说明同步更新。

## 开放问题（Open Questions）

无（命名与聚类异常策略已于 2026-08-22 与立哥定案，见上文）。
