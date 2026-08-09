# review01：工作区文件夹结构优化（spec-reviewer 第 1 轮）

审查日期：2026-08-08。审查对象：docs/workspace-layout/ 的 spec.md / plan.md / todo.md。
审查方式：只读核对文件系统（work/ 根、work/frames、work/detect、根目录文件）、.gitignore、tests/ 与 scripts/ 引用。

## 结论：有阻断问题（2 处事实性错误，已按本轮意见修订完毕，通过）

## 已核实无误的事实

- work/ 根散文件 11 个，与 spec 清单一一对应：_research.py、_research2.py + 7 个 log（detect_20260722、extract_20260722、gen_review_v3、vlm_20260722、vlm_20260722_v2、vlm_events_round1、vlm_events_round2）+ file_inventory.json、pilot_inventory.txt。
- work/frames/ 下 15 个短名测试目录属实：0007/0011/0014/0020/0022/0030/0033/0040/0048/0062/0086/0102/0120/0128/0147（dji_mimo_* 目录约 300 个，属冻结清单）。
- work/detect/ 下非 dji_mimo 的 mot_cache 共 14 个（0147 无对应缓存）。
- work/ 确为 .gitignore 排除区（第 12 行 `work/`）。
- 移动对测试零影响：tests/test_build_highlight.py:28、tests/test_gen_review_clips.py:33、tests/test_roster.py:14 的路径常量仅作错误信息字符串，不读真实文件；conftest.py 明确测试在 tmp_path 下隔离。
- scripts 默认常量指向旧路径的情况与 spec 一致：vlm_filter.py:50-52、gen_review_clips.py:40-42、gen_label_sheet.py:32、pilot_candidates.py:25。一期不改代码、生产参数注入的处置合理。
- 无任何 scripts/docs 引用根 goals.json 或 剪辑流程图.html，移动安全。
- 与 docs/dedup-same-goal/ 无冲突：本件冻结 work/20260722/（含 dedup 回放素材），且一期不改 scripts；两件可按任意顺序实施。
- todo 与 plan 前置检查 + 批次 A–E 对应；成功标准可检验。

## 阻断问题（已修订）

1. **"archive/ 为 gitignore 排除区"不成立（spec.md 原第 54 行）**。实测 .gitignore 仅有 work/，无任何 archive/ 条目；archive/ 现有内容属 git 跟踪区。按原方案把 work/ 产物移入 archive/work_legacy/（尤其批次 D 的 15 个 frames 目录、十几万张 jpg）后会全部变为 untracked，污染 git status 并有误 add 风险。→ 已修订：spec 风险节更正事实，plan 批次 B 与 todo 第 2 项加入"先把 archive/work_legacy/ 写进 .gitignore 并 git check-ignore 验证"前置步骤。
2. **根 goals.json 描述与实测不符（spec.md 原第 10 行）**。实测内容为 {"version": 3, "goals": []}，无 session 字段；spec 原写"session 为 None"。→ 已修订为实际内容描述。

## 建议项（已采纳）

- 冻结清单写明"现状权威副本为 work/20260722/roster.json"（根目录 roster_20260722.json 内容已分叉：tag 为"黑21"，work 侧为立哥两轮修正后的"黑21-大斌"/"黑21-王敏龙"）——已写入 spec 现状盘点。
- 批次 A 的 git mv 判定依赖 git ls-files（plan 前置检查 2 已含）；批次 D 移动前对 archive/validate_2026-07-23/ 的 ls 核对（plan 已含）保留，该目录确实存在。

## 规范符合性

- 四件套目录约定（docs/workspace-layout/ 下 spec/plan/todo + 本 review01）符合 AGENTS.md。
- 阻断问题修订完毕，本件通过，可进入实施；实施期间认人会话未结束则冻结清单相关项按 plan 延后。
