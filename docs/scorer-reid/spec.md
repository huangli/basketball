# Spec: 认人增强——Re-ID 聚类 + 多帧读号投票 + 名单映射

## Objective

认人提效（docs/scorer-cluster/）实跑结论：通用 CLIP 全身裁图聚类纯度不达标
（complete@0.15 = 52 簇/62.6%；85% 纯度需 81 簇无批量意义）。2026-08-09
立哥拍板三条增强（照片库暂缓，等供照）：

1. **Re-ID 专用模型聚类**：OSNet（torchreid）替换/对比 CLIP——专用行人
   重识别特征不被球衣颜色/场景带偏，目标同队不同人分得开。
2. **多帧读号投票**：多裁已有（每球最多 3 张），K3 读号从"只读 crops[0]"
   升级为"逐张读 + 众数投票"，压低单帧误读。
3. **名单映射预填**：立哥提供半截篮号码→姓名名单（地平线暂无），
   读号命中名单即预填真人名。机制已存在（gen_scorer_page --players +
   match_players_by_number），本功能补齐文件注入与队名映射核对。

成功标准：

- Re-ID 聚类实跑 20260722 三批次（对照 roster 104 assignments，入统口径
  同 cluster 标定——上一轮 CLIP 实为 99 键入统）：**≤30 簇且纯度 ≥85%**；
  不达标按既有降级出口（记 review、功能照上、纯度转观察值），并保留
  CLIP 后端可切换
- 多帧读号：合成数据单测覆盖投票规则（含 None 票与单票路径）；
  20260722 用跳票模式（--numbers-cache-only）重跑，**零新调用**回填不丢
  （旧缓存迁移只覆盖 crops[0] 一票，crops[1..] 跳票）；
  新场次全量模式每球新调用 ≤ best_crops 张且受 --max-reads 闸控制
- --players-file 注入名单 + 号码→姓名预填链路单测；无名单时页面行为不变
- ruff+pytest 全绿；四件套齐全

## Tech Stack

- 新增依赖：**torchreid**（PyPI: deep-person-reid；纯 PyTorch，CPU 可跑；
  立哥 2026-08-09 已批准"先用新模型"）。模型 osnet_x1_0（~2M 参数，
  权重 ~10MB，torchreid model zoo 经 `HTTPS_PROXY=http://127.0.0.1:7897`
  下载；输入 256×128 人形裁图，与现有裁图天然匹配）
- 既有：open_clip_torch（CLIP 后端保留）、scikit-learn、opencv、pillow
- K3 读号（既有 --read-numbers 链路，走订阅额度）

## Commands

```bash
# 质量门（改动后必跑）
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && \
  python -m ruff check --fix scripts tests && python -m pytest -q

# 依赖验证（Phase A spike，先跑这个再写后端）
# 勘误（2026-08-09 实跑）：PyPI 没有 deep-person-reid，实际包名是 torchreid
pip install torchreid tensorboard   # 清华镜像；tensorboard 是其隐性依赖
python -c "import torchreid; print(torchreid.__version__)"

# Re-ID 聚类 + 纯度自检（--model 切换后端，缓存键含 model 互不污染）
HTTPS_PROXY=http://127.0.0.1:7897 python scripts/cluster_scorers.py \
  --candidates work/20260722/scorers/scorer_candidates.json \
  --candidates work/20260722/scorers_b2/scorer_candidates.json \
  --candidates work/20260722/scorers_b3/scorer_candidates.json \
  --out work/20260722/scorer_clusters_reid.json \
  --model osnet_x1_0 --linkage complete --threshold <标定值> \
  --evaluate --roster work/20260722/roster.json

# 多帧读号（全量模式默认逐张读；旧数据重跑用跳票模式零新调用）
python scripts/crop_scorers.py --goals ... --read-numbers --max-reads 300 ...
python scripts/crop_scorers.py --goals ... --read-numbers --numbers-cache-only ...

# 名单文件注入认人页（与 --players 串互斥）
python scripts/gen_scorer_page.py --scorers ... --goals ... \
  --players-file work/<场次>/players.json ...
```

## Project Structure

```
scripts/
  cluster_scorers.py   改：encoder 后端抽象（clip|osnet_x1_0），--model 参数
  crop_scorers.py      改：读号逐张 + 众数投票；number_cache 键改裁图 md5 + 旧缓存迁移
  gen_scorer_page.py   改：--players-file（JSON 名单，与 --players 互斥）；
                       team_of_tag 队名映射核对（地平线/半截篮/便服）
work/<场次>/players.json → 名单（立哥供，格式同 roster.players 数组）
tests/                 → 纯函数单测（合成 embedding/投票序列，不碰真模型/网络）
docs/scorer-reid/      → 本四件套
```

## 数据契约

### cluster_scorers.py --model（后端抽象）

- CLI 取值 → 缓存 model_tag 对应表（写死）：

  | --model | model_tag | 说明 |
  |---------|-----------|------|
  | `clip`（默认） | `ViT-B-32/laion2b_s34b_b79k` | 现状 MODEL_TAG 保持不变，复用现有 clip_cache |
  | `osnet_x1_0` | `osnet_x1_0/market1501` | torchreid 后端 |

- 缓存键已含 model tag（`clip_cache.json` key = model + 裁图 md5），
  两后端共存不串（文件名沿用 clip_cache.json 不改，docstring 注明；
  _meta.model 只记最后运行者，可接受）；Re-ID 缓存同文件同规则
- 输出 scorer_clusters.json 的 model 字段记实际后端（现状硬编码
  MODEL_TAG，需改）；其余契约不变
- encoder 构造失败（torchreid 未装/权重下载失败）→ ExternalApiError
  显式报错含安装/代理提示，不静默回退 CLIP（防"以为在跑 Re-ID 实际不是"）

