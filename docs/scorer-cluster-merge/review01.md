# Review 01: 簇合并+折叠 spec 审查（第 1 轮）

日期：2026-08-14
对象：docs/scorer-cluster-merge/spec.md（初版）
审查人：spec-reviewer 子代理（对照 scripts/gen_scorer_page.py、scripts/roster.py、
docs/scorer-cluster/{spec,review01}.md 与 work/ 真实数据核查）

## 审查结论：3 个阻断问题，已全部修订

### 阻断 1：Commands 段命令不可执行——两处参数名错误（从旧 spec 复制带入）

- 问题：用 `--candidates`（实为 `--scorers`，gen_scorer_page.py:903）与
  `--out`（不存在，输出固定为 --scorers 同目录 scorer.html）
- 修订：命令改为 `--scorers/--goals/--clusters/--roster-existing/--index`，
  注明输出固定同目录 scorer.html、--clusters 须与 --scorers 同目录

### 阻断 2：实跑验证数据源已不存在

- 问题：spec 指定用 20260722 实跑验证，但 `work/20260722/` 已随 archive
  清理删除（2026-08-11），成功标准不可达
- 修订：数据源切换到现存 `work/20260805_车百鼎/`（scorers_b1 含
  scorer_candidates.json + scorer_clusters.json；goals 分三批取
  goals_batch1.json；roster 文件名带场次后缀
  `roster_20260805_车百鼎.json`）

### 阻断 3：clAssign 残留语义未定义，"归的人"显示有矛盾数据源

- 问题：冲突并后被并簇 marks 改归目标组，但 clAssign 残留旧归属；
  拆开"不动 clAssign"使残留记录既可能误导显示又可能误触默认折叠
- 修订：**clAssign 唯一用途 = 合并时预填来源**；合并时删除被并组
  clAssign（被目标组吸收）；组小结"归的人"= 组内非空 marks 众数；
  默认折叠判定只读 marks——显示与判定一律以 marks 现状为准

## 非阻断建议的处理（8 条全部采纳）

| 建议 | 处理 |
|------|------|
| 拖组行时预填应作用于被并组全部 keys | 采纳：合并动作第 1/2 条写明整组口径 |
| 验证清单漏组号显示/链式并改写/拖自身 | 采纳：清单补 3 条 |
| 嵌套对象沿用平铺 save() 防护粒度变粗 | 采纳：按 merges/clAssign/collapsed 子键分别读回合并 |
| "同操作序列 diff 为空"口径含糊 | 采纳：澄清为"不含新功能的同等操作序列 diff 为空 + 合并预填与逐球手填同归属导出一致" |
| 模板断言标识符（clusterAssign/cluster-row/const CLUSTERS）与 node --check | 采纳：Testing Strategy 补保留要求 |
| JSON 键字符串 vs cluster_id int | 采纳：数据契约写明一律 String(cid) |
| "A→B 后 B→A"实际不可达 | 采纳：注明交互不可达、解析层防御性环检测 |
| 组排序位置与图墙长度未定义 | 采纳：组位置=原簇位置；图墙较长可接受（折叠消化） |

## 核查通过项（审查代理确认）

- clAssign 正确识别为新增（现有 clusterAssign 只写 marks）；新键命名与
  marks/touched/pos 模式一致
- 导出契约不变声称成立：exportRoster 只读 marks/PLAYERS/EXPLAYERS，
  roster.py validate_roster 只认 session/confirmed/players/assignments
- touched 优先规则、save() 容错模式、无 --clusters 整区隐藏路径均有
  现有代码依据
- 52 簇/62.6% 纯度/20 人数据出处核实（docs/scorer-cluster/review01.md）
- 零 Python 逻辑变更可行（全在 _HTML 模板内实现）；无占位符/TBD

## 结论

阻断问题全部修订完毕，spec 可进立哥审阅，随后进 plan。

---

## 附：第 2 轮复审记录（2026-08-14，修订后复核）

- 三个阻断逐项复核**已真正修复**：命令五个参数对照
  gen_scorer_page.py:900-930 全部真实存在；20260805_车百鼎 批次1 的
  5 个引用文件逐一核实存在；clAssign 新语义与合并/拆开/折叠三节自洽
- 8 条非阻断建议全部落实，无虚报
- 复审发现一处口径缝隙（非阻断）：目标组全靠逐球覆盖认完（无
  clAssign）时合并不预填，与 Objective"目标组已归人即跟随"措辞
  不等价 → 已顺手修订：预填来源扩为"目标组 clAssign；无则组内非空
  marks 全部一致时用该 tag；混合不预填"
- 复审结论：**可实施**
