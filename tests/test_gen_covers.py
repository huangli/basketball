"""gen_covers 封面生成单测：抽帧偏移 clamp、3:4 裁剪、字体、文字、网格、回归。"""

import logging
import pathlib

import pytest
from PIL import Image

import gen_covers
from errors import BasketballPipelineError

W, H = 1080, 1440


def _solid(w: int, h: int, color: tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
    return Image.new("RGB", (w, h), color)


class TestClampAim:
    """抽帧时刻 = anchor - 0.5，且非负（spec D7）。"""

    def test_normal_offset(self) -> None:
        assert gen_covers._clamp_aim(10.0) == 9.5

    def test_early_anchor_clamps_to_zero(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        assert gen_covers._clamp_aim(0.3) == 0.0
        assert any("clamp" in r.message for r in caplog.records)


class TestCropCover:
    """等比充满 1080×1440 + 中心裁剪，不拉伸不黑边（spec D2/用例2、3）。"""

    def test_16_9_shrink_size(self) -> None:
        out = gen_covers.crop_cover(_solid(3840, 2160))
        assert out.size == (W, H)
        assert out.getpixel((W // 2, H // 2)) == (255, 0, 0)  # 中心充满无黑边

    def test_4_3_source_fills_no_black(self) -> None:
        out = gen_covers.crop_cover(_solid(2880, 2160))
        assert out.size == (W, H)
        # 四角也应为源色（放大/缩小后中心裁均充满，无黑边）
        for xy in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
            assert out.getpixel(xy) == (255, 0, 0)

    def test_grow_branch_fills(self) -> None:
        # 窄源（720×1280，scale=max(1080/720,1440/1280)=1.5 放大）→ 1080×1440 充满
        out = gen_covers.crop_cover(_solid(720, 1280))
        assert out.size == (W, H)
        assert out.getpixel((5, 5)) == (255, 0, 0)


class TestFont:
    """字体加载：微软雅黑存在；候选全缺则显式报错（spec S6）。"""

    def test_loads_system_font(self) -> None:
        font = gen_covers.load_font(24)
        assert font is not None

    def test_all_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gen_covers, "FONT_CANDIDATES", ("Z:/no_such.ttc",))
        with pytest.raises(BasketballPipelineError, match="字体"):
            gen_covers.load_font(24)


class TestBottomText:
    """片名剥离（spec D3：片名 = 产物主名去前导队伍名）。"""

    def test_team_stem(self) -> None:
        assert gen_covers._bottom_text("队伍_半截篮_进球集锦", "半截篮") == "进球集锦"

    def test_personal_stem(self) -> None:
        assert gen_covers._bottom_text("半截篮_黄立_进球合集", "半截篮") == "黄立_进球合集"


class TestOverlayText:
    def test_returns_cover_size(self) -> None:
        base = _solid(W, H, (0, 0, 0))
        out = gen_covers.overlay_text(base, "半截篮", "黄立_进球合集")
        assert out.size == (W, H)


class TestBuildSheet:
    def test_sheet_created_with_thumbnails(self, tmp_path: pathlib.Path) -> None:
        for i in range(3):
            _solid(1080, 1440, (i * 60, 0, 0)).save(tmp_path / f"c{i}.jpg", "JPEG")
        sheet = tmp_path / "sheet.jpg"
        gen_covers.build_sheet(
            [tmp_path / "c0.jpg", tmp_path / "c1.jpg", tmp_path / "c2.jpg"], str(sheet)
        )
        assert sheet.is_file()
        assert sheet.stat().st_size > 1000
