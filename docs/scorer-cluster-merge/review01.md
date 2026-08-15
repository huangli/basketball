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

---

## 附：第 3 轮复审记录（2026-08-15，合并弹条新增后）

- 立哥新增需求"合并瞬间弹选人"落为合并动作第 7 条；复审确认与
  clAssign 契约（用途唯一，记录途径二处不冲突）、marks 显示准绳、
  折叠规则、现有按键无矛盾
- 两条非阻断小点已顺手补：验证清单补"目标组归属混合也弹条"；
  spec 注明弹条打开期间屏蔽全局数字键 1-9/E（防误改逐球）
- 复审结论：**可实施**

---

## 附：第 4 轮审查记录（2026-08-15，plan.md + todo.md）

- **阻断 1（已修）**：splitGroup 删 merges 会被 saveClState 读回合并写复活
  → saveClState 改 `del = { merges, clAssign }` 双清单，splitGroup 传 doomed
- **阻断 2（已修）**：Task 4 替换 PICKER-HOOK 行后 Task 3 断言必红
  → 替换行保留 "PICKER-HOOK" 字样（`// PICKER-HOOK 已挂接：…`）
- **阻断 3（已修）**：弹条块 `!folded` 守卫会吞"混合目标组+整组全有 marks"
  场景的弹条（spec 动作 7 边界）→ 弹条块不加守卫，pickerGid 优先于折叠态
- 非阻断 6 条全采纳：delAssign 无条件收 src.cids（防 stored 独有键复活）、
  collapseAll 两态循环注明有意、组排序 `?? 0` 兜底、选人 for 加花括号、
  Task 6 手工验证措辞写清、todo Task 4 步数映射注明
- 核查通过：行号与原文引用逐字相符；测试断言标识符与实现一致；
  合并动作 1-6 无走样；折叠优先级正确；Task 中间态可接受；
  todo 与 plan 一一对应

---

## 附：整体终审记录（2026-08-15，code-reviewer 全分支审查 469f36d..f134a72）

- 结论：**Ready to merge = Yes**；实现与 plan 逐字一致、spec 数据契约逐条对齐，
  roster 导出契约与无簇兼容零回归，测试全绿
- 顺手修（终审 Minor 一行级）：keydown 弹条屏蔽段防 free 聚焦态 Enter 绕过
  （终审 Minor #2 + roll-up #3 同源）；task-5-report 测试计数更正（168→496）
- 终审 Minor triage：JS 行为级测试缺失 / dragleave 冒泡闪烁 / collapseAll
  期间单组折叠钮无反馈 / mergeInto 双渲染 / groupTag 双调用 ——全部"可留"
  （plan-mandated 或 cosmetic）；splitGroup 后 collapsed 残留备查不改
- 组小结无 marks 时不显示"未归属"字样（"已归属 0"信息等价）——可留
- 唯一在途项：spec 11 条手工验证清单待立哥浏览器实测（todo.md Task 6 已标注）
