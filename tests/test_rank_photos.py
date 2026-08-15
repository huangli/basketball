"""rank_photos.py 单元测试（打分 / 分桶 / 构图 / 尺度断言 / apply 校验）。

覆盖：每帧 max conf 球选取（conf<0.35 视为无球）、冲击分四信号
（球速/人球交互/主体尺度/球高度）、10s 分桶保底 1 张再按分补齐、
构图裁切（联合包围/头顶留白/三分法/边界夹取/放大降级/16:9 与 4:3）、
缓存坐标尺度可执行断言（越界抛 SchemaError）、selections.json schema 校验、
apply 落盘命名契约。不触碰真实素材与 ffmpeg。
"""

from __future__ import annotations

import pytest

from crop_scorers import MotCache
from errors import SchemaError
from geom import Box
from mot_candidates import Detection
from rank_photos import (
    OUT_4_3,
    OUT_16_9,
    ScoredCandidate,
    apply_filename,
    assert_cache_scale,
    bucket_pick,
    compose_crop,
    frame_ball,
    score_frames,
    validate_selections,
    window_times,
)

DET_W: int = 1920
DET_H: int = 1080


def _ball(conf: float, cx: int, cy: int, fi: int) -> Detection:
    """构造一个球检测（box 取球心 ±10px；sec 按 5fps 帧率换算）。"""
    return Detection(
        conf=conf,
        box=[cx - 10, cy - 10, cx + 10, cy + 10],
        cx=cx,
        cy=cy,
        sec=fi / 5,
        frame_idx=fi,
    )


def _cache(balls: list[tuple[Detection, ...]], persons: list[tuple[Box, ...]]) -> MotCache:
    """由逐帧列表构造 MotCache（frames 取两者长度）。"""
    assert len(balls) == len(persons)
    return MotCache(frames=len(balls), balls=tuple(balls), persons=tuple(persons))


def _big_person(cx: int = 960, cy: int = 700) -> Box:
    """大人框（约 0.14 帧面积，尺度项记满）。"""
    return Box(cx - 200, cy - 400, cx + 200, cy + 400)


class TestFrameBall:
    """每帧只取 max conf 球；conf < 0.35 视为无球。"""

    def test_picks_max_conf(self) -> None:
        balls = (_ball(0.5, 100, 100, 0), _ball(0.9, 500, 500, 0))
        picked = frame_ball(balls)
        assert picked is not None
        assert picked.conf == pytest.approx(0.9)

    def test_low_conf_treated_as_no_ball(self) -> None:
        assert frame_ball((_ball(0.34, 100, 100, 0),)) is None

    def test_threshold_boundary_kept(self) -> None:
        assert frame_ball((_ball(0.35, 100, 100, 0),)) is not None

    def test_empty(self) -> None:
        assert frame_ball(()) is None


class TestScoreFrames:
    """冲击分：有球有人 > 空帧；球速快 > 静止；低置信球按无球计。"""

    def test_ball_and_person_beats_empty(self) -> None:
        cache = _cache(
            [(), (_ball(0.9, 960, 300, 1),)],
            [(), (_big_person(),)],
        )
        scores = score_frames(cache, DET_H)
        assert scores[0] == 0.0
        assert scores[1] > 0.0

    def test_person_only_beats_empty(self) -> None:
        cache = _cache([(), ()], [(), (_big_person(),)])
        scores = score_frames(cache, DET_H)
        assert scores[1] > scores[0] == 0.0

    def test_fast_ball_beats_still_ball(self) -> None:
        still = _cache(
            [(_ball(0.9, 960, 500, 0),), (_ball(0.9, 960, 500, 1),)],
            [(_big_person(),), (_big_person(),)],
        )
        fast = _cache(
            [(_ball(0.9, 960, 500, 0),), (_ball(0.9, 1560, 500, 1),)],
            [(_big_person(),), (_big_person(),)],
        )
        assert score_frames(fast, DET_H)[1] > score_frames(still, DET_H)[1]

    def test_low_conf_ball_scores_like_no_ball(self) -> None:
        with_low = _cache([(), (_ball(0.30, 960, 200, 1),)], [(), (_big_person(),)])
        no_ball = _cache([(), ()], [(), (_big_person(),)])
        assert score_frames(with_low, DET_H)[1] == pytest.approx(score_frames(no_ball, DET_H)[1])

    def test_high_ball_beats_low_ball(self) -> None:
        # 静止球（帧间无位移，排除球速信号干扰）：画面上部 > 画面下部
        cache = _cache(
            [
                (),
                (_ball(0.9, 960, 100, 1),),
                (_ball(0.9, 960, 100, 2),),
                (_ball(0.9, 960, 900, 3),),
                (_ball(0.9, 960, 900, 4),),
            ],
            [(), (), (), (), ()],
        )
        scores = score_frames(cache, DET_H)
        assert scores[2] > scores[4]


