"""build_highlight 单元测试（goals.json schema 校验 + spec 组合真值表 8 分支）。

覆盖：_validate_goals 合法通过、非 confirmed 过滤、未知 status 跳过、各类结构
损坏抛 SchemaError；parse_argv 的 --out/--roster/--team 注入；scale_pad_filter
滤镜串；select_goals 真值表（①全员 ②旧 scorer 精确匹配+0 命中 WARNING
③全归属球+未归属 WARNING ④tag|name 解析输出名用 tag ⑤队伍合集 ⑥互斥
⑦无 roster 给 --team ⑧--team 便服）；require_confirmed 拒收未确认 roster。
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import pytest

from build_highlight import (
    _validate_goals,
    parse_argv,
    require_confirmed,
    scale_pad_filter,
    select_goals,
)
from errors import BasketballPipelineError, SchemaError
from roster import Player, Roster, format_key

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
    _, _, _, out_w, out_h, roster, team = parse_argv()
    # Assert：默认保持 4:3 老素材尺寸；roster/team 默认空
    assert (out_w, out_h) == (1440, 1080)
    assert roster == ""
    assert team == ""


def test_parse_argv_out_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(
        sys, "argv", ["build_highlight.py", "--goals", "g.json", "--out", "1920x1080"]
    )
    # Act
    _, _, _, out_w, out_h, _, _ = parse_argv()
    # Assert：16:9 场次注入 1920x1080
    assert (out_w, out_h) == (1920, 1080)


def test_parse_argv_roster_team(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_highlight.py", "--goals", "g.json", "--roster", "r.json", "--team", "黑"],
    )
    # Act
    _, _, _, _, _, roster, team = parse_argv()
    # Assert
    assert roster == "r.json"
    assert team == "黑"


def test_scale_pad_filter_uses_given_dims() -> None:
    # Arrange / Act
    vf = scale_pad_filter(1920, 1080)
    # Assert
    assert "scale=1920:1080" in vf
    assert "pad=1920:1080" in vf


def _roster(
    players: tuple[Player, ...] = (
        Player(tag="黑21", name="大斌", team="黑"),
        Player(tag="白22", name="", team="白"),
        Player(tag="灰T恤-A", name="", team="便服"),
    ),
    assignments: dict[str, str] | None = None,
    confirmed: bool = True,
) -> Roster:
    """构造一份 Roster 结构体（默认 3 球员：黑/白/便服各一）。"""
    if assignments is None:
        assignments = {format_key("a.MP4", 10.0): "黑21", format_key("b.MP4", 3.0): "白22"}
    return Roster(session="s", confirmed=confirmed, players=players, assignments=assignments)


class TestSelectGoalsTruthTable:
    """spec 组合真值表 8 分支逐一覆盖。"""

    def test_branch1_no_roster_no_filter_all(self) -> None:
        # Arrange：两条 confirmed
        goals = [_goal(), _goal(file="b.MP4", anchor_time=3.0, clip_start=0.0, clip_end=5.0)]
        # Act
        selected, stem = select_goals(goals, None, "", "")
        # Assert：全员现状不变
        assert len(selected) == 2
        assert stem == "个人_全员_进球合集"

    def test_branch2_legacy_scorer_exact_match(self) -> None:
        # Arrange：goals.scorer 旧字段精确匹配
        goals = [
            _goal(scorer="大斌"),
            _goal(file="b.MP4", anchor_time=3.0, clip_start=0.0, clip_end=5.0, scorer=""),
        ]
        # Act
        selected, stem = select_goals(goals, None, "大斌", "")
        # Assert
        assert len(selected) == 1
        assert stem == "个人_大斌_进球合集"

    def test_branch2_zero_hit_warns_roster_hint(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange / Act
        with caplog.at_level(logging.WARNING):
            selected, _ = select_goals([_goal()], None, "大斌", "")
        # Assert：0 命中 WARNING 提示改用 --roster
        assert selected == []
        assert any("--roster" in r.message for r in caplog.records)

    def test_branch3_roster_no_filter_assigned_only(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange：a.MP4@10.0 已归属黑21，c.MP4 未归属
        goals = [
            _goal(),
            _goal(file="c.MP4", anchor_time=3.0, clip_start=0.0, clip_end=5.0),
        ]
        # Act
        with caplog.at_level(logging.WARNING):
            selected, stem = select_goals(goals, _roster(), "", "")
        # Assert：只出已归属球；未归属 WARNING 跳过
        assert [g["file"] for g in selected] == ["a.MP4"]
        assert stem == "个人_全员_进球合集"
        assert any("未归属" in r.message for r in caplog.records)

    def test_branch4_scorer_resolved_by_name(self) -> None:
        # Arrange：--scorer 给名字，roster 内 name 命中
        goals = [_goal(), _goal(file="b.MP4", anchor_time=3.0, clip_start=0.0, clip_end=5.0)]
        # Act
        selected, stem = select_goals(goals, _roster(), "大斌", "")
        # Assert：输出名用解析后 tag（不用 --scorer 原值）
        assert [g["file"] for g in selected] == ["a.MP4"]
        assert stem == "个人_黑21_进球合集"

    def test_branch4_scorer_resolved_by_tag(self) -> None:
        # Arrange / Act：tag 直接命中
        selected, stem = select_goals([_goal()], _roster(), "黑21", "")
        # Assert
        assert len(selected) == 1
        assert stem == "个人_黑21_进球合集"

    def test_branch4_scorer_not_in_roster_raises(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(BasketballPipelineError, match="查无此人"):
            select_goals([_goal()], _roster(), "无名氏", "")

    def test_branch5_team_highlight(self) -> None:
        # Arrange：a.MP4→黑21（黑），b.MP4→白22（白）
        goals = [_goal(), _goal(file="b.MP4", anchor_time=3.0, clip_start=0.0, clip_end=5.0)]
        # Act
        selected, stem = select_goals(goals, _roster(), "", "黑")
        # Assert
        assert [g["file"] for g in selected] == ["a.MP4"]
        assert stem == "队伍_黑_进球集锦"

    def test_branch6_scorer_team_mutually_exclusive(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(BasketballPipelineError, match="互斥"):
            select_goals([_goal()], _roster(), "大斌", "黑")

    def test_branch7_team_without_roster_raises(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(BasketballPipelineError, match="无法分队"):
            select_goals([_goal()], None, "", "黑")

    def test_branch8_team_casual_raises(self) -> None:
        # Arrange / Act / Assert：便服不进分队合集（有/无 roster 都报错）
        with pytest.raises(BasketballPipelineError, match="便服"):
            select_goals([_goal()], _roster(), "", "便服")
        with pytest.raises(BasketballPipelineError):
            select_goals([_goal()], None, "", "便服")


class TestRequireConfirmed:
    """--roster 未 confirmed=true 拒收（spec 真值表）。"""

    def test_confirmed_passes(self) -> None:
        # Arrange / Act / Assert：不抛即通过
        require_confirmed(_roster(confirmed=True), "r.json")

    def test_unconfirmed_rejected(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(BasketballPipelineError, match="confirmed"):
            require_confirmed(_roster(confirmed=False), "r.json")
