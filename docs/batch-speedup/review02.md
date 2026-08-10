# review02：batch-speedup spec 第 2 轮复审（spec-reviewer）

日期：2026-08-10　审查方式：spec-reviewer 子代理（plan 型，只读）
判定：**通过**（4 阻断逐条复核修复属实，8 建议全部采纳，命令链抽查与
scripts/ 真实 CLI 吻合）

## 建议（2 条，已采纳）

1. 成功标准 2 的 <10s 阈值校准：extract_frames 幂等跳过仍逐文件 ffprobe
   探测，Windows 上 300 文件全量探测本身可能 >10s → 改为"单批 ≤50 文件
   <30s（探测串行开销计入）"
2. 阶段⑤写全参数：detect_hoops 的 --candidates/--out 无默认缺参报错 →
   阶段清单补全，与 ④⑥ 写法对齐
