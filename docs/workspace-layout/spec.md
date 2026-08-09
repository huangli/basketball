# spec：工作区文件夹结构优化（workspace-layout）

## 背景与问题

三批次闭环后，根目录与 `work/` 根散落早期一次性产物，与现行"按场次组织"约定（AGENTS.md：中间产物放 `work\<场次>\`）不一致，查找与续跑成本上升。

## 现状盘点（2026-08-08 核实）

**根目录散落**：
- `goals.json`：空残留（`{"version": 3, "goals": []}`，无 session 字段），早期模板
- `roster_20260722.json`：与 `work/20260722/roster.json` 同结构（session/confirmed/players/assignments）但内容已分叉（tag 命名不同：根为"黑21"，work 侧为立哥两轮修正后的"黑21-大斌"/"黑21-王敏龙"）；**现状权威副本为 `work/20260722/roster.json`**，根目录副本待认人会话确认后处置
- `剪辑流程图.html`：流程图文档

**`work/` 根散落**：`_research.py`、`_research2.py`（一次性探索）、`detect_20260722.log`、`extract_20260722.log`、`gen_review_v3.log`、`vlm_20260722.log`、`vlm_20260722_v2.log`、`vlm_events_round1.log`、`vlm_events_round2.log`（早期跑批日志）、`file_inventory.json`、`pilot_inventory.txt`（清单产物）

**`work/` 旧子目录**（早期测试素材 20250419 / 试点产物）：
- `work/investigate_0006/`（调查产物，含 REPORT.md）
- `work/label/`、`work/pilot/`、`work/review/`（v1 流水线产物；`scripts/vlm_filter.py`、`gen_review_clips.py`、`gen_label_sheet.py`、`pilot_candidates.py` 的默认常量仍指向这些路径，但生产均已参数注入到 `work/20260722/`，留档脚本 vlm_filter.py 不动）
- `work/frames/` 下 15 个短名测试目录（0007 等，对应 archive/0_raw_videos_test 素材）
- `work/detect/` 下旧测试 fid 的 mot_cache（与 dji_mimo 场次缓存混放）

## 目标

1. 根目录只留入口级文件（AGENTS.md、rules.md、pyproject.toml 等配置 + 场次无关的 goals.json 类状态文件按约定归位）
2. `work/` 按场次归拢：早期产物进 `archive/`，现行场次产物保持不动
3. 所有移动零破坏：测试全绿、脚本可用、断点续跑能力保留

## 冻结清单（绝对不动）

- **认人会话进行中**：`roster_20260722.json`（根目录）、`work/20260722/roster.json`、`work/20260722/scorers/` 及其相关一切——待认人会话结束后再归位
- **原始素材**：`20260722地平线/`（立哥自己管理）
- **现行场次产物**：`work/20260722/`、`work/frames/dji_mimo_*`、`work/detect/dji_mimo_*_mot_cache.json`（万一补跑要用）、`output/` 全部
- **留档脚本**：`scripts/vlm_filter.py` 等已下线脚本只移产物、不改代码

## 方案

- 根目录：`goals.json`（空残留）→ `archive/`；`剪辑流程图.html` → `docs/`
- `work/` 根散文件（日志/清单/探索脚本）→ `archive/work_legacy/`
- `work/` 旧子目录（investigate_0006、label、pilot、review）→ `archive/work_legacy/` 下对应子目录
- `work/frames/` 15 个测试目录、`work/detect/` 旧测试 fid 缓存 → `archive/work_legacy/`（frames/detect 中间产物可再生，但归档成本为零，不留"删除"隐患）
- 脚本默认常量（work/label 等）：**一期不改代码**，只在移动后验证这些脚本的参数注入路径不受影响；默认常量清理另立小任务（涉及 tests/ 预期路径，改动面需单独评估）

## 成功标准

- `ruff check scripts tests && pytest -q` 全绿（移动前后各跑一次对比）
- 冒烟验证：`build_highlight.py --goals work/20260722/goals_batch3.json` 关键路径可达（不实际重跑合成，验证输入文件存在性即可）
- 冻结清单逐项核对零变动（移动前后 `git status` 与文件计数对比）
- AGENTS.md 如有路径约定变化同步更新

## 风险

- **认人会话并发冲突**：冻结清单规避；实施前先确认认人会话状态
- **隐藏路径引用**：grep 已做一轮（scripts/），实施时补 grep tests/ 与 docs/，发现引用随移动同步改（仅限注释/文档级，代码默认常量一期不动）
- **git 可追溯性（已核实）**：`work/` 是 .gitignore 排除区，但 **`archive/` 不是**——archive/ 现有内容属 git 跟踪区，把 work/ 产物（尤其批次 D 十几万张帧图）移入后会全部变为 untracked，污染 `git status` 并有误 add 风险。实施前必须先把 `archive/work_legacy/` 加入 `.gitignore`（plan 批次 B 前置步骤），并用 `git check-ignore` 验证；根目录 `goals.json`、`剪辑流程图.html` 若在 git 跟踪中须用 `git mv`
