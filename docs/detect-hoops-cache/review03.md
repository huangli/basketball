# review03：筐检测消重 实施终审

日期：2026-08-16　审查员：独立 spec-reviewer（只读审查 + 关口复验）
对象：`scripts/mot_candidates.py`、`scripts/detect_hoops.py`、`tests/test_detect_hoops.py`
未提交改动（git diff）及 plan/todo/AGENTS.md/主文档回填

## 整体评价

实施与 spec/review02 闭环后的契约**逐项一致**，量化口径、严格大于过滤、回退分支、
懒加载四个关键点全部落实到位且经本审查员独立复验（关口全绿 + NMS 源码核对 +
真实数据回退路径零差异抽查）。无阻断问题。**结论：通过。**

## 契约一致性核对（审查要点 1）

| 契约项 | 实施 | 结果 |
|---|---|---|
| 量化口径复刻 detect_hoop_frame（review01 B1） | mot_candidates.py detect_frame Hoop 分支：`int(v)` 截断取 xyxy、`(x1+x2)//2`、`float(b.conf[0])` 原始 conf 不截断，与 detect_hoop_frame（detect_hoops.py:169-170）逐字符同语义 | ✓ |
| 严格大于过滤（实施中新发现） | load_hoop_frames `if conf > CONF`；已核对 ultralytics 8.4.104 `utils/nms.py:81` 确为 `prediction[...] > conf_thres`（严格大于），引用行号属实 | ✓ |
| 回退分支（旧缓存/缺失/损坏/帧数不符/元素损坏） | 五类分支齐全，各记一行 INFO/WARNING；元素级校验排除 bool、捕获 KeyError/TypeError 整体回退，不半路崩（review01 建议 2） | ✓ |
| 懒加载 | main() `model = None`，首个回退分支内首次构造；缓存命中路径不触碰 YOLO（单测用 `_boom` 替身断言） | ✓ |
| 不改 track_hoop/interpolate_gaps/select_hoop/CONF/IMGSZ/schema | diff 确认零改动 | ✓ |
| 不碰并行 session 文件 | diff 确认未触碰 build_highlight/goal_heatmap/video.py/docs/heatmap//test_goal_heatmap | ✓ |
| load_detection_cache 不校验 hoops、旧缓存仍命中 | diff 确认仅加 docstring 说明，校验逻辑原样 | ✓ |

## 独立复验（不只采信实施方自报）

- **关口三连（本审查员实跑）**：`ruff format --check` 47 文件已格式化、`ruff check` 全过、
  `pytest` **677 passed**（其中 test_detect_hoops **11 passed** = 7 旧 + 4 新，与宣称一致）。
- **回退路径真实数据抽查**：用现行旧缓存（无 hoops 键）对 fid 0001 实跑
  `detect_hoops.py --limit 1`，日志正确选路"旧缓存无 hoops 键，逐帧补检"，
  产出事件（24 点轨迹）与封存 `hoops_batch1.json` 对应条目 **key/window/anchor/detected/track 完全一致**；
  验证产物已清理。此抽验同时证明重构后的 main() 事件循环未引入回归。
- **现场状态**：work/detect 148 个缓存完整、无 bak 残留、work/diag 已清理，符合车百鼎封存口径。
- 缓存命中路径的零差异重放（0001/0002/0035，8 事件）为实施方自报，产物按 plan Step 4
  清理未留档；由单测（边界过滤/选路）+ 上述回退抽查 + NMS 源码级等价论证共同兜底，可接受。

## 代码质量（审查要点 2，对照 rules.md）

无问题。新代码类型注解齐全、捕获具体异常（OSError/JSONDecodeError/KeyError/TypeError）、
日志分级正确且含 fid 上下文、docstring Google 风格、无模块级副作用（模型懒加载后
detect_hoops 连 YOLO 构造都不发生）。

## 建议改进（不阻塞，下次顺手修）

1. **spec.md 未随实施同步**（review02 建议 1 遗留 + 新口径）：spec.md:94 风险表仍写
  "conf 为 NMS 后过滤"（与 §功能 3 矛盾，review02 已指）；此外 §功能 2/3 的"≥0.25 过滤"
  表述未按实施发现的严格大于口径更新（plan/todo 已改，spec 未改）。等价结论不变，
  但 spec 作为契约源头应与实施口径一致。
2. **load_hoop_frames 日志小瑕疵**：payload 非 dict 时也记"缓存帧数不符"，措辞不准
  （实际结构损坏）。INFO 级、不影响选路正确性。
3. **todo.md Task 4 fid 简写**："0001/0002/0035" 为后缀简写，plan 已明确 fid 取
  `events[].fid` 完整原值，todo 此处简写无碍执行，仅备注。

## 文档回填一致性（审查要点 3）

- plan.md Step 3 边界口径已同步修订（0.25 恰等被滤/0.26 保留，与代码 `conf > CONF` 一致）✓
- todo.md 勾选属实：Task 1-4 各项均有 diff/测试/关口证据支撑；Task 5 未勾项
  （spec-reviewer 审查、commit）确为在途事项，未虚报 ✓
- review02 建议 2（reviewNN 编号）已在 plan/todo 落实 ✓
- AGENTS.md 与主文档 §2 各一句同步，措辞与实施行为一致（缓存优先、旧缓存回退）✓

## 与 AGENTS.md 冲突对照表

无冲突。文档自审要求（docs/AGENTS.md 改动须 spec-reviewer 审查）由本报告履行；
commit 尚未执行，符合"审查通过后再提交"的顺序。

## 结论

**通过**。四个关键契约点全部落实并独立复验，关口 677 用例全绿，回退路径真实数据
零差异。建议改进 3 条均为文档级瑕疵，可并入 Task 5 收尾顺手修订，无需复审轮次。