### crop_scorers.py 读号投票（--read-numbers 语义升级）

- 对 status=OK 球的每张 crops（最多 best_crops 张）各读一次号
  （缓存命中不重复扣额度），逐张得 NumberGuess
- **投票规则（写死）**：number=None 的票（K3 看不清属合法返回）不参与
  计数，仅在有号码的票中投票——
  - 同号 ≥2 张 → 采纳该号
  - 有效票 =1 → 等价"取唯一"规则：conf=high 采纳、conf=low 归 None+low
  - 有效票 ≥2 且全不同 → 取唯一 conf=high 的单帧结果（多个 high 不采）
  - 其余（含有效票 =0）→ number=None、confidence=low
- **两种读号模式（写死）**：
  - 全量模式（默认）：缓存未命中的裁图发起新调用，受 --max-reads 闸控制；
    新场次用。额度估算 = 球数 × best_crops（如 100 球 ×3 ≈ 300 次新调用，
    --max-reads 要按此设，不再是球数 ×1）
  - 跳票模式（`--numbers-cache-only`）：缓存未命中的裁图跳过不读、只用
    已有票投票，零新调用；20260722 等"旧数据重跑回填"场景用
- entry["number_guess"] 结构不变（消费方零改动）；新增
  entry["number_votes"] = 逐张结果摘要（调试可追溯）
- **number_cache 键改 `<crop_md5>`**（跨球复用）；**迁移规则（写死）**：
  - 触发位置：--read-numbers 路径内、load_number_cache 之后、识别闸之前；
    不带 --read-numbers 的运行不迁移（该路径本就不回填号码，无损失）
  - 旧 goal key → 当前 run entries 反查该球 crops[0] 文件算 md5 重键，
    **零新 API 调用**
  - 旧 key 在当前 run entries 里查不到（删球/子集重跑）→ 原样保留记 INFO，
    清理由人决定
  - crops[0] 文件缺失算不出 md5 → 记 WARNING 保留原 key，不炸整批
  - 迁移幂等：二次执行零变化
- 闸：全量模式单次运行新调用 > --max-reads 拒绝执行（现状沿用）

### gen_scorer_page.py --players-file

- JSON 数组，与 roster.players 同构：`[{"tag":"白22","name":"小朱","team":"半截篮"}]`
- 与 --players 串互斥（同时给 → parser.error）；校验复用 roster.py 的
  Player/player_from_dict + 队名合法值（地平线/半截篮/便服）
- team_of_tag 前缀映射（现状已核实与目标口径一致：黑/蓝→地平线、
  白→半截篮、余→便服，gen_scorer_page.py _TEAM_PREFIXES）——**零改动，
  只补测试锁定**；顺手修 roster.py:16 docstring 的过时队名注释
  （写"黑/白/便服"，实际 VALID_TEAMS=地平线/半截篮/便服）

## Code Style

遵守根目录 rules.md（鲁棒优先 ＞ 性能 ＞ 简洁）；与现有 scripts 一致的
dataclass 契约 + 显式校验 + SchemaError/ExternalApiError 分层。

## Testing Strategy

- pytest 纯函数单测，不碰真模型/网络/真图：
  - encoder 后端工厂：注册/查无此模型显式失败（不 import 真 torchreid，
    注入假 encoder 测聚类主链路）
  - 投票规则：同号≥2 采纳 / 单票 high 采纳 low 归 None / 多票全不同取唯一
    high / None 票不参与计数（[7,null,null] 按单票路径走）/ 全 None 归 None+low
  - 跳票模式：缓存未命中不发起调用、用已有票投票、零新调用
  - 缓存迁移：goal key 旧缓存 → md5 新键（合成裁图文件），幂等（二次迁移
    零变化）；查不到 entry 的旧 key 保留 + INFO；裁图缺失 WARNING 保留原 key
  - --players-file：合法名单解析、与 --players 互斥、坏 JSON/坏队名抛 SchemaError
- Re-ID 实跑走 --evaluate 对照 roster 看报告，不进 pytest

## Boundaries

- Always：质量门全绿后按 Phase 分次提交；embedding/读号缓存幂等落盘
- Ask first：除 torchreid 外的新依赖；Re-ID 模型选型变更（osnet_x1_0 以外）
- Never：不改 goals/label 流程；不动 roster.json schema；聚类/读号/名单
  预填都不是终裁（立哥页面确认为终裁）；不删旧缓存（迁移是重键不是删除——
  迁移后旧条目保留一轮，下次实跑无误再清）
- torchreid 安装验证（Phase A）失败 → 停工报立哥，备选（timm 模型/手动
  加载 OSNet 权重）经立哥点头再换路

## Success Criteria

- [ ] torchreid 在 Python 3.14 + torch 2.13 (CPU) 装上且单张推理通过
- [ ] cluster_scorers --model osnet_x1_0 实跑 20260722：≤30 簇且纯度 ≥85%
  （不达标走降级出口并记录完整标定曲线）
- [ ] 读号投票 + 缓存迁移（零新调用）实跑 20260722 无回归
- [ ] --players-file 注入 + 号码→姓名预填链路（半截篮名单到位即可用）
- [ ] ruff+pytest 全绿；四件套齐全（review 按轮次编号）

## Open Questions

- torchreid 对 Py3.14/torch 2.13 的兼容性未验证（Phase A spike 第一件事）；
  若挂，备选路线见 Boundaries
- osnet_x1_0 输入 256×128 会重缩放裁图，远景小人裁图（高宽比异常）是否
  伤到特征——实跑标定时观察
- 半截篮名单立哥后补（文本发来我转 players.json）；地平线名单暂缺，
  其球员号码预填不生效（颜色+聚类分组照旧）
