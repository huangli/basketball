# Spec: 审核片段合并加空间约束与时长上限（event-split）

> 2026-09-06 立哥实测反馈立项。代码改动在新仓库 `C:\Code\basketball_clip` 的 `scripts/gen_review_clips.py`（spec 豁免清单外改动，立哥已口头批准方向并指定"先小样验证"）。

## Objective

修复审核片段"多回合并一段、跨场地不切断"的问题（根因实证：`gen_review_clips.py:261-296` `cluster_candidates` 纯时间链 ≤2s 不看位置 + 无时长上限）。

**目标口径（立哥原话）**：一个片段 = 一次进攻（可含多次投篮尝试），一次标注；场地转换必须切开。

## 设计

`cluster_candidates` 合并条件改为：

1. **纯时间链加空间约束**：间隔 ≤ `CLUSTER_GAP_SEC`(2.0s) **且** 两候选关联位置距离 ≤ 阈值 → 并。
   位置优先级：两候选各自时刻的**最近筐位**（hoops 数据）→ 缺筐数据退回球位（现状语义）。
   阈值：`CLUSTER_CHAIN_DIST = 800px`（img 系，初值；换场地时筐位差大半个画面 ≫ 800px，
   同回合镜头微动 ≪ 800px；小样验证时若误切再调）。
2. **补篮时空放宽阈值不动**：间隔 ≤6s 且距离 ≤400px（CLUSTER_MERGE_GAP_SEC/DIST 数值不变）——
   有实证依据（经验教训.md：同球对 anchor 差上限 4.2s/309px），收紧会拆真同球。
   **但距离源同样统一为"关联位置"（筐位优先、缺筐退球位）**（2026-09-06 T1 实证修订：
   跨场地对球位常 <400px——球贴各自筐，spec 原字面切不开目击案例，如旧 e18
   gap 3.5s/球距 209px/筐距 927px；统一距离源后 16/16 目击案例全部切开，
   副作用"同筐远球位对被并"恰合"一次进攻可含多次投篮"口径）。
3. **事件时长上限**：`CLUSTER_MAX_EVENT_SEC = 20.0`——事件首末候选跨度超 20s 强制切段
   （一次进攻含补篮通常 ≤15s；超长必是多回合链）。
4. 三个新参数为模块常量 + `cluster_candidates` kwargs（沿用现有风格）；CLI 不透传（主流程恒默认）。

## Commands

```powershell
C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m pytest -q
python -m ruff format scripts tests gui; python -m ruff check --fix scripts tests gui
```

## Project Structure

- `scripts/gen_review_clips.py`：cluster_candidates 改造（唯一代码改动点）
- `tests/test_gen_review_clips.py`：合并逻辑单测
- 文档：本目录四件套（旧工作区）

## Code Style / Boundaries

- 同 rules.md；`event_anchor` 取末成员口径、片段窗口（前 2 后 4）不动
- Ask first 已覆盖（立哥批准方向）；Never：不动 hoops/mot 上游产物格式

## Testing Strategy

- 单测（合成候选）：同回合近距离并入、跨场地远距离切断（时间链被距离否决）、
  超 20s 强制切段、缺筐数据退回球位、补篮规则回归（6s/400px 内仍并）
- **真实数据验证**：用第六人场次现有 `candidates_batch1.json` + `hoops_batch1.json`
  重跑聚类，片段出到**临时目录**（不动 review_batch1），事件清单前后对比给立哥过目

## Success Criteria

1. 单测全绿，存量测试不破
2. 第六人真实数据上：跨场地片段被切开（立哥目击案例必须命中），同回合补篮不拆
3. 立哥过目新旧片段对比后确认效果，再决定是否重出正式 review_batch1

## Open Questions

- O1：`CLUSTER_CHAIN_DIST` 初值 800px 是否合适——小样验证后定稿
