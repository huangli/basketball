# review17：v4.2 分区副图 + build 集成一轮审查（2026-08-16）

审查对象：docs/heatmap/spec.md（v4.2 节）、plan.md（Task 7）、todo.md
审查员：spec-reviewer（coder 子代理扮演，agent-65）· 结论：**需修订 → 已全部落实**

## 严重（S1-S4，已落实）

- **S1 边界条与改 video.py 矛盾**：边界节"不改 goal_heatmap.py 以外任何
  文件"与 v4.2 改 `_cmd_build` 直接冲突 → 边界条补 v4.2 例外写死
  （仅成功返回前追加触发，不改既有命令拼装/返回码语义）
- **S2 "界外点根本不进渲染输入"与 0.5m 余量矛盾**：余量带
  （|dx|∈(7.5,8.0] 或 dy<0）点会被 zone_of 归到多边形不含它的区
  （ra/paint 只覆盖 y≥0）→ 写死残余口径：余量带点归最近语义区、计数
  守恒、散点如实、报告注明（当前实测 dy≈+1.9~+4.5 无实害）
- **S3 "detect/frames 默认推导"实现侧未写死**：heat_session 四参全必填，
  推导只在 main() → 写死：三目录取 None 默认、推导收进 heat_session，
  video.py 只传 session_dir；monkeypatch 目标 = goal_heatmap.heat_session
- **S4 "matplotlib 已在本进程依赖链"事实错误**：video.py 顶层无
  matplotlib/numpy → 更正并写死成功分支内懒 import（防 score/people/
  photo 白付导入成本）

## 建议（J1-J5，已落实）

- J1 roster 缺失跳过降 INFO（尚未认人是预期常态，WARNING 留真异常）
- J2 重算副作用写死（重写 goal_landings/audit/output PNG，确定性原子写）
  + 耗时秒级~十秒级声明 + build 收尾 log 一行热图结果（出图/跳过/失败）
- J3 调色板字典序 = Unicode 码位序写死（半截篮 U+534A < 车百鼎 U+8F66
  → 暖红/深蓝，与打样图一致）
- J4 plan 头部同步 v4.2
- J5 由 J2 收尾摘要行闭环用户可发现性

## 对照核对通过项

10 区几何/填色公式/标注/视野与打样逐条相符；集成点与 _cmd_build 结构
吻合；HEX 删除与测试清单一致；test_video.py monkeypatch 结构可行。
审查员注明：修订后 diff 复核即可，无需整轮重审。
