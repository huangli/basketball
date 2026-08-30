"""视频封面生成（cover-gen）：每条输出视频生成多张候选封面供挑选。

产物：output/<场次>/covers/<产物主名>/cover_001..0NN.jpg + sheet.jpg（网格预览带编号）。
封面 3:4 竖版 1080×1440，等比缩放充满 + 中心裁剪（不拉伸不黑边），叠文字
（上缘队伍名，下缘片名）。抽帧时刻 = clamp(anchor_time - 0.5, 0)。

产物主名与 build_highlight 输出一一对应（复用 select_goals 命名真值表），
主键按 build 口径：队伍集锦 + 每个个人合集；无过滤缺省 = 等价 build --all
（不出一张"个人_全员"总封面）；未认人自动模式只出颜色队队伍集锦封面。

依赖：ffmpeg（抽帧）+ Pillow（裁剪/合成/网格）。spec: docs/cover-gen/spec.md。
"""

import argparse
import contextlib
import logging
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import video  # 复用批次/roster/session 解析（scripts/ 在 sys.path[0]）
from build_highlight import _validate_goals, select_goals
from errors import BasketballPipelineError
from pipe_common import configure_logging, new_run_id, read_json, run_ffmpeg
from roster import Player, Roster, validate_roster

logger = logging.getLogger(__name__)

COVER_W: int = 1080
COVER_H: int = 1440
FRAME_OFFSET: float = 0.5  # 入网前抽帧偏移（spec D2/D7）
JPEG_Q: int = 88
OUT_DIR_NAME: str = "covers"
# 中文封面字体（Windows：微软雅黑 → 宋体 → 黑体；皆缺则显式报错，见 load_font）
FONT_CANDIDATES: tuple[str, ...] = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)


