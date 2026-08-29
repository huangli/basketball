# plan：热图落点飞行段链接修复（heatmap-flight-link）

依据 spec.md（方向 1+2）。改动 3 处生产代码 + 3 处测试，全部小步可验。

## 改动点与接口

### 1. `scripts/mot_candidates.py` — run_mot 加门限参数

`run_mot(all_balls, *, min_length=STATIC_WINDOW, max_match_dist: float = MAX_MATCH_DIST)`：
函数体内 `best_d: float = float(MAX_MATCH_DIST)` 改为 `float(max_match_dist)`。
docstring 补参数说明（候选挖掘默认 80 不变；落点链路传放宽值）。
其余调用方全部不传参、行为不变——run_mot 生产调用方共 5 处：
`mot_candidates.py:697`（run_pipeline）、`crop_scorers.py:894`（locate_scorer）、
`goal_heatmap.py:377`（find_landing，本次改）、`gen_label_sheet.py:56`、
`pilot_candidates.py:55`。

### 2. `scripts/crop_scorers.py` — select_goal_track 加长轨偏好

新增常量（约 101 行 GOAL_TRACK_MAX_DIST_PX 旁）：

```python
PREFER_LONGER_SLACK_PX: int = 100  # 长轨偏好滑窗：端点距离 ≤ 最优+此值的轨迹进候选池
```

签名改 `select_goal_track(tracks, anchor_sec, anchor_xy, *, prefer_longer: bool = False)`。
有 anchor_xy 分支改为：

```python
    def _dist(t: Track) -> float:
        return euclidean((t.last_det.cx, t.last_det.cy), anchor_xy)

    best: Track = min(tracks, key=_dist)
    if prefer_longer:
        pool: list[Track] = [t for t in tracks if _dist(t) <= _dist(best) + PREFER_LONGER_SLACK_PX]
        best = max(pool, key=lambda t: (t.length, -_dist(t)))
    if _dist(best) > GOAL_TRACK_MAX_DIST_PX:
        return None
    return best
```

无 anchor_xy 分支与默认 prefer_longer=False 行为逐点不变（locate_scorer 不传参）。
`select_goal_track` docstring 同步更新（描述 prefer_longer 语义与默认不变）。

**增补（v4.3 实场验证首轮复盘，spec 范围 3）**：prefer_longer 覆盖 anchor_xy=None
分支——新增常量 `PREFER_LONGER_SLACK_SEC: float = 1.0`（长轨偏好时间滑窗），
None 分支改为：

```python
    if anchor_xy is None:
        if not prefer_longer:
            return min(tracks, key=lambda t: abs(t.last_det.sec - anchor_sec))
        best_t: Track = min(tracks, key=lambda t: abs(t.last_det.sec - anchor_sec))
        best_dt: float = abs(best_t.last_det.sec - anchor_sec)
        pool_t: list[Track] = [
            t for t in tracks if abs(t.last_det.sec - anchor_sec) <= best_dt + PREFER_LONGER_SLACK_SEC
        ]
        return max(pool_t, key=lambda t: (t.length, -abs(t.last_det.sec - anchor_sec)))
```

且 `find_landing` 在 anchor_xy 分支落空后回退时间域长轨选择：

```python
    track = select_goal_track(tracks, event.anchor_time, anchor_xy, prefer_longer=True)
    if track is None and anchor_xy is not None:
        # 机器候选空间误导（手工锚远离候选/候选错位）→ 退化时间域长轨偏好
        track = select_goal_track(tracks, event.anchor_time, None, prefer_longer=True)
```

### 3. `scripts/goal_heatmap.py` — find_landing 接入放宽门限 + 长轨偏好

新增常量（判据常量区）：

```python
FLIGHT_MATCH_DIST_PX: int = 250  # 落点链路 MOT 放宽门限（调研：15/19 no_landing 在此门限可链）
```

`find_landing` 首两行改为：

```python
    tracks = run_mot(
        track_window_dets(cache, event.anchor_time),
        min_length=1,
        max_match_dist=FLIGHT_MATCH_DIST_PX,
    )
    ...
    track = select_goal_track(tracks, event.anchor_time, anchor_xy, prefer_longer=True)
```

模块 docstring 口径段补一行 v4.3 说明；`heat_session` 的 report params 增加
`"flight_match_dist_px": FLIGHT_MATCH_DIST_PX`。

## 执行步骤（TDD，每步可验）

1. **测试先行 A**：新建 `tests/test_mot_candidates.py`——
   - 飞行球每帧位移 100px：默认门限 → 碎成单点轨迹（无长度 ≥5 的轨迹）；
   - 同输入 `max_match_dist=250` → 链成 1 条长轨迹；
   - 静止球默认参数产物与改前一致（回归）。
   跑 `pytest tests/test_mot_candidates.py -v` 确认前两条当前失败（无参数）/行为不符。
2. **实现改动 1**（run_mot），A 组测试转绿。
3. **测试先行 B**：`tests/test_crop_scorers.py` TestSelectGoalTrack 增例——
   - prefer_longer=True：短碎片端点距锚 10px、长轨迹端点距锚 80px（滑窗内）→ 选长轨迹；
   - 长轨迹端点距锚 150px（滑窗外）→ 仍选碎片；
   - prefer_longer=True 且池内全部端点 >200px → None（外层上界仍生效）；
   - 默认 False 行为不变（既有 4 例已覆盖，不改动）；
   - （增补）anchor_xy=None + prefer_longer=True：网内碎片端点时刻最近、长轨迹端点在
     1.0s 时间滑窗内 → 选长轨迹；长轨迹端点超滑窗 → 仍选时间最近者。
4. **实现改动 2**（select_goal_track），B 组转绿。
5. **测试先行 C**：`tests/test_goal_heatmap.py` 增两例——
   - C1（锁 max_match_dist 接线）：飞行段每帧 100px 的合成缓存
     （仿 `_shot_cache`，步长 20→100），anchor_xy 指向轨迹末端；旧行为碎成单点
     → no_landing，新行为链成长轨迹 → covered（trace 路径，落点框为预设人框）。
   - C2（锁 prefer_longer 接线，spec 审查 S1）：缓存中同时存在网内短碎片
     （端点距锚 ~10px）与长飞行轨迹（端点距锚 ~80px，100px 滑窗内）；
     若漏传 prefer_longer=True 会选碎片 → 结果退化，本例锁定接线。
   - C3（锁 anchor_xy 落空回退，spec 范围 3）：anchor_xy 远离一切轨迹端点
     （>200px）→ anchor_xy 分支 None → 回退时间域长轨选择 → covered。
6. **实现改动 3**（goal_heatmap），C 组转绿。heat_session 端到端测试只断言
   params 单个键值（team_color_guard 等），新增 flight_match_dist_px 键
   不破既有断言，无需同步更新。
7. **关口**：`ruff format scripts tests && ruff check --fix scripts tests && pytest -q`
   全绿（--fix 后复核 diff）。
8. **实场验证**：`python -X utf8 scripts/goal_heatmap.py --sessiondir work/20260822_citymonkey`，
   对比 coverage 45.7% → 新值、`no_landing` 19 → 新值、两队 teams 分布；
   核对 `heatmap_audit.png` 无异常后交立哥抽验。
9. **文档收尾**：写 review01.md；`docs/heatmap/spec.md` 头部加 v4.3 指针行；
   goal_heatmap 模块 docstring 已随改动 3 更新。
10. **提交**：`feat: 热图落点链路支持飞行段（MOT 放宽门限+长轨偏好）`（只 commit 不 push）。
