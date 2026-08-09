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

## 附录：实施记录（2026-08-09 回填）

### Task 0 前置检查结果

- 认人会话已结束：git log 见 roster/scorer 收官提交（298f05a 等），工作区无其未提交改动；立哥明确许可开工
- git 跟踪状态：根 `goals.json`、`剪辑流程图.html` 均被跟踪 → 用 git mv；work/ 全部内容本就在 .gitignore
- 引用 grep：`tests/test_build_highlight.py:28`、`tests/test_gen_review_clips.py:33` 的 `_PATH = "work/pilot/..."` 仅为错误消息标签字符串，从不读文件系统 → 移动零影响（pytest 实测证实）；docs 下引用均为历史记录性文字，不随移动改

### 移动清单（实际执行）

| 批次 | 内容 | 去向 | commit |
|---|---|---|---|
| 防护 | .gitignore 加 `archive/work_legacy/` + `*.pth` | — | e7a1985 |
| A | `goals.json`（空残留，version 3 空 goals）、`剪辑流程图.html` | `archive/goals_root_legacy.json`、`docs/剪辑流程图.html`（git mv 保历史） | a1e159e |
| B | work/ 根 13 散文件：`_research.py`、`_research2.py`、`dedup_replay_check.py`、`label_speedup_replay.py`、7 个 .log（detect/extract/gen_review_v3/vlm×2/vlm_events×2）、`file_inventory.json`、`pilot_inventory.txt` | `archive/work_legacy/` | 无跟踪变更（两侧均 gitignore），未产生 commit |
| C | `work/investigate_0006`、`work/label`、`work/pilot`、`work/review` | `archive/work_legacy/` 同名 | 同上 |
| D | `work/frames/` 15 个短名测试目录、`work/detect/` 14 个非 dji mot_cache | `archive/work_legacy/frames_test/`、`archive/work_legacy/detect_test/` | 同上 |

计划外新增项：批次 B 多收了 2 个本会话一次性回放脚本（todo 写于它们创建前）；
.gitignore 顺手补 `*.pth`（osnet 权重属"模型权重不入库"约定，原漏）。

### Task 6 冒烟结果

- 关键路径在位：work/20260722/goals_batch3.json、review_batch3/events_index.json、roster.json；frames/detect 的 dji_mimo 各 300 抽查首/中/尾 OK
- 冻结清单零变动：roster 两副本、素材 300 文件、work/20260722/、output/（4 场次目录 + 1 个 20260722_removed 目录）
- 每批后 pytest 全绿（终态 403 passed）；git status 无 untracked 污染
- 立哥授权"临时文件可删除"，仍按 spec 只移不删（archive/work_legacy 不碍事，
  要释放磁盘时整体删该目录即可，零关联风险）
