# Spec: 裁图质量闸（crop-quality）——废帧不进 candidates

## Objective

citymonkey 场次实锤三类废裁图（最早出处 docs/photo-roster/review03.md 小样
实锤，2026-08-27 三方调研 work/_clip_analysis/report.md 全量复核）：

1. **无人框**：t480.1 c0 裁的是场边瓶子（轨迹法定位错误），无人废图竟过 CLIP 闸
2. **畸形框**：t550.0 c0 宽高比 0.09（16 张样本裁图实测 0.28~0.58，该图为唯一
   极端离群），检测框漂成细条，经"短边不足 400 等比放大"（crop_scorers.py:976）
   硬拉约 11 倍 → 400×4456 糊图（数值来源：2026-08-27 手工实测 16 张裁图
   尺寸记录，非 report.md；C1 标定时全量复核）
3. **错人框**：t186.6 c1/c2、t34.1 c2、t264.4 c0 裁的是对方蓝衣球员（定位错人；
   注：truth_16 的 category 标的是**进球者**真值，错人框说的是**裁图内容**，
   两者维度不同不冲突）

废帧污染全部下游：CLIP 聚类、照片匹配、K3 读号（既有手工功能，级联不调，
v2.1 定案）、确认页认人。本功能在
**裁图产出环节**加质量闸：废帧不进 crops，多裁选帧机制自然跳过废帧选次优帧。

成功标准（可执行验证）：

- 质量闸落地后，citymonkey 重跑 crop：t480.1 瓶子帧、t550.0 细条帧被拦且留痕
  （**t550.0 被拦属预期拦截不计误杀**；若该球补位失败归 SKIP 也不算误杀——
  该球代表裁图本来即废帧）；**truth_16 我方 8 球中除 t550.0 外的 7 球有效
  裁图零误杀**（误杀率 0 容忍——宁漏拦不错杀，错杀直接损失认人证据）
- 全部帧被拦的球 status=SKIP 且 reason 留痕，不炸批
- ruff+pytest 全绿；四件套齐全

## Tech Stack

- 零新依赖：检测复用既有 yolov8n（人物模型，models/yolov8n.pt，持球排除用
  同款）；PIL/numpy 现状
- 不改检测模型、不动定位逻辑

## Commands

```bash
# 质量门（改动后必跑）
python -m ruff format scripts tests && python -m ruff check --fix scripts tests && \
  python -m pytest -q

# citymonkey 重跑验证（移走旧 crop 产物（备份不删）后重跑 people 裁图段，
# 命令以 plan C4 为准，必带 --no-read-numbers）
```

## Project Structure

```
scripts/
  crop_scorers.py   改：裁图产出链加质量闸（宽高比 sanity + 框内人物复检），
                    废帧跳过并留痕；全废球 status=SKIP + reason
tests/
  test_crop_scorers.py 改：合成框/合成图单测（不碰真模型真视频）
docs/crop-quality/  → 本四件套
```

## 数据契约

### 质量闸两道 + 边界说明（写死）

1. **宽高比 sanity**：外扩后框 `w/h` 超出 `[MIN_RATIO, MAX_RATIO]` → 废帧。
   阈值由 citymonkey 58 球裁图分布标定后写死（初步：下限 0.15，上限 1.2；
   站立人 0.28~0.58、蹲下/起跳更宽，宁宽勿严——标定数据附 review）
2. **框内人物复检**：对裁出区域跑 yolov8n person 检测，无可信 person 框
   （置信度 < PERSON_CONF，标定后写死）→ 无人废帧。瓶子/广告牌此类能挡住
3. **错人框（裁到对手）**：**边界外**——属轨迹定位逻辑问题，非图像质量问题，
   本功能不处理（列入 Open Questions，后续与"颜色分队不可靠"一起议）

### 行为口径（写死）

- **闸插选帧循环内（补位语义）**：候选帧逐帧过闸，废帧立即丢弃并继续取
  次优帧补位，直到凑够 best_crops 张或帧池耗尽；帧池全废才走 SKIP
- 废帧不进 crops 列表、不写 JPEG，记 INFO 留痕（帧时刻 + 拦截原因）
- 该球全部候选帧被拦 → status=SKIP、reason 记质量闸（与现有 SKIP 口径一致）；
  **SKIP 球的认人预览片段保留**（片段与定位解耦，crop_scorers.py:1369，
  供人裁，写死防回归）；**SKIP 条目不落 crops/crop_scores 字段**
  （与 crop_scorers.py:1335 现有口径一致）
- **幂等**：只对新跑生效；已产出的旧 scorer_candidates.json 不重判。
  citymonkey 验证靠移走旧产物（mv 成 .bak 备份不删）重跑（操作步骤写 plan）

## Code Style

遵守根目录 rules.md（鲁棒优先 ＞ 性能 ＞ 简洁）；阈值常量化带标定注释；
yolov8n 加载惰性（仅裁图路径用到时加载，不影响现有测试——测试注入假检测器）。

## Testing Strategy

- pytest 纯函数/合成数据单测，不碰真模型/真视频：
  - 宽高比闸：边界值（恰好等于上下限、略超）、正常框不误杀
  - 人物复检：注入假检测器——有可信框放行 / 无框拦截 / 低置信拦截
  - 全废球 → SKIP + reason；部分帧废 → crops 只剩好帧且留痕
  - 旧产物幂等：已有 candidates 的球不重判
- citymonkey 重跑真机验证走人工核对（t480.1/t550.0 被拦、truth_16 我方 8 球
  中除 t550.0 外的 7 球有效裁图零误杀），
  结果归档 review，不进 pytest

## Boundaries

- Always：质量门全绿后提交；阈值标定数据归档 review；宁漏拦不错杀
- Ask first：宽高比/置信度阈值定稿值；错人框（定位逻辑）后续立项
- Never：不改轨迹定位逻辑与选帧评分公式；不删旧场次已产出裁图
  （重跑由立哥决定）；不改 candidates schema 的既有字段语义

## Success Criteria

- [ ] 两道闸 + 留痕 + SKIP 语义，单测覆盖上述契约
- [ ] 阈值标定：citymonkey 58 球裁图宽高比分布 + 复检置信度分布归档
- [ ] citymonkey 重跑验证：t480.1/t550.0 被拦、truth_16 我方 8 球中除
  t550.0 外的 7 球有效裁图零误杀，归档 review
- [ ] ruff+pytest 全绿；四件套齐全（review 按轮次编号）

## Open Questions

- 错人框（裁到对手）后续怎么治：定位逻辑加颜色一致性检查？与
  team_guess 不可靠（蓝衣球 3/4 被猜白）是同一个坑的两个侧面，单独立项
- 框内复检用 yolov8n 是否够（小人/遮挡框置信度天然低，误杀风险）——
  标定时重点看正常球复检置信度分布下限
