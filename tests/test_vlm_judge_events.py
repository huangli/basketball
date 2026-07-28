"""vlm_judge_events 事件级判定单元测试（不碰网络/真帧）。

覆盖：真值对齐（匹配/2.0s 边界/负例计数/未匹配）、评估聚合（合成缓存→分布与
两种策略估算、token 汇总、正例判 NO 清单）、协议指纹变更整包作废、
裸 YES 降级沿用 test_vlm_filter.normalize_verdict。
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

import test_vlm_filter as tvf
import vlm_judge_events as vje


def _ev(key: str, src: str = "a.mp4", t0: float = 10.0) -> dict[str, Any]:
    return {"key": key, "fid": key.split("#")[0], "src_file": src, "anchor_t0": t0}


def _goal(file: str = "a.mp4", t: float = 10.0, status: str = "confirmed") -> dict[str, Any]:
    return {"file": file, "anchor_time": t, "status": status}


def test_match_basic_and_negative_count() -> None:
    # Arrange：3 事件，1 条真值匹配 e1
    events = [_ev("f#e1", t0=10.0), _ev("f#e2", t0=30.0), _ev("g#e1", src="b.mp4", t0=10.0)]
    goals = [_goal(t=10.5)]
    # Act
    pos_map, unmatched = vje.match_goals_to_events(events, goals)
    # Assert：同文件且 2s 内最近者命中；不同 src_file 不命中
    assert pos_map == {"f#e1": 0}
    assert unmatched == []


def test_match_boundary_tol_inclusive() -> None:
    # Arrange：恰好 2.0s 差
    events = [_ev("f#e1", t0=10.0)]
    # Act / Assert：<=2.0 含边界
    pos_map, unmatched = vje.match_goals_to_events(events, [_goal(t=12.0)])
    assert pos_map == {"f#e1": 0}
    assert unmatched == []
    # Act / Assert：2.01s 超出容差
    pos_map2, unmatched2 = vje.match_goals_to_events(events, [_goal(t=12.01)])
    assert pos_map2 == {}
    assert unmatched2 == [0]


def test_match_picks_nearest_event() -> None:
    # Arrange：同文件两事件都在容差内，取更近者
    events = [_ev("f#e1", t0=10.0), _ev("f#e2", t0=10.5)]
    # Act
    pos_map, _ = vje.match_goals_to_events(events, [_goal(t=10.4)])
    # Assert
    assert pos_map == {"f#e2": 0}


def test_evaluate_aggregation_and_strategies() -> None:
    # Arrange：4 事件（2 正例：1 confirmed 1 rejected；2 负例）
    events = [
        _ev("f#e1", t0=10.0),
        _ev("f#e2", t0=20.0),
        _ev("f#e3", t0=30.0),
        _ev("f#e4", t0=40.0),
    ]
    goals = [_goal(t=10.0, status="confirmed"), _goal(t=20.0, status="rejected")]
    cache = {
        "f#e1": {"answer": "YES", "usage": {"prompt_tokens": 100, "completion_tokens": 5}},
        "f#e2": {"answer": "NO", "usage": {"prompt_tokens": 200, "completion_tokens": 6}},
        "f#e3": {"answer": "UNCLEAR", "usage": {"prompt_tokens": 300, "completion_tokens": 7}},
        # f#e4 未判 → PENDING，无 usage
    }
    # Act
    r = vje.evaluate(events, goals, cache)
    # Assert：对齐计数
    assert r["n_events"] == 4
    assert r["n_pos"] == 2
    assert r["n_neg"] == 2
    # Assert：分布
    assert r["pos"]["YES"] == 1
    assert r["pos"]["NO"] == 1
    assert r["confirmed"]["YES"] == 1
    assert r["confirmed"]["NO"] == 0  # rejected 不计 confirmed
    assert r["neg"]["UNCLEAR"] == 1
    assert r["neg"]["PENDING"] == 1
    # Assert：正例判 NO 清单（召回事故必须可见）
    assert r["pos_no"] == ["f#e2"]
    # Assert：策略估算（a 只看 UNCLEAR=1；b 看 YES+UNCLEAR=2）
    assert r["strategy_a_human"] == 1
    assert r["strategy_b_human"] == 2
    # Assert：token 汇总
    assert r["in_tokens"] == 600
    assert r["out_tokens"] == 18
    assert r["unmatched_goals"] == []


def test_evaluate_reports_unmatched_goal() -> None:
    # Arrange：真值无对应事件
    r = vje.evaluate([_ev("f#e1", t0=10.0)], [_goal(t=99.0)], {})
    # Assert
    assert r["n_pos"] == 0
    assert len(r["unmatched_goals"]) == 1


def test_protocol_fp_changes_with_model() -> None:
    # Arrange / Act / Assert：MODEL 是指纹成分
    assert vje.protocol_fp("k3") != vje.protocol_fp("k2.6")
    assert len(vje.protocol_fp("k3")) == 12


def test_cache_roundtrip_and_protocol_invalidation(tmp_path: pathlib.Path) -> None:
    # Arrange
    path = str(tmp_path / "cache.json")
    cache = {"f#e1": {"answer": "YES", "usage": None, "raw": "x"}}
    # Act
    vje.save_cache(path, cache, "fp_A")
    # Assert：同指纹命中
    assert vje.load_cache(path, "fp_A") == cache
    # Assert：指纹变更整包作废
    assert vje.load_cache(path, "fp_B") == {}
    # Assert：损坏文件不抛错，空缓存重开
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert vje.load_cache(str(tmp_path / "bad.json"), "fp_A") == {}
    # Assert：缺失文件空缓存
    assert vje.load_cache(str(tmp_path / "none.json"), "fp_A") == {}


def test_bare_yes_downgrade_reused() -> None:
    # Arrange：事件级判定沿用 test_vlm_filter 的裸 YES 降级规则
    res = {"answer": "YES", "usage": None, "raw": "YES"}
    # Act / Assert
    assert tvf.normalize_verdict(res)["answer"] == "UNCLEAR"
    assert len(res["raw"]) < tvf.BARE_YES_MAX_RAW


def test_prompt_differs_only_in_frame_phrasing() -> None:
    # Arrange / Act / Assert：事件级 PROMPT 与候选级仅首句帧数表述不同
    assert vje.PROMPT != tvf.PROMPT
    assert "连续四帧" in vje.PROMPT
    assert "连续三帧" not in vje.PROMPT
    # 判定规则原文保留
    assert "禁止只凭球员跑动、攻防转换节奏等场面线索推断进球" in vje.PROMPT
    assert "最后一行只输出 YES、NO 或 UNCLEAR 之一" in vje.PROMPT


def test_load_events_schema_error(tmp_path: pathlib.Path) -> None:
    # Arrange：缺必填字段
    bad = tmp_path / "idx.json"
    bad.write_text('{"events": [{"key": "f#e1"}]}', encoding="utf-8")
    # Act / Assert：schema 损坏必须显式失败（rules.md §0.2）
    with pytest.raises(vje.SchemaError):
        vje.load_events(str(bad))


def test_renormalize_cache_demotes_bare_and_fallback_no() -> None:
    # Arrange：裸 NO、无筐回退 NO、带分析 NO、正常 YES 各一
    cache: dict[str, Any] = {
        "f#e1": {"answer": "NO", "usage": None, "raw": "NO"},
        "f#e2": {"answer": "NO", "usage": None, "raw": "四帧未见篮筐，按规则1判 NO。"},
        "f#e3": {"answer": "NO", "usage": None, "raw": "四帧未见篮筐，按规则1判 NO。"},
        "f#e4": {
            "answer": "YES",
            "usage": None,
            "raw": "第3帧清楚看到球穿过篮网，篮网被撑开。\nYES",
        },
    }
    # Act：f#e2 是无筐回退事件
    out, n = vje.renormalize_cache(cache, {"f#e2"})
    # Assert：裸 NO(e1)与回退 NO(e2)降级；带分析非回退 NO(e3)保留；YES 不动；降级计数 2
    assert out["f#e1"]["answer"] == "UNCLEAR"
    assert out["f#e2"]["answer"] == "UNCLEAR"
    assert out["f#e3"]["answer"] == "NO"
    assert out["f#e4"]["answer"] == "YES"
    assert n == 2
    # 原始缓存不被修改
    assert cache["f#e1"]["answer"] == "NO"


def test_demote_fallback_no_only_touches_fallback_no() -> None:
    # Arrange / Act / Assert
    assert vje.demote_fallback_no({"answer": "NO"}, True)["answer"] == "UNCLEAR"
    assert vje.demote_fallback_no({"answer": "NO"}, False)["answer"] == "NO"
    assert vje.demote_fallback_no({"answer": "YES"}, True)["answer"] == "YES"


def test_fallback_keys_covers_empty_track_and_missing() -> None:
    # Arrange：有 track / track 空但有 anchor（detected=False 不可信）/ 无筐事件
    events = [{"key": "f#e1"}, {"key": "f#e2"}, {"key": "f#e3"}]
    hoops_by_key = {
        "f#e1": {"key": "f#e1", "track": [[0.0, 100, 100, "det"]]},
        "f#e2": {"key": "f#e2", "track": [], "anchor": [1319, 774]},
    }
    # Act / Assert：仅 f#e1 可信
    assert vje.fallback_keys(events, hoops_by_key) == {"f#e2", "f#e3"}
