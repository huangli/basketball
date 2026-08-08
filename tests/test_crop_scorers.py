"""crop_scorers.py 单元测试（spec: docs/scorer/spec.md §投篮者定位算法 / §颜色分队判据）。

覆盖：mot_cache schema 校验、IoU 链关联、投票众数胜出、并列取平均距离更近、
有效票 <2 / anchor<1.5s → SKIP、裁图外扩 20% 且短边 ≥400px、颜色三分类（近阈归便服）、
CLI 端到端（合成 goals + mot_cache + 帧图，不碰真实素材）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from crop_scorers import (
    BallDet,
    MotCache,
    classify_team,
    crop_and_save,
    expand_box,
    link_tracks,
    load_mot_cache,
    locate_scorer,
    main,
    window_frames,
)
from errors import SchemaError
from geom import Box


def _ball(conf: float, cx: float, cy: float, fi: int) -> BallDet:
    """构造一个球检测。"""
    return BallDet(conf=conf, cx=cx, cy=cy, frame_idx=fi)


def _cache(balls: list[tuple[BallDet, ...]], persons: list[tuple[Box, ...]]) -> MotCache:
    """由逐帧列表构造 MotCache（frames 取两者长度）。"""
    assert len(balls) == len(persons)
    return MotCache(frames=len(balls), balls=tuple(balls), persons=tuple(persons))


def _empty_cache(frames: int) -> MotCache:
    """构造全空缓存（无球无人）。"""
    return _cache([()] * frames, [()] * frames)


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
        assert cache.balls[0][0].cx == 5.0
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


class TestWindowFrames:
    """投票窗口计算。"""

    def test_normal_window(self) -> None:
        # Arrange：anchor=16.5 → [14.0, 16.2] → 帧 70..81
        # Act
        frames = window_frames(16.5, 100)
        # Assert
        assert frames == list(range(70, 82))

    def test_clamped_to_cache(self) -> None:
        # Arrange：窗口右端超出缓存长度
        # Act / Assert
        assert window_frames(3.0, 8) == list(range(3, 8))


class TestLinkTracks:
    """IoU>0.3 贪心链：同一人跨帧串联，断裂开新 track。"""

    def test_two_persons_two_tracks(self) -> None:
        # Arrange：A 缓慢移动（IoU≈0.54），B 静止在远处
        persons = (
            (Box(0, 0, 100, 100), Box(500, 0, 600, 100)),
            (Box(30, 0, 130, 100), Box(500, 0, 600, 100)),
            (Box(60, 0, 160, 100), Box(500, 0, 600, 100)),
        )
        # Act
        tracks = link_tracks([0, 1, 2], persons)
        # Assert
        assert len(tracks) == 2
        lengths = sorted(len(t.dets) for t in tracks)
        assert lengths == [3, 3]

    def test_break_starts_new_track(self) -> None:
        # Arrange：第 2 帧 A 跳到远处（IoU=0 < 0.3），应开新 track
        persons = (
            (Box(0, 0, 100, 100),),
            (Box(400, 0, 500, 100),),
        )
        # Act
        tracks = link_tracks([0, 1], persons)
        # Assert
        assert len(tracks) == 2
        assert all(len(t.dets) == 1 for t in tracks)


class TestLocateScorer:
    """投票与 SKIP 规则（spec B2）。"""

    def _two_track_cache(self, ball_frames: dict[int, BallDet]) -> MotCache:
        """9 帧（anchor=2.0 → 窗口帧 0..8）：A 在左 B 在右，全程静止。"""
        persons = [(Box(0, 0, 100, 100), Box(500, 0, 600, 100))] * 9
        balls = [tuple([ball_frames[i]]) if i in ball_frames else () for i in range(9)]
        return _cache(balls, persons)

    def test_majority_wins(self) -> None:
        # Arrange：5 帧球在 A 旁、2 帧在 B 旁、2 帧无球
        balls = {i: _ball(0.9, 50, 50, i) for i in (0, 1, 2, 3, 4)}
        balls.update({i: _ball(0.9, 550, 50, i) for i in (5, 6)})
        cache = self._two_track_cache(balls)
        # Act
        result = locate_scorer(cache, 2.0)
        # Assert
        assert result.status == "OK"
        assert result.votes == 5
        assert result.total_votes == 7
        assert result.box == Box(0, 0, 100, 100)

    def test_tie_breaks_by_mean_distance(self) -> None:
        # Arrange：A、B 各 1 票；A 票距离 10，B 票距离 60 → A 胜
        persons = [(Box(0, 0, 100, 100), Box(500, 0, 600, 100))] * 9
        balls_list = [()] * 9
        balls_list[0] = (_ball(0.9, 50, 50, 0),)  # 距 A 中心 (50,50) → 0（在框内）
        balls_list[1] = (_ball(0.9, 650, 50, 1),)  # 距 B 框右边 50 → 50
        cache = _cache(balls_list, persons)
        # Act
        result = locate_scorer(cache, 2.0)
        # Assert
        assert result.status == "OK"
        assert result.votes == 1
        assert result.box == Box(0, 0, 100, 100)

    def test_few_votes_skip(self) -> None:
        # Arrange：仅 1 帧有球 → 有效票 <2 → SKIP
        cache = self._two_track_cache({3: _ball(0.9, 50, 50, 3)})
        # Act
        result = locate_scorer(cache, 2.0)
        # Assert
        assert result.status == "SKIP"
        assert result.reason == "few_votes"
        assert result.total_votes == 1

    def test_short_anchor_skip(self) -> None:
        # Arrange：anchor=1.0 < 1.5 → 短窗口直接 SKIP（不看缓存内容）
        cache = self._two_track_cache({i: _ball(0.9, 50, 50, i) for i in range(9)})
        # Act
        result = locate_scorer(cache, 1.0)
        # Assert
        assert result.status == "SKIP"
        assert result.reason == "short_window"

    def test_no_ball_at_all_skip(self) -> None:
        # Arrange：窗口内全程无球
        cache = _empty_cache(9)
        # Act
        result = locate_scorer(cache, 2.0)
        # Assert
        assert result.status == "SKIP"
        assert result.reason == "few_votes"

    def test_multi_ball_picks_max_conf(self) -> None:
        # Arrange：同帧两球，低 conf 球在 B 旁、高 conf 在 A 旁 → 票归 A
        persons = [(Box(0, 0, 100, 100), Box(500, 0, 600, 100))] * 9
        balls = [(_ball(0.9, 50, 50, i), _ball(0.2, 550, 50, i)) for i in range(3)]
        balls += [()] * 6
        cache = _cache(balls, persons)
        # Act
        result = locate_scorer(cache, 2.0)
        # Assert
        assert result.status == "OK"
        assert result.box == Box(0, 0, 100, 100)

    def test_rep_frame_is_closest(self) -> None:
        # Arrange：A 全票；第 4 帧球在框内（dist=0），其余帧球在框外 30 → 代表帧=4
        persons = [(Box(0, 0, 100, 100), Box(500, 0, 600, 100))] * 9
        balls = [(_ball(0.9, 130, 50, i),) for i in range(9)]
        balls[4] = (_ball(0.9, 50, 50, 4),)
        cache = _cache(balls, persons)
        # Act
        result = locate_scorer(cache, 2.0)
        # Assert
        assert result.frame_idx == 4


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
        out = tmp_path / "crop.jpg"
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
        """搭一套临时 goals/detect/frames/out，返回 (goals, detectdir, framesdir, out)。"""
        fid = "a_video"
        goals = tmp_path / "goals.json"
        goals.write_text(
            json.dumps(
                {
                    "session": "test",
                    "goals": [
                        {"file": f"{fid}.mp4", "anchor_time": 2.0, "status": "confirmed"},
                        {"file": f"{fid}.mp4", "anchor_time": 1.0, "status": "confirmed"},
                        {"file": f"{fid}.mp4", "anchor_time": 5.0, "status": "rejected"},
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
        (detectdir / f"{fid}_mot_cache.json").write_text(
            json.dumps({"frames": 9, "balls": balls, "persons": persons}), encoding="utf-8"
        )
        framesdir = tmp_path / "frames"
        (framesdir / fid).mkdir(parents=True)
        for i in range(9):
            Image.new("RGB", (1000, 800), (20, 20, 20)).save(framesdir / fid / f"f_{i + 1:05d}.jpg")
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
        assert skip["key"] == "a_video.mp4#1.0"
        assert skip["status"] == "SKIP"
        assert skip["reason"] == "short_window"
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
