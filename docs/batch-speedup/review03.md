# review03：batch-speedup plan/todo 审查（spec-reviewer 第 3 轮）

日期：2026-08-10　审查方式：spec-reviewer 子代理（plan 型，只读）
判定：**通过（无阻断问题）**

## 核实要点

- plan ↔ spec 对应：残次事件汇总、fid 覆盖核对、facts 比对、--keep-clips
  均有落实点，无私自加戏
- Step 0 循环导入处置成立：mot_candidates.py:31 引用 pipe_common，
  pipe_common 仅依赖 errors.py，反向 import 必成环 → 显式传 fps 零耦合
  正确；SAMPLE_FPS=5.0、parse_sec=round((idx-1)/5,1) 互逆映射经源码核实
- todo 可勾选性：Task 1→2→3 链正确，Checkpoint 位置合理，机检/人核分开
- F1 三条硬规定（合并写/已标禁用/不写位置键）均有机器可检的回归断言点
- F2 单测不动真实素材可行（tmp_path 伪造 + 探测可注入）

## 建议（4 条，已采纳）

1. todo Task 4 补两条 spec 漏项验收：混合分辨率/帧率终止、单文件失败
   汇总+非零退出
2. Task 4 加"dry-run/日志如实标注 ② 为全场抽 + 幂等跳过"
3. 扫描探测与命令清单构建拆函数（dry-run 单测可 monkeypatch 探测）——
   已写入 Task 4 设计点
4. plan Step 1 session 推导措辞修正（父目录以 review 开头才上溯祖父）

## 结论

四件套齐备可开工。实施后复审写 review04.md。
