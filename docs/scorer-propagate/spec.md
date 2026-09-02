# Spec: 认人提效二期——轨迹传播 + 离线读号

## Objective

2026-08-22 立哥问"不用 AI 的算法层面怎么提升认人命中率"，拍板做两件事：

1. **轨迹传播（主力）**：球员上场后连续打几分钟不换人。已确认的归属沿
   投篮者的人框轨迹（mot_cache 现成数据）传播给同轨迹上的其他进球——
   一个"在场时段"只认一次，不是每球认一次。纯几何规则（IoU 链），零模型
   零 token。
2. **离线读号（辅助，试验性质）**：传统 CV 模板匹配读背号，免 K3 额度。
   精度预期不如 K3，定位是"额度保险 + 跳票模式补强"；**实跑不达标就砍**，
   只留下降级说明。

成功标准（**前置条件：存在带 confirmed roster 的场次数据**——work/ 现已
清场，20260722 锚点数据不存在，实跑标定挂到下一个新场次（认人流程本来
就要跑，顺带留真值）；此前 Phase 实现+单测先行）：

- 轨迹传播：实跑新场次按 §--evaluate 协议报告——**预填准确率 ≥90% 且
  覆盖倍数 ≥1.5**（阈值可调，实跑标定记 review01）
- 页面：逐球归属时同轨迹球自动预填同 tag（规则见 §页面，写死）；
  传播预填优先级低于立哥手改、低于号码/照片/印名预填
- 离线读号：新场次对照 K3 已读结果实跑，**一致率 ≥70% 才保留**，
  否则该 Phase 砍掉、结论记 review01
- 纯函数单测 + ruff/pytest 全绿；四件套齐全

## 背景事实（已核实，写死）

- mot_cache：5fps 抽帧，persons 按帧对齐存 Box（`crop_scorers.load_mot_cache`）
- `locate_scorer` 定位投篮者得 (frame_idx, box)；`trace_person` 已有 ±2s
  IoU≥0.3 链（窗口常量 TRACE_WINDOW_SEC=2.0）
- 大疆分段：单个视频 ~20~60s，同文件常有多球（如 0030：60s/63s/66s）；
  **人轨迹不跨文件**（文件间人员位置任意跳变），跨文件传播不做
- 素材特性：约 7 成球入网后录像 <2s（docs/经验教训.md），锚点后轨迹常被
  物理截断——传播以**向前（往更早帧）回溯**为主
- work/ 已清场（2026-08-16 起 video clean），所有"旧数据兼容"语义指
  **新场次本次运行内**的兼容：crop_scorers 先跑落 seed 字段，propagate
  后跑消费；不存在历史 candidates 需要迁移

## Tech Stack

- 零新依赖：numpy/PIL/opencv/sklearn 足够（IoU 链纯几何；模板匹配用
  opencv matchTemplate）
- 不引入 tesseract 等外部 OCR 二进制

## 数据契约

### crop_scorers.py（小改）

- `_process_goal` 定位 OK 时 entry 增三个可选字段：`seed_frame`（int）、
  `seed_box`（[x1,y1,x2,y2]）、`seed_team`（种子帧 team_of_box 结果）；
  SKIP 球不落（与 crops 口径一致）
- propagate **只消费 entry 的 seed 字段，不自行重跑 locate_scorer**
  （重算不给 anchor_xy 会退化成"端点时间最近"，可能与裁图定位不一致）；
  seed 缺失的球 → WARNING 跳过进 unlinked，不静默退化

### 人轨迹（propagate_scorers.py，新脚本）

- **文件内贪心多目标跟踪**：逐帧（5fps）遍历 persons，活跃轨迹按
  最近框 IoU≥0.3 吸收检测框；无匹配开新轨；轨迹超过 `MAX_GAP_FRAMES`
  （默认 10 帧=2s）无更新即封存
- **唯一性规则（写死）**：每帧每框至多入一轨；同帧多轨迹竞争同一框时，
  按"轨迹最后更新帧更近 → IoU 更大 → track_id 更小"排序裁决