class TestBucketPick:
    """10s 分桶：每桶保底 1 张，再按分数全局补齐至 total。"""

    def _item(self, fid: str, fi: int, global_sec: float, score: float) -> ScoredCandidate:
        return ScoredCandidate(
            fid=fid, frame_idx=fi, sec=fi / 5, global_sec=global_sec, score=score
        )

    def test_each_bucket_guaranteed_one(self) -> None:
        # 3 个桶：桶0 一堆高分，桶1/桶2 各一张低分
        items = [self._item("a", i, i * 0.2, 0.9 - i * 0.01) for i in range(10)]
        items.append(self._item("b", 0, 15.0, 0.1))
        items.append(self._item("c", 0, 25.0, 0.2))
        picked = bucket_pick(items, total=4, bucket_sec=10.0)
        assert len(picked) == 4
        buckets = {int(p.global_sec // 10.0) for p in picked}
        assert buckets == {0, 1, 2}

    def test_fill_by_score_after_guarantee(self) -> None:
        items = [self._item("a", i, i * 0.2, s) for i, s in enumerate([0.5, 0.9, 0.8, 0.1])]
        picked = bucket_pick(items, total=3, bucket_sec=10.0)
        scores = sorted(p.score for p in picked)
        assert scores == [0.5, 0.8, 0.9]  # 保底 0.9，补齐取 0.8/0.5，丢 0.1

    def test_guarantee_beats_total_when_more_buckets(self) -> None:
        # 桶数多于目标张数时保底优先（宁多勿漏，不丢时间覆盖）
        items = [self._item("a", i, i * 12.0, 0.5) for i in range(10)]
        assert len(bucket_pick(items, total=4, bucket_sec=10.0)) == 10

    def test_fewer_items_than_total(self) -> None:
        items = [self._item("a", 0, 0.0, 0.5), self._item("a", 1, 30.0, 0.6)]
        assert len(bucket_pick(items, total=200, bucket_sec=10.0)) == 2

    def test_result_sorted_by_global_sec(self) -> None:
        items = [
            self._item("a", 0, 25.0, 0.9),
            self._item("a", 1, 1.0, 0.8),
            self._item("a", 2, 12.0, 0.7),
        ]
        picked = bucket_pick(items, total=3, bucket_sec=10.0)
        assert [p.global_sec for p in picked] == [1.0, 12.0, 25.0]

    def test_empty_input(self) -> None:
        assert bucket_pick([], total=200, bucket_sec=10.0) == []


class TestComposeCrop:
    """构图裁切：联合包围 / 头顶留白 / 三分法 / 边界夹取 / 放大降级 / 双比例。"""

    IMG_W: int = 3840
    IMG_H: int = 2160
    OUT_W, OUT_H = OUT_16_9

    def _person(self) -> Box:
        return Box(1500, 700, 1900, 1900)  # 高 1200，站画面中下部

    def test_aspect_and_out_size_16_9(self) -> None:
        plan = compose_crop(self._person(), None, self.IMG_W, self.IMG_H, *OUT_16_9)
        w = plan.box.x2 - plan.box.x1
        h = plan.box.y2 - plan.box.y1
        assert abs(w / h - 16 / 9) < 0.01

    def test_aspect_4_3(self) -> None:
        plan = compose_crop(self._person(), None, self.IMG_W, self.IMG_H, *OUT_4_3)
        w = plan.box.x2 - plan.box.x1
        h = plan.box.y2 - plan.box.y1
        assert abs(w / h - 4 / 3) < 0.01

    def test_headroom_at_least_10_percent(self) -> None:
        person = self._person()
        plan = compose_crop(person, None, self.IMG_W, self.IMG_H, *OUT_16_9)
        h = plan.box.y2 - plan.box.y1
        headroom = person.y1 - plan.box.y1
        assert headroom >= 0.10 * h - 2  # 2px 取整容差

    def test_person_fully_inside_crop(self) -> None:
        person = self._person()
        plan = compose_crop(person, None, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.box.x1 <= person.x1
        assert plan.box.x2 >= person.x2
        assert plan.box.y1 <= person.y1
        assert plan.box.y2 >= person.y2

    def test_near_ball_united(self) -> None:
        person = self._person()
        ball = Box(1680, 300, 1720, 340)  # 人头顶上方不远处
        plan = compose_crop(person, ball, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.box.x1 <= ball.x1
        assert plan.box.y1 <= ball.y1
        assert plan.box.x2 >= ball.x2

    def test_far_ball_not_united(self) -> None:
        person = self._person()
        ball = Box(100, 100, 140, 140)  # 画面远角，与人无关
        plan = compose_crop(person, ball, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.box.x1 > ball.x2 or plan.box.y1 > ball.y2

    def test_clamped_to_image_left_edge(self) -> None:
        person = Box(0, 700, 400, 1900)  # 贴左边缘
        plan = compose_crop(person, None, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.box.x1 >= 0
        assert plan.box.x2 <= self.IMG_W
        assert plan.box.x1 <= person.x1  # 人仍在框内

    def test_clamped_to_image_bottom_edge(self) -> None:
        person = Box(1500, 1600, 1900, 2160)  # 贴下边缘
        plan = compose_crop(person, None, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.box.y2 <= self.IMG_H
        assert plan.box.y2 >= person.y2

    def test_no_upscale_when_crop_wide_enough(self) -> None:
        plan = compose_crop(self._person(), None, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.upscale == pytest.approx(1.0)
        assert not plan.penalized

    def test_small_subject_needs_upscale(self) -> None:
        tiny = Box(1800, 1500, 2000, 1900)  # 宽 200，远小于 1920
        plan = compose_crop(tiny, None, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert plan.upscale > 1.5
        assert plan.penalized

    def test_upscale_between_1_and_threshold_not_penalized(self) -> None:
        person = Box(1000, 700, 2700, 1300)  # 宽 1700 → 裁框宽 1870，略小于 1920
        plan = compose_crop(person, None, self.IMG_W, self.IMG_H, *OUT_16_9)
        assert 1.0 < plan.upscale <= 1.5
        assert not plan.penalized


class TestAssertCacheScale:
    """尺度换算可执行断言：越界抛 SchemaError，合法返回换算因子。"""

    def test_valid_16_9_returns_factor(self) -> None:
        cache = _cache([(_ball(0.9, 1900, 1000, 0),)], [(Box(0, 0, 1920, 1080),)])
        factor = assert_cache_scale(cache, 3840, 2160, "t.mp4")
        assert factor == pytest.approx(2.0)

    def test_valid_4_3_returns_factor(self) -> None:
        cache = _cache([(_ball(0.9, 1900, 1400, 0),)], [(Box(0, 0, 1920, 1440),)])
        factor = assert_cache_scale(cache, 2560, 1920, "t.mp4")
        assert factor == pytest.approx(2560 / 1920)

    def test_x_beyond_detect_width_raises(self) -> None:
        cache = _cache([(_ball(0.9, 2100, 500, 0),)], [()])
        with pytest.raises(SchemaError):
            assert_cache_scale(cache, 3840, 2160, "t.mp4")

    def test_y_beyond_detect_height_raises(self) -> None:
        # 4:3 老场次检测帧高 1440；按 16:9 的 1080 上限误算会放过，按 1440 则越界
        cache = _cache([()], [(Box(0, 1400, 100, 1500),)])
        with pytest.raises(SchemaError):
            assert_cache_scale(cache, 2560, 1920, "t.mp4")

    def test_negative_beyond_tolerance_raises(self) -> None:
        cache = _cache([()], [(Box(-100, 0, 100, 500),)])
        with pytest.raises(SchemaError):
            assert_cache_scale(cache, 3840, 2160, "t.mp4")

    def test_within_tolerance_passes(self) -> None:
        # 1% 容差内的轻微越界放行（检测框贴边的浮点/取整误差）
        cache = _cache([(_ball(0.9, 1925, 10, 0),)], [()])
        assert_cache_scale(cache, 3840, 2160, "t.mp4")


class TestValidateSelections:
    """selections.json schema 校验（rules.md §0.2：损坏显式失败）。"""

    def _payload(self) -> dict:
        return {"session": "s1", "selected": ["c001", "c002"]}

    def test_valid(self) -> None:
        assert validate_selections(self._payload(), "s1") == ["c001", "c002"]

    def test_session_mismatch_raises(self) -> None:
        with pytest.raises(SchemaError):
            validate_selections(self._payload(), "other")

    def test_missing_selected_raises(self) -> None:
        with pytest.raises(SchemaError):
            validate_selections({"session": "s1"}, "s1")

    def test_non_string_id_raises(self) -> None:
        with pytest.raises(SchemaError):
            validate_selections({"session": "s1", "selected": ["c001", 2]}, "s1")

    def test_top_level_not_dict_raises(self) -> None:
        with pytest.raises(SchemaError):
            validate_selections(["c001"], "s1")


class TestWindowTimes:
    """抽取时刻夹取：片头不低 0，片尾留出余量（防 seek 过 EOF 抽帧失败）。"""

    def test_clamped_at_start(self) -> None:
        times = window_times(0.01, 59.94, 10.0)
        assert len(times) == 7
        assert all(t >= 0.0 for t in times)
        assert times[0] == 0.0

    def test_clamped_before_eof(self) -> None:
        # 片尾候选：所有时刻 ≤ duration − 1.5/fps
        times = window_times(9.98, 59.94, 10.0)
        assert max(times) <= 10.0 - 1.5 / 59.94 + 1e-9

    def test_middle_unclamped(self) -> None:
        times = window_times(5.0, 60.0, 20.0)
        assert times[0] == pytest.approx(5.0 - 3 / 60.0)
        assert times[-1] == pytest.approx(5.0 + 3 / 60.0)


class TestApplyFilename:
    """apply 落盘命名：照片_XXX_视频序号_时刻.jpg。"""

    def test_format(self) -> None:
        assert apply_filename(1, 23, 12.34) == "照片_001_v023_t0012.3.jpg"

    def test_zero_padded(self) -> None:
        name = apply_filename(7, 3, 0.5)
        assert name.startswith("照片_007_v003_t0000.5")
        assert name.endswith(".jpg")
