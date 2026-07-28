"""gen_label_page 单元测试：HTML 渲染与最新索引自动发现。

覆盖：build_html 内联事件与场次、无"大斌"专属按钮、含位置记忆与
"跳到未标"控件；find_latest_index 按 mtime 取最新、无匹配返回 None。
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

from gen_label_page import build_html, find_latest_index


def _event(key: str = "f1#e0") -> dict[str, Any]:
    """构造一条合法事件记录。"""
    return {
        "key": key,
        "fid": "f1",
        "event_idx": 0,
        "clip": "clips/a.mp4",
        "clip_wide": "clips/a_wide.mp4",
        "src_file": "a.mp4",
        "anchor_t0": 1.0,
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
