"""vlm_filter 三值判定相关单元测试（不跑真 VLM 调用）。

覆盖：parse_answer 三值解析（含 NOT CLEAR 陷阱）、find_event 事件归属、
hoop_centers 逐帧筐位选取。
"""

from __future__ import annotations

from typing import Any

from vlm_filter import find_event, hoop_centers, normalize_verdict, parse_answer


def test_parse_answer_exact_last_line_yes() -> None:
    # Arrange / Act / Assert
    assert parse_answer("第2帧球在网中。\nYES") == "YES"


def test_parse_answer_exact_no() -> None:
    assert parse_answer("分析\nNO") == "NO"


def test_parse_answer_exact_unclear() -> None:
    assert parse_answer("关键帧看不到球。\nUNCLEAR") == "UNCLEAR"


def test_parse_answer_not_clear_maps_to_unclear() -> None:
    # Arrange：变体 "NOT CLEAR"，子串含 "NO" 但应归 UNCLEAR
    # Act / Assert
    assert parse_answer("看不清\nNOT CLEAR") == "UNCLEAR"


def test_parse_answer_garbage_returns_err() -> None:
    assert parse_answer("无法回答这个问题") == "ERR"


def _ev(window: list[float], detected: bool = True) -> dict[str, Any]:
    return {
        "window": window,
        "detected": detected,
        "track": [[2.0, 10, 10, "det"], [3.0, 20, 20, "det"]] if detected else [],
    }


def test_find_event_hits_window() -> None:
    # Arrange
    events = [_ev([2.0, 6.0])]
    # Act / Assert
    assert find_event(events, 3.0) is events[0]
    assert find_event(events, 7.0) is None


def test_find_event_skips_undetected() -> None:
    # Arrange
    events = [_ev([2.0, 6.0], detected=False)]
    # Act / Assert
    assert find_event(events, 3.0) is None


def test_hoop_centers_picks_nearest_sec_point() -> None:
    # Arrange：track 两点（2.0/3.0 秒），STRIP_OFFSETS=(-1,0,1)
    ev = _ev([0.0, 9.0])
    # Act：t0=2.4 → 目标时刻 1.4/2.4/3.4
    centers = hoop_centers(ev, 2.4)
    # Assert：1.4→2.0 点，2.4→2.0 点（|0.4|<|0.6|），3.4→3.0 点
    assert centers == [(10, 10), (10, 10), (20, 20)]


def test_hoop_centers_empty_track_returns_none() -> None:
    # Arrange
    ev = _ev([0.0, 9.0], detected=False)
    # Act / Assert
    assert hoop_centers(ev, 2.0) is None


def test_normalize_verdict_bare_yes_downgrades() -> None:
    # Arrange：raw 仅 "YES"（3 字符 < 15）
    res = {"answer": "YES", "usage": None, "raw": "YES"}
    # Act
    out = normalize_verdict(res)
    # Assert
    assert out["answer"] == "UNCLEAR"
    assert out["raw"] == "YES"  # 原始回复保留可追溯


def test_normalize_verdict_analyzed_yes_kept() -> None:
    # Arrange：带证据分析的 YES
    res = {"answer": "YES", "usage": None, "raw": "第3帧球在网中，篮网被撑开。\nYES"}
    # Act / Assert
    assert normalize_verdict(res)["answer"] == "YES"


def test_normalize_verdict_other_answers_untouched() -> None:
    # Arrange / Act / Assert：UNCLEAR/ERR 不受影响（裸 NO 已改为降级，见下）
    for ans in ("UNCLEAR", "ERR"):
        assert normalize_verdict({"answer": ans, "raw": ""})["answer"] == ans


def test_normalize_verdict_bare_no_downgrades() -> None:
    # Arrange：raw 仅 "NO"（2 字符 < 15）——无证据终态会把真球挡在人工审核外
    res = {"answer": "NO", "usage": None, "raw": "NO"}
    # Act
    out = normalize_verdict(res)
    # Assert
    assert out["answer"] == "UNCLEAR"
    assert out["raw"] == "NO"  # 原始回复保留可追溯


def test_normalize_verdict_analyzed_no_kept() -> None:
    # Arrange：带分析的 NO（四帧均无投篮动作……\nNO）
    res = {"answer": "NO", "usage": None, "raw": "四帧中球始终在三分线外运球，无投篮动作。\nNO"}
    # Act / Assert
    assert normalize_verdict(res)["answer"] == "NO"
