# Spec: 认人页簇合并 + 折叠——拖拽并簇、归属预填跟随、已归属自动收起

## Objective

现状痛点（聚类实跑标定口径，docs/scorer-cluster/review01.md 附录）：
定稿聚类 complete@0.15 把进球者按人拆分严重不足（20260722 场次：
104 球 / 20 人 → 52 簇、纯度 62.6%），认人页簇区几十行带来两个问题：

1. 同一人被拆成多簇，立哥要对同人重复选队员（52 次而非 ~20 次）。
2. 簇区全展开把逐球确认区（裁图 + 视频）顶到页面很下方，看进球要滚屏。

本功能做三件事（2026-08-14 立哥拍板，方案 A 纯页面态）：

1. **拖拽合并簇**：簇行可拖拽，把一行拖到另一行上松开 = 并入目标行；
   合并行可一键"拆开"回原始簇（误并撤销）。
2. **归属预填跟随**：合并时若目标组已归人，被并组中未逐球手动改过的球
   立即批量预填该队员（"并入组跟着目标组走"，立哥选定）——
   认完人后看进球无需再次填写。
3. **簇折叠**：已全部归属的组页面加载即折叠、组内球补齐归属后自动收起；
   折叠态为一行小结；顶部有"全部展开/折叠"总开关。

成功标准：

- 拖拽合并 / 拆开 / 折叠 / 冲突并（两组各归不同人）行为符合本 spec
  数据契约，手工验证清单全过
- 导出 roster.json 契约不变：**不含新功能的同等操作序列**下导出产物与
  改动前 diff 为空；合并预填与逐球手填到同一归属时导出一致
  （合并只影响预填效率，不影响导出内容口径）
- 无 `--clusters` 时页面行为与现状完全一致（向后兼容）
- 现有 pytest 全绿（本功能零 Python 逻辑变更）、ruff format/check 干净

## Tech Stack

- Python 3.14（gen_scorer_page.py 模板字符串内嵌 HTML/CSS/JS）
- 纯前端：HTML5 Drag & Drop API + localStorage；零新 pip 依赖、零网络
- 改动面：**只动 `scripts/gen_scorer_page.py` 的页面模板**（样式 + JS），
  零 Python 逻辑变更；roster / clusters 数据契约不动

## Commands

```bash
# 质量门（改动后必跑）
export PYTHONIOENCODING=utf-8 && python -m ruff format scripts tests && \
  python -m ruff check --fix scripts tests && python -m pytest -q

# 生成认人页（无新参数；输出固定为 --scorers 同目录 scorer.html。
# 用 20260805_车百鼎 批次1 已有数据实跑验证；--clusters 须与 --scorers 同目录）
python scripts/gen_scorer_page.py \
  --scorers work/20260805_车百鼎/scorers_b1/scorer_candidates.json \
  --goals work/20260805_车百鼎/goals_batch1.json \
  --clusters work/20260805_车百鼎/scorers_b1/scorer_clusters.json \
  --roster-existing work/20260805_车百鼎/roster_20260805_车百鼎.json \
  --index work/20260805_车百鼎/review_batch1/events_index.json
```

## Project Structure

```
scripts/
  gen_scorer_page.py   改：页面模板——簇区支持拖拽合并/拆开/折叠，
                       新增 merges/clAssign/collapsed 三个页面态
tests/                 → 无新增（零 Python 逻辑变更；JS 交互走手工验证清单）
docs/scorer-cluster-merge/ → 本四件套
```

## 数据契约

### 页面态（新 localStorage 键，与 marks 同生命周期）

`scorer_<session>_clusters`（独立键，不动既有 marks/touched/pos 存储格式）：

```json
{
  "merges": { "3": 5, "7": 5 },
  "clAssign": { "5": "黑21" },
  "collapsed": { "5": true, "8": false }
}
```

- JSON 对象键必为字符串而 cluster_id 是 int：读写查找一律 `String(cid)`
  字符串化，实现时注意统一
- `merges`：被并簇 cluster_id → 目标组 cluster_id（值为最终组 id；
  链式并 A→B、B→C 时 A 的记录改写为 C，不存中间链）
