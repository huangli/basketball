# Plan: build 4K 输出（spec: docs/build-4k/spec.md v3）

## 组件与依赖

```
build_highlight.py --name-suffix（底层，无依赖，先做）
        ↓
video.py resolve_out_sizes 重构（尺寸分类单一来源）
        ↓
video.py per-filter 尺寸/后缀注入 + --4k 解析（依赖前两项）
        ↓
测试 → 实机验证 → 文档同步（AGENTS.md / 使用手册.html）→ 提交
```

## 步骤

1. **build_highlight.py 加 `--name-suffix`**
   - parse_argv（:100-143 手滚循环）加可选参数，默认 `""`
   - `select_goals` 返回的 out_stem 在尾部类型词前插入后缀：三条命名路径
     （:216 `队伍_{team}_进球集锦` / :231 `{team}_{display}_进球合集` /
     :242/:252/:255 `个人_*_进球合集`）统一在拼接处处理——
     最简做法：select_goals 返回后在 main（:598 附近）对 stem 做一次
     `"进球集锦" / "进球合集"` 前插，单点收口，不动真值表内部
   - 验收：`tests/test_build_highlight.py` 新用例 + 既有用例全绿（缺省逐字节一致）

2. **video.py `resolve_out_size` → `resolve_out_sizes`**
   - :398-447 重构：比例分类一次，返回 `(size_1080p, size_4k)`；
     混比例/未知比例的显式报错原样保留（:444-447 语义不丢）
   - 新增常量 `OUT4K_16_9 = "3840x2160"`、`OUT4K_4_3 = "2880x2160"`（:72-73 旁）
   - `OUR_TEAM = "半截篮"` 常量（:67-68 CASUAL_TEAM 旁）
   - 验收：既有 test_video 全绿（签名变化同步改调用点与相关测试）

3. **video.py `--4k` + per-filter 注入**
   - argparse（:1414-1422）：`bd.add_argument("--4k", dest="four_k", action="store_true")`
   - confirmed 路径（_cmd_build，:790-880）：现状 base 拼 `--out` 共用（:940）
     → 挪进 filter 循环，逐步骤定 `(out_size, name_suffix)`：
     - `("--team", OUR_TEAM)`：4K 原名，无后缀；若 args.four_k 则 INFO no-op 提示
     - 其余步骤：args.four_k → (4K 尺寸, `--name-suffix _4K`)，否则 (1080p, 无)
     - 每个 4K 步骤执行前 INFO 性能提示（D6）
   - 自动模式（_cmd_build_auto）：args.four_k → WARNING 忽略，行为不变
   - 验收：测试用例 1-9（spec Testing Strategy）

4. **关口**：`ruff format scripts tests && ruff check --fix scripts tests && pytest -q` 全绿
   （--fix 后复核 diff）

5. **实机验证**（20260822_citymonkey）
   - `video build --all` → ffprobe 核 `队伍_半截篮_进球集锦.mp4` = 3840×2160/50fps
   - `video build --scorer 黄立 --4k` → `半截篮_黄立_4K_进球合集.mp4` 出、1080p 版保留
   - `video build --team 半截篮 --4k` → 无 `队伍_半截篮_4K_*.mp4` 重复文件

6. **文档同步**：AGENTS.md 剪辑规格段 + 使用手册.html build 章节；
    docs/build-4k/ 文档过 spec-reviewer（agent-evaluator 代行）

7. **提交**：`feat: build 支持 4K 输出（半截篮集锦默认 4K + --4k 手动重出）`，不 push

## 风险与缓解

- **R1. resolve_out_sizes 签名变化波及现有调用/测试** → 先全量跑一遍 pytest 拿基线，
  改动后对比；grep 所有调用点一次改齐
- **R2. 后缀插入位置错配**（stem 末尾 vs 类型词前）→ 底层单点收口 + 测试锁死
  `队伍_X_4K_进球集锦` 字面断言
- **R3. --all --4k 半截篮重复文件** → D3 no-op 在 filter 循环内按值判定，
  测试 9 覆盖展开路径
- **R4. 4K 编码耗时** → 实机验证只跑 --team 半截篮 单点（21 球约 3~4 倍时长），
  不全量 --all 重出

## 并行/顺序

步骤 1 与 2 可并行（不同文件）；3 依赖 1+2；4-7 严格顺序。
