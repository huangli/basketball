"""gen_triage_page 单元测试：缩略图生成降级路径 + triage.html 硬规定回归断言。

覆盖：帧号钳位（高端/低端/零帧）、缺帧降级不崩且有 WARNING、key 文件名
安全化、残次事件跳过 + WARNING；html 含合并写关键代码、含 F 按钮禁用逻辑、
含 loading="lazy"、不含 POSKEY 写、raw string 下 \\n 字面量检查
（仿 test_gen_label_page.py 的黑屏回归断言）。
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from PIL import Image

from errors import BasketballPipelineError
from gen_triage_page import (
    CROP_WIDTH,
    build_event_thumbs,
    build_html,
    derive_session,
    frame_indices,
    load_anchors,
    make_thumbnail,
    safe_name,
)


def _event(
    key: str = "f1#e0",
    fid: str = "f1",
    anchor_t0: float = 1.0,
    verdict: str = "",
) -> dict[str, Any]:
    """构造一条合法事件记录（结构与 events_index.json 一致）。"""
    return {
        "key": key,
        "fid": fid,
        "event_idx": 0,
        "clip": "clips/a.mp4",
        "clip_wide": "clips/a_wide.mp4",
        "src_file": "a.mp4",
        "anchor_t0": anchor_t0,
        "hoop_dist": 46,
        "verdict": verdict,
    }


def _make_frames(root: pathlib.Path, fid: str, idxs: list[int]) -> None:
    """在 root/<fid>/ 下生成指定帧号的小帧图（PIL 纯色图即可）。"""
    d = root / fid
    d.mkdir(parents=True, exist_ok=True)
    for i in idxs:
        Image.new("RGB", (96, 54), (i % 256, 0, 0)).save(d / f"f_{i:05d}.jpg", "JPEG")


# ---------- frame_indices：帧号钳位 ----------


def test_frame_indices_center_window() -> None:
    # Arrange：anchor 1.0s @5fps → 锚点帧 round(5)+1=6
    # Act / Assert：±2 帧 = 4/6/8
    assert frame_indices(1.0, 100) == [4, 6, 8]


def test_frame_indices_clamps_high() -> None:
    # Arrange：anchor 5.0s → 锚点帧 26，帧数 27（大疆尾截短：+2 帧物理不存在）
    # Act / Assert：+2 帧钳位到末帧 27，合法降级不越界
    assert frame_indices(5.0, 27) == [24, 26, 27]


def test_frame_indices_clamps_low_and_dedupes() -> None:
    # Arrange：anchor 0.0s → 锚点帧 1，-2 帧钳位到 1 与锚点帧重复
    # Act / Assert：钳位 [1, 帧数] 且去重
    assert frame_indices(0.0, 27) == [1, 3]


def test_frame_indices_zero_frames_returns_empty() -> None:
    # Arrange / Act / Assert：帧目录缺失（计数 0）→ 空列表，不产生越界帧号
    assert frame_indices(1.0, 0) == []


# ---------- safe_name：文件名安全化 ----------


def test_safe_name_strips_unfriendly_chars() -> None:
    # Arrange / Act
    name = safe_name("dji_x#e3@2/1")
    # Assert：#、@、/ 等全部替换，仅留安全字符
    assert "#" not in name and "@" not in name and "/" not in name
    assert name == "dji_x_e3_2_1"


def test_safe_name_keeps_safe_chars() -> None:
    # Arrange / Act / Assert：字母数字 . _ - 原样保留
    assert safe_name("abc-1_2.3") == "abc-1_2.3"


# ---------- build_event_thumbs：缩略图与降级 ----------


def test_build_event_thumbs_generates_480px(tmp_path: pathlib.Path) -> None:
    # Arrange：5 帧，anchor 0.4s → 锚点帧 3，±2 = 1/3/5 全在界内
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [1, 2, 3, 4, 5])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    # Act
    enriched, degraded, skipped = build_event_thumbs([_event(anchor_t0=0.4)], frames, thumbs_dir)
    # Assert：3 帧全产、480px 宽、无降级无跳过；thumbs 带帧号溯源
    assert skipped == [] and degraded == []
    assert [t["frame"] for t in enriched[0]["thumbs"]] == [1, 3, 5]
    for t in enriched[0]["thumbs"]:
        p = thumbs_dir / pathlib.PurePosixPath(t["src"]).name
        assert p.is_file()
        with Image.open(p) as im:
            assert im.width == 480


def test_build_event_thumbs_missing_frame_degrades(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange：f_00001 缺失（目录只有 2/3 两帧，计数=2），anchor 0.0s → 帧号 [1, 2]
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [2, 3])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    # Act
    with caplog.at_level("WARNING", logger="gen_triage_page"):
        enriched, degraded, skipped = build_event_thumbs(
            [_event(anchor_t0=0.0)], frames, thumbs_dir
        )
    # Assert：不崩，降级用可用帧（f_00002）+ WARNING + 降级清单记录
    assert skipped == []
    assert [t["frame"] for t in enriched[0]["thumbs"]] == [2]
    assert len(degraded) == 1 and "缺帧 f_00001" in degraded[0]
    assert "降级用可用帧" in caplog.text


def test_build_event_thumbs_missing_dir_degrades_to_zero_frames(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange：fid 帧目录整体缺失
    frames = tmp_path / "frames"
    frames.mkdir()
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    # Act
    with caplog.at_level("WARNING", logger="gen_triage_page"):
        enriched, degraded, skipped = build_event_thumbs([_event()], frames, thumbs_dir)
    # Assert：事件仍上墙（零帧卡片），降级清单记录帧目录缺失
    assert skipped == []
    assert enriched[0]["thumbs"] == []
    assert len(degraded) == 1 and "帧目录缺失" in degraded[0]
    assert "帧目录缺失或为空" in caplog.text


def test_build_event_thumbs_thumb_filename_sanitized(tmp_path: pathlib.Path) -> None:
    # Arrange：key 含 #
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [1, 2, 3, 4, 5, 6, 7, 8])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    # Act
    enriched, _, _ = build_event_thumbs([_event(key="f1#e3", anchor_t0=1.0)], frames, thumbs_dir)
    # Assert：落盘文件名无 #
    names = [p.name for p in thumbs_dir.iterdir()]
    assert names and all("#" not in n for n in names)
    assert all(t["src"].startswith("thumbs/t_") for t in enriched[0]["thumbs"])


def test_build_event_thumbs_skips_malformed_events(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange：缺 anchor_t0 / fid / key 的残次事件各一 + 一条合法事件
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [1, 2, 3, 4, 5, 6, 7, 8])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    events = [
        {"fid": "f1", "key": "f1#e0"},  # 缺 anchor_t0
        {"anchor_t0": 1.0, "key": "f1#e1"},  # 缺 fid
        {"fid": "f1", "anchor_t0": 1.0},  # 缺 key
        _event("f1#e2"),
    ]
    # Act
    with caplog.at_level("WARNING", logger="gen_triage_page"):
        enriched, degraded, skipped = build_event_thumbs(events, frames, thumbs_dir)
    # Assert：残次跳过 + WARNING，合法事件正常产图
    assert len(enriched) == 1 and enriched[0]["key"] == "f1#e2"
    assert len(skipped) == 3 and degraded == []
    assert caplog.text.count("跳过缩略图") == 3


def test_build_event_thumbs_does_not_mutate_input(tmp_path: pathlib.Path) -> None:
    # Arrange
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [4, 6, 8])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    events = [_event()]
    # Act
    build_event_thumbs(events, frames, thumbs_dir)
    # Assert：不改调用方原 dict
    assert "thumbs" not in events[0]


# ---------- make_thumbnail：筐区裁剪模式 ----------


def test_make_thumbnail_crop_mode_centers_on_anchor(tmp_path: pathlib.Path) -> None:
    # Arrange：96×54 帧图，anchor 正中
    src = tmp_path / "f.jpg"
    Image.new("RGB", (96, 54), (10, 20, 30)).save(src, "JPEG")
    dst = tmp_path / "t.jpg"
    # Act
    mode = make_thumbnail(src, dst, anchor=(48.0, 27.0))
    # Assert：裁剪模式 + 落盘宽度 = CROP_WIDTH
    assert mode == "crop"
    with Image.open(dst) as im:
        assert im.width == CROP_WIDTH


def test_make_thumbnail_crop_clamps_out_of_bounds_anchor(tmp_path: pathlib.Path) -> None:
    # Arrange：anchor 越界（负坐标，脏数据防御）
    src = tmp_path / "f.jpg"
    Image.new("RGB", (96, 54), (10, 20, 30)).save(src, "JPEG")
    dst = tmp_path / "t.jpg"
    # Act / Assert：钳位不崩，仍产裁剪图
    assert make_thumbnail(src, dst, anchor=(-50.0, 999.0)) == "crop"
    assert dst.is_file()


def test_make_thumbnail_full_mode_without_anchor(tmp_path: pathlib.Path) -> None:
    # Arrange / Act：无 anchor → 全景等比缩放（旧行为）
    src = tmp_path / "f.jpg"
    Image.new("RGB", (96, 54), (10, 20, 30)).save(src, "JPEG")
    dst = tmp_path / "t.jpg"
    assert make_thumbnail(src, dst) == "full"
    with Image.open(dst) as im:
        assert im.width == 480


# ---------- load_anchors：hoops 锚点映射 ----------


def _write_hoops(path: pathlib.Path, events: list[Any]) -> None:
    """写最小 hoops json（detect_hoops 产物结构）。"""
    path.write_text(json.dumps({"events": events}, ensure_ascii=False), encoding="utf-8")


def test_load_anchors_parses_valid_entries(tmp_path: pathlib.Path) -> None:
    # Arrange：两合法 + 三类非法（anchor 缺失 / 形状错 / 含 bool）
    p = tmp_path / "hoops.json"
    _write_hoops(
        p,
        [
            {"key": "f1#e0", "anchor": [931, 877]},
            {"key": "f1#e1", "anchor": [10.5, 20.5]},
            {"key": "f1#e2"},
            {"key": "f1#e3", "anchor": [1]},
            {"key": "f1#e4", "anchor": [True, 2]},
            "garbage",
        ],
    )
    # Act
    anchors = load_anchors(p)
    # Assert：仅合法两条进映射，非法静默跳过（降级归调用方记录）
    assert anchors == {"f1#e0": (931.0, 877.0), "f1#e1": (10.5, 20.5)}


def test_load_anchors_filters_non_finite(tmp_path: pathlib.Path) -> None:
    # Arrange：Python json 默认放行 NaN/Infinity 字面量，isfinite 防御过滤
    p = tmp_path / "hoops.json"
    p.write_text(
        '{"events": [{"key": "f1#e0", "anchor": [NaN, 2]},'
        ' {"key": "f1#e1", "anchor": [1, Infinity]},'
        ' {"key": "f1#e2", "anchor": [3, 4]}]}',
        encoding="utf-8",
    )
    # Act / Assert：仅有限值条目进映射（round(nan) 会在裁剪时炸整页生成）
    assert load_anchors(p) == {"f1#e2": (3.0, 4.0)}


def test_load_anchors_missing_file_raises_oserror(tmp_path: pathlib.Path) -> None:
    # Arrange / Act / Assert：文件缺失 read_json 重试后抛 OSError（main 捕获转退出码 1）
    with pytest.raises(OSError):
        load_anchors(tmp_path / "nope.json")


def test_load_anchors_corrupt_json_raises_pipeline_error(tmp_path: pathlib.Path) -> None:
    # Arrange：JSON 损坏
    p = tmp_path / "hoops.json"
    p.write_text("{not json", encoding="utf-8")
    # Act / Assert：read_json 口径抛 BasketballPipelineError
    with pytest.raises(BasketballPipelineError):
        load_anchors(p)


# ---------- build_event_thumbs：带锚点裁剪与降级 ----------


def test_build_event_thumbs_with_anchors_marks_crop_mode(tmp_path: pathlib.Path) -> None:
    # Arrange：两事件，一个有锚点一个没有
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [1, 2, 3, 4, 5])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    events = [_event("f1#e0", anchor_t0=0.4), _event("f1#e1", anchor_t0=0.4)]
    # Act
    enriched, degraded, skipped = build_event_thumbs(
        events, frames, thumbs_dir, {"f1#e0": (48.0, 27.0)}
    )
    # Assert：有锚点全 crop；无锚点 full 降级 + 降级清单记录；无跳过
    assert skipped == []
    assert [t["mode"] for t in enriched[0]["thumbs"]] == ["crop", "crop", "crop"]
    assert [t["mode"] for t in enriched[1]["thumbs"]] == ["full", "full", "full"]
    assert len(degraded) == 1 and "hoops 无锚点" in degraded[0]


def test_build_event_thumbs_marks_anchor_frame_under_clamp(tmp_path: pathlib.Path) -> None:
    # Arrange：anchor 0.0s 低端钳位去重 → 帧 [1, 3]，锚点帧 1 在 index 0 而非中间
    frames = tmp_path / "frames"
    _make_frames(frames, "f1", [1, 2, 3])
    thumbs_dir = tmp_path / "thumbs"
    thumbs_dir.mkdir()
    # Act
    enriched, _, _ = build_event_thumbs([_event(anchor_t0=0.0)], frames, thumbs_dir)
    # Assert：is_anchor 显式标记在帧 1 上（页面大图按标记取，不按位置假设）
    assert [(t["frame"], t["is_anchor"]) for t in enriched[0]["thumbs"]] == [
        (1, True),
        (3, False),
    ]


# ---------- derive_session ----------


def test_derive_session_review_dir_goes_up(tmp_path: pathlib.Path) -> None:
    # Arrange：work/<场次>/review_batchK 结构
    d = tmp_path / "work" / "20260722" / "review_batch3"
    d.mkdir(parents=True)
    # Act / Assert：review 开头 → 上溯祖父目录名
    assert derive_session(d) == "20260722"


def test_derive_session_plain_parent(tmp_path: pathlib.Path) -> None:
    # Arrange / Act / Assert：非 review 开头 → 直接取父目录名
    d = tmp_path / "work" / "mysession"
    d.mkdir(parents=True)
    assert derive_session(d) == "mysession"


# ---------- build_html：三条硬规定回归断言 ----------


def _thumbed_event(key: str = "f1#e0", fid: str = "f1", anchor_t0: float = 1.0) -> dict[str, Any]:
    """带 thumbs 字段的增强事件（build_html 的输入形态）。"""
    e = _event(key, fid, anchor_t0)
    e["thumbs"] = [{"src": "thumbs/t_f1_e0_0.jpg", "frame": 4}]
    return e


def test_build_html_inlines_events_and_session() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "20260722_3")
    # Assert
    assert '"key": "f1#e0"' in html
    assert 'const SESSION = "20260722_3";' in html
    # LSKEY 与 label.html 完全一致（共享 localStorage 的前提）
    assert 'const LSKEY = "label_" + SESSION;' in html


def test_build_html_merge_write_and_no_poskey() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "s")
    # Assert：硬规定 3——合并写复刻（重读 LSKEY + Object.assign(stored, marks) 再写）
    assert "Object.assign(stored, marks)" in html
    assert "localStorage.setItem(LSKEY, JSON.stringify(marks))" in html
    # 绝不写位置键（墙没有位置概念，写了会破坏 label.html 断点续标）
    assert "POSKEY" not in html


def test_build_html_only_mark_no_and_disable_marked() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "s")
    # Assert：硬规定 1——只允许对未标事件写 {r:"no"}，页面不产生 goal/practice 写入
    assert 'marks[key] = { r: "no" }' in html
    # 硬规定 2——已标事件 F 按钮禁用；渲染与点击均以 localStorage 实时值为准
    assert "btn.disabled = !!m;" in html
    assert "marks = loadMarks();" in html
    assert "if (marks[key]) { render(); return; }" in html


def test_build_html_lazy_loading_thumbs() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "s")
    # Assert：缩略图懒加载（234 事件墙一次性加载会卡爆）
    assert 'loading="lazy"' in html


def test_build_html_anchor_frame_is_main_image() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "s")
    # Assert：主图按 is_anchor 标记取（钳位去重时锚点项不在中间），无标记回退中间项
    assert 'class="main"' in html
    assert "e.thumbs.findIndex(t => t.is_anchor)" in html
    assert '<div class="subs">' in html


def test_build_html_full_mode_badge() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "s")
    # Assert：全景降级事件有角标（无锚点的卡不是筐区特写，判读慎用）
    assert "全景降级" in html
    assert 't.mode === "full"' in html


def test_build_html_injects_group_fields() -> None:
    # Arrange：同 fid 两事件 anchor 差 3s ≤ 6s，窗口重叠成组
    events = [_thumbed_event("f1#e0", anchor_t0=1.0), _thumbed_event("f1#e1", anchor_t0=4.0)]
    # Act
    html = build_html(events, "s")
    # Assert：复用 assign_same_rally_groups 注入 grp/grp_size；不改调用方原 dict
    assert '"grp": 1' in html
    assert '"grp_size": 2' in html
    assert "疑似同回合" in html
    assert "grp" not in events[0] and "grp" not in events[1]


def test_build_html_raw_string_newline_literal() -> None:
    # Arrange / Act
    html = build_html([_thumbed_event()], "s")
    # Assert：防回归——JS 字符串的 \n 必须以字面两字符存在于源码（_HTML 为 raw
    # string 保此）；若被 Python 转义成真实换行，JS 字符串跨行 SyntaxError 整页黑屏
    assert "\\n" in html
    assert "全部事件均已有标注。\n判" not in html