- `clAssign`：组 id → 队员 tag。**新增**：簇级选人除批量写 marks 外，
  同时记 clAssign。**clAssign 唯一用途 = 合并时"跟着目标组走"的预填
  来源**；页面一切显示（组小结"归的人"、默认折叠判定）一律以 marks
  现状为准，不读 clAssign（防拆开后残留记录误导显示）
- `collapsed`：显式折叠状态，**true/false 都存**（行头折叠钮切换即写）；
  键缺失时才走默认折叠规则（见下）
- 读写沿用 save() 的"读回再合并写"防多开页面互踩，但按 `merges` /
  `clAssign` / `collapsed` 三个子键**分别**读回合并（现有 save() 是
  平铺浅合并，嵌套对象按子键粒度合并才保住防护效果）；JSON 解析失败
  回退空对象（沿用现模式）

### 显示组解析（页面加载/状态变更时）

- 组 id = 目标簇 cluster_id；组 keys = 原始簇 keys 的并集，组内球序按
  所属原始簇在 CLUSTERS 中的先后顺序拼接
- 组行在簇区列表中的位置 = 组 id 对应原始簇在 CLUSTERS 中的原位置
- 组标签：`簇#5（12 球，已归属 8，并自 #3/#7）`；未并过则无"并自"段
- 组代表图墙 = 各原始簇 rep_crops 按上述顺序拼接；多簇合并后图墙
  较长属可接受（折叠态只显示首图，长行可被折叠消化）
- 组小结"归的人" = 组内非空 marks 的众数 tag（无 marks 显示"未归属"，
  多属显示该众数并附"混合"提示）；已归属计数如实反映 marks 现状
- 逐球区条目追加显示的簇号 = 所属**组** id（合并后显示组号，与原
  cluster_id 的对应关系在组标签"并自"段可查）

### 合并动作（拖拽 drop 到目标行）

1. 写 `merges[被并cid] = 目标组id`；拖到已合并行上时目标取其组 id，
   被并方为整组时其全部原始簇记录一并指向目标组
2. 预填来源 = 目标组 clAssign；目标组无 clAssign（全靠逐球覆盖认完）
   且组内非空 marks **全部一致**时，用该 tag；组内归属混合则不预填。
   命中预填来源时：对被并组全部 keys 中**未 touched** 的球批量预填
   该 tag（写 marks）；已 touched 的球不动（逐球覆盖优先，现规则沿用）
3. 若无预填来源（目标组未归人或归属混合）：不动任何 marks，仅并显示
4. 被并组自身的 clAssign 条目**删除**（已被目标组吸收；防拆开后残留
   旧归属记录再当预填来源）
5. 拖到自身 / 已同组 = 无操作；环并（A→B 后再令 B→A）在交互上不可达
   （A 并入 B 后 A 行不再单独存在），解析层仍做防御性环检测不报错
6. 合并后若组内全部球有 marks，组自动折叠
7. **合并弹条选人**（2026-08-15 立哥加）：合并完成后若未发生自动预填
   （无预填来源或目标组归属混合），在该组行就地弹出选人条——一排
   队员按钮（同页面名单）+ "取消"；点队员 = 记 clAssign[组]=tag +
   批量预填整组未 touched 球（与簇级选人同一语义）；取消 / Esc /
   点选人条外区域关闭，组保持未归属。已自动预填的合并不弹条。
   **弹条打开期间屏蔽全局数字键 1-9/E**（防误触逐球 assign 改错球）

### 拆开动作（合并行的"拆开"按钮）

- 删除 merges 中指向该组的所有条目，组还原为原始簇行
- **不动任何 marks / 目标组的 clAssign**：已预填的归属保留，拆开后各
  原始簇行的"已归属"计数如实反映 marks 现状
- 拆开只撤分组，不是撤销归属——归属要改用逐球覆盖（现功能）

### 折叠

- 默认折叠规则：组内全部球有 marks（全部已归属）→ 折叠；否则展开。
  判定只读 marks，不读 clAssign
