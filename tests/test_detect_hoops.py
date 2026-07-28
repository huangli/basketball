"""detect_hoops 纯函数单元测试（选筐/追踪/插值），不跑真模型。

对应规格：多筐选离锚点最近；相邻帧跳变 >150px 截断；缺口 <=3 帧线性插值。
"""

from __future__ import annotations

from detect_hoops import interpolate_gaps, select_hoop, track_hoop


def test_select_hoop_picks_nearest_to_anchor() -> None:
    # Arrange：双筐（室内场两端）
    dets = [(800, 100), (100, 100)]
    # Act
    picked = select_hoop(dets, (95, 95))
    # Assert
    assert picked == (100, 100)


def test_select_hoop_empty_returns_none() -> None:
    # Arrange / Act / Assert
    assert select_hoop([], (100, 100)) is None


def test_track_hoop_follows_same_hoop_and_cuts_on_jump() -> None:
    # Arrange：前 4 帧同筐缓动，第 5 帧跳到远处（另一个筐/假筐）
    per_frame = [
        (0.0, [(800, 100), (100, 100)]),
        (0.2, []),
        (0.4, [(810, 100), (105, 103)]),
        (0.6, [(110, 104)]),
        (0.8, [(500, 500)]),
    ]
    # Act
    track = track_hoop(per_frame, anchor=(100, 100), anchor_sec=0.0)
    # Assert：截到跳变前，含起步帧在内 3 个 det 点，且始终在左侧筐
    assert [(p[0], p[1], p[2]) for p in track] == [
        (0.0, 100, 100),
        (0.4, 105, 103),
        (0.6, 110, 104),
    ]
    assert all(p[3] == "det" for p in track)


def test_track_hoop_walks_backward_from_anchor() -> None:
    # Arrange：锚点时刻在中间帧，向两侧都要连上
    per_frame = [
        (0.0, [(98, 100)]),
        (0.2, [(100, 100)]),
        (0.4, [(102, 100)]),
    ]
    # Act
    track = track_hoop(per_frame, anchor=(100, 100), anchor_sec=0.4)
    # Assert：从 0.4 起步，回连到 0.0
    assert [p[0] for p in track] == [0.0, 0.2, 0.4]


def test_track_hoop_no_detection_returns_empty() -> None:
    # Arrange：全窗口无检出
    per_frame = [(0.0, []), (0.2, [])]
    # Act / Assert
    assert track_hoop(per_frame, anchor=(1, 1), anchor_sec=0.0) == []


def test_interpolate_gaps_fills_short_gap() -> None:
    # Arrange：0.0 与 0.4 之间缺 1 帧（0.2）
    track = [(0.0, 100, 100, "det"), (0.4, 110, 104, "det")]
    all_secs = [0.0, 0.2, 0.4, 0.6]
    # Act
    out = interpolate_gaps(track, all_secs)
    # Assert：补 0.2 中点，标 interp
    assert len(out) == 3
    mid = out[1]
    assert mid[0] == 0.2
    assert mid[3] == "interp"
    assert mid[1] == 105
    assert mid[2] == 102


def test_interpolate_gaps_leaves_long_gap_open() -> None:
    # Arrange：缺口 9 帧（>3，云台转向，插值会造幽灵轨迹）
    track = [(0.0, 100, 100, "det"), (2.0, 400, 100, "det")]
    all_secs = [round(0.2 * i, 1) for i in range(11)]
    # Act
    out = interpolate_gaps(track, all_secs)
    # Assert：原样，不补
    assert out == track
