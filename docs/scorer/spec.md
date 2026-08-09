# Spec: 进球人识别（投篮者定位 / 分队 / 认人确认页 / roster.json）

> 2026-07-30 v1 → 2026-07-31 v2（按 docs/scorer/review01.md 修订：
> B1 真值表、B2 定位算法、M1-M6 全修）→ 2026-08-08 v3（轨迹法替换逐帧投票，
> 批次 1 验收返修；实测 OK 17/17、SKIP 0）。
> 目标：把"这球是谁进的"从纯人工问答变成"机器预填 + 立哥点确认"，
> 产出个人合集与分队合集。与批次 2 流水线并行开发，**只用新文件**，对既有数据只读。

## Objective

批次 1 已验收 17 个 confirmed 进球，批次 2（185 事件）标注在即。
要出 `个人_XX_进球合集.mp4` 和 `队伍_XX_进球集锦.mp4`，缺进球者归属。
约束（AGENTS.md 已定）：命名用标签不用真名、roster 按场次隔离且需立哥确认、跨场次不合并。

机器做三件事（全部可选降级，立哥确认是终裁）：

1. **投篮者定位**（零成本）：进球锚点前窗口内，mot_cache 球轨迹与人框关联找出投篮者，裁图。
2. **分队颜色**（零成本）：投篮者躯干主色 → 黑/白/便服。业余局按颜色分队，语义天然成立。
3. **号码识别**（可选，K3 走订阅额度）：读投篮者背号 → 预填"疑似黑21"。
   球衣互换时预填可能错，确认页裁图在立哥眼前，错了一键改。

成功 = 立哥在认人确认页上每个进球 1~2 秒完成归属，导出 roster.json 后一条命令出个人/分队合集。

## Tech Stack

Python 3.14.3（标准库 + numpy/PIL；scikit-learn 已装备用）；ffmpeg；
Kimi K3（可选号码识别，复用 vlm_filter 的 OAuth 凭证机制，不落文件）。无新依赖。

## Commands

```bash
export PYTHONIOENCODING=utf-8
python -m ruff format scripts tests && python -m ruff check --fix scripts tests && python -m pytest -q

# 投篮者裁图 + 颜色分队（轨迹法定位；产出 crops + clips + scorer_candidates.json）
python scripts/crop_scorers.py --goals work/20260722/goals.json --detectdir work/detect \
    --framesdir work/frames --out work/20260722/scorers \
    --candidates work/20260722/candidates.json \
    --rawdir "20260722地平线/2026 年 7月22 日 地平线"
# 号码识别（可选；结果落 number_cache.json 幂等不重复扣费；>20 球须先问立哥）
python scripts/crop_scorers.py --goals work/20260722/goals.json --detectdir work/detect \
    --framesdir work/frames --out work/20260722/scorers \
    --candidates work/20260722/candidates.json \
    --rawdir "20260722地平线/2026 年 7月22 日 地平线" --read-numbers
# 认人确认页（--players 优先；无名单时退化为自由文本输入 + 颜色预填）
python scripts/gen_scorer_page.py --scorers work/20260722/scorers/scorer_candidates.json \
    --goals work/20260722/goals.json --session 20260722 --players "黑21=大斌,白22=某某"
# 批次 2 合并：--roster-existing 读已有 roster，assignments 并集合并（同键冲突报错退出 1）
python scripts/gen_scorer_page.py --scorers work/20260722/scorers_b2/scorer_candidates.json \
    --goals work/20260722/goals_batch2.json --session 20260722 --roster-existing work/20260722/roster.json
# 出合集
python scripts/build_highlight.py --goals work/20260722/goals.json --roster work/20260722/roster.json \
    --rawdir "20260722地平线/2026 年 7月22 日 地平线" --out 1920x1080 --scorer 大斌
python scripts/build_highlight.py --goals work/20260722/goals.json --roster work/20260722/roster.json \
    --rawdir "20260722地平线/2026 年 7月22 日 地平线" --out 1920x1080 --team 黑
```

## Project Structure

