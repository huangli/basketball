"""video.py 统一入口单元测试：命令拼装逐字断言、批次双轨、尺寸换算、state、错误传播。

全部用 tmp_path 伪造 work/<场次>/ 产物；subprocess.run 一律 monkeypatch 拦截，
不启动任何真子进程（rules.md §9：慢外部 mock）。
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess
import sys
from typing import Any

import pytest

import video
from errors import BasketballPipelineError
from roster import format_key
from video import Batch

SESSION: str = "s1"
SCRIPT_DIR: pathlib.Path = pathlib.Path(video.SCRIPT_DIR)
# video.py 内部用相对 work/<场次>/ 路径（与 run_session 一致），测试 chdir 到 tmp_path 后
# 命令参数里的路径串按相对口径断言
REL: pathlib.Path = pathlib.Path("work") / SESSION


def _write_json(path: pathlib.Path, data: Any) -> None:  # noqa: ANN401 JSON 内容不定
    """落盘 JSON 测试夹具（自动建父目录）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _goals_payload(n_confirmed: int = 2) -> dict[str, Any]:
    """构造 goals.json 内容：n 条 confirmed + 1 条 rejected（不计数）。"""
    goals = [
        {"status": "confirmed", "file": f"f{i}.mp4", "anchor_time": float(i) + 0.5}
        for i in range(n_confirmed)
    ]
    goals.append({"status": "rejected", "file": "fx.mp4", "anchor_time": 99.0})
    return {"goals": goals}


def _facts_payload(width: int = 3840, height: int = 2160) -> dict[str, Any]:
    """构造 session_facts.json 内容（单文件）。"""
    return {"files": {"a.mp4": {"width": width, "height": height, "fps": 50.0}}}


