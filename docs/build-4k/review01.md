# Review 01：build-4k spec 审查（agent-evaluator 代行 spec-reviewer，2026-08-29）

**结论：不通过，修订后复审。** 三个阻断集中于同一根因：命名决策与示例代码未核对底层命名生成点和尺寸解析结构。

## 阻断问题

- **B1. `_4K` 后缀与"底层零改动"矛盾**：产物主名由 build_highlight.py 内部生成（:598/:216/:231），无输出名覆盖参数；video.py 调用面无法影响产物名。三者（零改动 / Never 不改底层 / 加后缀）不能同时成立。修法二选一：a) 底层加输出名/后缀参数（推荐）；b) video.py 事后 rename 并写清命名推导来源。
- **B2. `--team 半截篮 --4k` 语义未定义**：默认已 4K 原名，再加后缀会产出内容相同的重复文件。修法：明写该组合为幂等 no-op（或显式报错）。
- **B3. Code Style 示例与现状脱节**：`resolve_out_size`（video.py:398-447）只返回尺寸串、比例分类不外抛；现状用相对容差 RATIO_TOLERANCE 而非示例的 RATIO_EPS；且全 filters 共用一个 out_size（video.py:940），4K 化需把 --out 拼装挪进 filter 循环。修法：示例改为单一分类来源 + 相对容差，并明写 per-filter 注入重构。

## 建议

- S1. 常量实际在 video.py:72-73（spec 写 65-66）
- S2. 示例产物名应为 `队伍_citymonkey_4K_进球集锦.mp4`（底层主名带"队伍_"前缀）
- S3. `--4k` 不带选择器的语义未定义，建议明写
- S4. 缺幂等用例：连跑两次 --all，半截篮原名产物始终 4K 不回退
- S5. Boundaries 加一句：自动模式颜色队（白/黑）不视为半截篮，不出 4K
- S6. 性能提示位置明写（每个 4K 步骤执行前 INFO 一次）

## 通过项

- P1. --out 注入机制论断正确（build_highlight.py:125-128/:615，CRF 随像素放大）
- P2. --all 展开逻辑与代码一致，半截篮以 ("--team","半截篮") 进 filters，可按值识别
- P3. confirmed/auto 分流判断与代码一致
- P4. 热图仅 confirmed 路径触发、与分辨率无关，口径正确
- P5. 需求覆盖无过度设计，排除项干净
- P6. Success Criteria 1/3/4/5 可检验（2 受 B1 牵连）
