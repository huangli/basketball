# spec：跑批提效（缩略图墙扫尾 + 一键跑批）

日期：2026-08-10　状态：待审（review01 修订版）　提出：立哥选型"1+2 打包"（2026-08-09 会话）

## 背景与目标

批次 3 数字链：151 视频 → 913 候选 → 234 事件 → 人工判 61 J → 51 球。
dedup + label-speedup 已把标注侧砍一刀（同组跳过 + 有效 2x）。剩余两个痛点：

1. **尾部垃圾事件仍需逐条放视频**：事件已按筐距排序，尾部大量"没筐没投篮"
   的候选，放视频才能否掉，浪费立哥时间；
2. **跑批靠手工串联 5 条命令**：extract_frames → mot_candidates →
   pilot_candidates → detect_hoops → gen_review_clips → gen_label_page，
   参数（素材目录、场次 ID、--orig 尺寸、批次切分、--hoops、--keep-clips）
   全靠记忆，新场次开场成本高、易错。

目标：新场次（批次 4 起）标注前准备一键完成，人工标注量再降 30~40%。
两个子功能互独立，但都服务于"新场次跑批"，打包一个 spec。

## F1：缩略图墙扫尾（新脚本 scripts/gen_triage_page.py）

**功能**：在人工视频标注之前，先给全部事件出一页"缩略图墙"：

- 输入：`events_index.json`（事件顺序 = 筐距序，与 label.html 一致）+
  `work/frames/<fid>/f_%05d.jpg`（5fps、1920 宽，已存在，零新计算）
- 帧号映射：`帧号 = round(anchor_t0 × SAMPLE_FPS) + 1`（SAMPLE_FPS=5.0，
  与 mot_candidates.parse_sec 的 `sec=(idx-1)/5` 互为反函数，f_00001 ↔ t=0；
  **该映射做单点公共函数**，新脚本不另写魔数 5）。每事件取该帧及其 ±2 帧
  （±0.4s；钳位到 [1, 帧数]；缺帧降级为可用帧并记 WARNING，不崩；
  anchor_t0 按 0.1s 存储的 ±1 帧舍入误差在 ±2 帧窗口内可吸收）
- 用 PIL 生成缩略图落 `<review_dir>/thumbs/`：**默认筐区裁剪**——`--hoops`
  传入 detect_hoops 产物后，以事件锚点（筐/球静止点，帧图像素坐标）为中心
  裁帧宽 40% 的 16:9 窗口、640px 落盘（2026-08-11 批次 3 实测：全景 480px
  缩略图球仅几像素无法判读，筐区裁剪后入网瞬间清晰可辨，验收反馈修复）；
  锚点缺失事件降级全景 480px（等比不裁不切）并记降级清单；不传 --hoops
  整页全景降级
- 生成 `triage.html` 网格墙：**卡片主区域 = 悬停播放的审核片段**
  （events_index 的 clip，640px 宽 2x 慢放已烘焙，`preload="none"` +
  poster=锚点帧缩略图，mouseenter 播放 / mouseleave 停并回开头；
  2026-08-11 立哥验收反馈"静态图判不了进网还是弹出"，视频墙才可判；
  clip 缺失事件降级纯静态卡片并记降级清单）+ ±0.4s 两帧小图参考 +
  事件信息（key、
  anchor_t0、src_file、疑似同回合组标签复用 assign_same_rally_groups；
  缺 fid/anchor_t0/key 的残次事件跳过 + WARNING + 结尾汇总，与
  assign_same_rally_groups 同款口径）
- 交互与写盘纪律（召回红线，三条都是硬规定）：
  1. **墙只能否、不能是**——缩略图看不清入网瞬间，判"是"必须去
     label.html 放视频；
  2. **墙不得覆盖已有标注**——渲染与点击均以 localStorage 实时值为准，
     已标事件（无论 goal/practice/no）展示其标注且 F 按钮禁用，
     只允许对未标事件写 `{r:"no"}`；
  3. **合并写语义复刻 label.html**——每次保存前先重读 LSKEY、
     `Object.assign(stored, marks)` 再写（防止与 label.html 同时开
     互相覆盖）；**绝不写 `LSKEY_pos` 位置键**（墙没有位置概念，
     写了会破坏 label.html 的断点续标）
- 与 label.html 共享 localStorage：同 LSKEY（`label_<session>`）、
  同 marks 结构；墙里标 F 的事件 label.html 侧自动视为已标并跳过
- 生成时机：gen_review_clips 之后、人工标注之前（F2 编排自动衔接，
  也可手工单独跑）

**边界（不做）**：不替代 label.html；不提供 J/P 判定；不做自动否
（机器只排版，判定全在人）；跨文件帧缺失不补抽（留 WARNING 让人去视频判）。

**成功标准**：

1. 批次 3 回放生成：234 事件缩略图 100% 生成成功（缺帧走记录在案的
   降级，降级清单零意外——注意大疆尾截短特性：37/51 球入网后 <2s，
   锚点距片尾 <0.4s 时 +2 帧物理不存在，属合法降级）；
2. 帧时间对准抽查：随机 10 事件，缩略图中帧与"原片 anchor_t0 ±0.4s"
   内容一致（人工核）；
3. 联动断言：墙标 F → label.html 同 key 显示已标"不是"且自动跳过；
   label.html 已标事件 → 墙侧可见标注且 F 按钮禁用（回归断言 + 立哥实操）；
