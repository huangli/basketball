"""gen_review_clips._validate_candidates / find_source 单元测试。

覆盖：candidates.json schema 校验（合法通过、顶层非列表、记录非对象、
缺字段、数值字段为 bool）；find_source 的 --srcdir 直找与缺失。
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from errors import SchemaError
from gen_review_clips import (
    _validate_candidates,
    adaptive_crop,
    event_verdict,
    find_event_track,
    find_source,
)

_PATH = "work/pilot/candidates.json"


def _cand(**over: object) -> dict[str, Any]:
    """构造一条合法候选记录，按字段覆盖。"""
    base: dict[str, Any] = {
        "fid": "0011",
        "label": "#1",
        "t0": 18.2,
        "ac": 0.31,
        "cx": 960,
        "cy": 540,
    }
    base.update(over)
    return base


def test_valid_candidates_pass() -> None:
    # Arrange
    records = [_cand(), _cand(fid="0020", label="#3")]
    # Act
    result = _validate_candidates(records, _PATH)
    # Assert
    assert result == records


def test_top_level_not_list_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="顶层"):
        _validate_candidates({"cands": []}, _PATH)


def test_record_not_dict_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="第1条"):
        _validate_candidates([_cand(), 42], _PATH)


def test_missing_str_field_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="fid"):
        _validate_candidates([_cand(fid=None)], _PATH)


def test_bool_num_field_raises() -> None:
    # Arrange：bool 是 int 子类，必须显式排除
    with pytest.raises(SchemaError, match="t0"):
        _validate_candidates([_cand(t0=False)], _PATH)


def test_find_source_with_srcdir(tmp_path: pathlib.Path) -> None:
    # Arrange：dji 命名，fid 即主名
    (tmp_path / "dji_mimo_x.mp4").write_bytes(b"")
    # Act
    found = find_source("dji_mimo_x", str(tmp_path))
    # Assert
    assert found is not None
    assert found.endswith("dji_mimo_x.mp4")


def test_find_source_srcdir_missing_returns_none(tmp_path: pathlib.Path) -> None:
    # Arrange / Act / Assert：缺失返回 None（调用方记 ERROR 跳过），不抛异常
    assert find_source("nope", str(tmp_path)) is None


def test_adaptive_crop_bbox_with_margin() -> None:
    # Arrange：img 系轨迹两点 (100,100)-(200,150) → 原片系 ×2 = (200,200)-(400,300)
    track = [[0.0, 100, 100, "det"], [1.0, 200, 150, "det"]]
    # Act
    crop_x, crop_y, side = adaptive_crop(track, 3840, 2160)
    # Assert：span 200x100 + margin 600 = 800 < 下限 1200 → side=1200；中心 (300,250)
    assert side == 1200
    assert crop_x == 0  # 300-600<0 → clamp
    assert crop_y == 0


def test_adaptive_crop_caps_at_orig_short_side() -> None:
    # Arrange：轨迹横贯全场
    track = [[0.0, 10, 10, "det"], [1.0, 1900, 1000, "det"]]
    # Act
    _, _, side = adaptive_crop(track, 3840, 2160)
    # Assert：上限 = 原片短边 2160
    assert side == 2160


def test_find_event_track_hit_and_miss() -> None:
    # Arrange
    events = [
        {"window": [2.0, 6.0], "detected": True, "track": [[2.0, 10, 10, "det"]]},
        {"window": [8.0, 9.0], "detected": False, "track": []},
    ]
    # Act / Assert
    assert find_event_track(events, 3.0) == [[2.0, 10, 10, "det"]]
    assert find_event_track(events, 8.5) is None  # detected=false 不命中
    assert find_event_track(events, 99.0) is None


def test_event_verdict_four_branches() -> None:
    # Arrange
    members = [{"fid": "f1", "label": "#1"}, {"fid": "f1", "label": "#2"}]
    # Act / Assert：YES 优先；无 YES 有 UNCLEAR 为 ?；全 NO 为 N；未判为 ""
    assert event_verdict(members, {"f1#2@420": {"answer": "YES"}}) == "VLM:Y"
    assert event_verdict(members, {"f1#1@420": {"answer": "UNCLEAR"}}) == "VLM:?"
    assert (
        event_verdict(
            members,
            {"f1#1@420": {"answer": "NO"}, "f1#1@630": {"answer": "UNCLEAR"}},
        )
        == "VLM:?"
    )
    assert event_verdict(members, {"f1#1@420": {"answer": "NO"}}) == "VLM:N"
    assert event_verdict(members, {}) == ""
