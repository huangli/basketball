# plan：工作区文件夹结构优化

## 前置检查

1. 确认认人会话已结束（或拿到立哥明确许可）；未结束则冻结清单相关项延后
2. `git status` 记录基线；`git ls-files` 确认 `goals.json`、`剪辑流程图.html` 是否在 git 跟踪中（在则用 `git mv`，不在则普通移动）
3. 补 grep：`tests/`、`docs/` 下对 `work/label`、`work/pilot`、`work/review`、`work/investigate`、`goals.json`（根目录）的引用

## 执行（分批，每批后跑测试）

**批次 A：根目录**
- `goals.json`（空残留）→ `archive/goals_root_legacy.json`（改名防与场次 goals 混淆）
- `剪辑流程图.html` → `docs/剪辑流程图.html`
- 跑 `pytest -q`

**批次 B：work/ 根散文件**
- **前置（防翻车）**：先把 `archive/work_legacy/` 追加进 `.gitignore`，`git check-ignore archive/work_legacy/x` 验证生效——archive/ 本身是 git 跟踪区，不忽略会污染 git status（spec 风险节已载）
- 建 `archive/work_legacy/`
- `_research.py`、`_research2.py`、7 个 `.log`、`file_inventory.json`、`pilot_inventory.txt` → `archive/work_legacy/`
- 跑 `pytest -q`

**批次 C：work/ 旧子目录**
- `work/investigate_0006` → `archive/work_legacy/investigate_0006`
- `work/label` → `archive/work_legacy/label`
- `work/pilot` → `archive/work_legacy/pilot`
- `work/review` → `archive/work_legacy/review`
- 跑 `pytest -q`（若 tests 引用这些路径导致失败，按"改测试引用到新位置"处理并记录）

**批次 D：测试素材中间产物**
- `work/frames/` 下 15 个短名测试目录 → `archive/work_legacy/frames_test/`
- `work/detect/` 下非 dji_mimo 的 mot_cache → `archive/work_legacy/detect_test/`
- 注意：`archive/validate_2026-07-23/` 与这些可能有交集，移动前 ls 核对不覆盖
- 跑 `pytest -q`

**批次 E：收尾**
- 冒烟：核对 `work/20260722/goals_batch3.json`、`work/20260722/review_batch3/events_index.json` 等关键路径存在
- AGENTS.md 检查：若"中间产物放 work\"约定表述需补充 archive/work_legacy 说明则更新（走 spec-reviewer）
- commit（每批次 A–D 独立 commit，批次 E 文档单独 commit）

## 回滚

所有操作为 `mv`（无删除），回滚 = 反向 mv。每批 commit 前记录移动清单到本 plan 附录。

## 明确不做

- 不改 scripts/ 任何代码（默认常量清理另立任务）
- 不动冻结清单任何一项
- 不删除任何文件（只移动）
