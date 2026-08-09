# Review 01: 认人增强三件套 spec-reviewer 审查（第 1 轮）

日期：2026-08-09
对象：docs/scorer-reid/{spec,plan,todo}.md（初版）
审查人：spec-reviewer 子代理（对照 cluster_scorers/crop_scorers/gen_scorer_page/
roster.py 现状代码与 docs/scorer-cluster/review01.md 标定曲线核查）

## 审查结论：3 个阻断问题（全在 Phase C 契约完备性），已全部修订

### 阻断 1：投票规则未定义 None 票与单票退化路径

- 问题：K3 看不清合法返回 number=null，初版三态规则未定义 None 票如何计数、
  单票（只裁 1 张或其余全 null）如何处理；单票正是 20260722 迁移后每球必走
  的路径，不定义无法验证"无回归"
- 修订：spec 写死"None 票不参与计数；有效票=1 时 high 采纳、low 归 None+low；
  有效票≥2 全不同取唯一 high（多个 high 不采）；有效票=0 归 None+low"，
  测试策略补对应用例

### 阻断 2："零新调用"与投票机制在现有代码结构下不可兼得

- 问题：迁移只把旧 goal key 重键到 crops[0] 的 md5，crops[1]/crops[2] 从未
  被读过必然缓存未命中；20260722 重跑若全量投票将产生 ~208 次新调用，
  超 --max-reads 闸直接拒绝——"零新调用实跑"按初版契约不可达
- 修订：定义两种读号模式——全量模式（默认，新场次用，额度按 球数×best_crops
  估算）与跳票模式（--numbers-cache-only，缓存未命中跳过、已有票投票、
  零新调用，20260722 旧数据回填用）；spec 命令示例 --max-reads 80 修正为 300
  口径；成功标准改为"跳票模式重跑零新调用回填不丢"

### 阻断 3：缓存迁移边界行为未定义，旧条目信息不足

- 问题：旧缓存 value 不含裁图文件名，迁移只能靠当前 run entries 反查
  crops[0]；初版未定义：查不到 entry 的旧 key 怎么办、裁图缺失怎么办、
  迁移在哪触发（不带 --read-numbers 时旧缓存静默失效）
- 修订：迁移规则写死四条——触发位置（--read-numbers 路径内、load 之后、
  识别闸之前；不带则不迁移，该路径本就不回填无损失）；查不到 entry 的旧 key
  原样保留记 INFO（清理由人决定）；裁图缺失记 WARNING 保留原 key 不炸批；
  幂等（二次执行零变化）

## 非阻断建议的处理

| 建议 | 处理 |
|------|------|
| --model 取值与缓存 model_tag 脱节（CLIP tag 须保持不变复用旧缓存） | 采纳：spec 加"CLI 取值 → model_tag"对应表 |
| 共享 clip_cache.json 的 _meta/文件名语义 | 采纳：文件名不动，docstring 注明，_meta 记最后运行者可接受 |
| "104 球对照"口径（实 99 键入统） | 采纳：成功标准注明入统口径 |
| 标定只跑 complete linkage | 采纳：plan/todo B3 改 average+complete 双 linkage |
| ≤30 簇 ≥85% 偏紧 | 保留目标+降级出口；review 补标定时写明"不达标是基准情形"的预期管理 |
| team_of_tag 现状已与目标一致（黑/蓝→地平线、白→半截篮、余→便服） | 采纳：spec/todo 改为零改动+测试锁定 |
| roster.py:16 docstring 队名过时 | 采纳：Phase D 顺手修一行 |
| plan/todo C2/C3 实迁验收错位 | 采纳：实跑验证归入 todo Task C3 |

## 核查通过项（审查代理确认）

- 旧缓存 key 确为 goal key；entry["crop"]=crops[0] 保证"crops[0] 即当年被读的
  那张"成立；多裁重跑图内容漂移沿用 review01 已记录的可接受口径
- cluster 侧契约与现状兼容：缓存键 model:md5 前缀过滤天然支持双后端；
  ImageEncoder/EncoderFactory 已为假 encoder 注入留口
- --players-file 与现状可对接（match_players_by_number 只消费 Player 列表，
  与来源无关）；roster.py VALID_TEAMS=地平线/半截篮/便服 与 spec 一致
- Phase 依赖正确（A 卡 B；C/D 独立不触 torchreid）；todo↔plan 一一对应；
  分 Phase 提交、四件套目录、review 轮次编号符合 AGENTS.md 约定
- Boundaries 合理：不静默回退 CLIP、torchreid 失败停工报立哥、不删旧缓存

## 结论

阻断问题全部修订完毕，三件套可进入实施（Phase A spike 先行，
torchreid 装不上即停工报立哥）。
