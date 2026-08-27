"""face_match_scorers.py 单元测试（注册净化/比对/采纳闸/缓存/schema/CLI）。

全部合成数据 + 假识别器：不 import insightface/onnxruntime、不碰真模型真权重、
不碰网络与真实素材（console cp1252：测试内不 print 中文）。
覆盖：注册净化各分支（合格/无脸/小脸/宽度边界/号码全灭 WARNING/全库无效显式
失败/检测异常留痕）、注册审计（kept/dropped+原因+尺寸）、比对 top-1（每号码
max over photos、best 帧采纳、并列不采纳、单号码库 margin=+inf）、阈值边界
（sim==THRESHOLD 过、低即不过）、无脸裁图跳过记数、裁图缺失记数、单球失败
ERROR 不炸批、缓存幂等（含无脸缓存、模型前缀隔离、损坏显式失败）、号码归一化
（07→7）、产物过 validate_matches_payload 联调、CLI 端到端与失败路径 rc=1。
"""

from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import face_match_scorers as fms
from cluster_scorers import STATUS_OK, GoalCrops, file_md5, l2_normalize, merge_candidates
from errors import BasketballPipelineError, SchemaError
from face_match_scorers import (
    FACE_CACHE_NAME,
    MATCH_VERSION,
    MIN_FACE_WIDTH,
    MODEL_TAG,
    PHOTO_FACE_CACHE_NAME,
    REGISTRATION_AUDIT_NAME,
    THRESHOLD,
    AuditEntry,
    DetectedFace,
    GoalMatch,
    _parse_args,
    adopt,
    audit_payload,
    build_matches_payload,
    load_face_cache,
    main,
    match_goal,
    match_goals,
    register_gallery,
    save_face_cache,
    score_crop,
    top_hit,
)
from photo_match_scorers import scan_gallery, validate_matches_payload


def _vec(*xs: float) -> np.ndarray:
    """构造浮点向量（不保证归一，被测代码统一 L2 归一）。"""
    return np.asarray(xs, dtype=np.float64)


def _unit(*xs: float) -> np.ndarray:
    """构造 L2 归一化向量。"""
    return l2_normalize(_vec(*xs))


def _face(w: int, h: int, emb: tuple[float, ...], det: float = 0.9) -> DetectedFace:
    """构造一张合成检出脸。"""
    return DetectedFace(width=w, height=h, det_score=det, embedding=_vec(*emb))


class FakeDetector:
    """假识别器：按文件名查合成脸表并计数；表值为 Exception 实例时抛出（注入失败）。"""

    def __init__(self, table: dict[str, Any]) -> None:
        self.table = table
        self.calls = 0

    def __call__(self, path: Path) -> list[DetectedFace]:
        self.calls += 1
        value: Any = self.table[path.name]
        if isinstance(value, Exception):
            raise value
        return value


def _write_photos(photos_dir: Path, layout: dict[str, list[str]]) -> Path:
    """落一个合成照片库：layout = 文件夹名 → 照片文件名列表。"""
    for folder, names in layout.items():
        d = photos_dir / folder
        d.mkdir(parents=True, exist_ok=True)
        for name in names:
            (d / name).write_bytes(f"fake-img-{folder}-{name}".encode())
    return photos_dir


