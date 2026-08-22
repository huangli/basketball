# Todo: basketball-clip 实施任务清单

> 依据 plan.md（2026-08-22）。按依赖排序；每任务可在单次会话完成、改动 ≤5 文件、带验收与验证。

## SP 打包 spike（先行）

- [ ] SP-1 建 Python 3.10 干净 venv，装全量依赖
  - Acceptance: torch CPU/ultralytics/open_clip/cv2/fastapi/pyinstaller 全部装上，版本记录落盘
  - Verify: `pip list` 存档；`python -c "import torch, ultralytics, cv2, open_clip, fastapi"` 通过
  - Files: `packaging/spike/requirements-spike.txt`
- [ ] SP-2 PyInstaller 最小实包验证
  - Acceptance: 打出含 import 链（torch/ultralytics/cv2）的 exe，在无 Python 环境目录运行通过
  - Verify: 运行 exe 输出 OK；结论+踩坑写现工作区 `docs/basketball-clip/spike-report.md`（spike 先于新仓库存在，报告随四件套存档，结论摘进新仓 README/packaging 注释）
  - Files: `packaging/spike/hello.py`、`packaging/spike/hello.spec`

## A 仓库骨架 + 脱敏迁移

- [ ] A-1 新仓库骨架（空历史 git init，本地）
  - Acceptance: 目录结构按 spec；LICENSE(MIT)/.gitignore/pyproject.toml(打包元数据)/ruff.toml(target-version=py310) 就位
  - Verify: `git log` 仅初始提交；`ruff check` 配置生效
  - Files: `basketball-clip/` 根级 4 文件
- [ ] A-2a 迁移 scripts/（剔除 vlm_* 三脚本，逻辑零改动）
  - Acceptance: scripts/ 入新仓（无 vlm_filter/vlm_judge_events/vlm_trial_ark）；注释中私人字样脱敏
  - Verify: 关键词扫描 scripts/ 零命中（署名豁免除外）
  - Files: `basketball-clip/scripts/`（成批拷贝，逐文件过扫描）
- [ ] A-2b 迁移 tests/ 并脱敏（75 处私人字样 → 通用样例）
  - Acceptance: 立哥/半截篮/车百鼎/7897 等替换为 红队/20260801/测试员；行为等价
  - Verify: `pytest -q` 全绿；关键词扫描 tests/ 零命中
  - Files: `basketball-clip/tests/`（成批迁移 + 字样替换）
- [ ] A-3 README + 使用手册重写版 + 依赖许可声明
  - Acceptance: 中文 README（安装/使用/AGPL-LGPL 声明/English summary）；abdullahtarek 许可查实并记录结论
  - Verify: spec-reviewer 过审；许可结论写入 README 或首运下载改造立项
  - Files: `README.md`、`docs/使用手册.md`（新仓）

## B scripts 豁免改造（每类独立 commit）

- [ ] B-1 配置外置（代理/凭证 → 环境变量，缺省关闭）
  - Acceptance: `7897` 关键词全清；无代理环境跑聚类走直连
  - Verify: `pytest -q` 全绿 + 关键词扫描零命中
  - Files: `scripts/video.py`、`scripts/cluster_scorers.py`、`tests/` 对应用例
- [ ] B-2 队名可配置化
  - Acceptance: 队名会话级注入，无"半截篮"硬编码；CLI 行为兼容
  - Verify: 全绿 + CLI 回归对照（同输入同产物）
  - Files: `scripts/roster.py`、`scripts/gen_scorer_page.py`、`scripts/video.py`、对应测试
- [ ] B-3 crop_scorers 延迟导入 vlm（读号降级）
  - Acceptance: 顶层不再 import vlm_filter；--read-numbers 无凭证时显式报错；GUI/CLI 默认关闭
  - Verify: 全绿；无凭证机器跑 people 链路不炸
  - Files: `scripts/crop_scorers.py`、`scripts/video.py`、对应测试
- [ ] B-4 OSNet/torchreid 下线
  - Acceptance: cluster_scorers 仅 CLIP 后端；OSNet 用例剔除；依赖表去 torchreid
  - Verify: 全绿；`--model osnet_x1_0` 显式报错提示已下线
  - Files: `scripts/cluster_scorers.py`、`tests/test_cluster_scorers.py`、`pyproject.toml`

## C GUI

- [ ] C-1 runner 任务编排 + 进度协议
  - Acceptance: subprocess 调 scripts，logging 行→进度事件（SSE），状态落盘可续查；解析失败降级"运行中"
  - Verify: `tests/gui/test_runner.py` 全绿（成功/失败/中断三态）
  - Files: `gui/runner.py`、`tests/gui/test_runner.py`
- [ ] C-2 FastAPI 路由（REST + SSE + 静态托管）
  - Acceptance: 选目录/建场次/启动/查状态/取消接口齐；输入边界校验；确认页（标注/认人/照片）内嵌复用
  - Verify: `tests/gui/test_app.py` 全绿（TestClient）
  - Files: `gui/app.py`、`tests/gui/test_app.py`
- [ ] C-3 中文向导前端（选素材→设队名→检测→标注→认人→合集→照片）
  - Acceptance: 每步进度+失败友好提示；"导出诊断日志"按钮（随 D-1）
  - Verify: 浏览器自动化冒烟 2 条通过；小样片全流程手测走通存档截图
  - Files: `gui/static/index.html`、`gui/static/app.js`、`gui/static/style.css`

## D 售后配套

- [ ] D-1 诊断日志导出（版本+系统信息+后端日志 → zip）
  - Acceptance: zip 内容完整可解，无敏感路径外的私人信息
  - Verify: 测试断言 zip 条目；手测按钮产出
  - Files: `gui/diagnostics.py`、`tests/gui/test_diagnostics.py`
- [ ] D-2 issue 模板 + CONTRIBUTING.md
  - Acceptance: 中文 bug 模板引导附诊断 zip；贡献指南完整
  - Verify: push 后 GitHub 预览渲染正常（F 阶段验）
  - Files: `.github/ISSUE_TEMPLATE/bug_report.yml`、`CONTRIBUTING.md`

## E 打包与安装器（SP 通过后）

- [ ] E-1 PyInstaller spec 全量打包
  - Acceptance: 收齐 torch/ultralytics/open_clip 数据文件、ffmpeg(BtbN LGPL)+许可文本、双 YOLO、CLIP 权重
  - Verify: 打出的目录在无 Python 机器跑通 import + 小样片检测
  - Files: `packaging/basketball-clip.spec`、`packaging/fetch_assets.py`
- [ ] E-2 Inno Setup 安装器
  - Acceptance: 安装向导/桌面图标/卸载齐全；体积记录
  - Verify: 干净 Windows 环境安装 → 全流程小样片跑通（Success Criteria 4）
  - Files: `packaging/installer.iss`、`packaging/build_installer.py`

## F 发布（每步先问立哥）

- [ ] F-1 脱敏终审 + 建仓库 push
  - Acceptance: gitleaks + 关键词扫描零命中（署名豁免除外）；立哥过目后建公开仓库
  - Verify: 扫描报告存档；仓库首页立哥确认
  - Files: 无（操作类）
- [ ] F-2 Release v0.1.0 挂安装包
  - Acceptance: Release 页含安装包 + 中文更新说明
  - Verify: 从新下载链接安装验证一遍
  - Files: 无（操作类）
