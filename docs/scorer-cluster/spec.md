# Spec: 认人提效——轨迹选帧多裁 + CLIP 聚类逐人确认

## Objective

现状痛点：认人页逐球确认（104 球点 104 次），且裁图只取定位时刻单帧，
不一定清晰/正面，连累颜色分队与号码识别准确率。

本功能做两件事（2026-08-09 立哥拍板，方案 1+2）：

1. **追踪选帧多裁**：定位到投篮者后，沿其轨迹链取多帧，按质量分
  （框面积 × 清晰度）选 top N 帧裁图，喂给后续所有识别。
2. **聚类逐人确认**：用 CLIP 图像 embedding 把所有投篮者裁图按外貌聚类，
  认人页按"人"（簇）确认一次应用到全簇，104 球 → 认 ~20 人。

成功标准：

- 实跑 20260722 场次（104 confirmed 球，roster 已确认作真值；输入 =
  scorers + scorers_b2 + scorers_b3 三个 candidates 合并，evaluate 只统计
  roster assignments 里有的 104 键，其余键剔除）：簇数 15~25 区间，
  簇纯度（簇内多数 tag 占比）≥ 85%（--evaluate 报告）。
  纯度不达标时的降级出口：真实指标记 review，簇级功能照上
  （逐球覆盖兜底），纯度目标转为观察值
- 认人页支持簇级一次选人，逐球覆盖保留；导出 roster.json 契约不变
- 纯函数单测覆盖新逻辑，ruff+pytest 全绿

## Tech Stack

- Python 3.14，open_clip_torch 3.3.0（已装，CLIP 图像 embedding）
- scikit-learn 1.9.0（已装，AgglomerativeClustering）
- opencv 5.0.0（已装，Laplacian 清晰度）/ pillow 12.3
- 零 token、零新 pip 依赖；CLIP 权重（ViT-B-32）首次经
  `HTTPS_PROXY=http://127.0.0.1:7897` 从 HF 下载，之后本地缓存

## Commands

```bash
# 质量门（改动后必跑）
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && \
  python -m ruff check --fix scripts tests && python -m pytest -q

# 多裁（crop_scorers 增强，--best-crops 默认 3；--read-numbers 必带：
# 缓存命中零新调用直接回填，否则重跑落盘会丢现有 number_guess）
python scripts/crop_scorers.py --goals work/20260722/goals.json \
  --detectdir work/detect --framesdir work/frames \
  --out work/20260722/scorers_b3 --candidates work/20260722/candidates_batch3.json \
  --rawdir "20260722地平线/2026 年 7月22 日 地平线" --read-numbers --max-reads 80

# 聚类（新脚本；--candidates 可重复传多个批次文件，键集取并集）
python scripts/cluster_scorers.py \
  --candidates work/20260722/scorers/scorer_candidates.json \
  --candidates work/20260722/scorers_b2/scorer_candidates.json \
  --candidates work/20260722/scorers_b3/scorer_candidates.json \
  --out work/20260722/scorer_clusters.json

# 纯度自检（只统计 roster assignments 里的 104 键）
python scripts/cluster_scorers.py \
  --candidates work/20260722/scorers/scorer_candidates.json \
  --candidates work/20260722/scorers_b2/scorer_candidates.json \
  --candidates work/20260722/scorers_b3/scorer_candidates.json \
  --out work/20260722/scorer_clusters.json \
  --evaluate --roster work/20260722/roster.json

# 认人页（簇级确认；candidates 传哪批就出哪批，簇信息按 key 匹配）
python scripts/gen_scorer_page.py --goals work/20260722/goals.json \
  --candidates work/20260722/scorers_b3/scorer_candidates.json \
  --clusters work/20260722/scorer_clusters.json \
  --roster-existing work/20260722/roster.json \
  --index work/20260722/review_batch3/events_index.json \
  --out work/20260722/scorers_b3
```

## Project Structure

```
scripts/
  crop_scorers.py      改：定位后人框 IoU 链 + 质量选帧 + 多裁（--best-crops N）
  cluster_scorers.py   新：CLIP embedding + 凝聚聚类 + --evaluate 纯度自检
  gen_scorer_page.py   改：--clusters 注入，簇级选人应用全簇，逐球覆盖保留
work/<场次>/scorers*/  → 裁图（多裁）、scorer_candidates.json、scorer_clusters.json
tests/                 → 纯函数单测（合成 mot_cache/embedding，不碰真帧/网络）
docs/scorer-cluster/   → 本四件套
```

## 数据契约

### crop_scorers.py 多裁（scorer_candidates.json entry 增量）

candidates 文件顶层结构为 `{"session", "candidates": [...]}`（与现状一致）。

```json
{
  "crop": "最佳裁图文件名（= crops[0]，向后兼容，页面/号码识别沿用）",
  "crops": ["最佳", "次佳", "第三"],
  "crop_scores": [0.83, 0.71, 0.65]
}
```

