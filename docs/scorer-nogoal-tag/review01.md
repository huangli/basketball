# Review 01: 审查存档——认人页"不算进球"标签

- 范围：966b2e1..e8e0bff（单提交）+ Task 2 重生成/手册
- 审查方式：spec/plan 预审（Ready=No→修订）+ 任务级 spec+质量双审查 Approved（2026-08-15）
- 结论：**Approved**（无 Critical / 无 Important）

## spec 预审修订（plan 阶段吸收）

- **B1 阻断（已吸收进 plan 后实现）**：弹条屏蔽名单漏 N 键——弹条期间误按 N 会把
  当前球静默打成"不算进球"（导出即剔除、还记 touched 挡预填）。修复 = 屏蔽条件
  加 `|| k === "n"`，与 1-9/E 同行，并有测试断言锚住。
- S1 吸收：alert 剔除数改全量 marks 计数（跨批次共享 localStorage，只数本页会漏报）
- S2 吸收：按键提示行补 `N=不算进球`
- S3 吸收：spec 写明哨兵只在 roster 驱动合成里生效（裸跑模式不含此语义）

## 任务级审查核实要点

- E1-E7 与 plan 逐字一致；哨兵特殊分支严格限定 exportRoster 两处
- 六条链路推演：assign 继承 / clusterAssign+mergeInto 的 touched 预填保护 /
  renderReviewBar 核对对象行（普通 nav 钮不着色）/ confirmed 条件（哨兵非空即过）/
  导出补录循环（读已过滤 assignments，零改动即不进名单）/ build 三模式
  （无过滤 WARNING 跳过、--scorer/--team 反查不沾）
- --roster-existing 合并：哨兵键不在 EXISTING 但在 localStorage → 重生成后
  哨兵归属存活、再次导出再次剔除，行为一致
- E7 提示行折行偏差（E501 强制）：折点原为多空格处，渲染等价，实现者已主动披露

## 已知行为（不修，留档）

- mergeInto 的组内众数预填理论上可能把"不算进球"当 tag 扩散到被并组的未 touched
  球——"零特殊分支"的有意代价；可经核对对象行选"不算进球"找回改归
- 测试弱锚留档：`'k === "n"'` 断言与屏蔽行子串重叠（可改 `else if (k === "n") assign(NOGOAL)` 加固）
- goals.json 里剔除球仍是 confirmed：重生成确认页会再出现，靠 localStorage 哨兵
  marks 保持剔除状态；清站点数据后需重新剔除（spec 已写明该恢复路径）

## 交付物

- 质量门全绿；b1(29球)/b2(49球)/b3(44球)+demo 均已用新模板重生成
  （grep `id="nogoal"` 各 1 处；--roster-existing 用立哥最新 roster.json）
- 使用手册.html 第三步补"不算进球"操作（含弹条屏蔽键说明同步补 N；spec-reviewer PASS）

## 放行条件

- 立哥手工验证清单（spec 5 条，含 build 实测：剔除球不进合集、confirmed 不再拒收）
