# todo：标注页两个 bug 修复

依据 `docs/label-page-fixes/spec.md` / `plan.md`。

## Task 1：Bug① 声音开关不打断播放 ✅ 2026-08-16

- [x] sound onclick 删 `show(cur)`，只切 `v.muted` + 更新按钮文本
      （gen_label_page.py 原 :282）
- [x] 回归断言：sound onclick 语句块无 `show(`、含 `v.muted = !v.muted`
      （test_sound_toggle_does_not_reload_clip，语句块可多行提取）
- [x] node --check 通过（test_generated_js_syntax_node_check）；ruff + pytest 全绿

## Task 2：Bug② localStorage 跨批隔离 ✅ 2026-08-16

- [x] build_html 注入 `__LSUFFIX__`（batch 给 `_batchK`，否则空串）
- [x] 模板 LSKEY 拼 `__LSUFFIX__`；不传 batch 旧键逐字节不变
- [x] 回归断言：batch2/batch3 LSKEY 互不相同且 POSKEY 随之隔离
      （test_localstorage_keys_isolated_per_batch /
      test_localstorage_keys_unchanged_without_batch）；无 batch 无 `_batch` 后缀
- [x] node --check 通过；ruff + pytest 全绿

## Task 3：手册同步 ✅ 2026-08-16

- [x] 使用手册.html 标注节加"重生成页面清进度、先导出备份"注意事项
      （warn 块，含"进度按批次隔离"说明）
- [x] 手册更新日期刷新（2026-08-16，build 实测条目同日已更新）

## Task 4：收尾

- [ ] 独立审查员产出 review02.md（阻断问题须修订后再交付）
- [ ] 立哥页面实操验收（声音开关 + 跨批进度隔离）
- [ ] commit（只 add 本功能文件；不 push）
