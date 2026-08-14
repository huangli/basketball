# plan：认人确认页导出文件名即 roster.json

## 步骤

1. `scripts/gen_scorer_page.py`
   - `a.download = "roster_" + SESSION + ".json"` → `"roster.json"`
   - alert 文案同步（含"移到 work 场次目录"提示）
   - 页头提示行"导出文件名 roster___SESSION__.json" → "导出文件名 roster.json"
   - 模块 docstring 第 7 行同步
2. `tests/test_gen_scorer_page.py`：`test_export_contract_roster_json` 断言
   `a.download = "roster.json";`
3. `使用手册.html` §一第 3 步改名步骤改"移动即可"；§五 FAQ「build 报 roster
   不存在」补旧导出物改名说明
4. 质量门 + spec-reviewer + 提交

## 风险

| 风险 | 应对 |
|---|---|
| 多批导出同名带 ` (1)` 后缀 | 手册提醒移动时去掉；单测钉住精确文件名 |
| 旧导出物 roster_<场次>.json 存量 | 兼容不变：人工改名为 roster.json 照旧可接入 |