```
scripts/
  crop_scorers.py      新：投篮者定位裁图 + 颜色分队 +（可选）号码识别（带缓存）
  gen_scorer_page.py   新：认人确认页 scorer.html（独立于 gen_label_page.py；
                       默认输出 <scorer_candidates.json 同目录>/scorer.html）
  build_highlight.py   改：--roster/--team 参数 + 按 --team/--scorer 分支取名
                       （队伍_/个人_ 前缀）+ 过滤逻辑分叉
work/20260722/scorers/ → 裁图、scorer_candidates.json、number_cache.json
work/20260722/roster.json → 归属结果（立哥确认后由页面导出）
tests/                 → 纯函数单测（合成 mot_cache/goals，不碰真帧/网络）
```

## roster.json schema（写读双方契约，写死）

```json
{
  "session": "20260722",
  "confirmed": true,
  "players": [
    { "tag": "黑21", "name": "大斌", "team": "黑" },
    { "tag": "白22", "name": "某某", "team": "白" },
    { "tag": "灰T恤-A", "name": "", "team": "便服" }
  ],
  "assignments": {
    "dji_mimo_20260722_191948_0_1784829615943_video.mp4#4.1": "黑21"
  }
}
```

- `assignments` 键 = `<file>#<anchor_time>`（file 保留全名含 .mp4 供人工可读；
  anchor_time 格式化规则 = `f"{t:.1f}"`，认人页导出与 build_highlight 匹配**两端共用
  同一 format 函数**，禁止各自裸拼）；"黑"/"白"/"便服"为合法 team 值。
- `confirmed=true` 的条件：**全部非 SKIP confirmed 球都已归属**；SKIP 球允许未归属
  （build_highlight 对未归属球 WARNING 跳过，归入口头"未识别"桶，不阻塞合成）。
- fid 映射：`fid = 文件主名（去 .mp4）`（extract_frames/mot_candidates 一致）；
  定位读 `work/detect/<fid>_mot_cache.json`、`work/frames/<fid>/` 用 fid，roster 键用 file 全名。

## build_highlight 组合真值表（B1 修订，写死）

| --roster | --scorer | --team | 行为 |
|---|---|---|---|
| 无 | 无 | 无 | 全员（现状不变） |
| 无 | 有 | 无 | 旧兼容路径：精确匹配 goals.json 的 scorer 字段；命中 0 条时 WARNING 提示改用 --roster |
| 有 | 无 | 无 | 全员（roster 仅作 confirmed 校验，未 confirmed 拒收退出 1） |
| 有 | 有 | 无 | roster 内解析（tag 或 name 任一命中）→ 反查 assignments 过滤 |
| 有 | 无 | 有 | 按 team 取 players.tags → 反查 assignments 过滤；产出 `队伍_{team}_进球集锦.mp4` |
| 有 | 有 | 有 | 互斥，报错退出 1 |
| 无 | – | 有 | 无 roster 无法分队，报错退出 1 |

## 投篮者定位算法（B2 修订，v3 轨迹法，写死）

已知事实：mot_cache `persons` 是**无 track ID 的框列表**（run_mot 只对球做 MOT）；
逐帧 max-conf 球检测不可信（海报球/邻场球导致球位瞬移，批次 1 实测 0.2s 跳 800px），
**任何逐帧散点规则（持球/最近人框投票）均被证伪**（v2 的 IoU 链投票法即在此列，
17 球实测明确错 2 + 可疑多张）。v3 起改用轨迹法：

1. 窗口 [anchor−4.0, anchor+0.5]，用 `mot_candidates.run_mot(min_length=1)`
   在窗口内重链球轨迹（短轨迹必须保留：5fps 下飞行段必然断成 1–3 点短链）。
2. 选轨迹：末端与候选锚点（--candidates 提供的 cx/cy，fid+|t0−anchor|≤0.3s 匹配）
   最近者为进球轨迹；端点距 >200px → SKIP。
