# video.py 统一入口 CLI — spec

> 2026-08-11 立哥拍板：子命令薄封装（非旗标、不注册系统命令），`python scripts/video.py <子命令>`。

## 背景与目标

scripts/ 已 14 个脚本，跑场次靠翻文档记参数（run_session / crop_scorers / cluster_scorers / gen_scorer_page / build_highlight 五条命令链，参数散在 AGENTS.md 与 scorer 三件套里）。目标：一个薄入口把三条高频链路固化下来——

```
python scripts/video.py score <素材目录> --session <场次ID> [--batch-size N] [--fids a,b,c] [--force] [--dry-run]
python scripts/video.py people --session <场次ID> [--batch K] [--rawdir PATH] [--read-numbers] [--max-reads N] [--players-file PATH] [--skip-cluster] [--dry-run]
python scripts/video.py build --session <场次ID> [--batch K] [--rawdir PATH] [--scorer X | --team T | --all] [--dry-run]
```

**成功标准**：

1. 新场次全流程只需记 `video score` →（label.html 人工标注）→ `video people` →（确认页人工）→ `video build` 四条命令（含人工环节）
2. 所有子命令拼出的 subprocess 命令与现行文档定稿参数逐字一致（聚类显式 `--linkage complete --threshold 0.15`；build 尺寸按 session_facts 换算 16:9→1920x1080、4:3→1440x1080）
3. 任意子步骤 subprocess 非零即停、exit 1、打印失败命令；`--dry-run` 只打印不执行
4. 不改动任何现有脚本的行为；现有 pytest 全绿 + 新增单测覆盖命令拼装

## 边界（Out of Scope）

- 不重新实现检测/认人/合成任何逻辑，纯 subprocess 薄封装（参照 run_session.py 编排器模式）
- 不含 label.html 人工标注、不含确认页 roster 导出（浏览器人工环节，CLI 只生成页面）
- 不注册系统命令、不改 pyproject.toml；调用形态 `python scripts/video.py`（2026-08-12 起**任意目录可运行**：真实入口自动把相对路径参数按启动目录解析后 chdir 到仓库根；PowerShell profile 已装 `video` 函数别名，直接 `video score ...`）
- 机器裁判/VLM 环节已下线，不纳入任何子命令

## 关键设计

### 状态文件 video_cli.json

session_facts.json 只存尺寸/fps/文件清单，**不含素材目录**，而 people/build 需要 --rawdir。故 video.py 自带状态文件 `work/<场次>/video_cli.json`：

```json
{"version": 1, "session": "<场次ID>", "srcdir": "<素材目录绝对路径>", "updated_at": "...", "runs": [{"cmd": "score", "at": "...", "argv": [...]}]}
```

- `score` 成功后写入/更新 srcdir（原子写，走 pipe_common.atomic_write_json）
- `people`/`build` 的 --rawdir 缺省读 state 的 srcdir；显式 --rawdir 优先；两者都没有 → 报错退出 1（不猜路径）
- runs 只追加不覆盖（审计用，仿 run_session.log 的排障价值）

### 批次发现（people/build 共用）

扫描 `work/<场次>/` 的 goals 文件定位批次。**改名是人工步骤**：label.html 导出恒为 `goals_<S>.json`，立哥标注后人工改名为 `goals.json`（批次 1）或 `goals_batchK.json`（批次 K）——本命令只认改名后的文件。配套文件命名从 goals 文件名推导（双轨兼容）：

| goals 文件 | candidates | review 目录 | scorers 输出目录 |
|---|---|---|---|
| `goals.json`（旧布局，如 20260722） | `candidates.json` | `review/` | `scorers/` |
| `goals_batchK.json`（K≥1，run_session 现行布局） | `candidates_batchK.json` | `review_batchK/` | `scorers_bK/` |

`--batch K` 限定单批（K=1 时两种布局都试；同 K 双布局并存 → 报错退出 1，不猜）。发现阶段对配套缺失仅标注 WARNING，处置分两类：**candidates 缺失 → 执行阶段跳过该批**（裁图无锚点来源，不中断其他批次）；**events_index.json 缺失 → 仅 WARNING 降级继续**（people 第 3 段 --index 不传，页面仅失兜底视频引用）。配套检查细化到文件粒度——candidates 查 `candidates[_batchK].json`、review 查 `review[_batchK]/events_index.json`（旧布局 20260722 批次 1 的 review/ 下无此文件，属正常缺失）。

### score

透传 run_session.py：srcdir / --session / --batch-size / --fids / --force / --dry-run。子进程 exit 0 后写 video_cli.json（dry-run 不写；runs 记录 argv 与 exit code，部分失败语义不揣测、照实记）。

### people（逐批次三段链，批次间独立）

