# review04：batch-speedup 实施复审（spec-reviewer 第 4 轮）

日期：2026-08-10　审查方式：spec-reviewer 子代理（plan 型，只读）+ 主会话实测
判定：**通过（无阻断问题）**

## 成功标准核对结论

- **F1**：标准 1（234/234、702 张、0 降级 0 跳过）✅；标准 2 证据为 3 事件
  实片内容比对 + 两层单测（互逆映射/钳位），方向性风险已排除，满 10 抽
  查并入立哥验收项顺带核对 ✅；标准 3 联动机器部分验证充分（两侧 LSKEY/
  marks 结构/合并写完全对称，跳过逻辑为 label-speedup 既有已测行为）✅；
  标准 4 立哥验收待做
- **F2**：五条全过——dry-run 6 批×7 阶段含 --keep-clips + --orig 3840x2160
  （单测+真素材双证）；续跑 ②③ 毫秒级跳过；adhoc 全套产物；故障注入
  （facts 篡改退出码 2 实测 / candidates 截断走重算路径有单测）；
  pytest 455 passed、ruff 全绿

## subagent 自决项处置（审查方逐条判合理）

**立哥需知情的三条**：

1. **补素材进已跑场次**：facts 比对必判不一致，安全路径是
   `--force --fids 新文件`（adhoc 固定命名不覆盖历史批次产物；
   裸 --force 会真重算 ④⑤⑥ 且切批边界移动有事件 key 漂移风险）
2. **零帧卡片**：帧目录整体缺失的事件以零图卡片上墙 = "帧缺失，
   须去 label.html 放视频判"，不是页面坏了
3. **子进程无总超时**（有意权衡）：单批检测小时级，超时误杀比无界更糟；
   ffmpeg/ffprobe 层超时归老脚本内部管理

其余（钳位去重、safe_name 撞名实测不撞、降级退 0、fid 重名终止、
⑦页面非空即跳过、③缓存损坏重算）均合理，不改代码不改 spec。

## 遗留（非本功能引入，另立任务再议）

`__SESSION__` 直替换进 JS 字符串未转义引号、json.dumps 不转义 `</script>`
——与 gen_label_page 同款既有模式，如要修应两页一起修。

## 关口

ruff format / check 全绿；pytest 455 passed；node --check 两生成页通过。
commit 链：3d7a98c（四件套）→ 8b0acc1（Task1）→ 82e2d3b（F1）→
ae73ea7（F2）→ 本 review 随 todo 回填提交。

## 待办

- 立哥两项实操验收：①批次 3 triage.html 墙扫尾体验（顺带核对缩略图
  与视频时刻一致）；②dry-run 命令等价性对照
- AGENTS.md 同步（新脚本 run_session/gen_triage_page 入流水线描述）——
  执行时另一会话正在改 AGENTS.md，待其提交后补，防工作区搅动