4. 立哥验收：批次 3 墙上扫尾部，确认"敢直接否"的体验成立。

## F2：一键跑批（新脚本 scripts/run_session.py）

**功能**：`python scripts/run_session.py <素材目录> --session <场次ID>
[--batch-size N] [--fids 清单] [--force] [--dry-run]`

- **① 探测**：ffprobe 扫描素材目录（递归）：文件数、分辨率、帧率；
  混合分辨率/混合帧率 → WARNING 列明细并终止（规格要求按比例分别处理，
  不瞎猜）；场次事实表（文件数/各文件分辨率/帧率/时长）**落盘
  `work/<session>/session_facts.json`**——续跑时重探测比对，不一致即
  WARNING 并终止（`--force` 除外），这就是"尺寸不匹配"的检测基准
- **② 抽帧**：extract_frames.py。注意其粒度是"目录 + --limit"，无 fid
  过滤——实际行为 = 首批即全场抽、后续批次靠其内部帧计数校验幂等跳过，
  编排器如实呈现该行为，不假装能按批抽
- **③ 检测**：mot_candidates.py 按本批 fid 清单传位置参数（必须显式传，
  其默认是旧测试 fid）；mot_cache 逐文件落盘，天然断点续跑
- **④ 候选**：pilot_candidates.py --out work/<session>/candidates_batchK.json
  （必须显式 --out，其默认 work/pilot/ 是旧路径）；产出后核对
  **candidates 的 fid 覆盖数 == 本批 fid 数**（该脚本对无缓存 fid 只
  WARNING 产空，覆盖不足即汇总进失败清单）
- **⑤ 筐轨迹**：detect_hoops.py --candidates candidates_batchK.json
  --out hoops_batchK.json（两参数均无默认，缺参直接报错）
- **⑥ 审核片段**：gen_review_clips.py --candidates/--outdir/--srcdir/
  --orig（按①探测注入）/--hoops/**--keep-clips**（漏了它就不产
  events_index.json 与单事件 clips，下游全部断粮——历史命令均带）
  → work/<session>/review_batchK/
- **⑦ 标注页**：gen_label_page.py + F1 的 gen_triage_page.py，
  两者都显式传 --index/--session（不靠父目录名推导）；同场次多批次
  共享同一 `label_<session>` LSKEY 是既有行为（事件 key 跨批唯一，无害）
- **批次切分**：fid 按文件名排序（= 拍摄时间序），--batch-size（默认 50）
  自动切批，批次序号 K 从 1 递增；--fids 显式指定时产物用固定名
  `candidates_adhoc.json` / `hoops_adhoc.json` / `review_adhoc/`，
  不占批次序号、不覆盖历史批次产物
- **断点续跑**：每阶段产物存在且校验通过即跳过（校验 = JSON 可读 +
  关键字段齐全，防"存在但损坏"）；--force 强制重算
- **鲁棒（rules.md）**：单文件失败记 WARNING 继续，结尾汇总失败清单
  非零退出；ffprobe 探测失败立即终止（不猜尺寸）；日志落
  work/<session>/run_session.log
- **--dry-run**：只打印将执行的各阶段命令与批次划分，不执行

**边界（不做）**：不跑 VLM（已下线）；不自动导出 goals.json；不认人、
不合集（后续环节照现有人工流程）；不改 5 个老脚本的默认常量
（编排器全部显式传参绕过）。

**成功标准**：

1. --dry-run：对 20260722 素材输出 6 批 × 7 阶段的完整命令清单，
   与批次 1-3 历史手工命令等价（含 --keep-clips，对照主文档 §4 口径人工核）；
2. 续跑断言（机检口径）：frames/detect 缓存已存在时，对同一批
   （≤50 文件）续跑，阶段 ②③ 起止日志时间戳差 < 30s（②的 ffprobe
   逐文件探测串行开销计入，Windows 上 300 文件全量探测本身就可能 >10s）；
3. 小样本端到端：--fids 指定 3 个已有缓存的 dji 文件，产出
   candidates/hoops/review/双页面全套（adhoc 命名），结构与批次 3 一致；
4. 故障注入：篡改 session_facts.json 后续跑 → WARNING 并终止；
   candidates JSON 截断 → 重算或报错终止，不带着坏产物往下跑；
5. 关口：ruff + pytest 全绿；立哥用 --dry-run 验收命令等价性。

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 墙上误否真球（缩略图误判） | 中 | 墙只能否不能是；已标事件 F 按钮禁用；3 帧给上下文；拿不准不标；组标签提示同回合 |
| 墙与 label.html 同时开互相覆盖标注 | 中 | 合并写语义复刻 + 不写位置键（F1 硬规定 2/3） |
| 阶段⑥漏 --keep-clips 断链 | 高 | 已写进阶段清单并加粗；--dry-run 对照历史命令可审计 |
| 帧号↔时间映射错位 | 低 | 映射单点公共函数；±2 帧窗口吸收 0.1s 舍入；成功标准 2 人工抽查 |
| 混合比例素材进同批 | 中 | 阶段①探测即终止 + session_facts.json 落盘比对 |
| 编排器掩盖老脚本默认常量问题 | 低 | 全部显式传参；--dry-run 可审计 |