1. `crop_scorers.py --goals work/<S>/goals[_batchK].json --detectdir work/detect --framesdir work/frames --out work/<S>/scorers[_bK] --candidates <配套 candidates> --rawdir <rawdir> [--read-numbers [--max-reads N]]`
   - `--read-numbers` 默认不带（K3 读号要花 token，立哥按需开）；带上时 `--max-reads` 缺省 = 该批 confirmed 球数 ×3（推导自 --best-crops 默认 3：读号投票每球 ≤3 张新调用，定稿口径见 docs/scorer-reid/spec.md；best-crops 改档时此处同步）
2. `cluster_scorers.py --candidates work/<S>/scorers[_bK]/scorer_candidates.json --out work/<S>/scorers[_bK]/scorer_clusters.json --linkage complete --threshold 0.15`
   - **逐批聚类、clusters 落各批 scorers 目录**：gen_scorer_page 硬性要求 --clusters 与 --scorers 同目录（rep_crops 相对引用，--help 明文），合批聚类落场次根会被拒收；放弃跨批次合批聚类，跨批合并由 roster-existing 链条承担（如需合批纯度标定，手动跑，不在本命令职责内）
   - **定稿参数显式传**（脚本默认 average/0.25 是未标定起点，勿依赖默认值）；`--skip-cluster` 跳过本段且第 3 段不传 --clusters
   - 聚类需 CLIP 权重首跑下载：subprocess env 注入 `HTTPS_PROXY=http://127.0.0.1:7897`
3. `gen_scorer_page.py --scorers work/<S>/scorers[_bK]/scorer_candidates.json --goals work/<S>/goals[_batchK].json --session <S> [--index work/<S>/review[_batchK]/events_index.json（**文件存在才传**，缺失记 WARNING 降级——页面仅失兜底视频引用，裁图与预览 clips 仍在）] [--clusters work/<S>/scorers[_bK]/scorer_clusters.json] [--roster-existing work/<S>/roster.json（存在才传）] [--players-file PATH]`
   - **建议用法：逐批 `--batch K` 跑，浏览器确认导出 roster.json 后再跑下一批**——下一批生成页面时自动带上 --roster-existing 预填。一次跑全部批次则后续批次无 roster 预填（功能不差，预填少）
   - 幂等：裁图/embedding/读号全有缓存，重跑只补增量

### build

- 无 --scorer/--team/--all：出该批次全员合集（build_highlight 不带过滤参数的既有行为）
- `--scorer X` / `--team T`：单个合集（互斥，同 build_highlight 契约）
- `--all`：读 work/<S>/roster.json（走 roster.py validate_roster 校验），遍历 players 逐人 --scorer <tag> + 遍历出现过的 team 逐队 --team，顺序 subprocess；**便服队不入分队合集**——展开 team 时跳过「便服」并记 WARNING（口径同 build_highlight「--team 便服 报错退出 1」契约；便服球员的个人合集照常出）；roster 不存在 → 报错退出 1 并提示先跑 people。**注意 build_highlight 对 --roster 强制所有 assignment confirmed=true，未确认 roster 会被底层拒收退出 1**（报错自下而上冒出即可，CLI 不重复校验）
- 尺寸：读 `work/<S>/session_facts.json` 逐文件 width/height 做主比例判定 → 比例 ≈16:9 出 `1920x1080`、≈4:3 出 `1440x1080`（容差 ±1%）；**混比例或未知比例 → 报错退出 1 并列出各文件比例**（混比例须分别合成是立哥定的规格，CLI 不自动选）
- 透传：`build_highlight.py --goals ... --roster work/<S>/roster.json（存在才传） --rawdir <rawdir> --out <W>x<H> [--scorer X | --team T]`；输出目录 output/<场次>/ 由 build_highlight 自定（goals.json 的 session 字段），CLI 不管

### 错误处理（rules.md 鲁棒优先）

- 每个 subprocess 前 log 完整命令（shlex.join），非零即停：打印失败命令 + 已完成的步骤清单，exit 1
- run_step 统一给子进程 env 注入 `PYTHONIOENCODING=utf-8`（Windows 控制台中文日志/帮助会触发 UnicodeEncodeError，已知坑见 docs/经验教训.md §6）；聚类段再叠加 `HTTPS_PROXY`
- work/<场次>/ 不存在、goals 全缺失、state 与 --rawdir 都缺、混比例 → 均为前置校验报错退出 1，不启动任何 subprocess
- 所有 JSON 读写走 pipe_common（read_json/atomic_write_json），schema 坏抛错不静默

## Project Structure

```
scripts/
  video.py           新：统一入口（argparse 子命令 → subprocess 薄封装）
tests/
  test_video.py      新：命令拼装/批次发现/尺寸换算/state 读写/错误传播/dry-run
docs/video-cli/      本四件套
```

## Open Questions（已拍板）

- 子命令名 score/people/build——立哥定（2026-08-11 初定拼音 jinqiu，2026-08-12 改 score）
- 不做 `video label`：标注页由 score 链路末端 gen_label_page 生成，人工打开，无命令可封
- people 是否默认 --read-numbers：否（花 token，立哥按需显式开）
