# todo：工作区文件夹结构优化

## Task 0：前置检查

**Description：** 确认实施前提，记录基线。

**Acceptance criteria：**
- [x] 认人会话已结束（或立哥明确许可）；未结束则后续 Task 全部延后
- [x] `git status` 基线记录；`git ls-files` 确认根 `goals.json`、`剪辑流程图.html` 跟踪状态（在 git 则用 git mv）
- [x] 补 grep：`tests/`、`docs/` 下对 `work/label`、`work/pilot`、`work/review`、`work/investigate`、根 `goals.json` 的引用；结果记入 plan 附录

**Verification：**
- [x] 三项检查输出落 plan 附录

**Dependencies：** None
**Files likely touched：** `docs/workspace-layout/plan.md`（附录）
**Estimated scope：** XS

## Task 1：.gitignore 防护

**Description：** 把 `archive/work_legacy/` 追加进 `.gitignore`，验证生效。**必须先于批次 B-D 完成。**

**Acceptance criteria：**
- [x] `.gitignore` 新增一行 `archive/work_legacy/`
- [x] `git check-ignore archive/work_legacy/x` 返回命中

**Verification：**
- [x] check-ignore 输出验证；commit（与移动分开，单独一笔）

**Dependencies：** Task 0
**Files likely touched：** `.gitignore`
**Estimated scope：** XS

## Task 2：批次 A——根目录

**Description：** `goals.json`（空残留）→ `archive/goals_root_legacy.json`（改名防混淆）；`剪辑流程图.html` → `docs/剪辑流程图.html`。

**Acceptance criteria：**
- [x] 两文件到位，根目录不再存在
- [x] git 跟踪中的文件用 git mv 保历史；goals.json 落在 archive/ 根（不在 work_legacy 防护内），移动后 `git status` 确认其已被跟踪或显式接受 untracked 状态

**Verification：**
- [x] `pytest -q` 全绿；`git status` 无意外变更；commit

**Dependencies：** Task 0
**Files likely touched：** `goals.json`、`剪辑流程图.html`、`docs/剪辑流程图.html`
**Estimated scope：** XS

## Task 3：批次 B——work/ 根散文件

**Description：** 建 `archive/work_legacy/`；`_research.py`、`_research2.py`、7 个 `.log`（detect_20260722、extract_20260722、gen_review_v3、vlm_20260722、vlm_20260722_v2、vlm_events_round1、vlm_events_round2）、`file_inventory.json`、`pilot_inventory.txt` 移入。

**Acceptance criteria：**
- [x] 11 个文件全部到位，work/ 根无散落文件（实际 13 个：多收 2 个本会话一次性回放脚本，见 plan.md 附录）
- [x] `git status` 无 untracked 污染（验证 Task 1 防护生效）

**Verification：**
- [x] `pytest -q` 全绿；移动前后文件计数一致；commit（批次 B-D 两侧均在 gitignore 内，无跟踪变更，实际未产生 commit，见 plan.md 附录）

**Dependencies：** Task 1
**Files likely touched：** 上述 11 个文件（纯移动）
**Estimated scope：** S

## Task 4：批次 C——work/ 旧子目录

**Description：** `work/investigate_0006`、`work/label`、`work/pilot`、`work/review` → `archive/work_legacy/` 下同名子目录。

**Acceptance criteria：**
- [x] 4 个目录整体到位
- [x] 若 pytest 因 tests 引用旧路径失败，按"改测试引用到新位置"处理并记录（review01 已预判零影响，失败即异常需查清）

**Verification：**
- [x] `pytest -q` 全绿；commit

**Dependencies：** Task 3
**Files likely touched：** 4 个目录（纯移动）
**Estimated scope：** S

## Task 5：批次 D——测试素材中间产物

**Description：** `work/frames/` 下 15 个短名测试目录（0007/0011/0014/0020/0022/0030/0033/0040/0048/0062/0086/0102/0120/0128/0147）→ `archive/work_legacy/frames_test/`；`work/detect/` 下 14 个非 dji_mimo 的 mot_cache → `archive/work_legacy/detect_test/`。

**Acceptance criteria：**
- [x] 移动前 ls 核对 `archive/validate_2026-07-23/` 无覆盖冲突
- [x] dji_mimo_* 目录与缓存零变动（冻结清单核对）

**Verification：**
- [x] `pytest -q` 全绿；`git status` 无 untracked 污染；commit

**Dependencies：** Task 4
**Files likely touched：** 29 个目录/文件（纯移动）
**Estimated scope：** S

## Task 6：收尾

**Description：** 冒烟核对与文档同步。

**Acceptance criteria：**
- [x] 关键路径存在：`work/20260722/goals_batch3.json`、`work/20260722/review_batch3/events_index.json`、`work/frames/dji_mimo_*`（抽查 3 个）、`work/detect/dji_mimo_*_mot_cache.json`（抽查 3 个）
- [x] 冻结清单逐项核对零变动（roster 相关 / 素材 / work/20260722 / output）
- [x] AGENTS.md 若需补充 archive/work_legacy 说明则更新（走 spec-reviewer）
- [x] 移动清单回填 plan.md 附录

**Verification：**
- [x] 上述核对全过；commit

**Dependencies：** Task 5
**Files likely touched：** `docs/workspace-layout/plan.md`、可能 `AGENTS.md`
**Estimated scope：** XS
