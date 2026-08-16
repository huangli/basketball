# plan：标注页两个 bug 修复

依据 `docs/label-page-fixes/spec.md`。改动仅限 `scripts/gen_label_page.py`
（_HTML 模板 + build_html 注入）+ `tests/test_gen_label_page.py` +
`使用手册.html`。预估代码改动 <20 行（不含测试）。

**不碰**：build_highlight.py / goal_heatmap.py / video.py build 段 /
docs/heatmap/（另一 session 正在改）；任何上游检测/切片脚本。

## Step 1：Bug① 声音开关不打断播放

- `_HTML` 模板 sound onclick（现 `gen_label_page.py:282`）改为只切
  `v.muted` + 更新按钮文本：
  `() => { v.muted = !v.muted; document.getElementById("sound").textContent = v.muted ? "声音：关" : "声音：开"; }`
  ——删掉 `show(cur)`；按钮文案与 show() 内 :193 保持一致
- 测试（`tests/test_gen_label_page.py`）：新断言——提取含
  `getElementById("sound").onclick` 的行，断言行内无 `show(`、含
  `v.muted = !v.muted`
- 关口：node --check + ruff + pytest

## Step 2：Bug② localStorage 跨批隔离

- `build_html`：batch 非 None 时新增模板占位 `__LSUFFIX__` =
  `_batch{batch}`，否则空串；模板 `LSKEY = "label_" + SESSION + "__LSUFFIX__"`
  （POSKEY 派生逻辑不动，随之隔离）
- 模板替换链加 `.replace("__LSUFFIX__", ...)`；raw string 约束不变，
  不碰 confirm 文案
- 测试：`build_html(batch=2)` 含 `_batch2`、`batch=3` 含 `_batch3` 且两者
  LSKEY 不同；POSKEY 派生形式随之隔离（含 `_batchK_pos` 或等效断言）；
  不传 batch 不含 `_batch`（旧键逐字节不变）
- 关口：node --check + ruff + pytest

## Step 3：使用手册.html 同步

- 第 2 步标注节 tip 区加一条：批次页进度存浏览器、按批次隔离；
  **标注到一半的批次不要重新生成 label.html**（重生成会换存储键、该批
  进度清零），必须重生成时先点导出把 goals 文件下载备份
- 手册"更新日期"按惯例刷新

## Step 4：收尾

- 回填 todo.md 勾选
- review 由独立审查员产出 reviewNN.md（本 plan 不含）
- commit：两个修复同属标注页小修，一个 commit；只 add 本功能文件
  （gen_label_page.py / test_gen_label_page.py / 使用手册.html /
  docs/label-page-fixes/）；只 commit 不 push

## 验收关口

- [ ] node --check 生成页语法通过
- [ ] ruff format / check --fix / pytest -q 全绿（--fix 后复核 diff）
- [ ] 立哥实操验收（声音开关不打断 + 两批进度隔离）
- [ ] 手册注意事项上线
