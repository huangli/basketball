"""build_highlight._validate_goals 单元测试（goals.json schema 校验）。

覆盖：合法通过、非 confirmed 过滤、未知 status 跳过、各类结构损坏抛 SchemaError；
parse_argv 的 --out 尺寸注入（默认 1440x1080）；scale_pad_filter 滤镜串。
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from build_highlight import _validate_goals, parse_argv, scale_pad_filter
from errors import SchemaError

_PATH = "work/pilot/goals.json"


def _goal(**over: object) -> dict[str, Any]:
    """构造一条合法 confirmed 记录，按字段覆盖。"""
    base: dict[str, Any] = {
        "file": "a.MP4",
        "status": "confirmed",
        "anchor_time": 10.0,
        "clip_start": 6.0,
        "clip_end": 12.0,
    }
    base.update(over)
    return base


def test_valid_confirmed_passes() -> None:
    # Arrange
    data = {"session": "s", "goals": [_goal()]}
    # Act
    confirmed = _validate_goals(data, _PATH)
    # Assert
    assert len(confirmed) == 1
    assert confirmed[0]["file"] == "a.MP4"


def test_non_confirmed_status_filtered_out() -> None:
    # Arrange
    data = {"goals": [_goal(status="candidate"), _goal(status="removed")]}
    # Act
    confirmed = _validate_goals(data, _PATH)
    # Assert
    assert confirmed == []


def test_unknown_status_skipped_with_warning() -> None:
    # Arrange：拼错的 status 不应炸掉整批，但会被跳过（WARNING 由 caplog 之外保证）
    data = {"goals": [_goal(status="confirm"), _goal()]}
    # Act
    confirmed = _validate_goals(data, _PATH)
    # Assert：拼错条跳过，合法条保留
    assert len(confirmed) == 1


def test_top_level_not_dict_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="顶层"):
        _validate_goals([1, 2], _PATH)


def test_goals_not_list_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="goals"):
        _validate_goals({"goals": {}}, _PATH)


def test_status_not_str_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="status"):
        _validate_goals({"goals": [_goal(status=None)]}, _PATH)


def test_confirmed_missing_file_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(SchemaError, match="file"):
        _validate_goals({"goals": [_goal(file="")]}, _PATH)


def test_confirmed_bool_time_raises() -> None:
    # Arrange：bool 是 int 子类，必须显式排除
    with pytest.raises(SchemaError, match="anchor_time"):
        _validate_goals({"goals": [_goal(anchor_time=True)]}, _PATH)


def test_confirmed_bad_interval_raises() -> None:
    # Arrange：anchor 落在 [clip_start, clip_end] 之外（标注错误）
    with pytest.raises(SchemaError, match="时间区间"):
        _validate_goals({"goals": [_goal(anchor_time=99.0)]}, _PATH)


def test_parse_argv_out_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(sys, "argv", ["build_highlight.py", "--goals", "g.json"])
    # Act
    _, _, _, out_w, out_h = parse_argv()
    # Assert：默认保持 4:3 老素材尺寸
    assert (out_w, out_h) == (1440, 1080)


def test_parse_argv_out_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(
        sys, "argv", ["build_highlight.py", "--goals", "g.json", "--out", "1920x1080"]
    )
    # Act
    _, _, _, out_w, out_h = parse_argv()
    # Assert：16:9 场次注入 1920x1080
    assert (out_w, out_h) == (1920, 1080)


def test_scale_pad_filter_uses_given_dims() -> None:
    # Arrange / Act
    vf = scale_pad_filter(1920, 1080)
    # Assert
    assert "scale=1920:1080" in vf
    assert "pad=1920:1080" in vf