- **颜色守卫（写死）**：封存时沿轨迹每 5 帧采样 `team_of_box`；
  "便服"样本不计入一致也不计入不一致；黑/白样本中主色占比 <60% →
  `mixed=true`。mixed 轨迹只展示、不参与自动预填
- **进球→轨迹映射**：entry 的 seed_frame/seed_box 对该帧全部轨迹框找
  IoU 最大 ≥0.3 者归该轨；归不上 → 该球进 unlinked（不参与传播）
- **传播预填来源（写死）**：同文件同 track_id 的球中，已有"号码预填命中
  （唯一）或 roster 归属"的 tag；**被预填球自身不算源**；多个源冲突 →
  不预填，note="conflict"；源 tag = NOGOAL 哨兵永远不作源
- 输出 `<scorers 目录>/track_links.json`（candidates 文件只读不改）：
  `{version, per_file: {fid: {tracks: [{track_id, keys, mixed, span}], unlinked: [keys]}}}`
  （unlinked = 归不上轨迹的进球 key，不参与传播），
  页面按 key 反查 track_id，entry 不回写

### --evaluate 协议（写死，防自证清白）

模拟生产用法"立哥认一球 → 传播一片"：

- **roster-seeded（主指标）**：逐轨迹处理——轨迹内所有有 roster 归属的球
  轮流留 1 个作种子（取该轨迹时间最早球），其余有 roster 归属的球作为
  被预填对象；预填正确 = 预填 tag == roster 真值 tag
- **number-seeded（副指标）**：源只用号码预填命中的球（roster 不参与当源），
  真值仍对照 roster——测"无 roster 冷启动"场景
- **分母（写死）**：准确率 = 预填正确数 ÷ 收到预填的球数；覆盖倍数 =
  收到预填的球数 ÷ 种子球数；冲突不预填/mixed 轨迹/unlinked 球一律计入
  覆盖失败一侧；两种 seeded 分开报数不合并
- evaluate 报表逻辑做成纯函数（合成轨迹+合成 roster 可单测）

### 页面（gen_scorer_page.py --track-links，写死）

- `--track-links` 可选，须与 --scorers 同目录；无则行为与现状完全一致
- 条目显示 `轨迹#N`；传播预填规则：
  - 触发：立哥 assign(tag)（**tag ≠ NOGOAL**——"不算进球"绝不传播）
  - 生效对象：同 track_id 且 **无 marks、无 prefill_tag（号码/照片/印名
    预填）、未 touched** 的球；满足条件的写入 marks 并记入
    `propagateAssign` provenance 集合（localStorage 独立键）
  - 徽标判定式：`marks 有值 && key ∈ propagateAssign && !touched` →
    显示"同轨迹预填"徽标（供立哥扫一眼复核，逐球可改，改即 touched）
  - `acceptAllPrefills`（接受全部号码预填）与 E 键**只收 prefill_tag，
    不碰传播预填**；导出照旧（marks 全集）
- 预填优先级总链（写死）：立哥手改（touched）> 读号/照片/印名
  （既有 prefill_tag 链不变）> 传播预填 > 颜色 team_guess 展示

### 离线读号（Phase 2，试验；offline_number.py）

- 裁图躯干上部（垂直 10%~45%、水平中 70%）→ 放大 3 倍 → 自适应二值化
  → 连通域切数字候选 → 与模板库 matchTemplate（多尺度）→ 逐帧投票
  （规则复用读号投票）
- **模板库自举对齐规则（写死）**：对 K3 高置信条目的裁图跑同套切分；
  **连通域数 == len(number) 才接收该样本**，按连通域中心 x 升序与数字
  字符一一 zip 对应；粘连/断裂导致个数不符 → 丢弃该样本记 INFO；
  每数字 ≥3 个样本才启用该数字的匹配，不足不认
