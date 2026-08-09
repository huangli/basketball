# todo：工作区文件夹结构优化

- [ ] 0. 前置：确认认人会话状态；git 基线记录；补 grep tests/ + docs/
- [ ] 1. 批次 A：根目录 goals.json → archive/（改名）、剪辑流程图.html → docs/；pytest 全绿
- [ ] 2. 批次 B：`.gitignore` 先加 `archive/work_legacy/` 并 git check-ignore 验证；work/ 根散文件（2 探索脚本 + 7 日志 + 2 清单）→ archive/work_legacy/；pytest 全绿
- [ ] 3. 批次 C：work/ 旧子目录（investigate_0006/label/pilot/review）→ archive/work_legacy/；pytest 全绿
- [ ] 4. 批次 D：测试 frames（15 目录）+ 旧 detect 缓存 → archive/work_legacy/；pytest 全绿
- [ ] 5. 批次 E：关键路径冒烟核对；AGENTS.md 如需更新走 spec-reviewer
- [ ] 6. 每批次独立 commit；移动清单附录回填 plan.md
- [ ] 7. 冻结清单逐项核对零变动（roster 相关 / 素材 / work/20260722 / dji_mimo frames+detect / output）
