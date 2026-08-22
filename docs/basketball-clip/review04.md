# Review 04: spec.md v4 定案改动审查（2026-08-22）

> 审查员：spec-reviewer 角色子代理（只读审查）。范围：O1/O2/O3/O5/O6 定案写回 + Tech Stack 同步。

## 阻断问题与处置

- **B7（O3 × 脱敏扫描表冲突）**：仓库地址含 `huangli`，与关键词零命中要求互卡。
  → 已修：脱敏扫描清单新增豁免口径（仓库 URL/作者署名属开源必需公开署名，允许命中），Success Criteria 5 同步对齐。
- **B8（O6 双版本策略缺开发期语法防护）**：现 ruff.toml `target-version = "py314"`，开发期不拦 3.11+ 语法，打包才炸。
  → 已修：Code Style 节声明新仓库 ruff `target-version` 降为 `py310`；O6 行防护链补全（ruff 开发期拦截 + spike 实包验证）。

## 实证

- scripts/ 全量扫描 3.11+ 专属语法（tomllib/except*/typing.Self/ExceptionGroup/PEP 695/PEP 701 等）：**零命中，当前兼容 3.10**。
- O1/O2/O5 定案与 Tech Stack、Boundaries、Success Criteria 无新冲突。

## 结论

B7/B8 修复后**通过**（两处均为口径对齐，无实质风险，不再追加轮次）。