- **缓存隔离（写死）**：offline 结果单独落 `offline_number_cache.json`
  （键=裁图 md5），**不碰 K3 的 number_cache.json**——读端零歧义，
  K3 投票链路完全不知道 offline 的存在；离线结果的使用入口：
  跳票模式下号码预填来源 = K3 缓存 ∪ offline 缓存（K3 优先）

## Commands

```bash
# 质量门
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && \
  python -m ruff check --fix scripts tests && python -m pytest -q

# 轨迹传播（在 people 链中位于 crop_scorers 之后、聚类之前）
python scripts/propagate_scorers.py \
  --candidates work/<场次>/scorers_bK/scorer_candidates.json \
  --detectdir work/detect --framesdir work/frames
# 标定（数据就绪后）：加 --roster work/<场次>/roster.json --evaluate

# 认人页（传播预填生效）
python scripts/gen_scorer_page.py --scorers ... --goals ... \
  --track-links work/<场次>/scorers_bK/track_links.json ...
```

CLI 接线：`video people` 的批次步骤链改为 裁图 → **传播** → 聚类 → 确认页
（--track-links 在 track_links.json 存在才传给确认页）

## Code Style

遵守根目录 rules.md（鲁棒优先 ＞ 性能 ＞ 简洁）；dataclass 契约 + 显式校验
+ SchemaError/BasketballPipelineError 分层，与现有 scripts 一致。

## Boundaries

- Always：质量门全绿后按 Phase 分次提交；track_links/模板库落盘幂等
- Ask first：跨文件轨迹拼接（本 spec 明确不做）；引入外部 OCR 二进制
- Never：传播/预填不是终裁（立哥页面确认为终裁）；不改 roster schema；
  不改 goals/label 流程；mixed 轨迹不自动预填；NOGOAL 不传播；
  轨迹不跨文件；propagate 不改写 candidates 文件；离线读号不碰 K3 缓存

## Testing Strategy

- 纯函数单测（合成 persons 序列/合成裁图/合成轨迹+roster，不碰真帧真模型）：
  - 贪心跟踪器：链上/断轨封存/新轨/同帧竞争唯一性裁决
  - 颜色守卫：主色占比 <60% 标 mixed；便服样本不计入
  - 进球→轨迹映射：归上/归不上/多轨迹竞争取 IoU 最大
  - 传播来源：自身不算源/冲突不预填/NOGOAL 不作源
  - evaluate 报表：合成数据算准确率/覆盖倍数（leave-one-out 协议）
  - 页面：传播预填触发条件（无 marks+无 prefill_tag+未 touched 才写）、
    NOGOAL 不传播、徽标判定式、acceptAll/E 键不收传播、无 --track-links 兼容
- Phase 2：模板匹配用合成数字图；对齐规则（个数不符丢弃）单测

## Success Criteria

- [ ] propagate_scorers 产出 track_links.json；--evaluate 报表（双指标、
  纯函数可测）；实跑标定待新场次数据（前置条件见 Objective）
- [ ] 认人页 --track-links 传播预填 + 徽标 + touched 覆盖 + NOGOAL 排除
- [ ] entry 增 seed_frame/seed_box/seed_team；propagate 只消费 seed 字段
- [ ] Phase 2 对照实跑有结论（≥70% 留 / <70% 砍，review01 记录）——
  同样待新场次数据
- [ ] video people 链接线（裁图 → 传播 → 聚类 → 确认页）
- [ ] ruff+pytest 全绿；四件套齐全

## Open Questions

- MAX_GAP_FRAMES / 颜色主色占比阈值初值拍脑袋（10 帧 / 60%），
  新场次标定后写死进常量
- 轨迹碎片化严重时覆盖率可能很低（俯视人群 IoU 链易碎 + 锚点后轨迹常被
  物理截断）——覆盖倍数就是量这个的；<1.2 再考虑放宽 IoU 或框中心距离
  补链（标定后再定，不过度设计）
- 离线读号在模糊小字上的实际表现未知，Phase 2 末位实跑定生死
