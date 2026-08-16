# spec：标注页两个 bug 修复（声音开关不打断播放 + localStorage 跨批隔离）

日期：2026-08-16　状态：待实施　提出：主会话流程优化调研（标注页人工提效专项）

## 背景与问题

调研中发现 label.html 两个真实 bug（均已在车百鼎场次三批页面上实证）：

### Bug ①：声音开关重置播放状态

**现状证据**：`scripts/gen_label_page.py:282`——

```js
document.getElementById("sound").onclick = () => { v.muted = !v.muted; show(cur); };
```

`show(cur)`（`gen_label_page.py:170-196`）会：重设 `v.src`（浏览器重新加载
片段，播放进度归零）、`v.playbackRate = 1`（丢掉 S 键切的 4x）、`wide = true`
（翻回全景视角）。而欢呼是天然进球信号（经验教训 §4、主文档 §3.6）——立哥
恰在判读关键瞬间开声音确认，当前实现每次开/关声音都要从片头重看一遍，
打断节奏且丢倍速/视角。

**预期行为**：开/关声音只切 `v.muted` 并更新按钮文本，播放进度、倍速、
视角全部保持不动。

### Bug ②：localStorage 键跨批共享

**现状证据**：
- `gen_label_page.py:150-151`：`LSKEY = "label_" + SESSION`、
  `POSKEY = LSKEY + "_pos"`；
- `scripts/run_session.py:454-455`：各批生成页面时传同一个
  `--session session_dir.name`；
- 实证：车百鼎三个批次页面 grep 结果均为 `const SESSION = "20260805_车百鼎"`
  （`work/20260805_车百鼎/review_batch{1,2,3}/label.html`），三批共享同一
  LSKEY/POSKEY。

后果：
1. `stats()`（`gen_label_page.py:164-169`）统计整份 localStorage——batch2/3
   页头"已标 X（进球 Y）"混入其他批次的 marks，进度显示虚高；
2. `POSKEY` 共享——标完 batch1（末位置如 50）再开 batch2，启动逻辑
   （`:298-303`）把 50 当合法位置恢复，落在列表中间而非首个未标注事件。

（marks 本身以 `fid#eN` 为键、各批 fid 不重叠，不会互相覆盖——坏的是
统计口径与位置恢复，不是数据丢失。）

**预期行为**：批次页存储键带批次后缀 `label_<场次>_batchK`（POSKEY 随之
隔离）；不传 batch 的旧布局/adhoc 调用维持旧键 `label_<场次>` 逐字节不变。

### 旧键处理口径：作废，不迁移（选择及理由）

选 **作废**：场次标注完成即封存，下一个场次全部用新键，无历史包袱
（实证：车百鼎三批 goals_batch{1,2,3}.json 均已导出落盘，换键零存量损失）；
受影响场景仅"某批标注到一半时重新生成该批 label.html"（该批进度清零），
由使用手册注意事项覆盖。
不选一次性迁移：旧键混存多批 marks，迁移需按当前 EVENTS 过滤拆分 + 多页
并发竞争处理（~10 行 JS），成本高于实际收益；误迁移反而污染新键。

## 非目标（及理由）

- **P3 暂停/逐帧键**：等立哥实操反馈再定，避免无需求键位膨胀；
- **P4 下一片段预取**：本地文件加载已快，收益约半分钟/批，先不做；
- **P5 同组事件自动合并**：误并真两球 = 合集直接丢球（合并事件只导出末成员
  一个锚点）；"机器只提示不自动合并"是架构红线（dedup-same-goal spec 非
  目标），二期若做需先建回放验证框架，不在本次；
- 不动检测/切片/合并/排序任何上游环节；不碰另一 session 正在改的
  build_highlight.py / goal_heatmap.py / video.py build 段 / docs/heatmap/。

## 成功标准

1. Bug① 断言：生成 html 中 `getElementById("sound").onclick` 所在行不含
   `show(`，含 `v.muted = !v.muted` 与按钮文本更新；现有 `playbackRate = 1`
   等 label-speedup 断言不回归。
2. Bug② 断言：`build_html(..., batch=2)` 与 `batch=3` 产出的 LSKEY 表达式
   互不相同（含 `_batch2` / `_batch3`）；不传 batch 时 LSKEY 维持
   `"label_" + SESSION` 无后缀（旧布局兼容）。
3. `node --check` 生成页 JS 通过；`ruff format` / `ruff check --fix` /
   `pytest -q` 全绿。
4. 人工验收（立哥）：标注中开/关声音不跳回片头、不掉倍速/视角；
   两个批次页进度各自独立。

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 重新生成页面换键导致在标批次进度清零 | 低 | 手册注明：标注中的批次不要重新生成 label.html；必须重生成前先导出 goals 备份 |
| 模板 raw string 约束被误改（\n 转义黑屏） | 低 | 现有断言 test_build_html_export_has_same_rally_confirm 已锁；本次不碰 confirm 文案 |
| 旧布局/adhoc 调用键变化 | 无 | 不传 batch 时键与现状逐字节一致 |
