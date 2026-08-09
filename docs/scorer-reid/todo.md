# Todo: 认人增强——Re-ID 聚类 + 多帧读号投票 + 名单映射

- [ ] Task A1: torchreid 安装验证 spike（pip 装 → import → 权重下载 → 单张推理）
  - Acceptance: osnet_x1_0 对一张真裁图出 embedding；任一失败停工报立哥
  - Verify: python -c "import torchreid" + 推理脚本实跑
- [ ] Task B1: cluster_scorers encoder 后端抽象 + --model + osnet_x1_0
  - Acceptance: --model clip 行为与现状一致；osnet 查无依赖/权重显式报错不回退
  - Verify: pytest -q -k cluster
  - Files: scripts/cluster_scorers.py, tests/test_cluster_scorers.py
- [ ] Task B2: Phase B 单测 + 质量门
  - Verify: ruff+pytest 全绿
- [ ] Task B3: Re-ID 实跑标定（20260722 三批次 --evaluate，average+complete
  双 linkage 各 2~3 档）+ 提交 Phase B
  - Acceptance: 双曲线记 review01；≤30 簇 ≥85% 达标与否有明确结论
- [ ] Task C1: 读号逐张 + 众数投票（None 票不计数；同号≥2 采纳 / 单票
  high 采纳 low 归 None / 多票全不同取唯一 high / 余 None+low）+
  跳票模式（--numbers-cache-only 零新调用）+ entry 增 number_votes
  - Acceptance: 投票各路径单测覆盖；entry 契约增量不破坏消费方
  - Verify: pytest -q -k number
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py
- [ ] Task C2: number_cache 键改裁图 md5 + 旧 goal-key 缓存迁移
  （--read-numbers 路径内、闸之前触发；幂等；查不到 entry 保留+INFO；
  裁图缺失 WARNING 保留原 key）
  - Acceptance: 合成数据迁移幂等
  - Verify: pytest -q -k cache
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py
- [ ] Task C3: Phase C 质量门 + 20260722 跳票模式实跑（零新调用回填不丢）
  + 提交 Phase C
  - Verify: 全绿 + 实跑日志（新识别 0 张）
- [ ] Task D1: gen_scorer_page --players-file（与 --players 互斥）+
  team_of_tag 映射测试锁定（现状已核实一致：黑/蓝→地平线、白→半截篮、
  余→便服，零改动）+ 顺手修 roster.py:16 过时队名注释
  - Acceptance: 名单 JSON 解析校验；坏数据 SchemaError；互斥 parser.error
  - Verify: pytest -q -k players
  - Files: scripts/gen_scorer_page.py, scripts/roster.py, tests/test_gen_scorer_page.py
- [ ] Task D2: Phase D 质量门 + 提交 Phase D
- [ ] 收官: review01 补标定记录 + todo 全勾 + AGENTS.md 更新 + spec-reviewer + 提交
