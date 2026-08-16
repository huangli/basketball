# Spec: 读号默认开 + 确认页一键全收号码预填

> 2026-08-16 v1。来源：认人链路提效调研（车百鼎场次回测）P1 项，
> 调研实测数据归档于本目录 research.md。
> 目标：球衣有号场次的认人从"逐球看图点人"压到"进页点一次批量接受 + 第三步抽查"。

## Objective

现状痛点：

- `video people` 的 `--read-numbers` 默认关（`scripts/video.py:755`）。车百鼎整场
  未启用（三批均无 `number_cache.json`，`number_votes` 全 None）——"号码预填 →
  E 键接受"这条最准的机器预填通路没走；该场 roster 中带号 tag（黑24/对7/白1/
  黑9）覆盖 26/107 归属，本可大半免看。
- 确认页号码预填只能逐球按 E 接受（`gen_scorer_page.py:781-788` 按钮、
  `:895-898` 按键），122 球规模下带号球员也要逐球点一次。

本功能做两件小事（均为最小改动）：

1. **读号默认开**：`video people` 的 `--read-numbers` 改默认 True，新增
   `--no-read-numbers` 关闭；使用手册.html 同步写明适用前提（球衣有号场次）
   与 token 成本。
2. **一键全收号码预填**：确认页顶栏加「接受全部号码预填」按钮——对所有
   `prefill_tag` 非空且未 touched 的球批量写入 marks（**不标 touched**，保持
   "预填非终裁"语义，第三步逐球核对可翻检可改）。

成功 = 球衣有号场次，立哥打开确认页点一次按钮，带号且号码唯一的球全部预填
到位，只需第三步翻检；无号场次用 `--no-read-numbers`，零 token 零行为变化。

**非目标（明确排除，依据调研报告）**：

- P2 裁图"非人"守卫（酒瓶广告牌停链）——独立功能，另行立项
- P3 簇代表图多样性取样
- P4 照片库人脸 embedding——等立哥供照，非代码侧能推
- P5 机器侧提速——3 分钟/批不占人工瓶颈，不值当
- 跨批聚类继承预填——已证伪：用车百鼎三批缓存 embedding 实测，跨批
  complete@0.15 纯度 49.5%，一致簇继承与真值符合率 b2 2/29、b3 1/25，
  阈值收紧到 0.06 仍 2/6、0/1，不做

## 依据（为什么敢默认开 + 敢批量预填）

三重缓冲 + 实测：

1. **K3 读号忠实度实测 5/5 无幻觉**（`docs/scorer/spec.md` Open Questions 2，
   2026-08-08 批次 1 实测）。
2. **歧义不预填**：号码匹配到多个球员 → `prefill_tag` 置空、
   `prefill_note="ambiguous"`（`gen_scorer_page.py:1081-1110`
   `match_players_by_number` 唯一才命中、`:1432-1435` `build_entries` 写入），
   批量接受按 `prefill_tag` 非空过滤，天然跳过歧义球与 SKIP 球。
3. **预填非终裁**：批量写入不标 touched（touched 机制
   `gen_scorer_page.py:796-811`），第三步逐球核对照常翻检；球衣互换导致预填
   错的残余风险由"裁图在眼前 + 一键可改"兜底（经验教训 §3）。

成本已有闸：

- 单次运行新调用闸 `MAX_NUMBER_READS_PER_RUN=20`（`crop_scorers.py:131`）；
  `video people` 路径已自动放宽为 confirmed 球数 ×3（`MAX_READS_PER_GOAL`，
  `video.py:48`、`:357-364`）。
- 缓存键 = 裁图 md5，幂等不重复扣额度（`crop_scorers.py:487-628`
  `apply_number_reading`）；旧数据回填有跳票模式 `--numbers-cache-only`
  零新调用。
- K3 token 900s 临期重读与 401 重试为既有机制（`crop_scorers.py:394-471`
  `read_number`），本功能零改动。

## Tech Stack

无新依赖、无新 API、无 schema 变更。纯 CLI 参数默认值 + 确认页 JS。

## Commands

```powershell
$env:PYTHONIOENCODING="utf-8"
python -m ruff format scripts tests; python -m ruff check --fix scripts tests; python -m pytest -q

# 读号默认开（新行为；预算 = 该批 confirmed ×3 自动注入）
python scripts/video.py people --session 20260805_车百鼎 --batch 2
# 无号场次显式关闭，零 token
python scripts/video.py people --session 20260805_车百鼎 --batch 2 --no-read-numbers
# 页面 JS 语法检查：python 提取生成页 <script> 段落临时文件后 node --check tmp.js；
# 或生成实页后按 todo 手工清单目检
```

## 改动契约（写死）

### video.py（只允许动 people parser 的参数区）

