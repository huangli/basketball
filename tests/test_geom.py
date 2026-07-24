"""geom.Box / iou 单元测试。

结构遵循 AAA（Arrange / Act / Assert），用 fixture（见 conftest.py）解耦数据准备。
"""

from __future__ import annotations

import pathlib

import pytest

from geom import Box, iou


def test_iou_disjoint_boxes_returns_zero() -> None:
    # Arrange
    a = Box(0, 0, 10, 10)
    b = Box(20, 20, 30, 30)
    # Act
    score = iou(a, b)
    # Assert
    assert score == 0.0


def test_iou_identical_boxes_returns_one() -> None:
    # Arrange
    a = Box(0, 0, 10, 10)
    # Act
    score = iou(a, a)
    # Assert
    assert score == pytest.approx(1.0)


def test_iou_partial_overlap(box_unit: Box) -> None:
    # Arrange: 交集 5x5=25，并集 100+100-25=175
    b = Box(5, 5, 15, 15)
    # Act
    score = iou(box_unit, b)
    # Assert
    assert score == pytest.approx(25 / 175)


def test_box_rejects_degenerate_dimensions() -> None:
    # Arrange / Act / Assert：零面积框应在构造时被拒绝
    with pytest.raises(ValueError):
        Box(10, 10, 0, 0)


def test_box_center_and_area(box_unit: Box) -> None:
    # Arrange / Act / Assert
    assert box_unit.cx == 5
    assert box_unit.cy == 5
    assert box_unit.area == 100


def test_tmp_work_dir_is_writable(tmp_work_dir: pathlib.Path) -> None:
    # Arrange / Act
    target = tmp_work_dir / "goal.json"
    target.write_text("{}", encoding="utf-8")
    # Assert
    assert target.exists()