- 行头折叠钮逐行切换（写 collapsed 显式 true/false，覆盖默认规则：手动
  展开已归属组后刷新页面保持展开）；顶部"全部展开/折叠"总开关只改显示，
  不写 collapsed（刷新后回默认规则）
- 折叠态 = 一行小结：首张代表小图 + 组标签（簇号/球数/归的人）
- 组内球补齐归属（簇级选人或逐球覆盖至全部有 marks）后自动折叠该组
  （自动折叠不改 collapsed 显式状态，属默认规则生效）

## Code Style

遵守根目录 rules.md；模板内 JS 沿用现有风格（无框架、无构建、
函数挂全局、localStorage 容错 try/catch）。

## Testing Strategy

- 零 Python 逻辑变更 → 现有 pytest 保持全绿即可，无新增单测
- 注意 tests/test_gen_scorer_page.py 有模板字符串断言
  （`clusterAssign`、`cluster-row`、`const CLUSTERS = [];`、node --check
  JS 语法校验）：模板改动须保留这些标识符且 JS 语法合法
- ruff format/check 干净（模板字符串改动也应保持）
- JS 交互手工验证清单（20260805_车百鼎 批次1 实跑页面）：
  - [ ] 拖拽 A 行到 B 行 → 并成一组，标签含"并自 #A"，位置取 B 原位
  - [ ] 链式并：A→B 后 B 组→C → merges 里 A 记录改写为 C
  - [ ] 拖到自身 / 已同组行 = 无操作
  - [ ] 目标组已归人时合并 → 被并组未 touched 球自动预填该人；
        已 touched 球不变；被并组 clAssign 删除
  - [ ] 冲突并（两组各归不同人）→ 并入组跟着目标组走（未 touched 球
        改为目标组归属）
  - [ ] 合并弹条：无归属组合并后弹选人条，选人应用整组（未 touched 球）
        且记 clAssign；取消/Esc 不归属；已归组合并不弹条；目标组归属
        混合（无 clAssign、marks 多 tag）合并也弹条；弹条打开期间
        数字键 1-9/E 不触发逐球归属
  - [ ] 拆开 → 还原原始簇行，marks 不变
  - [ ] 折叠/展开、全归属自动折叠、手动展开刷新后保持、总开关刷新后
        回默认；逐球区条目显示组号
  - [ ] 导出 roster.json：不含新功能的同等操作序列与改动前 diff 为空；
        合并预填与逐球手填同归属导出一致
  - [ ] 刷新页面后合并/折叠/归属状态都在（localStorage 持久）
  - [ ] 不传 --clusters 生成的页面行为与现状一致

## Boundaries

- Always：质量门全绿后提交；localStorage 读写容错；逐球覆盖
  （touched）优先于一切簇级批量改动
- Ask first：无（零新依赖、零新 CLI 参数、零数据契约变更）
- Never：不改 roster.json 导出 schema；不改 scorer_clusters.json 产物；
  不做单球移出簇（上轮讨论已否：逐球覆盖已覆盖该诉求）；
  合并状态不回写任何 work/ 文件（纯页面态，方案 A）

## Success Criteria

- [ ] 簇行拖拽合并 + 拆开，标签/图墙/球数/位置正确
- [ ] 合并时归属预填跟随目标组（含冲突并、链式并口径），touched 球
      不受影响，被并组 clAssign 清除；无归属组合并后弹选人条可就地命名
- [ ] 折叠默认规则 + 手动覆盖 + 总开关，逐球区不再被顶到下方
- [ ] 导出 roster.json 契约不变（diff 验证）
- [ ] 无 --clusters 兼容；刷新持久；ruff+pytest 全绿
- [ ] 四件套齐全（review 按轮次编号）

## Open Questions

- 拖拽手感（行高、drop 高亮样式）以实跑为准，不立标准；若立哥实测
  拖拽误触多，降级出口 = 保留"并入选中簇"按钮式合并（选中态 + 按钮，
  无拖拽），分组/状态模型不变
- 合并后若仍有便服/噪声簇难判断归谁，属聚类纯度老问题
  （docs/scorer-cluster/review01.md 附录增强方向），不在本功能范围
