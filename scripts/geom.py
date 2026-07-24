"""几何工具：轴对齐边界框与交并比计算。

输入：YOLO 检测输出的 xyxy 像素坐标。
输出：Box 对象及其 IoU。
依赖：仅标准库（dataclasses）。
典型调用：``from geom import Box, iou``（scripts/ 已通过 pyproject.toml 加入 pythonpath）。

说明：本模块是 rules.md「正确写法」的标杆样本，对照
``scripts/batch_detect_v2.py`` 中无类型/``;``串/魔法数字的反例。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Box:
    """轴对齐边界框（像素坐标，左上角 / 右下角）。"""

    x1: int
    y1: int
    x2: int
    y2: int

    def __post_init__(self) -> None:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError(f"非法框 {self}：需 x2 > x1 且 y2 > y1")

    @property
    def cx(self) -> int:
        """中心 X 坐标（像素）。"""
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        """中心 Y 坐标（像素）。"""
        return (self.y1 + self.y2) // 2

    @property
    def area(self) -> int:
        """面积（平方像素）。"""
        return (self.x2 - self.x1) * (self.y2 - self.y1)


def iou(a: Box, b: Box) -> float:
    """计算两个边界框的交并比（Intersection over Union）。

    Args:
        a: 框 A。
        b: 框 B。

    Returns:
        IoU，取值 ``[0.0, 1.0]``；两框无相交返回 ``0.0``。

    Raises:
        ValueError: 输入框非法（由 Box 构造时校验，正常不会触发）。
    """
    inter_x1 = max(a.x1, b.x1)
    inter_y1 = max(a.y1, b.y1)
    inter_x2 = min(a.x2, b.x2)
    inter_y2 = min(a.y2, b.y2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    union = a.area + b.area - intersection
    return intersection / union
