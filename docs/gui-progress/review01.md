# Review 01: gui-progress spec/plan/todo 审查（2026-09-05）

> 审查员：spec-reviewer 角色子代理（只读审查）。

## 阻断问题与处置

- **缓存命中/断点续跑场景 overall_pct 分母缺失**：实证 `mot_candidates.py:671-678` 命中检测缓存的 fid 不进逐帧循环、不输出 `第x/y帧` 行，续跑时已完成 fid 不进分子也不进分母，百分比严重失真（例：5 fid 中 4 缓存，最后一个跑一半显示 50% 而非 90%）。
  → 已修：`mot_candidates.py:669` 对每个 fid（含缓存命中）输出 `=== <fid> (<N>帧) ===`，spec 设计节新增"分母注册"口径（解析该行提前注册全部分母；"命中缓存"行 → fid 瞬时计入分子）；成功标准 1 补续跑误差边界；plan/todo 补混合用例。

## 通过项

- 六要素齐全、成功标准可测；plan/todo 与 spec 一致；T2 chore 独立 commit。
- 单调不减口径无逻辑漏洞（首 fid 虚高属既定近似，已在 spec 写明）。
- 协议兼容性成立（app.js switch 无 default 抛错，新增事件对 v1 消费者静默忽略）。
- 正则误匹配已被风险表覆盖，实际日志格式与 spec 一致。