- `crops` 只在 status=OK 时存在；旧数据无此字段 → 消费方回退单 `crop`
- crops[0] = **质量分最佳帧**（写死）；定位帧只是链上候选之一，不保证入选。
  链错人时风险由"页面预览片段视频终裁"兜底
- 质量分 = 归一化框面积 × Laplacian 方差（裁图后算，仅相对排序有意义）
- 选帧窗口 = 定位帧前后各 min(2s, mot_cache 覆盖边界)，5fps 即各 ≤10 帧，
  越界即停；帧间 IoU ≥ 0.3 链上，链断即停
- 选帧去重：入选帧间隔 ≥0.5s（同人连续帧裁剪近乎重复，无信息增量）
- 多裁命名：`_crop_name(fid, anchor)` 主名 + `_q{rank}` 后缀
  （rank 1 为主名本身保持兼容，rank≥2 追加 `_q2`/`_q3`）
- 号码识别沿用 crops[0] 单张（多帧多数投票是后续增强，见 Open Questions）；
  number_cache 键仍为 goal key——多裁重跑后裁图内容可能变化而缓存沿用旧结论，
  属已知漂移，口径：号码只是预填提示，终裁在页面

### cluster_scorers.py 输出（scorer_clusters.json）

```json
{
  "version": "cluster-v1",
  "model": "ViT-B-32/laion2b_s34b_b79k",
  "threshold": 0.25,
  "clusters": [
    {"cluster_id": 1, "keys": ["<file>#<anchor>", "..."], "rep_crops": ["..."]}
  ],
  "unclustered": ["<SKIP 或无裁图球的 key>"]
}
```

- 一人多图：该球所有 crops 的 embedding 取均值再聚类（球为聚类单位，
  不是图为单位——避免同球多图散到不同簇）
- embedding 缓存落盘 `<out 同目录>/clip_cache.json`，key = model + 裁图 md5，
  断点续跑不重复推理；threshold 不进缓存键（只影响聚类步，标定调档
  不重复推理）；model 变更整体作废重建
- 多批次输入：`--candidates` 可重复传参，键集取并集；同 key 后者覆盖前者
- --evaluate 只统计 roster assignments 里有的键，其余键（removed/去重球）
  剔除不计入纯度

### gen_scorer_page.py 页面

- `--clusters` 可选；无则行为与现状完全一致（向后兼容）
- 有 clusters 时页面分两块：
  - **簇区**：每簇一行——代表图墙（rep_crops）+ 簇内球数 + 选球员按钮；
    选人一次应用到簇内全部球
  - **逐球区**：现有条目不变，追加显示簇号；单个改人覆盖簇归属
- 导出 roster.json 的 schema/合并逻辑不变（--roster-existing 沿用）

## Code Style

遵守根目录 rules.md（鲁棒优先 ＞ 性能 ＞ 简洁）；dataclass 契约 +
显式校验 + SchemaError/BasketballPipelineError 分层，与现有 scripts 一致。

## Testing Strategy

- pytest 纯函数单测，不碰真帧/真模型/网络：
  - 人框 IoU 链（合成 persons 序列：链上/链断/多人交叉）
  - 质量排序与 ≥0.5s 去重（合成分数序列）
  - 聚类：合成 embedding（明显两堆/全相同/全不同），断言簇划分
  - 簇级选人合并 assignments 的逻辑（页面 build 层纯函数）
- CLIP 推理与聚类实跑走 --evaluate 人工看报告，不进 pytest

## Boundaries

- Always：质量门全绿后提交；embedding/号码缓存落盘幂等
- Ask first：新 pip 依赖（本功能零新增）；CLIP 模型选型变更
- Never：不改 goals/label 流程；不动 roster.json schema；SKIP 球不进簇；
  不删除旧裁图（多裁是增量，旧单裁字段保留）
- 聚类只做**预填分组**，立哥确认仍是终裁；簇划分错误由逐球覆盖兜底

## Success Criteria

- [ ] crop_scorers --best-crops 产出多裁 + 质量分，旧数据兼容
- [ ] cluster_scorers 产出 scorer_clusters.json，缓存幂等
- [ ] --evaluate 对 20260722 报簇数/纯度，达标（15~25 簇、纯度 ≥85%）
- [ ] gen_scorer_page --clusters 簇级确认 + 逐球覆盖，导出契约不变
- [ ] ruff+pytest 全绿；四件套齐全（review 按轮次编号）

## Open Questions

- distance_threshold 默认 0.25 是拍脑袋起点，--evaluate 实跑后标定，
  标定值记 review01；三档（0.20/0.25/0.30）都不达标走降级出口
  （指标记 review、功能照上、纯度转观察值）
- ViT-B-32 权重 ~350MB 首跑下载；若代理不通则降级 laion2b 小模型或
  留立哥手动放权重（实跑时确认）
- 号码识别只用 crops[0]，而质量最佳帧未必露号码；多帧多数投票
  （同人多帧读号取众数）留作后续增强
