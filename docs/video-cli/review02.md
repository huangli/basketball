# video.py 统一入口 CLI — review02（实现阶段）

> 审查对象：scripts/video.py（612 行）、tests/test_video.py、AGENTS.md 指针行。审查者：python-reviewer 子代理。2026-08-11。

## 首轮结论：通过（0 阻断；3 建议 + 3 测试缺口全部本轮修复）

**spec 保真核验**：三条命令链逐字比对底层脚本 --help/parse_argv 全部吻合；44 测试全绿、全仓不回归、ruff 双干净；AGENTS.md 指针行逐项属实。

**建议改进（已全部修复）**：
1. **--all 展开跳过「便服」队**（原 video.py:486-490）：build_highlight 明文 `--team 便服` 退出 1，roster 含便服是常态（20260722 便服 8 球），不跳会在便服处中断后续所有合集 → 新增 `CASUAL_TEAM` 常量跳过 + WARNING（个人合集照出），口径已回写 spec.md build 节；新增 `test_all_skips_casual_team`
2. **dry-run 完成计数恒 0**（误导日志）→ 加 dry_count，结尾打「DRY-RUN 共 N 步（未执行）」
3. **events_index 缺失 WARNING 对 build 是噪音** → 检查从 discover_batches 迁入 _cmd_people，build 不再收到确认页相关 WARNING

**测试缺口（已补）**：a) `test_env_https_proxy_only_on_cluster_step` 锁定「HTTPS_PROXY 仅聚类段叠加」；b) build 侧 `--batch K` 限定单批用例；c) 4:3 容差内用例（2860x2160→1440x1080）。

**记录在案不处理（INFO）**：
- jinqiu 失败不写 runs（spec 主句字面支持；失败现场靠日志，可接受）
- load_state 不校验 state.session 与路径场次一致性（路径派生场景几乎不触发，纯防御项）

## 修复后关口

`ruff format` / `ruff check` 双干净；`pytest -q` 全量 **481 passed**（tests/test_video.py 48 个）。

**结论：通过，可交付。**
