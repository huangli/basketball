"""gen_label_page 单元测试：HTML 渲染与最新索引自动发现。

覆盖：build_html 内联事件与场次、无"大斌"专属按钮、含位置记忆与
"跳到未标"控件；find_latest_index 按 mtime 取最新、无匹配返回 None。
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

from gen_label_page import assign_same_rally_groups, build_html, find_latest_index


def _event(key: str = "f1#e0", fid: str = "f1", anchor_t0: float = 1.0) -> dict[str, Any]:
    """构造一条合法事件记录。"""
    return {
        "key": key,
        "fid": fid,
        "event_idx": 0,
        "clip": "clips/a.mp4",
        "clip_wide": "clips/a_wide.mp4",
        "src_file": "a.mp4",
        "anchor_t0": anchor_t0,
        "verdict": "?",
    }


def test_build_html_inlines_events_and_session() -> None:
    # Arrange / Act
    html = build_html([_event()], "20260722")
    # Assert
    assert '"key": "f1#e0"' in html
    assert 'const SESSION = "20260722";' in html


def test_build_html_has_no_dabin_button() -> None:
    # Arrange / Act
    html = build_html([_event()], "s")
    # Assert（大斌按钮已下线；导出仍兼容历史 scorer 字段，模板不含该文案）
    assert "大斌" not in html


def test_build_html_restores_position_and_has_jump_button() -> None:
    # Arrange / Act
    html = build_html([_event()], "s")
    # Assert
    assert 'id="toun"' in html
    assert "POSKEY" in html
    assert "localStorage.getItem(POSKEY)" in html


def test_find_latest_index_picks_newest(tmp_path: pathlib.Path) -> None:
    # Arrange：两个场次的索引，review_v2 修改时间更新
    old = tmp_path / "work" / "s1" / "review_v1"
    new = tmp_path / "work" / "s1" / "review_v2"
    for d in (old, new):
        d.mkdir(parents=True)
        (d / "events_index.json").write_text("{}", encoding="utf-8")
    os.utime(old / "events_index.json", (1_600_000_000, 1_600_000_000))
    os.utime(new / "events_index.json", (1_700_000_000, 1_700_000_000))
    # Act
    got = find_latest_index(str(tmp_path / "work"))
    # Assert
    assert got is not None
    assert "review_v2" in got


def test_find_latest_index_returns_none_when_empty(tmp_path: pathlib.Path) -> None:
    # Arrange / Act / Assert
    assert find_latest_index(str(tmp_path / "work")) is None


# 审核窗口口径：前 2s 后 4s（gen_review_clips.CLIP_BEFORE/AFTER_SEC），
# 相邻事件 anchor 差 ≤ 6s 则窗口重叠视为疑似同回合（传递闭包）。


def test_groups_no_overlap_stay_ungrouped() -> None:
    # Arrange：同 fid 两事件 anchor 差 19s，远超 6s 窗口
    events = [_event("f1#e0", anchor_t0=1.0), _event("f1#e1", anchor_t0=20.0)]
    # Act / Assert
    assert assign_same_rally_groups(events) == {}


def test_groups_pair_overlap_same_group() -> None:
    # Arrange：anchor 差 3s ≤ 6s，窗口重叠（批次 3 同球对差值 2.3~4.2s 模式）
    events = [_event("f1#e0", anchor_t0=1.0), _event("f1#e1", anchor_t0=4.0)]
    # Act
    groups = assign_same_rally_groups(events)
    # Assert
    assert groups == {"f1#e0": 1, "f1#e1": 1}


def test_groups_transitive_closure() -> None:
    # Arrange：1.0 与 9.0 不直接重叠（差 8s），但经 5.0 传递同组
    events = [
        _event("f1#e0", anchor_t0=1.0),
        _event("f1#e1", anchor_t0=5.0),
        _event("f1#e2", anchor_t0=9.0),
    ]
    # Act
    groups = assign_same_rally_groups(events)
    # Assert
    assert groups == {"f1#e0": 1, "f1#e1": 1, "f1#e2": 1}


def test_groups_never_cross_fid() -> None:
    # Arrange：不同 fid 即使 anchor 差 1s 也绝不混组
    # （跨文件同球识别是一期明确边界，见 docs/dedup-same-goal/spec.md）
    events = [_event("f1#e0", fid="f1", anchor_t0=1.0), _event("f2#e0", fid="f2", anchor_t0=2.0)]
    # Act / Assert
    assert assign_same_rally_groups(events) == {}


def test_groups_single_event_returns_empty() -> None:
    # Arrange / Act / Assert
    assert assign_same_rally_groups([_event()]) == {}


def test_groups_two_separate_groups_numbered_in_order() -> None:
    # Arrange：同 fid 四个事件成两组，组号按 anchor 升序递增
    events = [
        _event("f1#e0", anchor_t0=1.0),
        _event("f1#e1", anchor_t0=3.0),
        _event("f1#e2", anchor_t0=30.0),
        _event("f1#e3", anchor_t0=33.0),
    ]
    # Act
    groups = assign_same_rally_groups(events)
    # Assert
    assert groups == {"f1#e0": 1, "f1#e1": 1, "f1#e2": 2, "f1#e3": 2}
