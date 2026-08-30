# Review 02：build-4k spec v2 复审（agent-evaluator 代行 spec-reviewer，2026-08-29）

**结论：不通过（距通过只差两处一句话级修订），修订后即可交付，无需第三轮全量复审。**

## 剩余阻断

- **B4（修订引入）. `_4K` 后缀插入位置自相矛盾**：D2/L91 字面是 stem 末尾追加
  （`队伍_citymonkey_进球集锦_4K.mp4`），D5/测试 4/Commands 期望是中段插入
  （`队伍_citymonkey_4K_进球集锦.mp4`）。修法：钉死中段插入——"在主名尾部类型词
  （进球集锦/进球合集）之前插入 `_4K`"。
- **B5（B2 未完全闭环）. `--all --4k` 展开路径漏 OUR_TEAM no-op 规则**：`--all`
  展开含 `("--team","半截篮")`，机械执行 D2 会产出 `队伍_半截篮_4K_进球集锦.mp4`
  与默认原名产物内容重复。修法：D3 扩展为"OUR_TEAM 步骤无论单点还是 --all 展开，
  --4k 均为 no-op"，并补 `--all --4k` 测试。

## v1 阻断与建议闭环核对（通过项）

- B1 ✓（D2 放开为可选 --name-suffix，Never 同步改写）、B2 单点 ✓（D3+测试 3+SC2
  三处一致）、B3 ✓（resolve_out_sizes 返回对、沿用相对容差、D4 明写结构改动）
- S1 ✓ 行号、S2 ✓ 示例名（受 B4 牵连，位置定死即闭）、S3 ✓ 无选择器语义、
  S4 ✓ 幂等用例、S5 ✓ 颜色队边界、S6 ✓ 提示位置

## 建议

- A1. resolve_out_sizes docstring 补"比例混杂或未知"（现状 video.py:444-447 对
  混比例同样显式报错，重构不能丢）
- A2. 测试 4（全员 4K）在 SC2 补半句验收
- A3. Project Structure 写死 tests/test_build_highlight.py
