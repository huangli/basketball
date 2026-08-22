# Review 02: spec.md v2 复审（2026-08-22）

> 审查员：spec-reviewer 角色子代理（只读审查）。结论：**需修订**（两处新引入的自相矛盾，改动量小）。

## review01 处置核对

- B1（豁免清单）已处置；B2（脱敏面）已处置且数据准确（tests/ 私人字样实测恰好 75 处：立哥 6 + 半截篮 35 + 车百鼎 32 + 7897 2）；B4（队名可配置）已处置；S1–S5 全吸收。

## 遗留阻断问题

- **B3'：`vlm_filter.py` 剔除与 `crop_scorers.py` 保留互相矛盾。** `crop_scorers.py:72-87` 模块顶层 `from vlm_filter import ...`，剔除后一 import 即 ModuleNotFoundError——`video.py people` 整条认人链对所有用户不可用，相关 tests 全红。需扩豁免：允许 crop_scorers 对 vlm_filter 的引用改为延迟导入或内联所需常量/函数（crop_to_b64/load_token 归属需定）。
- **B5'：O7"OSNet 后端下线"不在豁免清单内，撞"其余行为零改动"边界。** OSNet 在 `cluster_scorers.py` 是实质代码（build_osnet_encoder、--model osnet_x1_0、MODEL_TAGS 分派）且 tests 有大量 OSNet 用例。需列为豁免第 5 类（含对应测试剔除），O7 状态对齐。

## 建议改进

- 脱敏扫描表口径扩为"新仓库全部已跟踪文件"（含 gui/、packaging/、pyproject.toml、README）。
- `video.py:906` argparse description 含"半截篮"，明确归入豁免第 2 类。
- "实测约 75 处"注明精确口径便于发布前对账。
- O6 行内明示降级路径（3.13/3.12）。
