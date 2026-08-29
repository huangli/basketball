# Review 06: photo-roster 战役总收尾（2026-08-29）

## 最终状态（立哥定案）

**认人 = 纯人工确认页**：CLIP 聚类分组 + 名单按钮（photos/names.json 号码=姓名）
+ 视频终裁。机器预填全关：人脸 `--photo-match`、K3 读号 `--read-numbers`
均默认关、显式开可恢复。裁图质量闸两道在线（crop-quality 专项已闭环）。

## 全战役时间线与证据链

| 阶段 | 结论 | 归档 |
|---|---|---|
| v1 CLIP 照片匹配 | 证伪（跨人对 0.936 超同人对、7 协议最好 2/8） | review03 |
| K3 照片对照小样 | 10/13 零误指认（但同样受错人框影响+烧 token） | work/k3_photo_test/ |
| v2.1 零 token 级联 | spike：OCR 不投（有效采纳 6.9%+同号红线）、人脸小样工作点 | review04（立哥选型人脸单路） |
| 人脸产品化 T11/T12 | face_match_scorers + people ②.5 串联 + read_numbers 默认关 | 61b3959 / f038975 |
| T13 全场评测 | 覆盖率 11.4%、**采纳误指认 100%（4/4）不达标**；根因 = 错人框一阶（t173.8 抽帧实锤）+ 注册太弱 + 阈值全场失效 | review05 |
| **终态** | 2026-08-29 立哥定纯人工；②.5 默认关 | acefdd2 + 本文件 |

## 关键教训（已入 docs/经验教训.md）

- 同队同球衣 1:N 识别：纯外观全线证伪；人脸小样好工作点不可外推全场
- **错人框是基于裁图的一切识别的一阶前提**——治理方向（入网瞬间离球/离筐
  一致性、多帧轨迹交叉验证）挂后续立项，当前不排产
- roster 真值以视频为终裁优于裁图判断（t173.8：裁图 14 → 视频 22 实证）

## 交付清单（本战役 commits）

- 61b3959 人脸 matcher 产品化；f038975 people ②.5 换人脸 + read_numbers 默认关
- 8b32c94 names.json 名单自动注入；a150cb9 裁图质量闸两道
- acefdd2 ②.5 默认关（纯人工定案落地）；b0980c7 T13 评测器测试 + review05
- 文档：手册认人段/names.json 维护节、AGENTS.md 认人链路、经验教训 2 条、
  spec v2.2 终态注记 + 阶段命名统一（spike→选型→产品化→评测→收尾）

## 遗留 suggestions（审查记录，不阻塞，复用时再议）

- 评测器 render_markdown：空混淆矩阵表头保护、显式 PASS/FAIL 判定行
- 端到端测试两比率同为 66.7% 的断言区分度加固；评测路径 OSError 竞态包裹
- score_goal_cached 遇裁图缺失整球不出分 vs live 跳张出分的口径差（保守方向，
  docstring 已注明）
- T11 spec/plan/todo 曾写"评测器改造 photo_match_scorers.py"，实落
  face_match_scorers.py（人脸缓存同模块，todo T13 已修订注明）

## Santa 纪律总结

- plan/todo 七轮双独立审（R7 双 PASS）；spike/标定两轮双审（修正后双 PASS）；
  T5+T6/T11/T12/默认关/T13 评测器代码各一轮双审全部 PASS（T11 修两条 MEDIUM：
  中文路径读图、detector 批级单例；names 注入修逗号防护/类归属/查重）