def _clamp_aim(anchor_time: float) -> float:
    """抽帧时刻 = anchor_time - FRAME_OFFSET；小于 0 则 clamp 到 0（spec D7）。

    Args:
        anchor_time: 进球锚点（秒）。

    Returns:
        非负抽帧时刻（秒）。
    """
    aim: float = anchor_time - FRAME_OFFSET
    if aim <= 0:
        logger.warning("anchor=%.1f 早于抽帧偏移 %.1fs，clamp 到 0", anchor_time, FRAME_OFFSET)
        return 0.0
    return aim


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载中文字体，返回 FreeTypeFont。

    按候选顺序（微软雅黑→宋体→黑体）取首个可加载者；皆缺显式报错（不静默回退成乱码）。

    Args:
        size: 字号像素。

    Returns:
        加载成功的 ImageFont。

    Raises:
        BasketballPipelineError: 所有候选字体均不存在（显式失败，避免乱码/成框）。
    """
    for path in FONT_CANDIDATES:
        p = Path(path)
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError as exc:  # 部分 ttc 子字体加载失败
                logger.warning("字体 %s 加载失败: %s", path, exc)
    raise BasketballPipelineError(
        f"无可加载中文字体（候选: {FONT_CANDIDATES}）——封面文字会乱码，请安装微软雅黑"
    )


def crop_cover(img: Image.Image, w: int = COVER_W, h: int = COVER_H) -> Image.Image:
    """等比缩放充满 w×h 画布并中心裁剪（spec D2：不拉伸不黑边）。

    Args:
        img: 源帧 PIL 图像。
        w: 目标宽。
        h: 目标高。

    Returns:
        裁好的 w×h 图像。
    """
    sw, sh = img.size
    scale: float = max(w / sw, h / sh)
    nw: int = max(1, round(sw * scale))
    nh: int = max(1, round(sh * scale))
    resized: Image.Image = img.resize((nw, nh), Image.LANCZOS)
    left: int = (nw - w) // 2
    top: int = (nh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _text_with_stroke(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
) -> None:
    """白字黑描边，保证深底/亮底都可读。"""
    draw.text(xy, text, font=font, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))


def overlay_text(img: Image.Image, top_text: str, bottom_text: str) -> Image.Image:
    """叠文字：上缘队伍名（左起）+ 下缘片名（左起），底部半透明深色条防串色。

    Args:
        img: 已裁好的封面。
        top_text: 上缘队伍名。
        bottom_text: 下缘片名。

    Returns:
        叠字后的图像。
    """
    canvas: Image.Image = img.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(72)
    sub_font = load_font(56)
    # 上缘：队伍名
    draw.rectangle((0, 0, canvas.width, 130), fill=(0, 0, 0, 120))
    _text_with_stroke(draw, (24, 16), top_text, title_font)
    # 下缘：片名 + 半透明底条
    if bottom_text:
        draw.rectangle((0, canvas.height - 96, canvas.width, canvas.height), fill=(0, 0, 0, 130))
        _text_with_stroke(draw, (24, canvas.height - 88), bottom_text, sub_font)
    return canvas.convert("RGB")


def extract_frame(src: str, aim_sec: float, out_png: str) -> None:
    """ffmpeg 抽出 aim_sec 处单帧到 out_png（spec D2，失败由调用方决定跳过）。

    Args:
        src: 原始视频路径。
        aim_sec: 抽帧时刻（秒，非负）。
        out_png: 输出 PNG 路径。

    Raises:
        BasketballPipelineError: 抽帧失败（run_ffmpeg 超时或非零且重试耗尽）。
    """
    run_ffmpeg(["-ss", f"{aim_sec:.3f}", "-i", src, "-frames:v", "1", out_png])


def render_cover(src: str, aim_sec: float, top_text: str, bottom_text: str, out_jpg: str) -> None:
    """抽帧 → 3:4 裁剪 → 叠文字 → 存 JPEG（单张封面）。

    Args:
        src: 原始视频路径。
        aim_sec: 抽帧时刻。
        top_text: 上缘队伍名。
        bottom_text: 下缘片名。
        out_jpg: 输出封面路径。

    Raises:
        BasketballPipelineError: 抽帧或图像处理失败。
    """
    with _TmpPNG() as png:
        extract_frame(src, aim_sec, png)
        with Image.open(png) as frame:
            crop = crop_cover(frame.convert("RGB"))
            out = overlay_text(crop, top_text, bottom_text)
            out.save(out_jpg, "JPEG", quality=JPEG_Q)


class _TmpPNG:
    """临时 PNG 文件上下文（抽帧中转，用后即删）。"""

    def __init__(self) -> None:
        self.path: str = ""

    def __enter__(self) -> str:
        import tempfile

        fd, self.path = tempfile.mkstemp(suffix=".png", prefix="cover_frame_")
        import os

        os.close(fd)
        return self.path

    def __exit__(self, *exc: object) -> None:
        with contextlib.suppress(FileNotFoundError):
            Path(self.path).unlink()


def build_sheet(cover_imgs: list[Path], sheet_path: str, cols: int = 4) -> None:
    """把候选封面拼成带编号的网格预览图（spec D1：sheet.jpg）。

    Args:
        cover_imgs: 候选封面路径列表（顺序与 cover_NNN 一致）。
        sheet_path: 输出网格图路径。
        cols: 每行列数。
    """
    thumb_w, thumb_h, gap, label_h = 135, 180, 12, 28
    rows = (len(cover_imgs) + cols - 1) // cols
    w = cols * thumb_w + (cols + 1) * gap
    h = rows * (thumb_h + label_h) + (rows + 1) * gap
    canvas = Image.new("RGB", (w, h), (28, 28, 28))
    num_font = load_font(20)
    for idx, path in enumerate(cover_imgs, 1):
        r, c = divmod(idx - 1, cols)
        x = gap + c * (thumb_w + gap)
        y = gap + r * (thumb_h + label_h + gap)
        with Image.open(path) as im:
            thumb: Image.Image = im.resize((thumb_w, thumb_h), Image.LANCZOS)
            canvas.paste(thumb, (x, y))
        draw = ImageDraw.Draw(canvas)
        draw.text((x + 6, y + thumb_h + 2), f"#{idx}", font=num_font, fill=(255, 255, 255))
    canvas.save(sheet_path, "JPEG", quality=JPEG_Q)


def _find_player(roster: Roster, value: str) -> Player | None:
    """按 tag 或 name 查球员，返回 Player | None（spec --scorer 解析）。"""
    for p in roster.players:
        if p.tag == value or p.name == value:
            return p
    return None


def _bottom_text(stem: str, top: str) -> str:
    """从产物主名剥离前导队伍名得到片名（team→进球集锦；个人→<名>_进球合集）。"""
    if stem.startswith("队伍_"):
        return stem[len("队伍_" + top + "_") :] if stem.startswith("队伍_" + top + "_") else stem
    if top and stem.startswith(top + "_"):
        return stem[len(top + "_") :]
    return stem


def _collect_goals(session_dir: Path, batches: list, session: str) -> list[dict]:
    """取选定批次的 confirmed 记录——多批时按 build 口径合并（spec D6）。

    Args:
        session_dir: work/<场次>。
        batches: 选定批次列表。
        session: 场次 ID（多批合并产物命名用）。

    Returns:
        confirmed 记录列表。
    """
    if len(batches) > 1:
        merged: Path = video._merge_goals_for_build(batches, session, session_dir)
        data = read_json(merged, what="merged_goals.json")
    else:
        data = read_json(batches[0].goals, what="goals.json")
    return _validate_goals(data, str(batches[0].goals))


def _resolve_jobs(
    args: argparse.Namespace, session_dir: Path, batches: list
) -> tuple[list[tuple[str, str]] | None, Roster | None]:
    """按 roster/自动模式与 flags 组装 (filter list, 生效 roster)。

    Returns:
        (filters, roster)：roster 为封面归属/文字所用（confirmed 或 auto_roster）；
        filters 为 None 表示本场无可产封面（记日志退出 0）。
    """
    roster_path = session_dir / "roster.json"
    if roster_path.is_file():
        roster = validate_roster(read_json(roster_path, what="roster.json"), str(roster_path))
        if roster.confirmed:
            if args.all or (not args.scorer and not args.team):
                known: set[str] = set()
                for b in batches:
                    known |= video._confirmed_keys(b.goals)
                return video._build_expand_all(session_dir, known), roster
            flag, value = ("--scorer", args.scorer) if args.scorer else ("--team", args.team)
            return [(flag, value)], roster
        logger.warning("roster 未 confirmed=true（%s），按未认人处理", roster_path)
    # 自动模式：只出颜色队队伍集锦封面（spec D4/SC4），个人合集不出
    auto_path = session_dir / "auto_roster.json"
    if not auto_path.is_file():
        logger.warning("未认人自动模式且无 auto_roster.json，covers 不出封面（先 people 认人）")
        return None, None
    auto = validate_roster(read_json(auto_path, what="auto_roster.json"), str(auto_path))
    known = set()
    for b in batches:
        known |= video._confirmed_keys(b.goals)
    _tags, teams = video._auto_roster_hit_groups(auto_path, known)
    if not teams:
        logger.warning("auto_roster 无颜色队归属球，covers 不出封面")
        return None, auto
    logger.warning("自动模式仅出颜色队队伍集锦封面（便服不出、个人不出）")
    return [("--team", t) for t in teams], auto


def main() -> int:
    """gen_covers 主入口。

    Returns:
        0=全部成功或本场无可产封面；1=参数/数据/处理失败。
    """
    args = _parse_argv()
    run_id = new_run_id()
    configure_logging(run_id)
    try:
        args.session = video.resolve_session(args)  # type: ignore[attr-defined]
        session_dir: Path = video.session_dir_or_die(args.session)
        state: dict = video.load_state(args.session)
        rawdir: Path = video.resolve_rawdir(args.rawdir, state)
    except BasketballPipelineError as exc:
        logger.error("场次/原片解析失败: %s", exc)
        return 1

    batches = video._select_batches(video.discover_batches(session_dir), args.batch)
    goals: list[dict] = _collect_goals(session_dir, batches, args.session)
    jobs, roster = _resolve_jobs(args, session_dir, batches)
    if jobs is None or roster is None:
        return 0

    covers_root: Path = video.OUTPUT_ROOT / args.session / OUT_DIR_NAME
    done: int = 0
    for flag, value in jobs:
        if flag == "--team":
            selected, stem = select_goals(goals, roster, "", value)
            top = value
        else:
            selected, stem = select_goals(goals, roster, value, "")
            player = _find_player(roster, value)
            top = player.team if player else ""
        if not selected:
            logger.warning("产物无命中球，跳过封面: %s", stem)
            continue
        bottom = _bottom_text(stem, top)
        out_dir: Path = covers_root / stem
        out_dir.mkdir(parents=True, exist_ok=True)
        covers: list[Path] = []
        failed: int = 0
        t0 = time.time()
        for i, goal in enumerate(selected, 1):
            src = str(rawdir / goal["file"])
            jpg = out_dir / f"cover_{i:03d}.jpg"
            if jpg.is_file():
                covers.append(jpg)
                continue
            try:
                aim = _clamp_aim(float(goal["anchor_time"]))
                render_cover(src, aim, top, bottom, str(jpg))
                covers.append(jpg)
            except BasketballPipelineError as exc:
                failed += 1
                logger.warning(
                    "封面抽帧失败 %s@%.1f: %s", goal["file"], float(goal["anchor_time"]), exc
                )
        logger.info(
            "封面完成 %s：%d 张候选，%.1fs",
            stem,
            len(covers),
            time.time() - t0,
        )
        if covers:
            build_sheet(covers, str(out_dir / "sheet.jpg"))
            done += 1
        if failed == len(selected):
            logger.error("产物 %s 全部抽帧失败，无封面", stem)

    if done == 0:
        logger.warning("covers 未产出任何封面")
    logger.info("covers 完成：%d 个产物，位于 %s", done, covers_root)
    return 0


def _parse_argv() -> argparse.Namespace:
    """解析命令行（与 build 子命令同骨架）。"""
    p = argparse.ArgumentParser(prog="gen_covers")
    p.add_argument("--session", default=None, help="场次 ID（缺省读当前场次指针）")
    p.add_argument("--rawdir", default=None, help="原片目录（缺省读 video_cli.json srcdir）")
    p.add_argument("--scorer", default="", help="单个人合集封面（tag 或姓名）")
    p.add_argument("--team", default="", help="单队伍集锦封面")
    p.add_argument("--batch", type=int, default=None, help="限定单批次 K")
    p.add_argument("--all", action="store_true", help="全部产物（缺省行为）")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
