"""crop_scorers.py 单元测试（轨迹法定位 + 颜色分队 + 预览片段）。

覆盖：mot_cache schema 校验、轨迹窗口取帧、进球轨迹选择（端点距候选锚点最近/
超界 SKIP/无锚点退时间最近）、持球点回放判定、无持球起点回退、无轨迹/无人 SKIP、
candidates 锚点索引匹配、裁图外扩 20% 且短边 ≥400px、颜色三分类（近阈归便服）、
预览片段参数与失败容错、CLI 端到端（合成 goals + mot_cache + 帧图，不碰真实素材）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from crop_scorers import (
    MotCache,
    _try_cut_preview,
    classify_team,
    crop_and_save,
    cut_preview_clip,
    expand_box,
    find_held_box,
    load_candidates_index,
    load_mot_cache,
    locate_scorer,
    main,
    match_anchor_xy,
    preview_window,
    select_goal_track,
    start_nearest_box,
    track_window_dets,
)
from errors import BasketballPipelineError, SchemaError
from geom import Box
from mot_candidates import Detection, Track


def _ball(conf: float, cx: int, cy: int, fi: int, sec: float | None = None) -> Detection:
    """构造一个球检测（box 取球心 ±10px；sec 缺省按 5fps 帧率换算）。"""
    return Detection(
        conf=conf,
        box=[cx - 10, cy - 10, cx + 10, cy + 10],
        cx=cx,
        cy=cy,
        sec=fi / 5 if sec is None else sec,
        frame_idx=fi,
    )


def _cache(balls: list[tuple[Detection, ...]], persons: list[tuple[Box, ...]]) -> MotCache:
    """由逐帧列表构造 MotCache（frames 取两者长度）。"""
    assert len(balls) == len(persons)
    return MotCache(frames=len(balls), balls=tuple(balls), persons=tuple(persons))


def _empty_cache(frames: int) -> MotCache:
    """构造全空缓存（无球无人）。"""
    return _cache([()] * frames, [()] * frames)


def _track(points: list[tuple[int, int, int]]) -> Track:
    """由 (cx, cy, frame_idx) 列表构造轨迹。"""
    return Track(dets=[_ball(0.9, cx, cy, fi) for cx, cy, fi in points])


class TestLoadMotCache:
    """mot_cache schema 校验：合法通过，损坏抛 SchemaError。"""

    def _write(self, tmp_path: Path, payload: Any) -> Path:  # noqa: ANN401 测试载荷
        p = tmp_path / "x_mot_cache.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def test_valid_passes(self, tmp_path: Path) -> None:
        # Arrange
        payload = {
            "frames": 2,
            "balls": [
                [
                    {
                        "conf": 0.8,
                        "box": [0, 0, 10, 10],
                        "cx": 5,
                        "cy": 5,
                        "sec": 0.0,
                        "frame_idx": 0,
                    }
                ],
                [],
            ],
            "persons": [[[0, 0, 100, 200]], []],
        }
        # Act
        cache = load_mot_cache(self._write(tmp_path, payload))
        # Assert
        assert cache.frames == 2
        assert cache.balls[0][0].cx == 5
        assert cache.balls[0][0].box == [0, 0, 10, 10]
        assert cache.persons[0][0] == Box(0, 0, 100, 200)

    def test_length_mismatch(self, tmp_path: Path) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError, match="长度不齐"):
            load_mot_cache(self._write(tmp_path, {"frames": 2, "balls": [[]], "persons": [[], []]}))

    def test_missing_top_keys(self, tmp_path: Path) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError):
            load_mot_cache(self._write(tmp_path, {"frames": 1, "balls": [[]]}))

    def test_bad_ball_field(self, tmp_path: Path) -> None:
        # Arrange
        payload = {"frames": 1, "balls": [[{"conf": "high"}]], "persons": [[]]}
        # Act / Assert
        with pytest.raises(SchemaError):
            load_mot_cache(self._write(tmp_path, payload))

    def test_bad_person_box(self, tmp_path: Path) -> None:
        # Arrange：框 x2<=x1 属数据损坏
        payload = {"frames": 1, "balls": [[]], "persons": [[[10, 10, 5, 20]]]}
        # Act / Assert
        with pytest.raises(SchemaError):
            load_mot_cache(self._write(tmp_path, payload))


class TestTrackWindowDets:
    """轨迹重链窗口取帧：[anchor−4.0, anchor+0.5]，裁剪到缓存边界。"""

    def test_normal_window(self) -> None:
        # Arrange：30 帧缓存，anchor=4.0 → [0.0, 4.5] → 帧 0..22
        cache = _empty_cache(30)
        # Act
        window = track_window_dets(cache, 4.0)
        # Assert
        assert len(window) == 23

    def test_clamped_at_start(self) -> None:
        # Arrange：anchor=1.0 → [max(0,−3), 1.5] → 帧 0..7
        cache = _empty_cache(30)
        # Act / Assert
        assert len(track_window_dets(cache, 1.0)) == 8

    def test_clamped_at_end(self) -> None:
        # Arrange：anchor=6.0，缓存仅 30 帧（到 5.8s）→ 右端夹到帧 29
        cache = _empty_cache(30)
        # Act / Assert
        assert len(track_window_dets(cache, 6.0)) == 20

    def test_window_keeps_frame_dets(self) -> None:
        # Arrange：帧 10 有一个球，窗口应带出来
        balls = [()] * 30
        balls[10] = (_ball(0.9, 100, 100, 10),)
        cache = _cache(balls, [()] * 30)
        # Act
        window = track_window_dets(cache, 4.0)
        # Assert：窗口起点帧 0，索引 10 对应窗口第 10 个
        assert len(window[10]) == 1
        assert window[10][0].cx == 100


class TestSelectGoalTrack:
    """进球轨迹选择：端点与候选锚点最近；超界/无轨迹 → None。"""

    def test_nearest_endpoint_wins(self) -> None:
        # Arrange：两条轨迹，t1 端点 (100,100)、t2 端点 (800,800)
        t1 = _track([(90, 100, 18), (100, 100, 19)])
        t2 = _track([(790, 800, 18), (800, 800, 19)])
        # Act / Assert：锚点 (110,100) → t1
        assert select_goal_track([t2, t1], 4.0, (110, 100)) is t1

    def test_too_far_returns_none(self) -> None:
        # Arrange：端点都在锚点 200px 外
        t1 = _track([(100, 100, 19)])
        t2 = _track([(800, 800, 19)])
        # Act / Assert
        assert select_goal_track([t1, t2], 4.0, (500, 500)) is None

    def test_no_anchor_xy_falls_back_to_time(self) -> None:
        # Arrange：无候选位置 → 端点时间距 anchor 最近者
        t1 = _track([(100, 100, 14)])  # end sec 2.8
        t2 = _track([(550, 50, 20)])  # end sec 4.0
        # Act / Assert
        assert select_goal_track([t1, t2], 4.0, None) is t2

    def test_empty_tracks(self) -> None:
        # Arrange / Act / Assert
        assert select_goal_track([], 4.0, (100, 100)) is None


class TestFindHeldBox:
    """持球点回放：从末端往回放找最后一个球心严格落在人框内的轨迹点。"""

    def test_last_held_point_wins(self) -> None:
        # Arrange：f0 在 A 内、f1 悬空、f2 在 B 内 → 取 f2/B（最后持球者）
        track = _track([(50, 50, 0), (300, 50, 1), (550, 50, 2)])
        persons = (
            (Box(0, 0, 100, 100), Box(500, 0, 600, 100)),
            (Box(0, 0, 100, 100), Box(500, 0, 600, 100)),
            (Box(0, 0, 100, 100), Box(500, 0, 600, 100)),
        )
        # Act
        got = find_held_box(track, persons)
        # Assert
        assert got is not None
        det, box = got
        assert det.frame_idx == 2
        assert box == Box(500, 0, 600, 100)

    def test_strictly_inside_no_margin(self) -> None:
        # Arrange：球心 (105,50) 在框外 5px（无 margin，不算持球）
        track = _track([(105, 50, 0)])
        persons = ((Box(0, 0, 100, 100),),)
        # Act / Assert
        assert find_held_box(track, persons) is None

    def test_no_held_returns_none(self) -> None:
        # Arrange：整轨球心都不在人框内
        track = _track([(300, 300, 0), (320, 300, 1)])
        persons = ((Box(0, 0, 100, 100),), (Box(0, 0, 100, 100),))
        # Act / Assert
        assert find_held_box(track, persons) is None


class TestStartNearestBox:
    """无持球回退：轨迹起点时刻离球心最近的人框。"""

    def test_nearest_person_at_start(self) -> None:
        # Arrange：起点 (50,300)，A 中心 (50,50) 距 250，B 中心 (550,50) 距 ~640
        track = _track([(50, 300, 0), (250, 300, 1)])
        persons = (
            (Box(0, 0, 100, 100), Box(500, 0, 600, 100)),
            (Box(0, 0, 100, 100), Box(500, 0, 600, 100)),
        )
        # Act
        got = start_nearest_box(track, persons)
        # Assert
        assert got is not None
        det, box = got
        assert det.frame_idx == 0
        assert box == Box(0, 0, 100, 100)

    def test_no_persons_returns_none(self) -> None:
        # Arrange / Act / Assert
        track = _track([(50, 300, 0)])
        assert start_nearest_box(track, ((),)) is None


class TestLocateScorer:
    """轨迹法端到端（合成缓存）：选轨 → 持球回放 → 回退 → SKIP。"""

    def _shot_cache(self, ball_y: int = 50) -> MotCache:
        """30 帧：进球轨迹帧 10..20 从 (50,ball_y) 每帧 +20px 移到 (250,ball_y)；
        另有静态干扰球 (550,50) 全程在 B 框内。人框 A(0,0,100,100)、B(500,0,600,100)。"""
        persons = [(Box(0, 0, 100, 100), Box(500, 0, 600, 100))] * 30
        balls: list[tuple[Detection, ...]] = [()] * 30
        for fi in range(10, 21):
            balls[fi] = (
                _ball(0.9, 50 + (fi - 10) * 20, ball_y, fi),
                _ball(0.5, 550, 50, fi),
            )
        return _cache(balls, persons)

    def test_held_point_wins_over_static_fp(self) -> None:
        # Arrange：anchor=4.0，候选锚点 = 进球轨迹端点 (250,50)
        cache = self._shot_cache()
        # Act
        result = locate_scorer(cache, 4.0, (250, 50))
        # Assert：干扰球全程在 B 内，但端点离锚点 300px → 不选它；
        # 回放最后持球点 = 帧 12（球心 x=90 仍在 A 内，帧 13 起 x=110 出框）
        assert result.status == "OK"
        assert result.reason == ""
        assert result.box == Box(0, 0, 100, 100)
        assert result.frame_idx == 12
        assert result.votes == 11
        assert result.total_votes == 2

    def test_no_held_falls_back_to_start(self) -> None:
        # Arrange：球沿 y=300 移动（全程不在任何人框内）
        cache = self._shot_cache(ball_y=300)
        # Act
        result = locate_scorer(cache, 4.0, (250, 300))
        # Assert：无持球点 → 起点 (50,300)@帧10 最近人框 A
        assert result.status == "OK"
        assert result.reason == "start_fallback"
        assert result.box == Box(0, 0, 100, 100)
        assert result.frame_idx == 10

    def test_no_persons_skip(self) -> None:
        # Arrange：有球轨但全程无人框
        balls: list[tuple[Detection, ...]] = [()] * 30
        for fi in range(10, 21):
            balls[fi] = (_ball(0.9, 50 + (fi - 10) * 20, 300, fi),)
        cache = _cache(balls, [()] * 30)
        # Act
        result = locate_scorer(cache, 4.0, (250, 300))
        # Assert：无持球 + 起点帧无人 → SKIP
        assert result.status == "SKIP"
        assert result.reason == "no_person"

    def test_no_tracks_skip(self) -> None:
        # Arrange：窗口内全程无球
        cache = _empty_cache(30)
        # Act
        result = locate_scorer(cache, 4.0, (250, 50))
        # Assert
        assert result.status == "SKIP"
        assert result.reason == "no_track"

    def test_far_endpoint_skip(self) -> None:
        # Arrange：轨迹存在，但端点离候选锚点 >200px
        cache = self._shot_cache()
        # Act
        result = locate_scorer(cache, 4.0, (1500, 900))
        # Assert
        assert result.status == "SKIP"
        assert result.reason == "no_track_near_anchor"

    def test_time_fallback_without_anchor_xy(self) -> None:
        # Arrange：无候选位置；A 球帧 10..14，B 球帧 10..20（端点 4.0 离 anchor 最近）
        persons = [(Box(0, 0, 100, 100), Box(500, 0, 600, 100))] * 30
        balls: list[tuple[Detection, ...]] = [()] * 30
        for fi in range(10, 21):
            frame_balls = [_ball(0.5, 550, 50, fi)]
            if fi <= 14:
                frame_balls.append(_ball(0.9, 50, 50, fi))
            balls[fi] = tuple(frame_balls)
        cache = _cache(balls, persons)
        # Act
        result = locate_scorer(cache, 4.0, None)
        # Assert：选中 B 轨迹（端点时间最近），B 球全程在 B 框内 → 持球点命中
        assert result.status == "OK"
        assert result.box == Box(500, 0, 600, 100)


class TestCandidatesIndex:
    """candidates.json 锚点索引：fid+t0 匹配取 cx/cy。"""

    def _write(self, tmp_path: Path, payload: Any) -> Path:  # noqa: ANN401 测试载荷
        p = tmp_path / "candidates.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def test_match_within_tolerance(self, tmp_path: Path) -> None:
        # Arrange
        path = self._write(
            tmp_path,
            [
                {
                    "t0": 14.1,
                    "dur": 0.6,
                    "ac": 0.6,
                    "cx": 1629,
                    "cy": 704,
                    "src": "rejoin",
                    "fid": "a_video",
                    "label": "#7",
                },
                {
                    "t0": 13.8,
                    "dur": 1.4,
                    "ac": 0.4,
                    "cx": 1387,
                    "cy": 485,
                    "src": "static",
                    "fid": "a_video",
                    "label": "#6",
                },
            ],
        )
        # Act
        index = load_candidates_index(path)
        # Assert：anchor=14.1 精确匹配 #7
        assert match_anchor_xy(index, "a_video", 14.1) == (1629, 704)
        # anchor=13.9 在两者容差内，取更近的 #6（|0.1| < |0.2|）
        assert match_anchor_xy(index, "a_video", 13.9) == (1387, 485)

    def test_no_match_returns_none(self) -> None:
        # Arrange
        index = {"a_video": [(14.1, 100, 200)]}
        # Act / Assert：超容差 / 异 fid 都None
        assert match_anchor_xy(index, "a_video", 16.0) is None
        assert match_anchor_xy(index, "b_video", 14.1) is None

    def test_bad_schema_raises(self, tmp_path: Path) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError):
            load_candidates_index(self._write(tmp_path, {"not": "list"}))
        with pytest.raises(SchemaError):
            load_candidates_index(self._write(tmp_path, [{"t0": 1.0}]))


class TestCrop:
    """裁图：外扩 20%、夹取边界、短边放大到 400px。"""

    def test_expand_box_ratio(self) -> None:
        # Arrange：100x200 框外扩 20% → 每侧 10px / 20px
        # Act
        x1, y1, x2, y2 = expand_box(Box(100, 100, 200, 300), 0.2, 1000, 1000)
        # Assert
        assert (x1, y1, x2, y2) == (90, 80, 210, 320)

    def test_expand_box_clamped(self) -> None:
        # Arrange / Act
        x1, y1, x2, y2 = expand_box(Box(0, 0, 50, 50), 0.2, 60, 60)
        # Assert：越界侧被夹到图像边缘
        assert (x1, y1, x2, y2) == (0, 0, 55, 55)

    def test_crop_upscales_short_side(self, tmp_path: Path) -> None:
        # Arrange：1000x800 图，框 100x150 → 外扩后 120x180 → 短边 120 <400 → 放大
        img = tmp_path / "f_00001.jpg"
        Image.new("RGB", (1000, 800), (10, 20, 30)).save(img)
        out = tmp_path / "out" / "crop.jpg"
        # Act
        crop_and_save(img, Box(100, 100, 200, 250), out)
        # Assert
        with Image.open(out) as im:
            assert min(im.size) == 400
            assert im.size == (400, 600)

    def test_crop_no_upscale_when_large(self, tmp_path: Path) -> None:
        # Arrange：框 400x600 → 外扩 480x720（不触边界），短边 ≥400 不放大
        img = tmp_path / "f_00001.jpg"
        Image.new("RGB", (1000, 800), (10, 20, 30)).save(img)
        out = tmp_path / "out" / "crop.jpg"
        # Act
        crop_and_save(img, Box(100, 100, 500, 700), out)
        # Assert
        with Image.open(out) as im:
            assert im.size == (480, 720)


class TestClassifyTeam:
    """颜色分队：纯色三分类，近阈/彩色归便服。"""

    def _img(self, tmp_path: Path, rgb: tuple[int, int, int], name: str = "c.jpg") -> Path:
        p = tmp_path / name
        Image.new("RGB", (400, 600), rgb).save(p)
        return p

    def test_black(self, tmp_path: Path) -> None:
        # Arrange / Act / Assert
        assert classify_team(self._img(tmp_path, (15, 15, 15))) == "黑"

    def test_white(self, tmp_path: Path) -> None:
        # Arrange / Act / Assert
        assert classify_team(self._img(tmp_path, (240, 240, 240))) == "白"

    def test_mid_gray_is_casual(self, tmp_path: Path) -> None:
        # Arrange：V=128 落在黑/白阈值之间（近阈）→ 便服
        assert classify_team(self._img(tmp_path, (128, 128, 128))) == "便服"

    def test_saturated_bright_is_casual(self, tmp_path: Path) -> None:
        # Arrange：亮红 V 高但 S 高 → 不归白
        assert classify_team(self._img(tmp_path, (220, 30, 30))) == "便服"


class TestCliEndToEnd:
    """CLI 端到端：合成 goals + mot_cache + 帧图，验证产物与退出码。"""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
        """搭一套临时 goals/detect/frames/out，返回 (goals, detectdir, framesdir, out)。

        a_video@2.0：球全程静止在 A 框内 → 轨迹法 OK；b_video@1.0：空缓存 →
        no_track SKIP；a_video@5.0 rejected 不处理。
        """
        goals = tmp_path / "goals.json"
        goals.write_text(
            json.dumps(
                {
                    "session": "test",
                    "goals": [
                        {"file": "a_video.mp4", "anchor_time": 2.0, "status": "confirmed"},
                        {"file": "b_video.mp4", "anchor_time": 1.0, "status": "confirmed"},
                        {"file": "a_video.mp4", "anchor_time": 5.0, "status": "rejected"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        detectdir = tmp_path / "detect"
        detectdir.mkdir()
        persons = [[[0, 0, 100, 100], [500, 0, 600, 100]]] * 9
        balls = [
            [
                {
                    "conf": 0.9,
                    "box": [40, 40, 60, 60],
                    "cx": 50,
                    "cy": 50,
                    "sec": i / 5,
                    "frame_idx": i,
                }
            ]
            for i in range(9)
        ]
        (detectdir / "a_video_mot_cache.json").write_text(
            json.dumps({"frames": 9, "balls": balls, "persons": persons}), encoding="utf-8"
        )
        (detectdir / "b_video_mot_cache.json").write_text(
            json.dumps({"frames": 9, "balls": [[]] * 9, "persons": [[]] * 9}),
            encoding="utf-8",
        )
        framesdir = tmp_path / "frames"
        (framesdir / "a_video").mkdir(parents=True)
        for i in range(9):
            Image.new("RGB", (1000, 800), (20, 20, 20)).save(
                framesdir / "a_video" / f"f_{i + 1:05d}.jpg"
            )
        out = tmp_path / "out"
        return goals, detectdir, framesdir, out

    def test_end_to_end(self, tmp_path: Path) -> None:
        # Arrange
        goals, detectdir, framesdir, out = self._setup(tmp_path)
        # Act
        rc = main(
            [
                "--goals",
                str(goals),
                "--detectdir",
                str(detectdir),
                "--framesdir",
                str(framesdir),
                "--out",
                str(out),
            ]
        )
        # Assert
        assert rc == 0
        payload = json.loads((out / "scorer_candidates.json").read_text(encoding="utf-8"))
        assert payload["session"] == "test"
        entries = payload["candidates"]
        assert len(entries) == 2  # rejected 不处理
        ok = entries[0]
        assert ok["key"] == "a_video.mp4#2.0"
        assert ok["status"] == "OK"
        assert ok["team_guess"] == "黑"  # 帧图近黑
        assert (out / ok["crop"]).is_file()
        skip = entries[1]
        assert skip["key"] == "b_video.mp4#1.0"
        assert skip["status"] == "SKIP"
        assert skip["reason"] == "no_track"
        assert skip["crop"] == ""

    def test_missing_cache_exit_1(self, tmp_path: Path) -> None:
        # Arrange
        goals, detectdir, framesdir, out = self._setup(tmp_path)
        for p in detectdir.glob("*.json"):
            p.unlink()
        # Act
        rc = main(
            [
                "--goals",
                str(goals),
                "--detectdir",
                str(detectdir),
                "--framesdir",
                str(framesdir),
                "--out",
                str(out),
            ]
        )
        # Assert：素材缺失 → 逐条 SKIP 但退出码非零（产出型脚本口径）
        assert rc == 1
        payload = json.loads((out / "scorer_candidates.json").read_text(encoding="utf-8"))
        assert all(e["status"] == "SKIP" for e in payload["candidates"])
        assert all(e["reason"] == "missing_cache" for e in payload["candidates"])

    def test_candidates_arg_feeds_anchor_xy(self, tmp_path: Path) -> None:
        # Arrange：给 --candidates，a_video@2.0 的锚点 (50,50) 匹配上静态球轨迹
        goals, detectdir, framesdir, out = self._setup(tmp_path)
        candidates = tmp_path / "candidates.json"
        candidates.write_text(
            json.dumps(
                [
                    {
                        "t0": 2.0,
                        "dur": 0.8,
                        "ac": 0.9,
                        "cx": 50,
                        "cy": 50,
                        "src": "static",
                        "fid": "a_video",
                        "label": "#1",
                    }
                ]
            ),
            encoding="utf-8",
        )
        # Act
        rc = main(
            [
                "--goals",
                str(goals),
                "--detectdir",
                str(detectdir),
                "--framesdir",
                str(framesdir),
                "--out",
                str(out),
                "--candidates",
                str(candidates),
            ]
        )
        # Assert：照常 OK（锚点命中静态轨迹，持球点在 A 框）
        assert rc == 0
        payload = json.loads((out / "scorer_candidates.json").read_text(encoding="utf-8"))
        assert payload["candidates"][0]["status"] == "OK"


class TestPreviewClip:
    """--rawdir 认人预览片段：窗口夹取、路径组装、ffmpeg 参数、失败容错。"""

    def test_preview_window_normal(self) -> None:
        # Arrange / Act / Assert：锚点前 4s 后 2s
        assert preview_window(16.5) == (12.5, 18.5)

    def test_preview_window_clamped_at_zero(self) -> None:
        # Arrange / Act / Assert：anchor<4s 起点夹取到 0，不越界
        assert preview_window(1.3) == (0.0, 3.3)
        assert preview_window(4.0) == (0.0, 6.0)

    def test_cut_preview_clip_ffmpeg_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：拦截 run_ffmpeg 验证参数
        calls: list[dict[str, Any]] = []

        def fake_run_ffmpeg(
            args: list[str], *, timeout_sec: int = 600, retries: int = 1, backoff_sec: float = 5.0
        ) -> None:
            calls.append({"args": args, "timeout_sec": timeout_sec})

        monkeypatch.setattr("crop_scorers.run_ffmpeg", fake_run_ffmpeg)
        rawdir = tmp_path / "raw"
        rawdir.mkdir()
        (rawdir / "a_video.mp4").write_bytes(b"")
        # Act
        cut_preview_clip(rawdir, "a_video.mp4", 16.5, tmp_path / "out" / "clips" / "x.mp4")
        # Assert：输入侧 -ss/-to、1280 宽、libx264 crf26 veryfast、无声、超时下限 120s
        assert len(calls) == 1
        args = calls[0]["args"]
        assert args[:4] == ["-ss", "12.50", "-to", "18.50"]
        assert args[args.index("-i") + 1].endswith("a_video.mp4")
        assert "scale=1280:-2" in args
        assert args[args.index("-crf") + 1] == "26"
        assert args[args.index("-preset") + 1] == "veryfast"
        assert "-an" in args
        assert calls[0]["timeout_sec"] == 120

    def test_try_cut_preview_no_rawdir(self, tmp_path: Path) -> None:
        # Arrange / Act：未给 --rawdir 不切片
        clip, failed = _try_cut_preview(
            {"file": "a.mp4", "anchor_time": 2.0}, None, tmp_path, "a.mp4#2.0"
        )
        # Assert
        assert clip == ""
        assert failed is False

    def test_try_cut_preview_missing_src(self, tmp_path: Path) -> None:
        # Arrange：原片不存在
        rawdir = tmp_path / "raw"
        rawdir.mkdir()
        # Act
        clip, failed = _try_cut_preview(
            {"file": "ghost.mp4", "anchor_time": 2.0}, rawdir, tmp_path, "ghost.mp4#2.0"
        )
        # Assert：记失败但返回（不炸整批），调用方计入缺失错误使退出码非零
        assert clip == ""
        assert failed is True

    def test_try_cut_preview_ffmpeg_failure_tolerated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：ffmpeg 重试耗尽抛错
        def fake_run_ffmpeg(
            args: list[str], *, timeout_sec: int = 600, retries: int = 1, backoff_sec: float = 5.0
        ) -> None:
            raise BasketballPipelineError("boom")

        monkeypatch.setattr("crop_scorers.run_ffmpeg", fake_run_ffmpeg)
        rawdir = tmp_path / "raw"
        rawdir.mkdir()
        (rawdir / "a.mp4").write_bytes(b"")
        # Act
        clip, failed = _try_cut_preview(
            {"file": "a.mp4", "anchor_time": 2.0}, rawdir, tmp_path, "a.mp4#2.0"
        )
        # Assert：失败容错，不抛出
        assert clip == ""
        assert failed is True

    def test_try_cut_preview_success_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：ffmpeg 成功（假造输出文件）
        def fake_run_ffmpeg(
            args: list[str], *, timeout_sec: int = 600, retries: int = 1, backoff_sec: float = 5.0
        ) -> None:
            Path(args[-1]).write_bytes(b"mp4")

        monkeypatch.setattr("crop_scorers.run_ffmpeg", fake_run_ffmpeg)
        rawdir = tmp_path / "raw"
        rawdir.mkdir()
        (rawdir / "a_video.mp4").write_bytes(b"")
        # Act
        clip, failed = _try_cut_preview(
            {"file": "a_video.mp4", "anchor_time": 16.5}, rawdir, tmp_path, "k"
        )
        # Assert：相对路径 clips/<fid>_t<anchor:.1f>.mp4，正斜杠
        assert clip == "clips/a_video_t16.5.mp4"
        assert failed is False
        assert (tmp_path / "clips" / "a_video_t16.5.mp4").is_file()


class TestCliPreviewClip:
    """CLI 端到端 --rawdir：SKIP 球也切预览片段，clip 字段写入 candidates。"""

    def test_skip_goal_also_gets_clip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：复用端到端场景（a_video OK 球 + b_video no_track SKIP 球）
        setup = TestCliEndToEnd()
        goals, detectdir, framesdir, out = setup._setup(tmp_path)
        rawdir = tmp_path / "raw"
        rawdir.mkdir()
        (rawdir / "a_video.mp4").write_bytes(b"")
        (rawdir / "b_video.mp4").write_bytes(b"")

        def fake_run_ffmpeg(
            args: list[str], *, timeout_sec: int = 600, retries: int = 1, backoff_sec: float = 5.0
        ) -> None:
            Path(args[-1]).write_bytes(b"mp4")

        monkeypatch.setattr("crop_scorers.run_ffmpeg", fake_run_ffmpeg)
        # Act
        rc = main(
            [
                "--goals",
                str(goals),
                "--detectdir",
                str(detectdir),
                "--framesdir",
                str(framesdir),
                "--out",
                str(out),
                "--rawdir",
                str(rawdir),
            ]
        )
        # Assert：两球都有预览片段（SKIP 球也切），退出码 0
        assert rc == 0
        payload = json.loads((out / "scorer_candidates.json").read_text(encoding="utf-8"))
        ok, skip = payload["candidates"]
        assert ok["clip"] == "clips/a_video_t2.0.mp4"
        assert skip["status"] == "SKIP"
        assert skip["clip"] == "clips/b_video_t1.0.mp4"
        assert (out / skip["clip"]).is_file()

    def test_clip_failure_exit_1_but_candidates_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange：原片缺失 → 切片失败，但定位/裁图照常产出
        setup = TestCliEndToEnd()
        goals, detectdir, framesdir, out = setup._setup(tmp_path)
        rawdir = tmp_path / "raw"
        rawdir.mkdir()  # 空目录：a_video.mp4 / b_video.mp4 不存在
        # Act
        rc = main(
            [
                "--goals",
                str(goals),
                "--detectdir",
                str(detectdir),
                "--framesdir",
                str(framesdir),
                "--out",
                str(out),
                "--rawdir",
                str(rawdir),
            ]
        )
        # Assert：缺失可观测（退出 1），candidates 照常落盘、clip 为空
        assert rc == 1
        payload = json.loads((out / "scorer_candidates.json").read_text(encoding="utf-8"))
        assert all(e["clip"] == "" for e in payload["candidates"])
        assert payload["candidates"][0]["status"] == "OK"
