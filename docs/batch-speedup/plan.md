# plan：跑批提效（缩略图墙扫尾 + 一键跑批）

> **注意（2026-08-11）**：F1（gen_triage_page.py / sec_to_frame_idx）已下线
> 并删除，本文 F1 相关步骤为历史存档勿再执行；F2（run_session.py）现役。
> 见 review07.md。

依据 `docs/batch-speedup/spec.md`（review01-02 通过版）。
新脚本 ×2（`gen_triage_page.py`、`run_session.py`）+ 公共函数 ×1 +
测试 ×2；**不改 5 个老流水线脚本**。

## 步骤

### Step 0：帧号映射公共函数（先行，F1 依赖）

- `scripts/pipe_common.py` 加 `sec_to_frame_idx(sec: float, fps: float) -> int`
  （`round(sec × fps) + 1`，docstring 注明与 mot_candidates.parse_sec
  互逆、f_00001 ↔ t=0）；fps 参数默认引 `mot_candidates.SAMPLE_FPS`
  ——注意循环导入：pipe_common 被 mot_candidates 引用，故只能
  pipe_common 内复制常量值 5.0 并注释对齐，或函数要求显式传 fps。
  实施时选后者（显式传参，零耦合）
- `tests/test_pipe_common.py` 加映射用例（0s→1、6.1s→31、0.1s 舍入）
- 关口：ruff + pytest

### Step 1：F1 缩略图生成（gen_triage_page.py 前半）

- 读 events_index.json → 每事件算 3 帧号（±2，钳位 [1, 帧数]）→
  PIL 缩 480px 宽存 `<review_dir>/thumbs/t_<safekey>_<i>.jpg`
  （key 含 `#`/`@`，文件名安全化）
- 缺 fid/anchor_t0/key → WARNING 跳过；帧文件缺失 → 降级用可用帧 +
  WARNING，结尾汇总降级清单
- CLI：`--index <events_index.json> [--session <场次>]`（session 推导与
  gen_label_page 同款条件：父目录名，父目录以 review 开头时上溯祖父；
  编排器显式传）
- 单测：帧号钳位、缺帧降级、文件名安全化
- 关口：ruff + pytest

### Step 2：F1 triage.html 生成 + localStorage 联动

- 模板同 gen_label_page 的 raw string 纪律（黑屏教训）；注入事件数组
  （含 grp 组标签，复用 assign_same_rally_groups）
- JS 硬规定落实：渲染/点击以 localStorage 实时值为准；已标事件展示
  标注 + F 按钮禁用；save 复刻合并写（重读 + Object.assign）；不写位置键
- 回归断言：html 含合并写代码、含禁用逻辑、不含 POSKEY 写；
  `node --check` 通过
- 批次 3 回放生成：234 事件全产、51 球 3 帧全到位或降级清单零意外
- 关口：ruff + pytest + node --check

### Step 3：F2 run_session.py 编排器

- 阶段 ①-⑦ 按 spec；subprocess 调老脚本（显式传参清单见 spec），
  逐阶段产物校验（JSON 可读 + 关键字段）；session_facts.json 落盘 + 比对
- --batch-size 50 默认切批（fid 文件名排序）；--fids → adhoc 固定命名；
  --dry-run 只打印；--force 强制重算；日志 work/<session>/run_session.log
- 单测：批次切分、产物校验器（好/坏/截断 JSON）、facts 比对
  （一致/不一致/缺失）、dry-run 命令清单含 --keep-clips 与全部显式参数
- 关口：ruff + pytest

### Step 4：端到端验证（spec 成功标准 1-4）

- dry-run 对 20260722 素材出 6 批命令清单 → 人工对照历史命令
- 续跑断言：缓存齐时单批 ②③ < 30s（日志时间戳）
- --fids 3 个 dji 缓存文件小样本端到端 → adhoc 全套产物
- 故障注入：篡改 session_facts.json → 终止；截断 candidates → 重算或终止

### Step 5：文档与提交

- 回填 todo；spec-reviewer 实施复审写 review03.md（review01/02 = spec 两轮）
- commit（只 add 本功能文件）

## 依赖与顺序

Step 0 → 1 → 2（F1）与 Step 3（F2）可并行，但单会话顺序做：0→1→2→3→4→5。
每 Step 一个 commit 单元。

## 验收关口

- [ ] ruff format / check --fix / pytest -q 全绿
- [ ] node --check 两个生成页语法通过
- [ ] spec 成功标准 F1 1-4 / F2 1-5 逐条过
- [ ] 立哥验收：批次 3 墙扫尾体验 + dry-run 命令等价性
