"""gen_review_clips._validate_candidates 单元测试（candidates.json schema 校验）。

覆盖：合法通过、顶层非列表、记录非对象、缺字段、数值字段为 bool 等失败场景。
"""

from __future__ import annotations

from typing import Any

import pytest

from errors import SchemaError
from gen_review_clips import _validate_candidates

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
