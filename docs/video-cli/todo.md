# video.py 统一入口 CLI — todo

> 对应 spec.md / plan.md。完成一项勾一项。

- [x] Task 1：video.py 骨架（argparse 子命令、run_step、state 读写、resolve_rawdir、discover_batches、session_dir_or_die）
- [x] Task 2：jinqiu 子命令 + 单测（透传拼装、state 写入、dry-run 不写）
- [x] Task 3 前置：`gen_scorer_page.py --help` 等实跑核对参数名 + help 文本中的约束说明（同目录、互斥等）（已做 2026-08-11：参数全对；发现 --clusters 必须与 --scorers 同目录 → 改逐批聚类，见 spec）
- [x] Task 3：people 子命令 + 单测（三段链、定稿聚类参数、max-reads 缺省 =3×confirmed、roster-existing 两态、--skip-cluster）
- [x] Task 4：build 子命令 + 单测（尺寸三态、--all 展开、互斥、roster 缺失报错）
- [x] Task 5：ruff format/check + pytest 全绿（481 passed）；AGENTS.md 补一行入口指向；--help smoke
- [x] review01：spec 阶段两轮（2 阻断修订后通过）
- [x] review02：实现审查（0 阻断；便服跳过/dry-run 计数/WARNING 噪音 3 建议 + 3 测试缺口已修复）
