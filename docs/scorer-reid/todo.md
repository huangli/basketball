# Todo: 认人增强——Re-ID 聚类 + 多帧读号投票 + 名单映射

- [x] Task A1: torchreid 安装验证 spike（pip 装 → import → 权重下载 → 单张推理）
  - 结果：通过。包名 torchreid 0.2.5（非 deep-person-reid）+ 补装 tensorboard；
    Market1501 权重按官方 MODEL_ZOO 另下到 models/osnet_x1_0_market1501.pth
- [x] Task B1: cluster_scorers encoder 后端抽象 + --model + osnet_x1_0
  - 结果：MODEL_TAGS 映射表；build_encoder 分派；失败显式报错不回退
- [x] Task B2: Phase B 单测 + 质量门（403 全绿）
- [x] Task B3: Re-ID 实跑标定（双 linkage 各档）+ 提交 Phase B（4875c03）
  - 结果：**目标未达**——OSNet 与 CLIP 持平略差（complete@0.15: 43簇/51.5% vs
    CLIP 52簇/62.6%）；定稿维持 CLIP complete@0.15，OSNet 后端保留备用；
    曲线记 review01 附录；顺手修了 clip_cache 跨后端互冲 bug
- [x] Task C1: 读号逐张 + 众数投票 + 跳票模式 + entry 增 number_votes
  - 结果：投票全路径单测覆盖（含 None 票/单票/多 high 不采）
- [x] Task C2: number_cache 键改裁图 md5 + 旧缓存迁移（幂等/保留/WARNING）
- [x] Task C3: Phase C 质量门 + 20260722 跳票实跑（0 新调用 0 tokens）+
  提交 Phase C（59a1164）
- [x] Task D1: --players-file（互斥/校验复用 player_from_dict）+
  team_of_tag 测试锁定（零改动）+ roster.py 注释修正
- [x] Task D2: Phase D 质量门 + 提交 Phase D（3b1edd8）；
  真实名单 players.json（21 人）冒烟命中 白23-保罗
- [ ] 收官: AGENTS.md 更新（torchreid 环境 + Re-ID 标定结论 + 名单/投票口径）
  + spec-reviewer + 提交
