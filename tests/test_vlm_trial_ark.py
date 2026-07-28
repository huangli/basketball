"""vlm_trial_ark 纯函数单元测试（不碰网络与凭证，rules.md §9 AAA 结构）。

覆盖：build_payload 请求结构、extract_content 响应取文本、parse_response 三值解析
（含裸 YES/NO 降级沿用 normalize_verdict）、is_model_unavailable 模型错误识别、
load_manifest schema 校验、结果落盘往返、aggregate_confusion 混淆聚合、
load_api_key 环境变量校验。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from errors import ExternalApiError, SchemaError
from vlm_trial_ark import (
    PROMPT_VERSION,
    VIDEO_FPS,
    ClipResult,
    ManifestEntry,
    Usage,
    aggregate_confusion,
    build_payload,
    extract_content,
    is_model_unavailable,
    load_api_key,
    load_manifest,
    load_results,
    parse_response,
    result_from_dict,
    save_results,
)

_MODEL: str = "doubao-seed-1-6-vision-250815"


def _entry(key: str, truth: str) -> ManifestEntry:
    """构造 manifest 条目（file/crop 对本组测试无影响）。"""
    return ManifestEntry(key=key, truth=truth, file=f"{key}.mp4", crop=True)


def _result(
    key: str,
    verdict: str,
    *,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    latency_sec: float = 1.5,
) -> ClipResult:
    """构造已判结果（raw/时间戳对本组测试无影响）。"""
    return ClipResult(
        key=key,
        verdict=verdict,
        raw="分析文本\n" + verdict,
        model=_MODEL,
        latency_sec=latency_sec,
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        ts="2026-07-28T00:00:00+00:00",
    )


def test_build_payload_structure() -> None:
    # Arrange / Act
    payload = build_payload(_MODEL, "QUJD")
    # Assert
    assert payload["model"] == _MODEL
    content = payload["messages"][0]["content"]
    video_part = content[0]
    assert video_part["type"] == "video_url"
    assert video_part["video_url"]["url"] == "data:video/mp4;base64,QUJD"
    assert video_part["video_url"]["fps"] == VIDEO_FPS
    text_part = content[1]
    assert text_part["type"] == "text"
    # 判定协议关键规则不丢：海报警告、证据要求、末行三值
    assert "海报" in text_part["text"]
    assert "直接证据" in text_part["text"]
    assert "YES、NO 或 UNCLEAR" in text_part["text"]


def test_extract_content_str() -> None:
    # Arrange
    data = {"choices": [{"message": {"content": "分析\nYES"}}]}
    # Act / Assert
    assert extract_content(data) == "分析\nYES"


def test_extract_content_parts_list() -> None:
    # Arrange：content 为 parts 列表（部分模型的返回形态）
    data = {
        "choices": [{"message": {"content": [{"type": "text", "text": "分析"}, {"text": "YES"}]}}]
    }
    # Act / Assert
    assert extract_content(data) == "分析\nYES"


def test_extract_content_missing_choices() -> None:
    # Arrange / Act / Assert
    assert extract_content({}) == ""
    assert extract_content({"choices": []}) == ""
    assert extract_content({"choices": [{"message": {}}]}) == ""


def test_parse_response_yes_with_evidence_kept() -> None:
    # Arrange：带证据（第几秒）的 YES
    data = {
        "choices": [{"message": {"content": "约第 11 秒球穿过篮网，篮网明显晃动。\nYES"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }
    # Act
    res = parse_response("k1", _MODEL, data, 12.345, "2026-07-28T00:00:00+00:00")
    # Assert
    assert res.verdict == "YES"
    assert res.usage.prompt_tokens == 100
    assert res.usage.completion_tokens == 20
    assert res.latency_sec == 12.35


def test_parse_response_bare_yes_downgrades() -> None:
    # Arrange：裸 YES（raw <15 字符，沿用 vlm_filter 降级规则）
    data = {"choices": [{"message": {"content": "YES"}}]}
    # Act / Assert
    assert parse_response("k1", _MODEL, data, 1.0, "").verdict == "UNCLEAR"


def test_parse_response_bare_no_downgrades() -> None:
    # Arrange：裸 NO（无证据终态会把真球挡在人工审核外，同样降级）
    data = {"choices": [{"message": {"content": "NO"}}]}
    # Act / Assert
    assert parse_response("k1", _MODEL, data, 1.0, "").verdict == "UNCLEAR"


def test_parse_response_analyzed_no_kept() -> None:
    # Arrange：带分析的 NO
    data = {"choices": [{"message": {"content": "全程运球推进，无投篮动作，球未到筐区。\nNO"}}]}
    # Act / Assert
    assert parse_response("k1", _MODEL, data, 1.0, "").verdict == "NO"


def test_parse_response_empty_content_is_err() -> None:
    # Arrange：取不到 content
    data = {"choices": []}
    # Act / Assert
    assert parse_response("k1", _MODEL, data, 1.0, "").verdict == "ERR"


def test_parse_response_usage_missing_defaults_zero() -> None:
    # Arrange：无 usage 字段
    data = {"choices": [{"message": {"content": "分析\nNO"}}]}
    # Act
    res = parse_response("k1", _MODEL, data, 1.0, "")
    # Assert
    assert res.usage == Usage()


def test_is_model_unavailable_404() -> None:
    # Arrange / Act / Assert
    assert is_model_unavailable(404, "whatever") is True


def test_is_model_unavailable_markers() -> None:
    # Arrange：方舟典型模型错误文案
    bodies = [
        '{"error":{"code":"ModelNotOpen","message":"Model doubao-x is not open"}}',
        '{"error":{"message":"The model `doubao-x` does not exist"}}',
        '{"error":{"message":"model has been Shutdown"}}',
        '{"error":{"code":"NotFound","message":"Model not found"}}',
    ]
    # Act / Assert
    for body in bodies:
        assert is_model_unavailable(400, body) is True


def test_is_model_unavailable_other_errors() -> None:
    # Arrange / Act / Assert：限流/普通参数错不应触发换模型
    assert is_model_unavailable(429, "rate limit exceeded") is False
    assert is_model_unavailable(400, "invalid request: bad fps") is False


def test_load_manifest_ok(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps([{"key": "a#e1", "truth": "POS", "file": "a.mp4", "crop": True}]),
        encoding="utf-8",
    )
    # Act
    entries = load_manifest(path)
    # Assert
    assert entries == [ManifestEntry(key="a#e1", truth="POS", file="a.mp4", crop=True)]


def test_load_manifest_schema_errors(tmp_path: Path) -> None:
    # Arrange：四类损坏——顶层非数组、truth 非法、缺字段、key 重复
    bad_payloads = [
        {"key": "a"},
        [{"key": "a", "truth": "MAYBE", "file": "a.mp4", "crop": True}],
        [{"key": "a", "truth": "POS", "crop": True}],
        [
            {"key": "a", "truth": "POS", "file": "a.mp4", "crop": True},
            {"key": "a", "truth": "NEG", "file": "b.mp4", "crop": False},
        ],
    ]
    for payload in bad_payloads:
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        # Act / Assert
        with pytest.raises(SchemaError):
            load_manifest(path)


def test_result_roundtrip() -> None:
    # Arrange
    res = _result("k1", "YES", latency_sec=12.34)
    # Act
    restored = result_from_dict("k1", asdict(res))
    # Assert：含 float latency 与嵌套 Usage 的完整往返
    assert restored == res


def test_results_save_load_roundtrip(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "ark_results.json"
    results = {"k1": _result("k1", "YES"), "k2": _result("k2", "NO")}
    # Act
    save_results(path, _MODEL, {"m-old": "err"}, results)
    meta, loaded = load_results(path)
    # Assert
    assert meta["prompt_version"] == PROMPT_VERSION
    assert meta["model"] == _MODEL
    assert meta["model_errors"] == {"m-old": "err"}
    assert loaded == results


def test_load_results_protocol_mismatch_invalidates(tmp_path: Path) -> None:
    # Arrange：prompt 版本不符的旧结果文件
    path = tmp_path / "ark_results.json"
    path.write_text(
        json.dumps(
            {
                "_meta": {"prompt_version": "ark-p1-v0", "fps": VIDEO_FPS},
                "results": {"k1": asdict(_result("k1", "YES"))},
            }
        ),
        encoding="utf-8",
    )
    # Act
    meta, loaded = load_results(path)
    # Assert：作废重开
    assert meta == {}
    assert loaded == {}


def test_load_results_missing_file(tmp_path: Path) -> None:
    # Arrange / Act
    meta, loaded = load_results(tmp_path / "nonexistent.json")
    # Assert
    assert meta == {}
    assert loaded == {}


def test_aggregate_confusion_full_matrix() -> None:
    # Arrange：POS 覆盖 YES/UNCLEAR/NO/ERR/PENDING，NEG 覆盖 NO/YES/ERR
    entries = [
        _entry("p1", "POS"),
        _entry("p2", "POS"),
        _entry("p3", "POS"),
        _entry("p4", "POS"),
        _entry("p5", "POS"),
        _entry("n1", "NEG"),
        _entry("n2", "NEG"),
        _entry("n3", "NEG"),
    ]
    results = {
        "p1": _result("p1", "YES", prompt_tokens=100, completion_tokens=10, latency_sec=2.0),
        "p2": _result("p2", "UNCLEAR", prompt_tokens=200, completion_tokens=20, latency_sec=3.0),
        "p3": _result("p3", "NO"),
        "p4": _result("p4", "ERR"),
        "n1": _result("n1", "NO"),
        "n2": _result("n2", "YES"),
        "n3": _result("n3", "ERR"),
    }
    # Act
    stats = aggregate_confusion(entries, results)
    # Assert
    assert stats.pos == {"YES": 1, "UNCLEAR": 1, "NO": 1, "ERR": 1, "PENDING": 1}
    assert stats.neg == {"YES": 1, "UNCLEAR": 0, "NO": 1, "ERR": 1, "PENDING": 0}
    assert stats.pos_as_no == ("p3",)
    assert stats.neg_as_yes == ("n2",)
    assert stats.pending == ("p5",)
    assert stats.input_tokens == 100 + 200 + 10 * 5
    assert stats.output_tokens == 10 + 20 + 5 * 5
    assert stats.judged == 7
    assert stats.latency_sec == 2.0 + 3.0 + 1.5 * 5


def test_aggregate_confusion_empty() -> None:
    # Arrange / Act
    stats = aggregate_confusion([], {})
    # Assert
    assert stats.judged == 0
    assert stats.pos == {"YES": 0, "UNCLEAR": 0, "NO": 0, "ERR": 0, "PENDING": 0}


def test_load_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    # Act / Assert
    with pytest.raises(ExternalApiError):
        load_api_key()


def test_load_api_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("ARK_API_KEY", "ark-test-dummy")
    # Act / Assert
    assert load_api_key() == "ark-test-dummy"