3. 沿轨迹从末端回放：最后一个球心严格落在人框内（无 margin）的轨迹点 →
   该人框=投篮者（最后持球者）；整轨无持球点 → 轨迹起点时刻最近人框（start_fallback）；
   轨迹不存在 → SKIP。
4. 裁图帧=该轨迹点所在帧；规格不变（外扩 20%、短边放大到 400px）。

批次 1 实测：OK 17/17、SKIP 0；裁图明确对 4 / 勉强 10 / 可疑 1 / 明确错 2。
**残余风险**（锚点落在防守人身上或锚点附近只有场边人时轨迹法无解）由确认页
人工终裁兜底——预览片段与裁图同锚点，立哥一眼可改。裁图/预填只是辅助，视频是终裁依据。

## 颜色分队判据（M4 修订）

- 采样区：人框水平中 60% × 垂直 25%~60% 中间带（躯干，排除头/腿/背景边缘）。
- 判据：采样区像素 HSV 双阈——黑：V < TH_BLACK；白：V > TH_WHITE 且 S < TH_SAT；
  其余（含近阈）归"便服"。TH_* 数值按批次 1 的 17 张裁图标定，常量注释实测来源。

## Testing Strategy

pytest 纯函数单测（不碰真帧/网络/API）：

- 定位（v3 轨迹法）：合成 mot_cache 窗口重链（run_mot min_length=1）；端点距候选锚点
  最近者胜出、>200px → SKIP；持球点严格包含无 margin；整轨无持球 → start_fallback；
  SKIP 三分支（no_track / 端点过远 / 起点无人框）；--candidates fid+|t0−anchor|≤0.3s
  匹配、未给或未匹配时退化为端点时间最近选轨迹
- 键格式化：f"{t:.1f}" 两端一致（4.1234→"4.1"）；file→fid 去扩展名
- 颜色分队：合成纯色裁图 → 三分类正确；近阈归"便服"
- roster schema：缺 players / tag 重复 / team 非法值 / 键格式错 → SchemaError
- 真值表：七个组合分支逐一覆盖（含互斥报错、无 roster 给 --team 报错）
- 合并：--roster-existing 并集合并、同键冲突退出 1、players 缺 tag WARNING

## Boundaries

- Always：ruff+pytest 全绿再交付；roster 每场独立且 confirmed=true 才用于合成；
  预填只是建议，确认页必须同时显示裁图让立哥目检；
  本 spec 已授权 build_highlight 的 --roster/--team/--scorer 语义改动（真值表范围）
- Ask first：号码识别单批超 20 次新调用；**超出真值表范围**的 build_highlight 语义改动；
  把 roster 写进 goals.json（当前设计分离，不合并）
- Never：写真名进代码/测试（名单只从 --players/--players-file/players.json 注入）；
  修改 gen_review_clips.py / gen_label_page.py；改动批次 1 封存的 goals.json；
  API key 入文件或日志

## Success Criteria

1. ruff + pytest 全绿（≥115 + 新增）
2. 批次 1 的 17 个 confirmed 各产出投篮者裁图；立哥抽查 ≥3 张认可"是投篮者本人"
   （SKIP 不计入分母；SKIP 率 >30% 则定位规则返工）
3. 颜色分队在批次 1 上产出黑/白分布，立哥目检分布合理（抽查 3 张）
4. roster.assignments 覆盖全部非 SKIP confirmed 球时，--scorer/--team 合集进球数
   与归属数一致；SKIP 未归属球 WARNING 跳过且不阻塞
5. gen_label_page.py 与 review_batch2 产物零改动（git status 无这两个路径）

## Open Questions

1. 本场球员名单（号码/特征 → 称呼 + 队别）——阻塞球员按钮；无名单时确认页退化为
   自由文本输入 + 颜色预填（聚类分组留待后续）
2. 号码识别：2026-08-08 立哥拍板启用（K3，订阅额度；批次 1 实测读号 5/5 忠实无幻觉）
3. 便服球员默认不进任何分队合集，只进全员与个人合集
4. 批次 1/批次 2 roster 合并走 --roster-existing（见 Commands），players 以新名单为准
