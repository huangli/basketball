# plan：标注页导出文件名自动带批次号

## 步骤

1. `scripts/gen_label_page.py`
   - argparse 加 `--batch`（type=int，default=None）
   - 新增内部变量 `out_name = f"goals_batch{K}.json" if batch else f"goals_{session}.json"`，
     以 `__OUTNAME__` 占位符注入 HTML 模板（同 `__SESSION__` 现有机制）
   - 模板三处用文件名的地方改引用注入值：导出按钮文案、`a.download`、导出成功 alert
2. `scripts/run_session.py` ⑦ 命令构建：非 adhoc 批次追加 `--batch <K>`（K = 批次序号，
   即 label `batchK` 的数字）；adhoc 不传
3. 测试
   - `tests/test_gen_label_page.py`：传 --batch 时 HTML 含 `goals_batch2.json`；
     不传时仍为 `goals_<session>.json`
   - `tests/test_run_session.py`：⑦ 命令含 `--batch 1`（batch1）/ adhoc 不含 --batch
4. 文档联动：`使用手册.html` 第 2 步、`docs/video-cli/spec.md` §45 口径
5. 质量门：ruff format / check --fix / pytest -q；spec-reviewer 审 docs + 手册

## 风险

| 风险 | 应对 |
|---|---|
| 旧页面（已生成的 label.html）不会追溯更新 | 预期内：重跑⑦或手工改名照旧兼容，CLI 双轨识别不变 |
| 模板占位符遗漏导致 JS 报错 | 测试断言 HTML 含目标文件名；node --check 同款静态检查如有惯例则沿用 |
