"""gen_scorer_page 单元测试（spec: docs/scorer/spec.md T4 认人确认页）。

覆盖：team_of_tag 前缀推队、parse_players 名单解析、merge_assignments 并集/
同键冲突、match_clip 4s 容差匹配与相对路径、build_entries 排序与无候选兜底、
build_html 内联数据与导出契约、main 端到端（tmp 目录写 scorer.html）；
--clusters 簇级确认（docs/scorer-cluster/spec.md）：clusters schema 校验、
build_cluster_map 归属与越界 key 跳过、cluster_id 注入与 unclustered→None、
build_page_clusters 过滤、簇区渲染与 node --check JS 语法校验；
--players-file 名单文件注入（docs/scorer-reid/spec.md Phase D）：合法名单解析、
坏 JSON/坏结构/非法队名 SchemaError、与 --players 互斥、号码预填链路命中。
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import subprocess

import pytest

from errors import BasketballPipelineError, SchemaError
from gen_scorer_page import (
    _validate_clusters,
    build_cluster_map,
    build_entries,
    build_html,
    build_page_clusters,
    load_players_file,
    main,
    match_clip,
    match_players_by_name,
    match_players_by_number,
    merge_assignments,
    opponent_of,
    parse_players,
    team_of_tag,
)
from roster import Player, format_key


def _goal(file: str = "a.mp4", anchor: float = 4.1) -> dict:
    """构造一条合法 confirmed 记录。"""
    return {
        "file": file,
        "anchor_time": anchor,
        "clip_start": max(0.0, anchor - 4.0),
        "clip_end": anchor + 2.0,
        "status": "confirmed",
        "scorer": "",
    }


def _candidate(
    file: str = "a.mp4",
    anchor: float = 4.1,
    status: str = "OK",
    crop: str = "a_t4.1.jpg",
    team_guess: str | None = "黑",
) -> dict:
    """构造一条合法候选记录（key 走 roster.format_key 契约）。"""
    return {
        "key": format_key(file, anchor),
        "file": file,
        "anchor_time": anchor,
        "status": status,
        "reason": "" if status == "OK" else "few_votes",
        "crop": crop,
        "team_guess": team_guess,
        "votes": 3,
        "total_votes": 10,
    }


def _event(src_file: str = "a.mp4", anchor_t0: float = 4.0, clip: str = "clips/a_e1.mp4") -> dict:
    """构造一条合法事件记录。"""
    return {
        "key": "a#e1",
        "fid": "a",
        "event_idx": 1,
        "clip": clip,
        "clip_wide": "clips/a_e1_wide.mp4",
        "src_file": src_file,
        "anchor_t0": anchor_t0,
        "verdict": "?",
    }


class TestOpponentOf:
    """对手队名派生：场次 ID 后缀；无后缀/空白后缀回退地平线（老场次历史口径）。"""

    def test_suffix(self) -> None:
        assert opponent_of("20260805_车百鼎") == "车百鼎"

    def test_no_suffix_fallback(self) -> None:
        assert opponent_of("20260722") == "地平线"

    def test_blank_suffix_fallback(self) -> None:
        assert opponent_of("20260722_") == "地平线"


class TestTeamOfTag:
    """标签前缀推队（页面 JS teamOfTag 同规则；对手队名由 opp 参数注入）。"""

    def test_prefix_teams(self) -> None:
        # Arrange / Act / Assert
        assert team_of_tag("黑21", "地平线") == "地平线"
        assert team_of_tag("白-熊志鹏", "地平线") == "半截篮"
        assert team_of_tag("灰T恤-A", "地平线") == "便服"

    def test_blue_prefix_maps_to_opponent_team(self) -> None:
        # Arrange / Act / Assert：蓝 → 对手队（蓝27 归对手系 2026-08-09 立哥口径）
        assert team_of_tag("蓝27", "地平线") == "地平线"

    def test_opponent_name_follows_opp_arg(self) -> None:
        # Arrange / Act / Assert：对手队名随 opp 走，不硬编码（2026-08-15 队名会话化）
        assert team_of_tag("黑21", "车百鼎") == "车百鼎"
        assert team_of_tag("蓝27", "车百鼎") == "车百鼎"


class TestParsePlayers:
    """--players 名单串解析。"""

    def test_tag_name_pairs(self) -> None:
        # Arrange / Act
        players = parse_players("黑21=大斌,白-熊志鹏=熊志鹏,白-小陈=小陈", "地平线")
        # Assert
        assert players == [
            Player(tag="黑21", name="大斌", team="地平线"),
            Player(tag="白-熊志鹏", name="熊志鹏", team="半截篮"),
            Player(tag="白-小陈", name="小陈", team="半截篮"),
        ]

    def test_name_optional_and_empty_spec(self) -> None:
        # Arrange / Act / Assert
        assert parse_players("", "地平线") == []
        assert parse_players("黑21", "地平线") == [Player(tag="黑21", name="", team="地平线")]

    def test_opp_arg_flows_to_team(self) -> None:
        # Arrange / Act / Assert：黑/蓝前缀队名 = opp 参数（队名会话化）
        players = parse_players("黑21,蓝27", "车百鼎")
        assert [p.team for p in players] == ["车百鼎", "车百鼎"]

    def test_missing_tag_raises(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError, match="tag"):
            parse_players("=大斌", "地平线")


# ---- --players-file 名单文件注入（docs/scorer-reid/spec.md Phase D） ----


def _write_players_file(tmp_path: pathlib.Path, payload: object) -> pathlib.Path:
    """把名单 payload 写成 JSON 文件，返回路径。"""
    path = tmp_path / "players.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class TestLoadPlayersFile:
    """--players-file 名单文件解析：与 roster.players 同构，复用 roster 校验。"""

    def test_valid_players_parsed(self, tmp_path: pathlib.Path) -> None:
        # Arrange：文件里的 team 以文件为准（不做前缀推定）
        path = _write_players_file(
            tmp_path,
            [
                {"tag": "白22-小朱", "name": "小朱", "team": "半截篮"},
                {"tag": "黑21-大斌", "name": "大斌", "team": "地平线"},
                {"tag": "灰T恤-A", "name": "", "team": "便服"},
            ],
        )
        # Act
        players = load_players_file(path)
        # Assert
        assert players == [
            Player(tag="白22-小朱", name="小朱", team="半截篮"),
            Player(tag="黑21-大斌", name="大斌", team="地平线"),
            Player(tag="灰T恤-A", name="", team="便服"),
        ]

    def test_bad_json_raises(self, tmp_path: pathlib.Path) -> None:
        # Arrange：文件内容不是合法 JSON
        path = tmp_path / "players.json"
        path.write_text("[{not json", encoding="utf-8")
        # Act / Assert
        with pytest.raises(SchemaError):
            load_players_file(path)

    def test_top_level_not_list_raises(self, tmp_path: pathlib.Path) -> None:
        # Arrange：顶层是对象而非数组（roster.json 整文件误传场景）
        path = _write_players_file(tmp_path, {"players": []})
        # Act / Assert
        with pytest.raises(SchemaError, match="数组"):
            load_players_file(path)

    def test_invalid_team_raises(self, tmp_path: pathlib.Path) -> None:
        # Arrange：team 空串（team 已放宽为任意非空 str，见 docs/session-opponent-name/spec.md）
        path = _write_players_file(tmp_path, [{"tag": "白22-小朱", "name": "小朱", "team": ""}])
        # Act / Assert
        with pytest.raises(SchemaError, match="team"):
            load_players_file(path)

    def test_duplicate_tag_raises(self, tmp_path: pathlib.Path) -> None:
        # Arrange：tag 重复（roster 契约同一校验）
        path = _write_players_file(
            tmp_path,
            [
                {"tag": "白22-小朱", "name": "小朱", "team": "半截篮"},
                {"tag": "白22-小朱", "name": "朱", "team": "半截篮"},
            ],
        )
        # Act / Assert
        with pytest.raises(SchemaError, match="重复"):
            load_players_file(path)

    def test_number_prefill_with_file_players(self, tmp_path: pathlib.Path) -> None:
        # Arrange：文件名单注入后走号码预填链路（match_players_by_number 命中）
        path = _write_players_file(
            tmp_path, [{"tag": "白22-小朱", "name": "小朱", "team": "半截篮"}]
        )
        players = load_players_file(path)
        cand = _candidate()
        cand["number_guess"] = {
            "number": "22",
            "color": "白",
            "name_text": None,
            "confidence": "high",
        }
        # Act
        entries = build_entries([_goal()], [cand], None, "", "", players)
        # Assert
        assert entries[0]["prefill_tag"] == "白22-小朱"
        assert entries[0]["prefill_note"] == ""


class TestPlayersFileCli:
    """--players-file CLI 层：与 --players 互斥、端到端生成页面。"""

    def _write_inputs(self, tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        """造 scorers/goals 两个输入文件，返回路径。"""
        scorers_dir = tmp_path / "scorers"
        scorers_dir.mkdir()
        scorers = scorers_dir / "scorer_candidates.json"
        scorers.write_text(
            json.dumps({"session": "s", "candidates": [_candidate()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        goals = tmp_path / "goals.json"
        goals.write_text(
            json.dumps({"session": "s", "goals": [_goal()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        return scorers, goals

    def test_mutex_with_players_rejected(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        scorers, goals = self._write_inputs(tmp_path)
        players_file = _write_players_file(tmp_path, [])
        # Act / Assert：同给两源 → parser.error 显式拒绝（SystemExit 2）
        with pytest.raises(SystemExit):
            main(
                [
                    "--scorers",
                    str(scorers),
                    "--goals",
                    str(goals),
                    "--players",
                    "黑21=大斌",
                    "--players-file",
                    str(players_file),
                ]
            )

    def test_end_to_end_with_players_file(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        scorers, goals = self._write_inputs(tmp_path)
        players_file = _write_players_file(
            tmp_path, [{"tag": "白22-小朱", "name": "小朱", "team": "半截篮"}]
        )
        # Act
        rc = main(
            [
                "--scorers",
                str(scorers),
                "--goals",
                str(goals),
                "--players-file",
                str(players_file),
            ]
        )
        # Assert：页面正常生成，文件名单内联为按钮名单
        assert rc == 0
        html = (scorers.parent / "scorer.html").read_text(encoding="utf-8")
        assert '"tag": "白22-小朱"' in html
        assert '"team": "半截篮"' in html

    def test_bad_players_file_exit_1(self, tmp_path: pathlib.Path) -> None:
        # Arrange：名单文件 schema 损坏（team 空串）
        scorers, goals = self._write_inputs(tmp_path)
        players_file = _write_players_file(tmp_path, [{"tag": "白22", "name": "小朱", "team": ""}])
        # Act：SchemaError 经 main 转为退出 1（显式失败不静默）
        rc = main(
            [
                "--scorers",
                str(scorers),
                "--goals",
                str(goals),
                "--players-file",
                str(players_file),
            ]
        )
        # Assert
        assert rc == 1


class TestMergeAssignments:
    """--roster-existing 并集合并（spec T4）。"""

    def test_union_disjoint(self) -> None:
        # Arrange / Act
        merged = merge_assignments({"a.mp4#4.1": "黑21"}, {"b.mp4#2.0": "白22"})
        # Assert
        assert merged == {"a.mp4#4.1": "黑21", "b.mp4#2.0": "白22"}

    def test_same_key_same_value_ok(self) -> None:
        # Arrange / Act
        merged = merge_assignments({"a.mp4#4.1": "黑21"}, {"a.mp4#4.1": "黑21"})
        # Assert
        assert merged == {"a.mp4#4.1": "黑21"}

    def test_same_key_conflict_raises(self) -> None:
        # Arrange / Act / Assert：同键不同值显式失败（调用方退出 1）
        with pytest.raises(BasketballPipelineError, match="同键冲突"):
            merge_assignments({"a.mp4#4.1": "黑21"}, {"a.mp4#4.1": "白22"})


class TestMatchClip:
    """审核片段匹配：src_file 相同且 |anchor_t0−anchor|≤4s，取最近者。"""

    def test_match_within_tolerance(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        index_dir = tmp_path / "s" / "review_v3"
        out_dir = tmp_path / "s" / "scorers"
        index_dir.mkdir(parents=True)
        out_dir.mkdir()
        events = [_event(anchor_t0=6.0), _event(anchor_t0=100.0)]
        # Act
        rel = match_clip(events, "a.mp4", 4.1, str(index_dir), str(out_dir))
        # Assert：命中 6.0（|6.0−4.1|=1.9≤4s），优先全景 clip_wide，相对路径用正斜杠
        assert rel == "../review_v3/clips/a_e1_wide.mp4"

    def test_fallback_to_clip_when_no_wide(self, tmp_path: pathlib.Path) -> None:
        # Arrange：无 clip_wide 字段回退筐区 clip
        index_dir = tmp_path / "s" / "review_v3"
        out_dir = tmp_path / "s" / "scorers"
        index_dir.mkdir(parents=True)
        out_dir.mkdir()
        ev = _event(anchor_t0=6.0)
        del ev["clip_wide"]
        # Act
        rel = match_clip([ev], "a.mp4", 4.1, str(index_dir), str(out_dir))
        # Assert
        assert rel == "../review_v3/clips/a_e1.mp4"

    def test_backslash_clip_normalized(self, tmp_path: pathlib.Path) -> None:
        # Arrange：events_index 实跑产物是 Windows 反斜杠
        index_dir = tmp_path / "s" / "review_v3"
        out_dir = tmp_path / "s" / "scorers"
        index_dir.mkdir(parents=True)
        out_dir.mkdir()
        ev = _event(anchor_t0=4.0)
        ev["clip_wide"] = "clips\\a_e1_wide.mp4"
        # Act
        rel = match_clip([ev], "a.mp4", 4.1, str(index_dir), str(out_dir))
        # Assert
        assert rel == "../review_v3/clips/a_e1_wide.mp4"

    def test_no_match_returns_empty(self, tmp_path: pathlib.Path) -> None:
        # Arrange：异源文件 / 超容差 都不匹配
        events = [_event(src_file="b.mp4", anchor_t0=4.0), _event(anchor_t0=20.0)]
        # Act / Assert
        assert match_clip(events, "a.mp4", 4.1, str(tmp_path), str(tmp_path)) == ""


class TestMatchPlayersByNumber:
    """号码+颜色 → 名单 tag 匹配（含歧义与数字边界）。"""

    @staticmethod
    def _players() -> list[Player]:
        """本场名单（含两个黑21，供歧义分支）。"""
        return [
            Player(tag="黑21-大斌", name="大斌", team="地平线"),
            Player(tag="黑21-王敏龙", name="王敏龙", team="地平线"),
            Player(tag="白-熊志鹏", name="熊志鹏", team="半截篮"),
            Player(tag="蓝色27", name="", team="便服"),
            Player(tag="赛文21", name="", team="便服"),
        ]

    def test_single_match(self) -> None:
        # Arrange / Act
        got = match_players_by_number(self._players(), "21", "黑")
        # Assert：三个 21 中颜色滤掉赛文21，剩两个黑21（调用方判歧义）
        assert [p.tag for p in got] == ["黑21-大斌", "黑21-王敏龙"]

    def test_unique_number_ignores_color_misread(self) -> None:
        # Arrange / Act / Assert：27 唯一，颜色误读为黑也命中蓝色27
        assert [p.tag for p in match_players_by_number(self._players(), "27", "黑")] == ["蓝色27"]

    def test_blue_color_match(self) -> None:
        # Arrange / Act / Assert
        assert [p.tag for p in match_players_by_number(self._players(), "27", "蓝")] == ["蓝色27"]

    def test_wrong_color_falls_back_to_ambiguous(self) -> None:
        # Arrange：三个 21 用白色过滤为空 → 回退歧义全集（不放过潜在误杀）
        # Act / Assert
        got = match_players_by_number(self._players(), "21", "白")
        assert [p.tag for p in got] == ["黑21-大斌", "黑21-王敏龙", "赛文21"]

    def test_digit_boundary_no_substring(self) -> None:
        # Arrange / Act / Assert：号码 "2" 不误中 "黑21"
        assert match_players_by_number(self._players(), "2", "黑") == []

    def test_none_number_no_match(self) -> None:
        # Arrange / Act / Assert：无号码不参与匹配
        assert match_players_by_number(self._players(), None, "黑") == []

    def test_same_number_no_color_is_ambiguous(self) -> None:
        # Arrange / Act / Assert：同号无颜色提示 → 返回全部候选（歧义）
        got = match_players_by_number(self._players(), "21", None)
        assert len(got) == 3


class TestMatchPlayersByName:
    """印名模糊匹配：精确或差 1 字符（K3 误读容差），只看非空 name。"""

    def _players(self) -> list:
        return [
            Player(tag="黑21-大斌", name="大斌", team="地平线"),
            Player(tag="黑21-王敏龙", name="王敏龙", team="地平线"),
            Player(tag="蓝色27", name="", team="便服"),
        ]

    def test_exact_name_match(self) -> None:
        # Arrange / Act / Assert
        assert [p.tag for p in match_players_by_name(self._players(), "大斌")] == ["黑21-大斌"]

    def test_one_char_misread_match(self) -> None:
        # Arrange / Act / Assert：K3 把"大斌"读成"大秋"（差 1 字符）仍命中
        assert [p.tag for p in match_players_by_name(self._players(), "大秋")] == ["黑21-大斌"]

    def test_no_match_and_empty(self) -> None:
        # Arrange / Act / Assert：无关文本与空值不中
        assert match_players_by_name(self._players(), "杭州60岁") == []
        assert match_players_by_name(self._players(), "") == []
        assert match_players_by_name(self._players(), None) == []


class TestNumberPrefill:
    """条目预填：号码匹配 > 颜色；同号多人歧义不预填。"""

    def _candidate_with_number(self, number: str | None, color: str | None) -> dict:
        """造一条带 number_guess 的候选。"""
        c = _candidate()
        c["number_guess"] = {
            "number": number,
            "color": color,
            "name_text": None,
            "confidence": "high" if number else "low",
        }
        return c

    def test_unique_number_match_prefills(self) -> None:
        # Arrange：名单只有一个 黑21
        players = [Player(tag="黑21-大斌", name="大斌", team="地平线")]
        # Act
        entries = build_entries(
            [_goal()], [self._candidate_with_number("21", "黑")], None, "", "", players
        )
        # Assert：号码预填压过颜色 team_guess（候选 team_guess=黑）
        assert entries[0]["prefill_tag"] == "黑21-大斌"
        assert entries[0]["prefill_note"] == ""

    def test_ambiguous_same_number_no_prefill(self) -> None:
        # Arrange：两个黑21 → 歧义
        players = [
            Player(tag="黑21-大斌", name="大斌", team="地平线"),
            Player(tag="黑21-王敏龙", name="王敏龙", team="地平线"),
        ]
        # Act
        entries = build_entries(
            [_goal()], [self._candidate_with_number("21", "黑")], None, "", "", players
        )
        # Assert
        assert entries[0]["prefill_tag"] == ""
        assert entries[0]["prefill_note"] == "ambiguous"

    def test_no_number_no_prefill(self) -> None:
        # Arrange：K3 没读出号码
        players = [Player(tag="黑21-大斌", name="大斌", team="地平线")]
        # Act
        entries = build_entries(
            [_goal()], [self._candidate_with_number(None, "黑")], None, "", "", players
        )
        # Assert：回退颜色预填（prefill 字段为空，页面显示 team_guess）
        assert entries[0]["prefill_tag"] == ""
        assert entries[0]["prefill_note"] == ""
        assert entries[0]["team_guess"] == "黑"


class TestBuildEntries:
    """页面条目组装：confirmed 球为全集，按 key 关联候选。"""

    def test_sorted_and_joined(self) -> None:
        # Arrange：goals 乱序，候选含 SKIP
        goals = [_goal("b.mp4", 2.0), _goal("a.mp4", 4.1)]
        candidates = [
            _candidate("a.mp4", 4.1),
            _candidate("b.mp4", 2.0, status="SKIP", crop="", team_guess=None),
        ]
        # Act
        entries = build_entries(goals, candidates, None, "", "")
        # Assert：按 file+anchor 排序；SKIP 无裁图无预填
        assert [e["key"] for e in entries] == ["a.mp4#4.1", "b.mp4#2.0"]
        assert entries[0]["crop"] == "a_t4.1.jpg"
        assert entries[0]["team_guess"] == "黑"
        assert entries[0]["clip"] == ""  # 无 --index
        assert entries[1]["status"] == "SKIP"

    def test_goal_without_candidate_becomes_skip(self) -> None:
        # Arrange / Act
        entries = build_entries([_goal()], [], None, "", "")
        # Assert：防御兜底，不炸、按 SKIP 列出
        assert entries[0]["status"] == "SKIP"
        assert entries[0]["reason"] == "no_candidate"
        assert entries[0]["crop"] == ""

    def test_clip_filled_when_events_given(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        index_dir = tmp_path / "s" / "review_v3"
        out_dir = tmp_path / "s" / "scorers"
        index_dir.mkdir(parents=True)
        out_dir.mkdir()
        # Act
        entries = build_entries(
            [_goal()], [_candidate()], [_event(anchor_t0=4.0)], str(index_dir), str(out_dir)
        )
        # Assert
        assert entries[0]["clip"] == "../review_v3/clips/a_e1_wide.mp4"

    def test_candidate_clip_preferred_over_events(self, tmp_path: pathlib.Path) -> None:
        # Arrange：candidates 带现切预览片段时优先于 events_index 匹配
        index_dir = tmp_path / "s" / "review_v3"
        out_dir = tmp_path / "s" / "scorers"
        index_dir.mkdir(parents=True)
        out_dir.mkdir()
        cand = _candidate()
        cand["clip"] = "clips/a_t4.1.mp4"
        # Act
        entries = build_entries(
            [_goal()], [cand], [_event(anchor_t0=4.0)], str(index_dir), str(out_dir)
        )
        # Assert：与裁图同锚点的预览片段胜出，不走事件兜底
        assert entries[0]["clip"] == "clips/a_t4.1.mp4"

    def test_empty_candidate_clip_falls_back_to_events(self, tmp_path: pathlib.Path) -> None:
        # Arrange：candidates 有 clip 字段但为空串（切片失败）→ 仍走事件兜底
        index_dir = tmp_path / "s" / "review_v3"
        out_dir = tmp_path / "s" / "scorers"
        index_dir.mkdir(parents=True)
        out_dir.mkdir()
        cand = _candidate()
        cand["clip"] = ""
        # Act
        entries = build_entries(
            [_goal()], [cand], [_event(anchor_t0=4.0)], str(index_dir), str(out_dir)
        )
        # Assert
        assert entries[0]["clip"] == "../review_v3/clips/a_e1_wide.mp4"


class TestBuildHtml:
    """HTML 渲染：数据内联、导出契约、交互控件。"""

    def test_inlines_items_players_session(self) -> None:
        # Arrange
        entries = build_entries([_goal()], [_candidate()], None, "", "")
        players = [Player(tag="黑21", name="大斌", team="地平线")]
        # Act
        html = build_html(entries, players, "20260722", {}, {}, "地平线")
        # Assert
        assert '"key": "a.mp4#4.1"' in html
        assert '"tag": "黑21"' in html
        assert 'const SESSION = "20260722";' in html

    def test_progress_localstorage_key_contains_session(self) -> None:
        # Arrange / Act
        html = build_html([], [], "mysession", {}, {}, "地平线")
        # Assert
        assert '"scorer_" + SESSION' in html
        assert "localStorage" in html

    def test_export_contract_roster_json(self) -> None:
        # Arrange / Act
        html = build_html([], [], "20260722", {}, {}, "地平线")
        # Assert：导出结构字段与文件名契约（roster.py validate_roster 可过；
        # roster-export-name：下载名即 roster.json，移到 work/<场次>/ 直接接入 CLI）
        assert 'a.download = "roster.json";' in html
        assert "confirmed" in html
        assert "assignments" in html
        assert "players" in html
        # confirmed 条件：全部非 SKIP 球已归属
        assert 'it.status === "SKIP" || marks[it.key]' in html

    def test_skip_badge_and_free_text_and_keys(self) -> None:
        # Arrange / Act
        html = build_html([], [], "s", {}, {}, "地平线")
        # Assert：SKIP 标"无法定位"、自由文本输入、数字键 1-9、S 跳过、E 采用预填
        assert "无法定位" in html
        assert 'id="free"' in html
        assert '"1" && k <= "9"' in html
        assert '"s"' in html
        assert 'id="accept"' in html
        assert '"e"' in html
        assert "号码歧义" in html

    def test_existing_assignments_inlined(self) -> None:
        # Arrange / Act
        html = build_html([], [], "s", {"a.mp4#4.1": "黑21"}, {}, "地平线")
        # Assert：已有 roster 归属内联作预填底色
        assert '"a.mp4#4.1": "黑21"' in html

    def test_opponent_injected_and_semantic_css(self) -> None:
        # Arrange / Act
        html = build_html([], [], "20260805_车百鼎", {}, {}, "车百鼎")
        # Assert：对手队名注入 JS 常量；CSS/类名走语义类（队名随场次、类名固定）
        assert 'const OPP = "车百鼎";' in html
        assert "team-opp" in html
        assert "team-home" in html
        assert "team-casual" in html
        assert "function teamClass(" in html
        assert "b.className = teamClass(p.team)" in html
        assert "const KNOWN_TEAMS = [OPP, " in html
        # 兜底行：roster team 与当前场次三行不符的队员归"其他"，不静默消失
        assert "其他（team 口径不符）" in html


class TestMain:
    """main 端到端：tmp 目录造输入，产出 scorer.html。"""

    def _write_inputs(self, tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        """造 scorers/goals 两个输入文件，返回路径。"""
        scorers_dir = tmp_path / "scorers"
        scorers_dir.mkdir()
        scorers = scorers_dir / "scorer_candidates.json"
        scorers.write_text(
            json.dumps({"session": "s", "candidates": [_candidate()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        goals = tmp_path / "goals.json"
        goals.write_text(
            json.dumps({"session": "s", "goals": [_goal()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        return scorers, goals

    def test_generates_scorer_html(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        scorers, goals = self._write_inputs(tmp_path)
        # Act
        rc = main(
            [
                "--scorers",
                str(scorers),
                "--goals",
                str(goals),
                "--session",
                "s",
                "--players",
                "黑21=大斌",
            ]
        )
        # Assert：默认输出 <scorers 同目录>/scorer.html
        assert rc == 0
        html_path = scorers.parent / "scorer.html"
        assert html_path.is_file()
        html = html_path.read_text(encoding="utf-8")
        assert '"key": "a.mp4#4.1"' in html

    def test_roster_existing_merged(self, tmp_path: pathlib.Path) -> None:
        # Arrange：已有 roster 的归属应内联进页面
        scorers, goals = self._write_inputs(tmp_path)
        existing = tmp_path / "roster.json"
        existing.write_text(
            json.dumps(
                {
                    "session": "s",
                    "confirmed": True,
                    "players": [{"tag": "黑21", "name": "大斌", "team": "地平线"}],
                    "assignments": {"a.mp4#4.1": "黑21"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # Act
        rc = main(
            [
                "--scorers",
                str(scorers),
                "--goals",
                str(goals),
                "--roster-existing",
                str(existing),
            ]
        )
        # Assert
        assert rc == 0
        html = (scorers.parent / "scorer.html").read_text(encoding="utf-8")
        assert '"a.mp4#4.1": "黑21"' in html

    def test_bad_candidates_schema_exit_1(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        scorers_dir = tmp_path / "scorers"
        scorers_dir.mkdir()
        scorers = scorers_dir / "scorer_candidates.json"
        scorers.write_text(json.dumps({"candidates": [{"key": 1}]}), encoding="utf-8")
        goals = tmp_path / "goals.json"
        goals.write_text(json.dumps({"goals": []}), encoding="utf-8")
        # Act
        rc = main(["--scorers", str(scorers), "--goals", str(goals), "--session", "s"])
        # Assert：schema 损坏显式失败
        assert rc == 1


def test_match_clip_picks_closest(tmp_path: pathlib.Path) -> None:
    # Arrange：两个同文件事件都在容差内，取时间差最小者（全景优先）
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    far = _event(anchor_t0=1.0, clip="clips/far.mp4")
    far["clip_wide"] = "clips/far_wide.mp4"
    near = _event(anchor_t0=4.0, clip="clips/near.mp4")
    near["clip_wide"] = "clips/near_wide.mp4"
    events = [far, near]
    # Act
    rel = match_clip(events, "a.mp4", 4.1, str(index_dir), str(tmp_path))
    # Assert
    assert rel.endswith("clips/near_wide.mp4")


def test_entries_clip_empty_without_index() -> None:
    # Arrange / Act：无 --index 时只显示裁图
    entries = build_entries([_goal()], [_candidate()], None, "", "")
    # Assert
    assert entries[0]["clip"] == ""


def test_validate_candidates_bad_status(tmp_path: pathlib.Path) -> None:
    # Arrange：status 非法值必须显式失败（经 main 退出 1）
    scorers_dir = tmp_path / "scorers"
    scorers_dir.mkdir()
    scorers = scorers_dir / "scorer_candidates.json"
    bad = _candidate(status="BROKEN")
    scorers.write_text(json.dumps({"session": "s", "candidates": [bad]}), encoding="utf-8")
    goals = tmp_path / "goals.json"
    goals.write_text(json.dumps({"goals": []}), encoding="utf-8")
    # Act / Assert
    assert main(["--scorers", str(scorers), "--goals", str(goals), "--session", "s"]) == 1


def test_main_missing_session_exit_1(tmp_path: pathlib.Path) -> None:
    # Arrange：candidates 无 session 且未给 --session
    scorers_dir = tmp_path / "scorers"
    scorers_dir.mkdir()
    scorers = scorers_dir / "scorer_candidates.json"
    scorers.write_text(json.dumps({"candidates": []}), encoding="utf-8")
    goals = tmp_path / "goals.json"
    goals.write_text(json.dumps({"goals": []}), encoding="utf-8")
    # Act / Assert
    assert main(["--scorers", str(scorers), "--goals", str(goals)]) == 1


def test_index_events_bad_schema_exit_1(tmp_path: pathlib.Path) -> None:
    # Arrange：events_index 损坏（事件缺 clip）
    scorers_dir = tmp_path / "scorers"
    scorers_dir.mkdir()
    scorers = scorers_dir / "scorer_candidates.json"
    scorers.write_text(json.dumps({"session": "s", "candidates": [_candidate()]}), encoding="utf-8")
    goals = tmp_path / "goals.json"
    goals.write_text(json.dumps({"session": "s", "goals": [_goal()]}), encoding="utf-8")
    index = tmp_path / "events_index.json"
    index.write_text(
        json.dumps({"events": [{"src_file": "a.mp4", "anchor_t0": 4.0}]}), encoding="utf-8"
    )
    # Act / Assert
    rc = main(
        [
            "--scorers",
            str(scorers),
            "--goals",
            str(goals),
            "--session",
            "s",
            "--index",
            str(index),
        ]
    )
    assert rc == 1


def test_main_output_next_to_candidates(tmp_path: pathlib.Path) -> None:
    # Arrange
    scorers_dir = tmp_path / "deep" / "scorers"
    scorers_dir.mkdir(parents=True)
    scorers = scorers_dir / "scorer_candidates.json"
    scorers.write_text(json.dumps({"session": "s", "candidates": [_candidate()]}), encoding="utf-8")
    goals = tmp_path / "goals.json"
    goals.write_text(json.dumps({"session": "s", "goals": [_goal()]}), encoding="utf-8")
    # Act
    rc = main(["--scorers", str(scorers), "--goals", str(goals)])
    # Assert：输出默认取 candidates 里的 session，文件落在同目录
    assert rc == 0
    assert (scorers_dir / "scorer.html").is_file()


def test_match_clip_absolute_vs_relative_consistent(tmp_path: pathlib.Path) -> None:
    # Arrange：out_dir 与 index_dir 同根时相对路径不含 ".."
    base = tmp_path / "s"
    index_dir = base / "review"
    out_dir = base / "scorers"
    index_dir.mkdir(parents=True)
    out_dir.mkdir()
    # Act
    rel = match_clip([_event(anchor_t0=4.0)], "a.mp4", 4.1, str(index_dir), str(out_dir))
    # Assert
    assert os.sep not in rel or "/" in rel  # 统一正斜杠
    assert rel == "../review/clips/a_e1_wide.mp4"


# ---- --clusters 簇级确认（docs/scorer-cluster/spec.md） ----


def _cluster(
    cid: int = 1,
    keys: tuple[str, ...] = ("a.mp4#4.1",),
    rep_crops: tuple[str, ...] = ("a_t4.1.jpg",),
) -> dict:
    """构造一条合法簇记录（cluster_scorers 输出契约）。"""
    return {"cluster_id": cid, "keys": list(keys), "rep_crops": list(rep_crops)}


class TestValidateClusters:
    """scorer_clusters.json schema 校验（顶层缺 clusters/类型错 → SchemaError）。"""

    def test_valid_payload(self) -> None:
        # Arrange / Act
        clusters = _validate_clusters(
            {"version": "cluster-v1", "clusters": [_cluster()], "unclustered": []}, "c.json"
        )
        # Assert
        assert clusters == [_cluster()]

    def test_top_level_not_dict(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError, match="顶层"):
            _validate_clusters([], "c.json")

    def test_missing_clusters(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError, match="clusters"):
            _validate_clusters({"version": "cluster-v1"}, "c.json")

    def test_clusters_not_list(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError, match="clusters"):
            _validate_clusters({"clusters": {}}, "c.json")

    def test_bad_cluster_field_types(self) -> None:
        # Arrange / Act / Assert：cluster_id bool、keys 非 str 列表、rep_crops 非列表
        with pytest.raises(SchemaError, match="cluster_id"):
            _validate_clusters({"clusters": [_cluster(cid=True)]}, "c.json")
        with pytest.raises(SchemaError, match="keys"):
            _validate_clusters({"clusters": [_cluster(keys=(1,))]}, "c.json")  # type: ignore[arg-type]
        with pytest.raises(SchemaError, match="rep_crops"):
            _validate_clusters({"clusters": [_cluster(rep_crops=("a.jpg", 2))]}, "c.json")  # type: ignore[arg-type]

    def test_duplicate_cluster_id(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SchemaError, match="重复"):
            _validate_clusters({"clusters": [_cluster(cid=1), _cluster(cid=1)]}, "c.json")


class TestBuildClusterMap:
    """key → cluster_id 映射：越界 key WARNING 跳过，同 key 多簇取首个。"""

    def test_basic_mapping(self) -> None:
        # Arrange / Act
        m = build_cluster_map(
            [
                _cluster(cid=1, keys=("a.mp4#4.1", "b.mp4#2.0")),
                _cluster(cid=2, keys=("c.mp4#1.0",)),
            ],
            {"a.mp4#4.1", "b.mp4#2.0", "c.mp4#1.0"},
        )
        # Assert
        assert m == {"a.mp4#4.1": 1, "b.mp4#2.0": 1, "c.mp4#1.0": 2}

    def test_key_not_in_candidates_warns_and_skips(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange / Act
        with caplog.at_level(logging.WARNING):
            m = build_cluster_map([_cluster(keys=("a.mp4#4.1", "ghost.mp4#9.9"))], {"a.mp4#4.1"})
        # Assert：越界 key 跳过不炸，记 WARNING
        assert m == {"a.mp4#4.1": 1}
        assert any("ghost.mp4#9.9" in r.message for r in caplog.records)

    def test_key_in_two_clusters_first_wins(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange / Act
        with caplog.at_level(logging.WARNING):
            m = build_cluster_map(
                [_cluster(cid=1), _cluster(cid=2, keys=("a.mp4#4.1",))], {"a.mp4#4.1"}
            )
        # Assert
        assert m == {"a.mp4#4.1": 1}
        assert any("同时属于" in r.message for r in caplog.records)


class TestBuildEntriesClusterId:
    """cluster_id 注入：同 key 同簇、unclustered→None、无 --clusters 全 None。"""

    def test_cluster_id_injected(self) -> None:
        # Arrange / Act
        entries = build_entries(
            [_goal()],
            [_candidate()],
            None,
            "",
            "",
            cluster_map={"a.mp4#4.1": 3},
        )
        # Assert
        assert entries[0]["cluster_id"] == 3

    def test_unclustered_key_gets_none(self) -> None:
        # Arrange / Act：映射里没有该 key（unclustered）
        entries = build_entries([_goal()], [_candidate()], None, "", "", cluster_map={})
        # Assert
        assert entries[0]["cluster_id"] is None

    def test_no_cluster_map_all_none(self) -> None:
        # Arrange / Act：不传 --clusters（向后兼容）
        entries = build_entries([_goal()], [_candidate()], None, "", "")
        # Assert
        assert entries[0]["cluster_id"] is None


class TestBuildPageClusters:
    """簇区数据：keys 过滤到本页 confirmed 球，空簇剔除，rep_crops 透传。"""

    def test_filters_keys_not_in_entries(self) -> None:
        # Arrange：簇含本页球 + 其他批次球
        entries = build_entries([_goal()], [_candidate()], None, "", "")
        clusters = [_cluster(keys=("a.mp4#4.1", "other.mp4#1.0"))]
        # Act
        page = build_page_clusters(clusters, entries)
        # Assert
        assert page == [{"cluster_id": 1, "keys": ["a.mp4#4.1"], "rep_crops": ["a_t4.1.jpg"]}]

    def test_cluster_without_page_keys_dropped(self) -> None:
        # Arrange / Act
        page = build_page_clusters([_cluster(keys=("other.mp4#1.0",))], [])
        # Assert
        assert page == []


class TestBuildHtmlClusters:
    """簇区渲染：有簇出标记与 rep_crops 引用；无簇不渲染且行为同旧版。"""

    def test_cluster_section_with_rep_crops(self) -> None:
        # Arrange
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        # Act
        html = build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)
        # Assert：簇区容器/行样式/代表图引用/簇级选人函数/逐球覆盖注释口径
        assert 'id="clusters"' in html
        assert "cluster-row" in html
        assert "clusterAssign" in html
        assert "a_t4.1.jpg" in html
        assert '"cluster_id": 1' in html

    def test_no_clusters_renders_empty(self) -> None:
        # Arrange / Act
        html = build_html([], [], "s", {}, {}, "地平线")
        # Assert：无簇数据 → CLUSTERS 空数组，JS 整区隐藏
        assert "const CLUSTERS = [];" in html

    def test_generated_js_syntax_node_check(self, tmp_path: pathlib.Path) -> None:
        # Arrange：node 不在 PATH 则跳过（仿 7e9967c 防模板转义黑屏回归）
        node = shutil.which("node")
        if node is None:
            pytest.skip("node 不在 PATH")
        entries = build_entries(
            [_goal()],
            [_candidate()],
            None,
            "",
            "",
            [Player(tag="黑21", name="大斌", team="地平线")],
            cluster_map={"a.mp4#4.1": 1},
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        html = build_html(
            entries,
            [Player(tag="黑21", name="大斌", team="地平线")],
            "s",
            {},
            {},
            "地平线",
            clusters=page_clusters,
        )
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        js_path = tmp_path / "page.js"
        js_path.write_text(script, encoding="utf-8")
        # Act
        proc = subprocess.run(  # noqa: S603 node 路径来自 shutil.which，可信
            [node, "--check", str(js_path)], capture_output=True, text=True, check=False
        )
        # Assert
        assert proc.returncode == 0, proc.stderr


class TestBuildHtmlClusterMerge:
    """簇合并+折叠模板断言（docs/scorer-cluster-merge/spec.md）：标识符在，JS 语法合法。"""

    def _html(self) -> str:
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)

    def test_cluster_state_layer_present(self) -> None:
        html = self._html()
        assert 'CLSTATE_KEY = LSKEY + "_clusters"' in html
        assert "function saveClState(" in html
        assert "function groupIdOf(" in html
        assert "function computeGroups(" in html
        assert "function groupTag(" in html
        assert "clState.clAssign" in html

    def test_group_render_and_split_present(self) -> None:
        html = self._html()
        assert "function splitGroup(" in html
        assert "function groupLabel(" in html
        assert "并自" in html
        assert "row.dataset.gid" in html

    def test_drag_merge_present(self) -> None:
        html = self._html()
        assert "function mergeInto(" in html
        assert "row.draggable = true" in html
        assert "drop-target" in html
        assert "PICKER-HOOK" in html

    def test_merge_picker_present(self) -> None:
        html = self._html()
        assert "function openPicker(" in html
        assert "pickerGid" in html
        assert "openPicker(dstGid)" in html
        assert 'className = "picker"' in html
        assert 'ev.key === "Escape"' in html

    def test_collapse_present(self) -> None:
        html = self._html()
        assert "function isCollapsed(" in html
        assert "function toggleCollapse(" in html
        assert "collapseAll" in html
        assert "全部展开" in html


class TestBuildHtmlTeamDrag:
    """队员拖拽改队模板断言（docs/player-team-drag/spec.md）。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_team_drag_present(self) -> None:
        html = self._html()
        assert '"_teamovr"' in html
        assert "function changeTeam(" in html
        assert "function saveTeamOvr(" in html
        assert "div.dataset.team" in html
        assert "b.draggable = true" in html
        assert "text/player-tag" in html


