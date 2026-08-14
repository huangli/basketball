# todo：标注页导出文件名自动带批次号

- [x] Task 1：gen_label_page --batch 参数 + `__OUTNAME__` 注入（按钮/download/alert 三处）
  - Verify：build_html 单测两处文件名断言全绿；batch<1 防御 ValueError
- [x] Task 2：run_session ⑦ 传 --batch（adhoc 不传）
  - Verify：dry-run 单测断言 ⑦ argv 含 `--batch 1`；adhoc argv 无 `--batch`
- [x] Task 3：测试补齐 + ruff + pytest 全绿（含 node --check 同款 JS 语法回归测试）
- [x] Task 4：使用手册.html §一第 2 步 + video-cli spec §批次发现 口径同步
- [x] Task 5：spec-reviewer 审查通过（review01.md），建议改进 3 条全部落实后提交
