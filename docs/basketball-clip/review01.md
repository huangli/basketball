# Review 01: spec.md 初稿审查（2026-08-22）

> 审查员：spec-reviewer 角色子代理（只读审查）。结论：**需修订**。

## 阻断问题（必须改）

- **B1. "scripts 原样迁移、行为零改动"与脱敏改造自相矛盾。** 脱敏清单要求 video.py 代理硬编码改环境变量，但边界条款禁止修改 scripts 任何行为。必须划出"脱敏/配置化"豁免清单，否则实现阶段每行改动都撞边界。
- **B2. 脱敏清单严重低估泄露面。** 实证扫描：代理 `127.0.0.1:7897` 硬编码还有 `cluster_scorers.py:62`；"立哥"在 scripts/ 注释 30+ 处；"半截篮"硬编码于 `gen_scorer_page.py:61` `TEAM_WHITE` 及前端 JS；场次名"车百鼎/淳化"散见各脚本示例；`tests/` 含 75 处私人字样（清单完全没提 tests）；`resource/logo.png`、`docs/` 私人决策记录去留未交代。脱敏清单需升级为可执行扫描清单（关键词表 + 全文件类型覆盖）。
- **B3. Kimi 凭证依赖链未处置。** `vlm_filter.py` 硬编码 `~/.kimi-code/credentials/kimi-code.json`；读号功能依赖立哥个人订阅，普通用户必然不可用。需定案：(a) 已下线/试验脚本（vlm_filter/vlm_judge_events/vlm_trial_ark）剔除还是迁移；(b) 读号在开源版隐藏/禁用/报错。
- **B4. 队名"半截篮"硬编码是核心功能缺陷。** 面向普通用户必须队名可配置（会话级注入），GUI 向导需"输入队名"步骤；spec 全文未提。
- **B5. Open Questions 漏打包最大可行性风险：PyInstaller × Python 3.14。** PyInstaller 对新大版本支持历来滞后，3.14 + torch 2.13 组合无验证记录；需验证项 + 降级备选。另补：torchreid 0.2.5 老旧包兼容性，或 OSNet 后端在新仓库下线。

## 建议改进（可选）

- S1. "全历史扫描通过"落成具体口径（gitleaks + 关键词清单；新仓库空历史 init 写进成功标准）。
- S2. 体积拆分口径（torch/ffmpeg/双 YOLO/CLIP 各占多少）；ffmpeg 选项加"BtbN LGPL build"。
- S3. spec 点一句 runner 解析子进程日志的进度协议约定。
- S4. 前端加 1–2 条浏览器自动化冒烟（本机有 Chrome DevTools MCP）。
- S5. README 不写清华镜像本机约定，改"网络受限用户可选镜像"。