class TestMainClusters:
    """main 端到端 --clusters：同目录强校验、schema 损坏退出 1、簇区内联。"""

    def _write_inputs(
        self, tmp_path: pathlib.Path
    ) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
        """造 scorers/goals/clusters 三个输入文件（clusters 与 scorers 同目录），返回路径。"""
        scorers_dir = tmp_path / "scorers"
        scorers_dir.mkdir()
        scorers = scorers_dir / "scorer_candidates.json"
        scorers.write_text(
            json.dumps({"session": "s", "candidates": [_candidate()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        goals = tmp_path / "goals.json"
        goals.write_text(
            json.dumps({"session": "s", "goals": [_goal()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        clusters = scorers_dir / "scorer_clusters.json"
        clusters.write_text(
            json.dumps(
                {
                    "version": "cluster-v1",
                    "model": "m",
                    "threshold": 0.25,
                    "clusters": [_cluster()],
                    "unclustered": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return scorers, goals, clusters

    def test_end_to_end_with_clusters(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        scorers, goals, clusters = self._write_inputs(tmp_path)
        # Act
        rc = main(
            [
                "--scorers",
                str(scorers),
                "--goals",
                str(goals),
                "--clusters",
                str(clusters),
                "--players",
                "黑21=大斌",
            ]
        )
        # Assert
        assert rc == 0
        html = (scorers.parent / "scorer.html").read_text(encoding="utf-8")
        assert '"cluster_id": 1' in html
        assert "a_t4.1.jpg" in html

    def test_bad_clusters_schema_exit_1(self, tmp_path: pathlib.Path) -> None:
        # Arrange
        scorers, goals, clusters = self._write_inputs(tmp_path)
        clusters.write_text(json.dumps({"version": "cluster-v1"}), encoding="utf-8")
        # Act
        rc = main(["--scorers", str(scorers), "--goals", str(goals), "--clusters", str(clusters)])
        # Assert：schema 损坏显式失败
        assert rc == 1

    def test_clusters_different_dir_rejected(self, tmp_path: pathlib.Path) -> None:
        # Arrange：clusters 与 scorers 不同目录（rep_crops 相对引用口径破坏）
        scorers, goals, _ = self._write_inputs(tmp_path)
        other = tmp_path / "other" / "scorer_clusters.json"
        other.parent.mkdir()
        other.write_text(json.dumps({"clusters": []}), encoding="utf-8")
        # Act / Assert：parser.error 显式拒绝（SystemExit 2）
        with pytest.raises(SystemExit):
            main(["--scorers", str(scorers), "--goals", str(goals), "--clusters", str(other)])


class TestBuildHtmlStepBars:
    """三步引导标题条（docs/scorer-three-step/spec.md）：判队伍/并簇认人/逐球核对。"""

    def _html(self, with_clusters: bool = True) -> str:
        if with_clusters:
            entries = build_entries(
                [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
            )
            page_clusters = build_page_clusters([_cluster()], entries)
            return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)
        return build_html([], [], "s", {}, {}, "地平线")

    def test_step_bars_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "stepbar" in html
        assert "第一步：判队伍" in html
        assert "第二步：并簇认人" in html
        assert "第三步：逐球核对" in html

    def test_step2_toggles_with_clusters(self) -> None:
        # Arrange / Act：无簇页面也要有 step2 元素 + JS 开关（随簇区隐藏）
        html = self._html(with_clusters=False)
        # Assert
        assert 'id="step2"' in html
        assert 'getElementById("step2")' in html


class TestBuildHtmlDeleteCluster:
    """删簇（docs/scorer-three-step/spec.md）：deleted 墓碑子键，组从簇区隐藏不动归属。"""

    def _html(self) -> str:
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)

    def test_delete_cluster_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "function deleteCluster(" in html
        assert "deleted:" in html
        assert "clState.deleted" in html
        assert "删除簇#" in html

    def test_deleted_subkey_loaded_and_saved(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert：加载白名单与 saveClState 合并分支都带上 deleted
        assert '"deleted"' in html
        assert "stored.deleted" in html


class TestBuildHtmlRename:
    """页内改真名（docs/scorer-three-step/spec.md）：独立 _names 键，清空=写空串不删键。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_rename_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert '"_names"' in html
        assert "function renamePlayer(" in html
        assert "function saveNames(" in html
        assert "改名" in html

    def test_rename_entry_in_player_rows(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert：改名钮只挂队伍区（含兜底行）按钮旁，簇区/弹条不加
        assert "renamePlayer(p.tag)" in html


class TestBuildHtmlReviewByPlayer:
    """按人核对（docs/scorer-three-step/spec.md）：_review 键 + 可见集过滤 + 位置分键。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_review_state_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert '"_review"' in html
        assert "function reviewTarget(" in html
        assert "function visible(" in html
        assert "function renderReviewBar(" in html
        assert "function posKey(" in html

    def test_review_bar_and_special_value(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "核对对象" in html
        assert "__none__" in html
        assert 'id="reviewbar"' in html

    def test_free_input_rejects_none_sentinel(self) -> None:
        # Arrange / Act：自由输入拒绝 __none__（防撞未归属特殊值）
        html = self._html()
        # Assert
        assert 'tag === "__none__"' in html


class TestBuildHtmlReviewLayout:
    """逐球区布局（docs/scorer-three-step/spec.md）：#review flex 定高不定宽 + 悬停放大浮层。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_review_flex_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert 'id="review"' in html
        assert "align-items: flex-start" in html
        assert "68vh" in html

    def test_hover_zoom_present(self) -> None:
        # Arrange / Act：悬停浮层规则须在（点击放大已证伪）
        html = self._html()
        # Assert
        assert "#review #crop:hover" in html
        assert "img.rep:hover" in html


class TestBuildHtmlClickMerge:
    """点选合并（docs/scorer-click-merge/spec.md）：与拖拽并存，复用 mergeInto 语义。"""

    def _html(self) -> str:
        entries = build_entries(
            [_goal()], [_candidate()], None, "", "", cluster_map={"a.mp4#4.1": 1}
        )
        page_clusters = build_page_clusters([_cluster()], entries)
        return build_html(entries, [], "s", {}, {}, "地平线", clusters=page_clusters)

    def test_click_merge_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert "function pickMerge(" in html
        assert "let mergeSrc = null" in html
        assert "并入这里" in html
        assert "merge-src" in html

    def test_drag_merge_untouched(self) -> None:
        # Arrange / Act：拖拽路径标识符原样保留（两套并存）
        html = self._html()
        # Assert
        assert "row.draggable = true" in html
        assert "text/plain" in html
        assert "function mergeInto(" in html


class TestBuildHtmlNoGoalTag:
    """不算进球标签（docs/scorer-nogoal-tag/spec.md）：页面剔除假进球，导出自动过滤。"""

    def _html(self) -> str:
        return build_html([], [], "s", {}, {}, "车百鼎")

    def test_nogoal_present(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert
        assert 'const NOGOAL = "不算进球"' in html
        assert 'id="nogoal"' in html
        assert 'k === "n"' in html

    def test_export_strips_nogoal(self) -> None:
        # Arrange / Act
        html = self._html()
        # Assert：assignments 收集过滤哨兵 + alert 报剔除数
        assert "t !== NOGOAL" in html
        assert "已剔除不参与合成" in html

    def test_picker_shields_n_key(self) -> None:
        # Arrange / Act：弹条期间 N 与 1-9/E 同屏蔽（防误触静默剔除当前球）
        html = self._html()
        # Assert
        assert '|| k === "n") return;' in html