- 新增 `--no-read-numbers`（`action="store_false"`, `dest="read_numbers"`）；
  保留既有 `--read-numbers`（`action="store_true"`，同一 dest）作显式开启的
  同义开关——老命令与手册示例不炸。**缺省 True 必须由两条 add_argument 之后
  显式 `pp.set_defaults(read_numbers=True)` 保证**：argparse 填默认值带
  hasattr 守卫、先注册者胜出，靠 add_argument 的 `default=True` 会被先注册的
  store_true（隐式 default False）压住、静默不生效（review01 B1，本机实证）；
  set_defaults 行内注释说明该语义。
- 预算口径说明：默认开后每批新调用预算 = confirmed×3（按场次实测，车百鼎
  三批 = 87/147/132 张），
  由 `build_people_steps` 既有逻辑自动注入 `--max-reads`；原 spec 的
  ">20 新调用须先问立哥"边界在 people 默认路径下等效预授权——本 spec 经
  立哥确认即视为授权此口径。`crop_scorers.py` 直跑（不经 video.py）仍受
  20 张闸，不变。
- **边界红线：另一 session 正在改 video.py 的 build 段与 build_highlight.py /
  goal_heatmap.py / docs/heatmap/，本功能只允许改 people parser 的
  add_argument 区域及 `build_people_steps` 相关注释行，其余一律不碰；提交前
  `git diff` 复核改动仅限上述行。使用手册.html 仅动 people/认人相关小节，
  build 小节不碰；tests/test_video.py 只新增 people parser 用例，不改既有
  build 用例。**

### gen_scorer_page.py（确认页）

- 顶栏加按钮 `#acceptall`「接受全部号码预填」（放 `#accept` 旁，初始即显示）。
- 点击行为（写死）：
  - 遍历 ITEMS：`it.prefill_tag` 非空 且 `!touched[it.key]` →
    `marks[it.key] = it.prefill_tag`；**不写 touched**（保持预填语义：
    簇级选人仍可覆盖、第三步可翻检）。
  - 歧义球（`prefill_tag` 为空、`prefill_note="ambiguous"`）与 SKIP 球
    天然不满足条件，不被动。
  - 完成后 `alert` 报"已接受 N 个号码预填（歧义 X / 已手改 Y 跳过）"——
    口径写死：X = `prefill_note="ambiguous"` 的球数，Y = `prefill_tag` 非空
    且 touched 的球数；`save()` + `show(cur)`。
- 只加按钮不加快捷键，不触碰既有键盘屏蔽规则（picker 弹条逻辑零改动）。
- 导出 roster 契约不变（`exportRoster` 读 marks 现状逻辑天然兼容）。

## Testing Strategy

pytest 纯函数/字符串级单测（不碰网络/真帧）：

- video.py：people parser 缺省 `read_numbers=True`；`--no-read-numbers` →
  False；显式 `--read-numbers` 仍 True；`build_people_steps` 默认 argv 含
  `--read-numbers` 且 `--max-reads = confirmed×3`，`--no-read-numbers` 时
  两者均不出现。
- gen_scorer_page.py：`_HTML` 含 `acceptall` 按钮与守卫条件（`prefill_tag`
  非空 + 未 touched）关键串断言（防改丢的轻量锁定）；既有
  `build_entries` 预填/歧义用例零回归。
- JS 侧：生成的实页过 `node --check`；手工清单（plan Checkpoint 2）覆盖
  四类球（号码预填 / 歧义 / SKIP / 已逐球手改）点一次按钮后的 marks 落位。

## Boundaries

- Always：质量门全绿再提交；批量接受不标 touched；歧义球永不批量接受；
  video.py diff 仅限 people parser 参数区
- Ask first：默认开路径实跑 token 超出 confirmed×3 预算的口径调整；
  roster schema 任何变更（本功能不涉及）
- Never：碰 video.py build 段 / build_highlight.py / goal_heatmap.py /
  docs/heatmap/（另一 session 在改）；改 `crop_scorers.py` 读号逻辑与
  投票规则；把批量接受做成页面加载自动执行（必须立哥手动点按钮，
  终裁在人）；API key 入文件或日志

## Success Criteria

1. ruff + pytest 全绿（含新增用例）
2. `video people` 不带读号参数实跑：日志显示 `--read-numbers` 生效、
   预算 = 该批 confirmed×3；`--no-read-numbers` 实跑零新调用
3. 实页手工验收：构造含号码预填/歧义/SKIP/已手改四类球的页面，点一次
   「接受全部号码预填」后仅第一类写入 marks，其余不动；导出 roster
   归属数与 confirmed 计数正确
4. 使用手册.html 已同步（读号默认开、适用前提、token 成本、新按钮说明）
5. 四件套齐全（review 由独立审查员另行产出）

## Open Questions

1. ~~无号场次识别~~（已收口为决策，review01 O2）：读号结果全 None 时打一行
   INFO"本场可能无号，下批可用 --no-read-numbers"，不加分支逻辑；手册写明
   "球衣有号才划算"。
2. `--read-numbers` 与 `--no-read-numbers` 同传时的 argparse 行为（后者
   覆盖前者，argparse 同 dest 后值胜出）——测试锁定，文档不展开。
