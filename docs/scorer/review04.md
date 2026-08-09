# Review 04: T7 号码识别预填（K3 版）提交前审查

> - 审查对象：T7 diff（scripts/crop_scorers.py +305、gen_scorer_page.py +78、两个测试、todo.md）
> - 审查日期：2026-08-08
> - 审查人：Kimi Code（spec-reviewer 子代理）
> - 结论：**需修订（仅文档同步）→ 已修完**；代码本身可提交

## 阻断问题与修复

| # | 问题 | 修法 | 状态 |
|---|---|---|---|
| B1 | spec.md 4 处残留"豆包"（L19/L27/L154/L174），T7 已改 K3——凭证机制写错会误导维护 | spec 4 行改为 K3（订阅 OAuth、无 ARK_API_KEY、不按 ¥ 计费）；Open Q2 标记已拍板 | 已修 |

## 非阻断建议与处理

1. crop_scorers.py:189 docstring 残留"豆包" → 已改 K3
2. `data.get("choices",[{}])[0]` 空 choices 会 IndexError 炸整批 → 已加 `or [{}]` 护栏
3. `except TypeError, ValueError` 无括号元组（3.14 新语法可用但不一致）→ 已统一带括号
4. apply_number_reading 成功路径未端到端测 → 记录在案，下轮补
5. 提交卫生：素材目录 untracked，显式 add 清单不用 -A → 已照做

## 逐项核对（全部通过）

- K3 调用复用 vlm_filter 封装（API_URL/MODEL/crop_to_b64/load_token/重试口径）✓
- 凭证不落文件；number_cache.json 幂等（prompt_version 变更作废有测试）✓
- >20 张新调用抛 ExternalApiError 护栏（缓存命中不计）✓
- 号码→tag 匹配：数字边界防子串误配、颜色字必含、同号歧义不预填（均有测试）✓
- 预填优先级：号码 > 颜色 ✓
- 禁区零改动（gen_review_clips / gen_label_page / review_batch2）✓
- 实测：ruff 全绿、相关测试 101 项全过（断言与桩逐条核对，非假绿）✓
- 批次 1 实跑：17 球读号 5 张 high 全部忠实裁图、token 23001（均值 1353/张）、0 ERR ✓
