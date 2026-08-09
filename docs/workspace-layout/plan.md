# plan：工作区文件夹结构优化

## Overview

根目录与 `work/` 根的早期一次性产物分批迁入 `archive/work_legacy/`（只移不删），恢复"按场次组织"约定。一期不改任何 scripts 代码。分批执行，每批后 pytest 验证。

## Architecture Decisions

- **只移不删**：回滚 = 反向 mv，零数据风险
- **`archive/work_legacy/` 先入 .gitignore 再移动**：archive/ 本身是 git 跟踪区，不忽略会把十几万张帧图变成 untracked 污染 git status
- **一期不改脚本默认常量**：vlm_filter.py / gen_review_clips.py 等默认路径指向旧目录，但生产均参数注入；默认常量清理另立任务（涉及 tests 预期路径，改动面单独评估）
- **冻结清单绝对不动**：roster 相关（认人会话中）、原始素材、work/20260722/、dji_mimo 的 frames+detect 缓存、output/

## Task List

### Phase 1：前置与防护

- [ ] Task 0：前置检查（认人会话状态 / git 基线 / 补 grep）
- [ ] Task 1：.gitignore 加 `archive/work_legacy/` 并验证

### Phase 2：分批移动（每批独立 commit + pytest）

- [ ] Task 2：批次 A——根目录散文件
- [ ] Task 3：批次 B——work/ 根散文件
- [ ] Task 4：批次 C——work/ 旧子目录
- [ ] Task 5：批次 D——测试素材中间产物

### Checkpoint：每批后

- [ ] `pytest -q` 全绿；冻结清单零变动核对；失败即反向 mv 回滚

### Phase 3：收尾

- [ ] Task 6：关键路径冒烟 + AGENTS.md 同步检查 + 移动清单回填

## Risks and Mitigations

| 风险 | 影响 | 对策 |
|---|---|---|
| archive/ 非 gitignore 区，移入帧图污染 git | 高 | Task 1 先行，git check-ignore 验证后才动批次 B-D |
| 认人会话并发改 roster | 高 | 冻结清单；Task 0 确认会话状态，未结束则整体延后 |
| 隐藏路径引用（tests/docs） | 中 | Task 0 补 grep；发现引用随移动同步改（仅注释/文档级） |
| git mv 误用（未跟踪文件） | 低 | Task 0 用 git ls-files 判定跟踪状态 |

## Open Questions

- 根目录 `roster_20260722.json` 的最终处置（归档 or 删除）——待认人会话结束后与立哥确认，不在本期任务内