@pytest.fixture
def session_dir(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """隔离的 work/<SESSION>/ 目录（chdir 到 tmp_path，video.WORK_ROOT 相对解析）。"""
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "work" / SESSION
    d.mkdir(parents=True)
    return d


@pytest.fixture
def run_recorder(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], dict[str, str]]]:
    """拦截 subprocess.run：记录 (cmd, env) 并返回成功。"""
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(
        cmd: list[str], *, check: bool, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        calls.append((list(cmd), dict(env)))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    return calls


def _fail_recorder(
    monkeypatch: pytest.MonkeyPatch, fail_at: int, returncode: int = 1
) -> list[list[str]]:
    """拦截 subprocess.run：第 fail_at 次（0 起）调用返回非零，其余成功。"""

    calls: list[list[str]] = []
    state = {"n": 0}

    def fake_run(
        cmd: list[str], *, check: bool, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        rc = returncode if state["n"] == fail_at else 0
        state["n"] += 1
        return subprocess.CompletedProcess(cmd, rc)

    monkeypatch.setattr(video.subprocess, "run", fake_run)
    return calls


class TestScore:
    """score：透传 run_session 命令拼装、state 写入、dry-run 不写。"""

    def test_command_verbatim_minimal(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        # Act
        rc = video.main(["score", "素材目录", "--session", SESSION])
        # Assert：逐字断言最小命令（无可选旗标时一个都不多传）
        assert rc == 0
        assert run_recorder[0][0] == [
            sys.executable,
            str(SCRIPT_DIR / "run_session.py"),
            "素材目录",
            "--session",
            SESSION,
        ]

    def test_command_verbatim_full_flags(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rc = video.main(
            [
                "score",
                "素材目录",
                "--session",
                SESSION,
                "--batch-size",
                "30",
                "--fids",
                "a,b,c",
                "--force",
            ]
        )
        assert rc == 0
        assert run_recorder[0][0] == [
            sys.executable,
            str(SCRIPT_DIR / "run_session.py"),
            "素材目录",
            "--session",
            SESSION,
            "--batch-size",
            "30",
            "--fids",
            "a,b,c",
            "--force",
        ]

    def test_env_injects_pythonioencoding(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        video.main(["score", "素材目录", "--session", SESSION])
        assert run_recorder[0][1]["PYTHONIOENCODING"] == "utf-8"

    def test_state_written_on_success(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        tmp_path: pathlib.Path,
    ) -> None:
        src = tmp_path / "素材目录"
        src.mkdir()
        video.main(["score", str(src), "--session", SESSION])
        state = json.loads((session_dir / "video_cli.json").read_text(encoding="utf-8"))
        assert state["version"] == 1
        assert state["session"] == SESSION
        assert state["srcdir"] == str(src.resolve())
        assert len(state["runs"]) == 1
        assert state["runs"][0]["cmd"] == "score"
        assert state["runs"][0]["exit_code"] == 0

    def test_state_runs_append_only(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        tmp_path: pathlib.Path,
    ) -> None:
        src = tmp_path / "素材目录"
        src.mkdir()
        video.main(["score", str(src), "--session", SESSION])
        video.main(["score", str(src), "--session", SESSION])
        state = json.loads((session_dir / "video_cli.json").read_text(encoding="utf-8"))
        assert len(state["runs"]) == 2

    def test_dry_run_no_state(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rc = video.main(["score", "素材目录", "--session", SESSION, "--dry-run"])
        assert rc == 0
        assert "--dry-run" in run_recorder[0][0]
        assert not (session_dir / "video_cli.json").exists()

    def test_nonzero_stops_exit1(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fail_recorder(monkeypatch, fail_at=0)
        rc = video.main(["score", "素材目录", "--session", SESSION])
        assert rc == 1
        assert not (session_dir / "video_cli.json").exists()


class TestDiscoverBatches:
    """批次发现双轨：goals.json（旧布局）/ goals_batchK.json（现行）/ 同 K 冲突。"""

    def test_old_layout_batch1(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "goals.json", _goals_payload())
        batches = video.discover_batches(session_dir)
        assert batches == [
            Batch(
                1,
                session_dir / "goals.json",
                session_dir / "candidates.json",
                session_dir / "review",
                session_dir / "scorers",
            )
        ]

    def test_new_layout_batch_k(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "goals_batch2.json", _goals_payload())
        batches = video.discover_batches(session_dir)
        assert len(batches) == 1
        b = batches[0]
        assert b.batch == 2
        assert b.candidates == session_dir / "candidates_batch2.json"
        assert b.review_dir == session_dir / "review_batch2"
        assert b.scorers_dir == session_dir / "scorers_b2"

    def test_same_k_dual_layout_conflict(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "goals.json", _goals_payload())
        _write_json(session_dir / "goals_batch1.json", _goals_payload())
        with pytest.raises(BasketballPipelineError, match="双布局并存"):
            video.discover_batches(session_dir)

    def test_no_goals_at_all(self, session_dir: pathlib.Path) -> None:
        with pytest.raises(BasketballPipelineError, match="无 goals"):
            video.discover_batches(session_dir)

    def test_sorted_and_unrecognized_skipped(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "goals_batch3.json", _goals_payload())
        _write_json(session_dir / "goals_batch1.json", _goals_payload())
        _write_json(session_dir / "goals_legacy_20260722.json", _goals_payload())
        batches = video.discover_batches(session_dir)
        assert [b.batch for b in batches] == [1, 3]


class TestPeople:
    """people：三段链命令拼装、max-reads 换算、--index/--clusters 条件传递。"""

    def _setup_batch(self, session_dir: pathlib.Path, *, events_index: bool = True) -> pathlib.Path:
        """备好现行布局批次 2 的全部前置产物，返回 rawdir。"""
        _write_json(session_dir / "goals_batch2.json", _goals_payload(2))
        _write_json(session_dir / "candidates_batch2.json", [])
        if events_index:
            _write_json(session_dir / "review_batch2" / "events_index.json", {"events": []})
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        return rawdir

    def test_three_steps_verbatim(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        assert len(run_recorder) == 3
        # ① 裁图（无 --read-numbers 时一个读号旗标都不带）
        assert run_recorder[0][0] == [
            sys.executable,
            str(SCRIPT_DIR / "crop_scorers.py"),
            "--goals",
            str(REL / "goals_batch2.json"),
            "--detectdir",
            str(pathlib.Path("work/detect")),
            "--framesdir",
            str(pathlib.Path("work/frames")),
            "--out",
            str(REL / "scorers_b2"),
            "--candidates",
            str(REL / "candidates_batch2.json"),
            "--rawdir",
            str(rawdir),
        ]
        # ② 聚类：显式定档 --linkage complete --threshold 0.15，clusters 落本批目录
        assert run_recorder[1][0] == [
            sys.executable,
            str(SCRIPT_DIR / "cluster_scorers.py"),
            "--candidates",
            str(REL / "scorers_b2" / "scorer_candidates.json"),
            "--out",
            str(REL / "scorers_b2" / "scorer_clusters.json"),
            "--linkage",
            "complete",
            "--threshold",
            "0.15",
        ]
        assert run_recorder[1][1]["HTTPS_PROXY"] == "http://127.0.0.1:7897"
        assert run_recorder[1][1]["PYTHONIOENCODING"] == "utf-8"
        # ③ 确认页：--index 存在才传、--clusters 同目录
        assert run_recorder[2][0] == [
            sys.executable,
            str(SCRIPT_DIR / "gen_scorer_page.py"),
            "--scorers",
            str(REL / "scorers_b2" / "scorer_candidates.json"),
            "--goals",
            str(REL / "goals_batch2.json"),
            "--session",
            SESSION,
            "--index",
            str(REL / "review_batch2" / "events_index.json"),
            "--clusters",
            str(REL / "scorers_b2" / "scorer_clusters.json"),
        ]

    def test_env_https_proxy_only_on_cluster_step(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange：排除父进程已带 HTTPS_PROXY 的干扰
        monkeypatch.delenv("HTTPS_PROXY", raising=False)
        rawdir = self._setup_batch(session_dir)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        base_keys = set(os.environ) | {"PYTHONIOENCODING"}
        # ①③ 非聚类段：相对 os.environ 无额外键（锁定 HTTPS_PROXY 仅聚类段叠加）
        for idx in (0, 2):
            assert set(run_recorder[idx][1]) - base_keys == set()
        # ② 聚类段：恰好只多 HTTPS_PROXY
        assert set(run_recorder[1][1]) - base_keys == {"HTTPS_PROXY"}
        assert run_recorder[1][1]["HTTPS_PROXY"] == "http://127.0.0.1:7897"

    def test_read_numbers_max_reads_default(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir), "--read-numbers"])
        assert rc == 0
        crop_cmd = run_recorder[0][0]
        # 缺省 = confirmed 2 条 ×3 = 6（rejected 不计）
        assert crop_cmd[-3:] == ["--read-numbers", "--max-reads", "6"]

    def test_read_numbers_max_reads_explicit(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        rc = video.main(
            [
                "people",
                "--session",
                SESSION,
                "--rawdir",
                str(rawdir),
                "--read-numbers",
                "--max-reads",
                "9",
            ]
        )
        assert rc == 0
        assert run_recorder[0][0][-2:] == ["--max-reads", "9"]

    def test_index_omitted_when_missing(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir, events_index=False)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        assert "--index" not in run_recorder[2][0]

    def test_skip_cluster(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir), "--skip-cluster"])
        assert rc == 0
        # 只跑 ①③ 两段，③ 不传 --clusters
        assert len(run_recorder) == 2
        assert "cluster_scorers.py" not in run_recorder[1][0][1]
        assert "--clusters" not in run_recorder[1][0]

    def test_roster_existing_and_players_file(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        _write_json(
            session_dir / "roster.json",
            {"players": [{"tag": "红-7", "name": "", "team": "半截篮"}], "assignments": {}},
        )
        players_file = session_dir / "players.json"
        _write_json(players_file, [])
        rc = video.main(
            [
                "people",
                "--session",
                SESSION,
                "--rawdir",
                str(rawdir),
                "--players-file",
                str(players_file),
            ]
        )
        assert rc == 0
        page_cmd = run_recorder[2][0]
        assert "--roster-existing" in page_cmd
        assert page_cmd[page_cmd.index("--roster-existing") + 1] == str(REL / "roster.json")
        assert "--players-file" in page_cmd

    def test_batch_filter(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        _write_json(session_dir / "goals_batch3.json", _goals_payload())
        _write_json(session_dir / "candidates_batch3.json", [])
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir), "--batch", "3"])
        assert rc == 0
        # 只跑批次 3（3 段），批次 2 不跑
        assert len(run_recorder) == 3
        assert any("goals_batch3.json" in item for item in run_recorder[0][0])

    def test_batch_not_found(self, session_dir: pathlib.Path) -> None:
        rawdir = self._setup_batch(session_dir)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir), "--batch", "9"])
        assert rc == 1

    def test_missing_candidates_skips_batch(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        # Arrange：批次 2 缺 candidates（跳）、批次 3 齐（跑）
        _write_json(session_dir / "goals_batch2.json", _goals_payload())
        _write_json(session_dir / "goals_batch3.json", _goals_payload())
        _write_json(session_dir / "candidates_batch3.json", [])
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        assert len(run_recorder) == 3
        assert any("goals_batch3.json" in item for item in run_recorder[0][0])

    def test_rawdir_from_state(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        tmp_path: pathlib.Path,
    ) -> None:
        self._setup_batch(session_dir)
        src = tmp_path / "state素材"
        src.mkdir()
        _write_json(
            session_dir / "video_cli.json",
            {"version": 1, "session": SESSION, "srcdir": str(src), "runs": []},
        )
        rc = video.main(["people", "--session", SESSION])
        assert rc == 0
        assert run_recorder[0][0][-2:] == ["--rawdir", str(src)]

    def test_rawdir_missing_everywhere(self, session_dir: pathlib.Path) -> None:
        self._setup_batch(session_dir)
        rc = video.main(["people", "--session", SESSION])
        assert rc == 1

    def test_nonzero_stops_exit1(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rawdir = self._setup_batch(session_dir)
        calls = _fail_recorder(monkeypatch, fail_at=1)  # 聚类段失败
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir)])
        # 非零即停：只跑了 ①② 两步，③ 未执行
        assert rc == 1
        assert len(calls) == 2

    def test_dry_run_executes_nothing(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rawdir = self._setup_batch(session_dir)

        def forbidden(*a: object, **kw: object) -> None:
            raise AssertionError("dry-run 不得启动子进程")

        monkeypatch.setattr(video.subprocess, "run", forbidden)
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir), "--dry-run"])
        assert rc == 0

    def test_old_layout_paths(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        _write_json(session_dir / "goals.json", _goals_payload())
        _write_json(session_dir / "candidates.json", [])
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        rc = video.main(["people", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        crop_cmd = run_recorder[0][0]
        assert str(REL / "scorers") in crop_cmd
        assert str(REL / "candidates.json") in crop_cmd


class TestResolveOutSize:
    """build 尺寸换算三态：16:9 / 4:3 / 混比例或未知报错。"""

    def test_16_9(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "session_facts.json", _facts_payload(3840, 2160))
        assert video.resolve_out_size(session_dir) == "1920x1080"

    def test_16_9_within_tolerance(self, session_dir: pathlib.Path) -> None:
        # 容差 ±1% 内（3830x2160 ≈ 16:9 - 0.26%）
        _write_json(session_dir / "session_facts.json", _facts_payload(3830, 2160))
        assert video.resolve_out_size(session_dir) == "1920x1080"

    def test_4_3(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "session_facts.json", _facts_payload(2880, 2160))
        assert video.resolve_out_size(session_dir) == "1440x1080"

    def test_4_3_within_tolerance(self, session_dir: pathlib.Path) -> None:
        # 容差 ±1% 内（2860x2160 ≈ 4:3 - 0.69%，与 16:9 侧对称）
        _write_json(session_dir / "session_facts.json", _facts_payload(2860, 2160))
        assert video.resolve_out_size(session_dir) == "1440x1080"

    def test_mixed_ratios_error_lists_files(self, session_dir: pathlib.Path) -> None:
        facts = {
            "files": {
                "a.mp4": {"width": 3840, "height": 2160},
                "b.mp4": {"width": 2880, "height": 2160},
            }
        }
        _write_json(session_dir / "session_facts.json", facts)
        with pytest.raises(BasketballPipelineError) as exc_info:
            video.resolve_out_size(session_dir)
        msg = str(exc_info.value)
        assert "a.mp4" in msg and "b.mp4" in msg
        assert "16:9" in msg and "4:3" in msg

    def test_unknown_ratio_error(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "session_facts.json", _facts_payload(1000, 1000))
        with pytest.raises(BasketballPipelineError, match="未知"):
            video.resolve_out_size(session_dir)

    def test_missing_facts(self, session_dir: pathlib.Path) -> None:
        with pytest.raises(BasketballPipelineError, match="session_facts"):
            video.resolve_out_size(session_dir)


class TestBuild:
    """build：命令拼装、--all 展开、互斥、roster 缺失、错误传播。"""

    def _setup(self, session_dir: pathlib.Path, *, roster: bool = False) -> pathlib.Path:
        _write_json(session_dir / "goals_batch1.json", _goals_payload())
        _write_json(session_dir / "candidates_batch1.json", [])
        _write_json(session_dir / "session_facts.json", _facts_payload())
        if roster:
            _write_json(
                session_dir / "roster.json",
                {
                    "players": [
                        {"tag": "红-7", "name": "大斌", "team": "半截篮"},
                        {"tag": "黑-A", "name": "", "team": "地平线"},
                        {"tag": "黑-B", "name": "", "team": "地平线"},
                    ],
                    "assignments": {
                        format_key("f0.mp4", 0.5): "红-7",
                        format_key("f1.mp4", 1.5): "黑-A",
                    },
                },
            )
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        return rawdir

    def test_command_verbatim_default(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup(session_dir)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        # 无过滤无 roster：全员合集，不带 --roster/--scorer/--team
        assert run_recorder[0][0] == [
            sys.executable,
            str(SCRIPT_DIR / "build_highlight.py"),
            "--goals",
            str(REL / "goals_batch1.json"),
            "--rawdir",
            str(rawdir),
            "--out",
            "1920x1080",
        ]

    def test_roster_passed_when_present(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup(session_dir, roster=True)
        rc = video.main(
            ["build", "--session", SESSION, "--rawdir", str(rawdir), "--scorer", "红-7"]
        )
        assert rc == 0
        assert run_recorder[0][0] == [
            sys.executable,
            str(SCRIPT_DIR / "build_highlight.py"),
            "--goals",
            str(REL / "goals_batch1.json"),
            "--roster",
            str(REL / "roster.json"),
            "--rawdir",
            str(rawdir),
            "--out",
            "1920x1080",
            "--scorer",
            "红-7",
        ]

    def test_all_expands_players_and_teams(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup(session_dir, roster=True)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        assert rc == 0
        # 黑-B 无归属球零命中跳过：2 人（红-7、黑-A）+ 2 队（半截篮、地平线）= 4 条
        assert len(run_recorder) == 4
        tail = [c[0][-2:] for c in run_recorder]
        assert tail == [
            ["--scorer", "红-7"],
            ["--scorer", "黑-A"],
            ["--team", "半截篮"],
            ["--team", "地平线"],
        ]

    def test_batch_filter(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup(session_dir)
        _write_json(session_dir / "goals_batch2.json", _goals_payload())
        _write_json(session_dir / "candidates_batch2.json", [])
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--batch", "2"])
        assert rc == 0
        # 只跑批次 2，批次 1 不跑
        assert len(run_recorder) == 1
        assert str(REL / "goals_batch2.json") in run_recorder[0][0]

    def test_all_skips_casual_team(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        rawdir = self._setup(session_dir)
        _write_json(
            session_dir / "roster.json",
            {
                "players": [
                    {"tag": "红-7", "name": "", "team": "半截篮"},
                    {"tag": "便-X", "name": "", "team": "便服"},
                ],
                "assignments": {
                    format_key("f0.mp4", 0.5): "红-7",
                },
            },
        )
        caplog.set_level(logging.WARNING)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        assert rc == 0
        tail = [c[0][-2:] for c in run_recorder]
        # 便-X 无归属球零命中跳过；便服分队合集跳过（build_highlight 拒收 --team 便服）
        assert tail == [["--scorer", "红-7"], ["--team", "半截篮"]]
        assert "便服" in caplog.text

    def test_all_roster_missing(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup(session_dir, roster=False)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        assert rc == 1
        assert run_recorder == []  # 前置校验失败，不启动任何子进程

    def test_all_roster_schema_bad(self, session_dir: pathlib.Path) -> None:
        rawdir = self._setup(session_dir)
        _write_json(session_dir / "roster.json", {"players": [{"tag": "x", "team": "不存在队"}]})
        # roster schema 损坏（team 非法值）→ validate_roster 抛 SchemaError，退出 1
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        assert rc == 1

    def test_mutex_violation(self, session_dir: pathlib.Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            video.main(["build", "--session", SESSION, "--scorer", "红-7", "--team", "半截篮"])
        assert exc_info.value.code == 2

    def test_4_3_out_size(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        rawdir = self._setup(session_dir)
        _write_json(session_dir / "session_facts.json", _facts_payload(2880, 2160))
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        assert run_recorder[0][0][-2:] == ["--out", "1440x1080"]

    def test_nonzero_stops_exit1(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rawdir = self._setup(session_dir, roster=True)
        calls = _fail_recorder(monkeypatch, fail_at=1)  # 第二个合集失败
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        assert rc == 1
        assert len(calls) == 2

    def test_dry_run_executes_nothing(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rawdir = self._setup(session_dir, roster=True)

        def forbidden(*a: object, **kw: object) -> None:
            raise AssertionError("dry-run 不得启动子进程")

        monkeypatch.setattr(video.subprocess, "run", forbidden)
        rc = video.main(
            ["build", "--session", SESSION, "--rawdir", str(rawdir), "--all", "--dry-run"]
        )
        assert rc == 0


class TestBuildHeatmap:
    """build 收尾热图触发（v4.2，docs/heatmap/spec.md）：合集全成后自动调
    goal_heatmap.heat_session；roster 缺失 INFO 跳过；热图失败不阻塞主链；
    dry-run 不执行。"""

    def _setup(self, session_dir: pathlib.Path, *, roster: bool = True) -> pathlib.Path:
        _write_json(session_dir / "goals_batch1.json", _goals_payload())
        _write_json(session_dir / "candidates_batch1.json", [])
        _write_json(session_dir / "session_facts.json", _facts_payload())
        if roster:
            _write_json(
                session_dir / "roster.json",
                {
                    "players": [{"tag": "红-7", "name": "", "team": "半截篮"}],
                    "assignments": {format_key("f0.mp4", 0.5): "红-7"},
                },
            )
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        return rawdir

    def _record_heatmap(self, monkeypatch: pytest.MonkeyPatch) -> list[pathlib.Path]:
        """拦截 goal_heatmap.heat_session（懒 import 后经模块属性调用，patch 模块本体生效）。"""
        import goal_heatmap

        calls: list[pathlib.Path] = []
        monkeypatch.setattr(goal_heatmap, "heat_session", lambda sd, *a, **k: calls.append(sd))
        return calls

    def test_heatmap_triggered_after_build(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls = self._record_heatmap(monkeypatch)
        rawdir = self._setup(session_dir)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        assert len(run_recorder) == 1  # 合集照常合成
        assert calls == [
            pathlib.Path("work") / SESSION
        ]  # 只传 session_dir（目录推导在 goal_heatmap 侧）

    def test_heatmap_failure_does_not_block(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import goal_heatmap

        def boom(sd: pathlib.Path) -> None:
            raise RuntimeError("热图炸了")

        monkeypatch.setattr(goal_heatmap, "heat_session", boom)
        rawdir = self._setup(session_dir)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0  # 附属产物失败不改 build 返回码
        assert len(run_recorder) == 1

    def test_heatmap_skipped_without_roster(
        self,
        session_dir: pathlib.Path,
        run_recorder: list[tuple[list[str], dict[str, str]]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls = self._record_heatmap(monkeypatch)
        rawdir = self._setup(session_dir, roster=False)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir)])
        assert rc == 0
        assert calls == []  # 未认人是预期常态，INFO 跳过不调 heat_session

    def test_heatmap_not_run_on_dry_run(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rawdir = self._setup(session_dir)

        def forbidden(*a: object, **kw: object) -> None:
            raise AssertionError("dry-run 不得启动子进程/热图")

        monkeypatch.setattr(video.subprocess, "run", forbidden)
        import goal_heatmap

        monkeypatch.setattr(goal_heatmap, "heat_session", forbidden)
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--dry-run"])
        assert rc == 0


class TestBuildMultiBatch:
    """多批次合并合成 + --all 零命中跳过（docs/build-multi-batch/spec.md）。"""

    def _setup_two_batches(self, session_dir: pathlib.Path) -> pathlib.Path:
        _write_json(session_dir / "goals_batch1.json", _goals_payload())
        _write_json(session_dir / "goals_batch2.json", _goals_payload())
        _write_json(session_dir / "candidates_batch1.json", [])
        _write_json(session_dir / "candidates_batch2.json", [])
        _write_json(session_dir / "session_facts.json", _facts_payload())
        rawdir = session_dir.parent.parent / "raw"
        rawdir.mkdir()
        return rawdir

    def _roster_full_hits(self, session_dir: pathlib.Path) -> None:
        _write_json(
            session_dir / "roster.json",
            {
                "players": [
                    {"tag": "红-7", "name": "", "team": "半截篮"},
                    {"tag": "黑-A", "name": "", "team": "地平线"},
                ],
                "assignments": {
                    format_key("f0.mp4", 0.5): "红-7",
                    format_key("f1.mp4", 1.5): "黑-A",
                },
            },
        )

    def test_multi_batch_merges_goals_and_single_call_per_filter(
        self, session_dir: pathlib.Path, run_recorder: list
    ) -> None:
        # Arrange
        rawdir = self._setup_two_batches(session_dir)
        self._roster_full_hits(session_dir)
        # Act
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        # Assert：2 球员 + 2 队 = 4 条命令，每 filter 只调一次，--goals 指向合并文件
        assert rc == 0
        assert len(run_recorder) == 4
        for cmd, _env in run_recorder:
            assert str(REL / "merged_goals_cli.json") in cmd
        # 合并文件已写盘：两批各 2 confirmed+1 rejected 逐字拼接 + session 字段
        merged = json.loads((session_dir / "merged_goals_cli.json").read_text("utf-8"))
        assert merged["session"] == SESSION
        assert len(merged["goals"]) == 6

    def test_all_skips_zero_hit_players_and_teams(
        self,
        session_dir: pathlib.Path,
        run_recorder: list,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Arrange：黑-A 有归属但不在 confirmed 键集（键对不上）→ 零命中
        rawdir = self._setup_two_batches(session_dir)
        _write_json(
            session_dir / "roster.json",
            {
                "players": [
                    {"tag": "红-7", "name": "", "team": "半截篮"},
                    {"tag": "黑-A", "name": "", "team": "地平线"},
                ],
                "assignments": {
                    format_key("f0.mp4", 0.5): "红-7",
                    "ghost.mp4#9.9": "黑-A",
                },
            },
        )
        caplog.set_level(logging.WARNING)
        # Act
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        # Assert：只出 红-7 + 半截篮；黑-A 与 地平线 零命中跳过（WARNING）
        assert rc == 0
        tail = [c[0][-2:] for c in run_recorder]
        assert tail == [["--scorer", "红-7"], ["--team", "半截篮"]]
        assert "零命中" in caplog.text

    def test_all_zero_hits_exit1(self, session_dir: pathlib.Path, run_recorder: list) -> None:
        # Arrange：assignments 全对不上 confirmed 键
        rawdir = self._setup_two_batches(session_dir)
        _write_json(
            session_dir / "roster.json",
            {
                "players": [{"tag": "红-7", "name": "", "team": "半截篮"}],
                "assignments": {"ghost.mp4#9.9": "红-7"},
            },
        )
        # Act
        rc = video.main(["build", "--session", SESSION, "--rawdir", str(rawdir), "--all"])
        # Assert：全零命中 → exit 1 且无子进程
        assert rc == 1
        assert run_recorder == []

    def test_dry_run_does_not_write_merged_file(
        self, session_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        rawdir = self._setup_two_batches(session_dir)
        self._roster_full_hits(session_dir)

        def forbidden(*a: object, **kw: object) -> None:
            raise AssertionError("dry-run 不得启动子进程")

        monkeypatch.setattr(video.subprocess, "run", forbidden)
        # Act
        rc = video.main(
            ["build", "--session", SESSION, "--rawdir", str(rawdir), "--all", "--dry-run"]
        )
        # Assert
        assert rc == 0
        assert not (session_dir / "merged_goals_cli.json").exists()


class TestMainEntry:
    """入口行为：无子命令退出 2；场次目录缺失退出 1。"""

    def test_no_subcommand_exit2(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert video.main([]) == 2
        assert "score" in capsys.readouterr().out

    def test_session_dir_missing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert video.main(["people", "--session", "nope", "--rawdir", "x"]) == 1

    def test_state_version_mismatch(self, session_dir: pathlib.Path) -> None:
        _write_json(session_dir / "video_cli.json", {"version": 99, "runs": []})
        with pytest.raises(BasketballPipelineError, match="版本"):
            video.load_state(SESSION)


class TestRelocate:
    """relocate=True（真实 CLI 入口）：相对路径按启动目录解析、chdir 到 REPO_ROOT。"""

    def _setup(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[pathlib.Path, pathlib.Path]:
        """构造假仓库根与独立启动目录，返回 (repo, launch)。"""
        repo: pathlib.Path = tmp_path / "repo"
        (repo / "work" / SESSION).mkdir(parents=True)
        launch: pathlib.Path = tmp_path / "elsewhere"
        launch.mkdir()
        monkeypatch.setattr(video, "REPO_ROOT", repo)
        monkeypatch.chdir(launch)
        return repo, launch

    def test_relative_srcdir_resolved_against_launch_cwd(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        # Arrange
        repo, launch = self._setup(tmp_path, monkeypatch)
        # Act
        rc = video.main(["score", "素材目录", "--session", SESSION], relocate=True)
        # Assert：相对 srcdir 按启动目录解析为绝对路径透传；cwd 已切到仓库根
        assert rc == 0
        assert run_recorder[0][0][2] == str((launch / "素材目录").resolve())
        assert pathlib.Path.cwd() == repo

    def test_absolute_srcdir_unchanged(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        # Arrange
        self._setup(tmp_path, monkeypatch)
        src: pathlib.Path = tmp_path / "绝对素材"
        # Act
        rc = video.main(["score", str(src), "--session", SESSION], relocate=True)
        # Assert：绝对路径原样透传
        assert rc == 0
        assert run_recorder[0][0][2] == str(src)

    def test_relocate_false_keeps_cwd_and_args(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        run_recorder: list[tuple[list[str], dict[str, str]]],
    ) -> None:
        # Arrange
        _, launch = self._setup(tmp_path, monkeypatch)
        # Act：relocate=False（测试/库内调用口径）不切目录、不解析路径
        rc = video.main(["score", "素材目录", "--session", SESSION], relocate=False)
        # Assert
        assert rc == 0
        assert run_recorder[0][0][2] == "素材目录"
        assert pathlib.Path.cwd() == launch
