# Review 01: 认人提效二期三件套 spec-reviewer 审查（第 1 轮）

日期：2026-09-02
对象：docs/scorer-propagate/{spec,plan,todo}.md（初版）
审查人：spec-reviewer 子代理（对照 crop_scorers/gen_scorer_page 现状代码、
work/ 实际状态、scorer-cluster/scorer-reid 对照 spec 核查）

## 审查结论：5 个阻断问题，已全部修订

### B1（致命）：评估锚点数据不存在

- 问题：work/ 已被 video clean 清场（20260722 的 roster/candidates/frames/
  detect 全部不存在），初版 spec 的"实跑 20260722 标定"无从跑起
- 修订：成功标准加前置条件——实跑标定/对照挂到下一个带 confirmed roster
  的新场次；本周期交付 = 实现 + 单测 + 接线；Task 9/10 标记【挂起】
  并写明前置条件

### B2：--evaluate 自证清白 + 口径未定义

- 问题：传播源含"已有 roster 归属"而 evaluate 真值就是同一 roster，
  不排除自身则准确率恒 100%；分母、混合轨迹球计法均未定义
- 修订：§--evaluate 协议写死——roster-seeded（主指标，逐轨迹留 1 球作
  种子、被预填球自身不作源）与 number-seeded（副指标，模拟冷启动）分开
  报数；分母=收到预填的球；冲突/mixed/unlinked 计入覆盖失败；报表逻辑
  纯函数可单测

### B3：页面侧三个冲突点

- 问题：①NOGOAL 哨兵会沿 assign 传播扩散（真球被静默标"不算进球"）；
  ②传播写 marks 会遮蔽号码 prefill_tag 展示与 acceptAll 幂等判定，与
  声明的优先级相反；③传播载体字段/徽标判定/与 acceptAll、E 键、照片
  印名预填的关系全未定义
- 修订：§页面写死——assign 仅 tag≠NOGOAL 触发传播；只写"无 marks 且无
  prefill_tag 且未 touched"的球；provenance 集合（localStorage 独立键）
  支撑徽标判定式；acceptAll/E 键只收 prefill_tag 不碰传播；预填优先级
  总链：手改 > 读号/照片/印名 > 传播 > 颜色

### B4：Phase 2 模板自举缺对齐规则 + 缓存污染 K3 语义

- 问题：number_cache 条目无数字包围盒，"切数字区域"无规则（粘连/断裂
  常态）；offline 结果写同一 number_cache 而读端不看 source，弱结果会
  被当 K3 结果入票
- 修订：对齐规则写死（连通域数==号码位数才接收样本，按中心 x 升序 zip，
  不符丢弃记 INFO；每数字 ≥3 样本才启用）；offline 结果单独落
  offline_number_cache.json，K3 链路零感知，仅跳票模式作 K3 缓存的
  并集来源（K3 优先）

### B5：propagate 重算种子的保真度问题

- 问题：初版允许 propagate 自行重跑 locate_scorer 补 seed，但不给
  anchor_xy 会退化选错轨迹，传播映射的人与裁图里的人可能对不上
- 修订：写死"propagate 只消费 entry 的 seed_* 字段，不重算"；seed 缺失
  WARNING 跳过进 unlinked；crop_scorers 先跑落字段成为 people 链的硬性
  顺序（video.py 接线体现）

## 非阻断建议的处理（全部采纳）

- 跟踪器唯一性规则写死（每框至多入一轨；竞争按"最后更新帧更近 → IoU
  更大 → track_id 更小"裁决）
- 颜色守卫"便服"样本不计入一致也不计入不一致
- track_id 不落 entry（candidates 只读），页面从 track_links.json 反查
- video people 接线明确（裁图 → 传播 → 聚类 → 确认页）
- spec 补 Code Style 段（与 scorer-cluster/scorer-reid 一致）
- 实跑任务加前置条件栏（todo Task 9/10）
- 素材特性提醒（7 成球入网后 <2s）写进背景事实——传播以前向回溯为主

## 结论

阻断全部修订完毕。本周期实施范围 = Phase 1（轨迹传播脚本+页面+接线）
+ Phase 2（离线读号脚本），实跑标定待新场次数据（Task 9/10 挂起）。
