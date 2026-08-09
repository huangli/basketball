# Todo: 进球人识别（plan: docs/scorer/plan.md）

- [x] T1: scripts/roster.py 契约模块 + tests/test_roster.py
  - Acceptance: roster schema 校验（缺 players/tag 重复/team 非法/键格式错 → SchemaError）；
    format_key 双端一致（4.1234→"4.1"）；fid_of 去扩展名；resolve_scorer 命中 tag 或 name
  - Verify: pytest tests/test_roster.py 全绿
  - Files: scripts/roster.py, tests/test_roster.py（S）

- [x] T2: scripts/crop_scorers.py 投篮者定位 + 裁图 + tests（**口径已被 T2b 轨迹法替换**）
  - Acceptance: 合成 mot_cache 下 IoU 链关联正确、投票众数胜出、并列取更近；
    有效票 <2 → SKIP（含 anchor<1.5s）；裁图外扩 20%、短边 ≥400px；
    CLI（--goals/--detectdir/--framesdir/--out）产出 crops + scorer_candidates.json
  - Verify: pytest 全绿；批次 1 goals.json 实跑 17 球出图无炸
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py（M）

- [x] T3: 颜色分队 + 批次 1 实跑验收
  - Acceptance: 采样区=水平中 60%×垂直 25~60%；HSV 双阈三分类、近阈归便服；
    阈值按 17 张实裁图标定并注释来源；scorer_candidates.json 含 team_guess 字段
  - Verify: pytest 全绿；立哥抽查 ≥3 张裁图是投篮者、颜色分布合理（Checkpoint 1）
  - Files: scripts/crop_scorers.py, tests/test_crop_scorers.py（M）

- [x] T4: scripts/gen_scorer_page.py 认人确认页 + tests
  - Acceptance: 每球显示片段+裁图+预填（颜色/号码）；球员按钮（--players）或
    自由文本（无名单）；SKIP 球标"无法定位"仍可手选；导出 roster.json
    （format_key 用 roster.py，默认输出 <scorer_candidates.json 同目录>/scorer.html）；
    --roster-existing 并集合并、同键冲突退出 1；进度存 localStorage
  - Verify: pytest 全绿；页面可开、可导出、build_highlight 能读导出物
  - Files: scripts/gen_scorer_page.py, tests/test_gen_scorer_page.py（M）

- [x] T4b（2026-08-08 立哥验收返修）：确认页视频改为按进球锚点现切的预览片段
  - 背景：原引用 events_index 事件片段（覆盖长事件全程，开头是另一回合），
    与裁图（投篮者，锚点前窗口定位）人/时刻对不上；人工改锚的 3 球（0544/1508/1948）
    与事件旧锚点差 >4s 连匹配都失败
  - Acceptance: crop_scorers 加 --rawdir，逐 confirmed 球（含 SKIP）切
    [max(0,anchor−4), anchor+2] 预览片段（1280 宽 crf26 veryfast 无声）到
    <out>/clips/，clip 相对路径写入 scorer_candidates.json，切片失败记 ERROR
    不炸整批；gen_scorer_page 视频优先级 = candidates clip ＞ events clip_wide 兜底
  - Verify: pytest 全绿；批次 1 重跑 17 球片段齐；ffprobe 抽查时长/宽度/无音轨
  - Files: scripts/crop_scorers.py, scripts/gen_scorer_page.py,
    tests/test_crop_scorers.py, tests/test_gen_scorer_page.py（S）

- [x] T2b（2026-08-08 立哥验收返修）：轨迹法定位投篮者（替换逐帧投票）
  - 背景：逐帧取 max-conf 球做"最近人框"投票，在海报球/隔壁场球间瞬移
    （实测 0.2s 跳 800px），裁出筐下防守人/路人；MOT 轨迹本身可靠
  - Acceptance: 窗口 [anchor−4.0, anchor+0.5] 内 run_mot 重链（min_length=1，
    mot_candidates.run_mot 加默认参数兼容）；端点距候选锚点（--candidates 的
    t0/cx/cy，批次 1 全部 dt=0 匹配）最近者为进球轨迹（>200px → SKIP）；
    从末端回放找最后一个球心严格落在人框内的点=投篮者；整轨无持球点 →
    轨迹起点最近人框；无轨迹 → SKIP；预览片段逻辑不变
  - Verify: pytest 全绿（233）；批次 1 重跑 OK=17 SKIP=0；17 张裁图逐张目检
    （明确对 4 / 勉强 10 / 可疑 1 / 错 2：1056 裁了防守人、2102 裁了场边路人——
    候选锚点本身落在防守人身上的 case 轨迹法也救不回，确认页人工终裁兜底）
  - Files: scripts/crop_scorers.py, scripts/mot_candidates.py（run_mot 加
    min_length 默认参数）, tests/test_crop_scorers.py（M）

- [x] T5: build_highlight.py 真值表改造 + tests
  - Acceptance: 分支全实现（①无 roster 无过滤=全员现状不变；②无 roster 给 --scorer=
    goals.scorer 精确匹配+0 命中 WARNING；③有 roster 无过滤=全归属球（未归属 WARNING 跳过）；
    ④--scorer 解析 tag|name、输出名用解析后 tag；⑤--team 出 队伍_{team}_进球集锦.mp4；
    ⑥--scorer+--team 互斥退出 1；⑦无 roster 给 --team 退出 1；
    ⑧--team 便服 退出 1；--roster 未 confirmed=true 拒收退出 1）
  - Verify: pytest 全绿（分支逐一覆盖）；git status 无 gen_review_clips/gen_label_page
    改动、无 work/20260722/review_batch2/ 写入（Checkpoint 2）
  - Files: scripts/build_highlight.py, tests/test_build_highlight.py（M）

- [x] T6: 批次 1 端到端试点（2026-08-08 完成）
  - Acceptance: 17 球裁图→确认页→立哥确认导出 roster.json→--scorer/--team 出合集；
    合集进球数与归属数一致；SKIP 未归属 WARNING 不阻塞
  - Verify: 立哥验收个人+分队合集（Checkpoint 3）；两轮 roster 修正
    （黑21 拆分 大斌/王敏龙、白22 并入小朱、0544 改归蓝色27）后重出验收
  - Files: 无新代码（work/20260722/scorers/、roster.json、output/20260722/）

- [x] T7: 号码识别试点（2026-08-08 立哥拍板启用，K3 非豆包——豆包余额可能不足）
  - Acceptance: --read-numbers 走 number_cache.json 幂等；≤20 次新调用/轮；
    K3 读裁图背号+颜色+背后名字（严格 JSON）；scorer_candidates.json 每条加
    number_guess；确认页预填 号码匹配>颜色、同号多人标"号码歧义"不预填；
    预填准确率告知立哥
  - Verify: 缓存命中不重复扣额度；17 球逐球对照真值（1948=大斌黑21、1040=王敏龙黑21、
    2034=小陈白T、0552/1056/1342=熊志鹏白、0544=蓝色27）
  - Files: scripts/crop_scorers.py, scripts/gen_scorer_page.py,
    tests/test_crop_scorers.py, tests/test_gen_scorer_page.py（M）

- [x] T8: 收尾
  - Acceptance: spec-reviewer 审 plan/todo/最终 diff；AGENTS.md 状态同步；git 提交（立哥确认）
  - Verify: ruff+pytest 全绿；立哥确认提交