def _write_candidates(path: Path, entries: list[dict[str, Any]]) -> Path:
    """落一份 scorer_candidates.json。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"session": "s", "candidates": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _cache_key(path: Path, model_tag: str = MODEL_TAG) -> str:
    """缓存键 = ``model_tag:文件 md5``。"""
    return f"{model_tag}:{file_md5(path)}"


def _gallery_vecs() -> dict[str, tuple[np.ndarray, ...]]:
    """两号码正交单位向量库：7 号 = (1,0,0)，9 号 = (0,1,0)。"""
    return {"7": (_unit(1.0, 0.0, 0.0),), "9": (_unit(0.0, 1.0, 0.0),)}


def _write_crops(d: Path, names: list[str]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name in names:
        (d / name).write_bytes(f"crop-{name}".encode())


class TestLazyImport:
    """惰性 import：加载本模块不得拉进 insightface/onnxruntime（测试不碰真模型）。"""

    def test_module_import_does_not_load_insightface(self) -> None:
        assert "insightface" not in sys.modules
        assert "onnxruntime" not in sys.modules


class TestImreadUnicode:
    """中文路径读图：np.fromfile+cv2.imdecode（cv2.imread 中文路径静默 None 的既有教训）。"""

    def test_chinese_filename_roundtrip(self, tmp_path: Path) -> None:
        # Arrange：cv2.imencode 出真 jpg 字节，Path.write_bytes 落中文文件名
        # （cv2.imwrite 中文路径同样失败，写盘绕开 cv2）
        import cv2

        img = np.zeros((8, 12, 3), dtype=np.uint8)
        img[:] = (1, 2, 3)
        ok, buf = cv2.imencode(".jpg", img)
        assert ok
        p = tmp_path / "照片_中文名.jpg"
        p.write_bytes(buf.tobytes())
        # Act
        loaded = fms._imread_unicode(p)
        # Assert
        assert isinstance(loaded, np.ndarray)
        assert loaded.shape[:2] == (8, 12)

    def test_undecodable_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "坏图.jpg"
        p.write_bytes(b"not an image")
        with pytest.raises(BasketballPipelineError, match="解码失败"):
            fms._imread_unicode(p)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(BasketballPipelineError, match="不可读"):
            fms._imread_unicode(tmp_path / "ghost.jpg")


class TestRegistrationGate:
    """注册净化：最大面积脸 + 宽 ≥MIN_FACE_WIDTH 才注册，其余弃用留痕。"""

    def _register(
        self, tmp_path: Path, layout: dict[str, list[str]], table: dict[str, Any]
    ) -> tuple[dict[str, tuple[np.ndarray, ...]], list[AuditEntry], FakeDetector, dict[str, Any]]:
        gallery = scan_gallery(_write_photos(tmp_path / "photos", layout))
        detector = FakeDetector(table)
        cache: dict[str, Any] = {}
        vectors, audit = register_gallery(gallery, lambda: detector, cache, MODEL_TAG)
        return vectors, audit, detector, cache

    def test_kept_big_face(self, tmp_path: Path) -> None:
        vectors, audit, _, _ = self._register(
            tmp_path, {"7": ["a.jpg"]}, {"a.jpg": [_face(300, 400, (1.0, 0.0, 0.0))]}
        )
        assert list(vectors) == ["7"]
        assert np.allclose(vectors["7"][0], _unit(1.0, 0.0, 0.0))  # 已 L2 归一
        assert audit[0].kept is True
        assert audit[0].face_w == 300

    def test_max_area_face_picked_not_max_det(self, tmp_path: Path) -> None:
        # Arrange：小脸 det 更高（spike 教训：det 最大脸可能是背景路人）
        faces = [
            _face(90, 90, (0.0, 1.0, 0.0), det=0.99),
            _face(300, 400, (1.0, 0.0, 0.0), det=0.80),
        ]
        vectors, audit, _, _ = self._register(tmp_path, {"7": ["a.jpg"]}, {"a.jpg": faces})
        # Assert：注册的是大脸 (1,0,0)，不是 det 最高的小脸
        assert np.allclose(vectors["7"][0], _unit(1.0, 0.0, 0.0))
        assert audit[0].kept is True

    def test_dropped_no_face(self, tmp_path: Path) -> None:
        # Arrange：7 无脸弃用（全灭 WARNING 不阻塞）、9 合格保底（全灭才显式报错）
        vectors, audit, _, _ = self._register(
            tmp_path,
            {"7": ["a.jpg"], "9": ["b.jpg"]},
            {"a.jpg": [], "b.jpg": [_face(300, 400, (0.0, 1.0, 0.0))]},
        )
        assert list(vectors) == ["9"]
        assert audit[0].kept is False
        assert "no face" in (audit[0].reason or "")

    def test_dropped_small_face(self, tmp_path: Path) -> None:
        vectors, audit, _, _ = self._register(
            tmp_path,
            {"7": ["a.jpg"], "9": ["b.jpg"]},
            {
                "a.jpg": [_face(MIN_FACE_WIDTH - 1, 400, (1.0, 0.0, 0.0))],
                "b.jpg": [_face(300, 400, (0.0, 1.0, 0.0))],
            },
        )
        assert list(vectors) == ["9"]
        assert audit[0].kept is False
        assert str(MIN_FACE_WIDTH - 1) in (audit[0].reason or "")
        assert audit[0].face_w == MIN_FACE_WIDTH - 1  # 弃用也留尺寸

    def test_boundary_width_kept(self, tmp_path: Path) -> None:
        vectors, _, _, _ = self._register(
            tmp_path,
            {"7": ["a.jpg"]},
            {"a.jpg": [_face(MIN_FACE_WIDTH, 400, (1.0, 0.0, 0.0))]},
        )
        assert list(vectors) == ["7"]

    def test_number_all_dropped_warns_others_kept(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            vectors, audit, _, _ = self._register(
                tmp_path,
                {"7": ["a.jpg"], "9": ["b.jpg"]},
                {"a.jpg": [], "b.jpg": [_face(300, 400, (0.0, 1.0, 0.0))]},
            )
        assert list(vectors) == ["9"]
        assert any("7" in r.message for r in caplog.records if r.levelno == logging.WARNING)
        assert [a.kept for a in audit] == [False, True]

    def test_all_numbers_empty_raises(self, tmp_path: Path) -> None:
        with pytest.raises(BasketballPipelineError, match="无可用"):
            self._register(tmp_path, {"7": ["a.jpg"], "9": ["b.jpg"]}, {"a.jpg": [], "b.jpg": []})

    def test_detector_error_recorded_not_blocking(self, tmp_path: Path) -> None:
        vectors, audit, _, _ = self._register(
            tmp_path,
            {"7": ["a.jpg", "b.jpg"]},
            {"a.jpg": RuntimeError("boom"), "b.jpg": [_face(300, 400, (1.0, 0.0, 0.0))]},
        )
        assert list(vectors) == ["7"]  # 好照片仍注册
        assert audit[0].kept is False
        assert "boom" in (audit[0].reason or "")

    def test_photo_cache_idempotent_including_no_face(self, tmp_path: Path) -> None:
        # Arrange：一张合格 + 一张无脸
        layout = {"7": ["a.jpg", "b.jpg"]}
        table = {"a.jpg": [_face(300, 400, (1.0, 0.0, 0.0))], "b.jpg": []}
        vectors1, _, det1, cache = self._register(tmp_path, layout, table)
        assert det1.calls == 2
        # Act：缓存落盘重读，注入全新计数识别器二跑
        cache_path = tmp_path / PHOTO_FACE_CACHE_NAME
        save_face_cache(cache_path, MODEL_TAG, cache)
        cache2 = load_face_cache(cache_path)
        gallery = scan_gallery(tmp_path / "photos")
        det2 = FakeDetector(table)
        vectors2, audit2 = register_gallery(gallery, lambda: det2, cache2, MODEL_TAG)[0:2]
        # Assert：全缓存命中（含无脸 None 条目）零推理，结果一致
        assert det2.calls == 0
        assert list(vectors2) == list(vectors1)
        assert [a.kept for a in audit2] == [True, False]
        assert cache2[_cache_key(tmp_path / "photos" / "7" / "b.jpg")] is None


class TestAuditPayload:
    """注册审计落盘格式：kept/dropped + 原因 + 尺寸。"""

    def test_payload_structure(self) -> None:
        audit = [
            AuditEntry("7", "a.jpg", True, None, 300, 400, 0.9),
            AuditEntry("8", "b.jpg", False, "no face", None, None, None),
        ]
        payload = audit_payload(audit, MODEL_TAG)
        assert payload["model"] == MODEL_TAG
        photos = payload["photos"]
        assert photos[0] == {
            "number": "7",
            "file": "a.jpg",
            "kept": True,
            "picked": {"w": 300, "h": 400, "det": 0.9},
        }
        assert photos[1] == {"number": "8", "file": "b.jpg", "kept": False, "reason": "no face"}
        # JSON 可序列化（落盘前提）
        json.loads(json.dumps(payload, ensure_ascii=False))


class TestScoring:
    """比对：每号码 max over photos 余弦、top-1、并列不采纳、单号码库 margin=+inf。"""

    def test_score_crop_max_over_photos(self) -> None:
        gallery = {"7": (_unit(1.0, 0.0), _unit(0.0, 1.0)), "9": (_unit(0.6, 0.8),)}
        sims = score_crop(_unit(0.0, 1.0), gallery)
        assert sims["7"] == pytest.approx(1.0)  # 第二张照片命中
        assert sims["9"] == pytest.approx(0.8)

    def test_top_hit_basic(self) -> None:
        hit = top_hit({"7": 0.9, "9": 0.6, "11": 0.3})
        assert hit.number == "7"
        assert hit.sim == pytest.approx(0.9)
        assert hit.margin == pytest.approx(0.3)

    def test_top_hit_tie_not_adopted(self) -> None:
        hit = top_hit({"7": 0.5, "9": 0.5})
        assert hit.number is None
        assert hit.margin == 0.0

    def test_top_hit_single_number_margin_inf(self) -> None:
        hit = top_hit({"7": 0.45})
        assert hit.number == "7"
        assert math.isinf(hit.margin)

    def test_top_hit_empty_raises(self) -> None:
        with pytest.raises(BasketballPipelineError):
            top_hit({})


class TestAdoptGate:
    """采纳闸：best sim ≥ THRESHOLD（含等于）；无命中/无脸恒不过。"""

    def _m(self, number: str | None, score: float | None) -> GoalMatch:
        return GoalMatch(number, score, 0.1, 1, 1, 0, 0)

    def test_exact_threshold_adopted(self) -> None:
        assert adopt(self._m("7", THRESHOLD), THRESHOLD)

    def test_below_threshold_rejected(self) -> None:
        assert not adopt(self._m("7", THRESHOLD - 0.001), THRESHOLD)

    def test_tie_never_adopted(self) -> None:
        assert not adopt(self._m(None, 0.99), THRESHOLD)

    def test_no_face_never_adopted(self) -> None:
        assert not adopt(self._m(None, None), THRESHOLD)


class TestMatchGoal:
    """单球比对：best 帧采纳、无脸裁图跳过记数、裁图缺失记数、失败可注入。"""

    def _goal(self, d: Path, key: str, crops: list[str], status: str = STATUS_OK) -> GoalCrops:
        return GoalCrops(key=key, status=status, crops=tuple(crops), crop_scores=(), base_dir=d)

    def test_best_frame_wins(self, tmp_path: Path) -> None:
        d = tmp_path / "scorers"
        _write_crops(d, ["c1.jpg", "c2.jpg", "c3.jpg"])
        table = {
            "c1.jpg": [_face(50, 60, (0.6, 0.8, 0.0))],  # 9@0.8
            "c2.jpg": [_face(50, 60, (1.0, 0.0, 0.0))],  # 7@1.0 全场最佳
            "c3.jpg": [_face(50, 60, (0.0, 1.0, 0.0))],  # 9@1.0 并列最佳但靠后
        }
        goal = self._goal(d, "a.mp4#1.0", ["c1.jpg", "c2.jpg", "c3.jpg"])
        m = match_goal(goal, _gallery_vecs(), {}, MODEL_TAG, lambda: FakeDetector(table))
        assert m.number == "7"
        assert m.score == pytest.approx(1.0)
        assert m.margin == pytest.approx(1.0)
        assert m.n_face == 3

    def test_no_face_crops_skipped_counted(self, tmp_path: Path) -> None:
        d = tmp_path / "scorers"
        _write_crops(d, ["c1.jpg", "c2.jpg"])
        table = {"c1.jpg": [], "c2.jpg": [_face(50, 60, (1.0, 0.0, 0.0))]}
        goal = self._goal(d, "a.mp4#1.0", ["c1.jpg", "c2.jpg"])
        m = match_goal(goal, _gallery_vecs(), {}, MODEL_TAG, lambda: FakeDetector(table))
        assert m.number == "7"
        assert m.n_no_face == 1
        assert m.n_face == 1

    def test_all_crops_no_face_not_adopted(self, tmp_path: Path) -> None:
        d = tmp_path / "scorers"
        _write_crops(d, ["c1.jpg"])
        goal = self._goal(d, "a.mp4#1.0", ["c1.jpg"])
        m = match_goal(goal, _gallery_vecs(), {}, MODEL_TAG, lambda: FakeDetector({"c1.jpg": []}))
        assert m.number is None
        assert m.score is None
        assert not adopt(m, THRESHOLD)

    def test_missing_crop_file_counted(self, tmp_path: Path) -> None:
        d = tmp_path / "scorers"
        _write_crops(d, ["c2.jpg"])
        table = {"c2.jpg": [_face(50, 60, (1.0, 0.0, 0.0))]}
        goal = self._goal(d, "a.mp4#1.0", ["ghost.jpg", "c2.jpg"])
        m = match_goal(goal, _gallery_vecs(), {}, MODEL_TAG, lambda: FakeDetector(table))
        assert m.n_missing == 1
        assert m.number == "7"


class TestMatchGoals:
    """批量：单球失败 ERROR 不炸批；SKIP/无裁图不出分；裁图缓存幂等。"""

    def _goals(self, tmp_path: Path) -> tuple[dict[str, Any], Path]:
        d = tmp_path / "scorers"
        _write_crops(d, ["c1.jpg", "c2.jpg", "c3.jpg", "c4.jpg"])
        cand = _write_candidates(
            d / "scorer_candidates.json",
            [
                {"key": "a.mp4#1.0", "status": "OK", "crops": ["c1.jpg"]},
                {"key": "a.mp4#2.0", "status": "OK", "crops": ["c2.jpg"]},
                {"key": "a.mp4#3.0", "status": "OK", "crops": ["c3.jpg", "c4.jpg"]},
                {"key": "a.mp4#4.0", "status": "SKIP"},
            ],
        )
        return merge_candidates([cand]), d

    def _table(self) -> dict[str, Any]:
        return {
            "c1.jpg": [_face(50, 60, (1.0, 0.0, 0.0))],  # 7@1.0
            "c2.jpg": RuntimeError("detector boom"),  # 单球失败注入
            "c3.jpg": [],
            "c4.jpg": [_face(50, 60, (0.0, 1.0, 0.0))],  # 9@1.0
        }

    def test_single_goal_failure_not_blocking(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        goals, _ = self._goals(tmp_path)
        with caplog.at_level(logging.ERROR):
            results = match_goals(
                goals, _gallery_vecs(), lambda: FakeDetector(self._table()), MODEL_TAG
            )
        assert list(results) == ["a.mp4#1.0", "a.mp4#3.0"]  # k2 失败跳过、k4 SKIP 不出分
        assert results["a.mp4#1.0"].number == "7"
        assert results["a.mp4#3.0"].number == "9"  # c3 无脸跳过、c4 命中
        assert any("a.mp4#2.0" in r.message for r in caplog.records if r.levelno == logging.ERROR)

    def test_crop_cache_idempotent_second_run_zero_calls(self, tmp_path: Path) -> None:
        goals, d = self._goals(tmp_path)
        table = self._table()
        table["c2.jpg"] = [_face(50, 60, (0.0, 1.0, 0.0))]
        det1 = FakeDetector(table)
        match_goals(goals, _gallery_vecs(), lambda: det1, MODEL_TAG)
        assert det1.calls == 4
        assert (d / FACE_CACHE_NAME).is_file()
        # Act：二跑注入全新计数识别器
        det2 = FakeDetector(table)
        results2 = match_goals(goals, _gallery_vecs(), lambda: det2, MODEL_TAG)
        # Assert：含无脸 c3 全缓存命中，零推理
        assert det2.calls == 0
        assert results2["a.mp4#3.0"].number == "9"

    def test_detector_factory_called_once_for_batch(self, tmp_path: Path) -> None:
        # Arrange：3 个 OK 球缓存全未命中（c2 换成正常脸避免失败分支干扰）
        goals, _ = self._goals(tmp_path)
        table = self._table()
        table["c2.jpg"] = [_face(50, 60, (0.0, 1.0, 0.0))]
        fake = FakeDetector(table)
        factory_calls = 0

        def counting_factory() -> FakeDetector:
            nonlocal factory_calls
            factory_calls += 1
            return fake

        # Act
        match_goals(goals, _gallery_vecs(), counting_factory, MODEL_TAG)
        # Assert：检测器提升到批级，N 球只建一次（球级重建 = 每球全量加载模型）
        assert factory_calls == 1
        assert fake.calls == 4

    def test_detector_factory_zero_calls_when_all_cached(self, tmp_path: Path) -> None:
        # Arrange：首跑建满缓存
        goals, _ = self._goals(tmp_path)
        table = self._table()
        table["c2.jpg"] = [_face(50, 60, (0.0, 1.0, 0.0))]
        match_goals(goals, _gallery_vecs(), lambda: FakeDetector(table), MODEL_TAG)
        factory_calls = 0

        def counting_factory() -> FakeDetector:
            nonlocal factory_calls
            factory_calls += 1
            return FakeDetector(table)

        # Act：二跑全缓存命中
        match_goals(goals, _gallery_vecs(), counting_factory, MODEL_TAG)
        # Assert：惰性保持——零加载模型
        assert factory_calls == 0

    def test_corrupt_crop_cache_raises(self, tmp_path: Path) -> None:
        goals, d = self._goals(tmp_path)
        (d / FACE_CACHE_NAME).write_text(json.dumps({"entries": {"k": 123}}), encoding="utf-8")
        with pytest.raises(SchemaError):
            match_goals(goals, _gallery_vecs(), lambda: FakeDetector(self._table()), MODEL_TAG)


class TestFaceCache:
    """缓存读写：缺失→空、损坏→SchemaError、模型前缀隔离、原子落盘可回读。"""

    def test_missing_returns_empty(self, tmp_path: Path) -> None:
        assert load_face_cache(tmp_path / "ghost" / FACE_CACHE_NAME) == {}

    def test_roundtrip_and_prefix_isolated(self, tmp_path: Path) -> None:
        path = tmp_path / FACE_CACHE_NAME
        foreign = "OldModel/x:deadbeef"
        entry = {"w": 300, "h": 400, "det": 0.9, "emb": [1.0, 0.0]}
        save_face_cache(path, MODEL_TAG, {foreign: None, f"{MODEL_TAG}:aa": entry})
        loaded = load_face_cache(path)
        assert loaded[foreign] is None  # 外模型键保留不冲
        assert loaded[f"{MODEL_TAG}:aa"] == entry

    def test_corrupt_raises(self, tmp_path: Path) -> None:
        path = tmp_path / FACE_CACHE_NAME
        path.write_text(json.dumps({"entries": [1, 2]}), encoding="utf-8")
        with pytest.raises(SchemaError):
            load_face_cache(path)
        path.write_text(json.dumps({"entries": {"k": {"w": "x"}}}), encoding="utf-8")
        with pytest.raises(SchemaError):
            load_face_cache(path)

    def test_bool_w_h_rejected(self, tmp_path: Path) -> None:
        # Arrange：True 是 int 子类，w/h 必须与 det 一致排除 bool
        path = tmp_path / FACE_CACHE_NAME
        bad = {"w": True, "h": 400, "det": 0.9, "emb": [1.0, 0.0]}
        path.write_text(json.dumps({"entries": {"k": bad}}), encoding="utf-8")
        # Act / Assert
        with pytest.raises(SchemaError, match="w/h"):
            load_face_cache(path)


class TestBuildPayload:
    """photo_matches.json 载荷：仅高置信命中入 matches，实测 score/margin，过 schema 校验。"""

    def test_only_adopted_in_payload(self) -> None:
        results = {
            "k1": GoalMatch("7", 0.62, 0.4, 1, 1, 0, 0),  # 过闸
            "k2": GoalMatch("9", 0.39, 0.2, 1, 1, 0, 0),  # 阈值下
            "k3": GoalMatch(None, None, None, 1, 0, 1, 0),  # 无脸
            "k4": GoalMatch(None, 0.9, 0.0, 1, 1, 0, 0),  # 并列
        }
        payload = build_matches_payload(results, THRESHOLD, MODEL_TAG)
        assert payload["version"] == MATCH_VERSION
        assert payload["model"] == MODEL_TAG
        assert payload["threshold"] == THRESHOLD
        assert payload["margin"] == 0.0  # 人脸单路不设 margin 闸（占位）
        assert list(payload["matches"]) == ["k1"]
        assert payload["matches"]["k1"] == {"number": "7", "score": 0.62, "margin": 0.4}
        # 红线联调：产物过既有 validate_matches_payload 零改动消费
        entries = validate_matches_payload(json.loads(json.dumps(payload)), "<mem>")
        assert entries["k1"].number == "7"

    def test_inf_margin_json_roundtrip(self) -> None:
        # Arrange：单号码库命中 margin=+inf → json 落 Infinity，Python 可回读
        payload = build_matches_payload(
            {"k1": GoalMatch("7", 0.9, math.inf, 1, 1, 0, 0)}, THRESHOLD, MODEL_TAG
        )
        entries = validate_matches_payload(json.loads(json.dumps(payload)), "<mem>")
        assert math.isinf(entries["k1"].margin)


class TestParseArgs:
    """CLI 解析：--photos/--candidates/--out 必填；--candidates 可重复。"""

    def test_required_args(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args([])
        with pytest.raises(SystemExit):
            _parse_args(["--photos", "p"])

    def test_full_accepted(self) -> None:
        ns = _parse_args(
            ["--photos", "p", "--candidates", "a.json", "--candidates", "b.json", "--out", "o.json"]
        )
        assert ns.photos == Path("p")
        assert ns.candidates == [Path("a.json"), Path("b.json")]
        assert ns.out == Path("o.json")


class TestMainCli:
    """CLI 端到端：monkeypatch 假识别器不碰真模型；产物/审计/缓存落盘；失败 rc=1。"""

    def _setup(self, tmp_path: Path) -> dict[str, Path]:
        photos = _write_photos(tmp_path / "photos", {"07": ["p7a.jpg"], "9": ["p9a.jpg"]})
        scorers = tmp_path / "scorers"
        _write_crops(scorers, ["c1.jpg", "c2.jpg", "c3.jpg", "c5.jpg"])
        cand = _write_candidates(
            scorers / "scorer_candidates.json",
            [
                {"key": "a.mp4#1.0", "status": "OK", "crops": ["c1.jpg"]},
                {"key": "a.mp4#2.0", "status": "OK", "crops": ["c2.jpg"]},
                {"key": "a.mp4#3.0", "status": "OK", "crops": ["c3.jpg"]},
                {"key": "a.mp4#4.0", "status": "SKIP"},
                {"key": "a.mp4#5.0", "status": "OK", "crops": ["c5.jpg"]},
            ],
        )
        return {
            "photos": photos,
            "candidates": cand,
            "out": scorers / "photo_matches.json",
        }

    def _detector(self) -> FakeDetector:
        return FakeDetector(
            {
                "p7a.jpg": [_face(300, 400, (1.0, 0.0, 0.0))],
                "p9a.jpg": [_face(300, 400, (0.0, 1.0, 0.0))],
                "c1.jpg": [_face(50, 60, (1.0, 0.0, 0.0))],  # 7@1.0 过闸
                "c2.jpg": [_face(50, 60, (0.35, 0.30, 0.8874))],  # 7@0.35 阈值下
                "c3.jpg": [],  # 无脸
                "c5.jpg": [_face(50, 60, (0.0, 1.0, 0.0))],  # 9@1.0 过闸
            }
        )

    def _argv(self, paths: dict[str, Path]) -> list[str]:
        return [
            "--photos",
            str(paths["photos"]),
            "--candidates",
            str(paths["candidates"]),
            "--out",
            str(paths["out"]),
        ]

    def test_end_to_end(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        paths = self._setup(tmp_path)
        monkeypatch.setattr(fms, "build_face_detector", lambda: self._detector())
        rc = main(self._argv(paths))
        assert rc == 0
        payload = json.loads(paths["out"].read_text(encoding="utf-8"))
        entries = validate_matches_payload(payload, str(paths["out"]))
        # k1 中 7（文件夹 07 归一化为 7）、k5 中 9；k2 阈值下 / k3 无脸 / k4 SKIP 不入
        assert sorted(entries) == ["a.mp4#1.0", "a.mp4#5.0"]
        assert entries["a.mp4#1.0"].number == "7"
        assert entries["a.mp4#1.0"].score == pytest.approx(1.0)
        assert entries["a.mp4#5.0"].number == "9"
        assert payload["model"] == MODEL_TAG
        # 注册审计 + 双侧缓存落盘
        audit = json.loads((paths["photos"] / REGISTRATION_AUDIT_NAME).read_text(encoding="utf-8"))
        assert [p["kept"] for p in audit["photos"]] == [True, True]
        assert (paths["photos"] / PHOTO_FACE_CACHE_NAME).is_file()
        assert (paths["candidates"].parent / FACE_CACHE_NAME).is_file()

    def test_second_run_zero_detector_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        paths = self._setup(tmp_path)
        monkeypatch.setattr(fms, "build_face_detector", lambda: self._detector())
        assert main(self._argv(paths)) == 0
        det2 = self._detector()
        monkeypatch.setattr(fms, "build_face_detector", lambda: det2)
        assert main(self._argv(paths)) == 0
        assert det2.calls == 0  # 照片+裁图（含无脸）全缓存命中

    def test_missing_photos_dir_returns_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        paths = self._setup(tmp_path)
        monkeypatch.setattr(fms, "build_face_detector", lambda: self._detector())
        rc = main(
            [
                "--photos",
                str(tmp_path / "ghost"),
                "--candidates",
                str(paths["candidates"]),
                "--out",
                str(paths["out"]),
            ]
        )
        assert rc == 1

    def test_all_photos_faceless_returns_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        paths = self._setup(tmp_path)
        monkeypatch.setattr(
            fms,
            "build_face_detector",
            lambda: FakeDetector({"p7a.jpg": [], "p9a.jpg": []}),
        )
        rc = main(self._argv(paths))
        assert rc == 1
        assert not paths["out"].exists()
