# Task 2/3：篮筐标定——extract: pilot 50 文件 50% 时长处抽帧 + 拼 sheet + meta.json
#           check: 按 hoops.json 的 crop 取 25% 帧 crop→320 格拼 check sheet + check_meta.json
# 用法: python scripts/build_hoop_calib.py extract|check
import argparse
import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
CALIB = ROOT / "work" / "frames" / "_calib"
FRAMES_DIR = CALIB / "frames"  # 单帧与 sheet 分目录，避免 glob 自匹配（v2 教训）
CHECK_DIR = CALIB / "check_frames"  # check 裁剪小图，同样与 sheet 分目录
META = CALIB / "meta.json"
CHECK_META = CALIB / "check_meta.json"
INV = ROOT / "work" / "file_inventory.json"
PILOT = ROOT / "work" / "pilot_files.json"
HOOPS = ROOT / "work" / "hoops.json"
CELL_W, CELL_H = 480, 360
MULTIPLIER = 8  # 3840 / 480，格坐标还原原片坐标的倍率
COLS, ROWS = 4, 3
PER_SHEET = COLS * ROWS
CHECK_CELL = 320  # check sheet 每格边长（crop 区域缩放到 320×320）
CHECK_TS = 0.25  # check 抽帧位置：25% 时长


def extract_one(item):
    name, duration = item
    stem = Path(name).stem
    out = FRAMES_DIR / f"{stem}.jpg"
    if out.exists():
        return stem, "skip", ""
    if not (RAW / name).exists():
        return stem, "error", "原始 MP4 缺失"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{duration * 0.5:.3f}", "-i", str(RAW / name),
           "-map", "0:v:0", "-frames:v", "1", "-vf", f"scale={CELL_W}:{CELL_H}",
           "-q:v", "2", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and out.exists():
        return stem, "ok", ""
    return stem, "error", r.stderr.strip()[:200]


def build_sheets(stems, force=False):
    """50 帧一次 concat 成序列，tpad 克隆末帧补齐到 12 的倍数（防 tile 丢尾），
    tile=4x3 输出 sheet_%02d.jpg；克隆格在 meta order 中标 null。
    输入走 concat demuxer 清单（concat 滤镜对单帧图片会丢帧，实测 50 进 3 出）。"""
    n_sheets = math.ceil(len(stems) / PER_SHEET)
    padded = n_sheets * PER_SHEET - len(stems)
    order = stems + [None] * padded
    meta = {"cell": [CELL_W, CELL_H], "multiplier": MULTIPLIER,
            "order": order, "padded": padded}
    sheets = sorted(CALIB.glob("sheet_*.jpg"))
    if not force and META.exists() and len(sheets) == n_sheets:
        try:
            if json.loads(META.read_text(encoding="utf-8")) == meta:
                return "skip", ""
        except json.JSONDecodeError:
            pass
    for sh in sheets:
        sh.unlink()
    lines = []
    for s in stems:
        lines += [f"file '{FRAMES_DIR / (s + '.jpg')}'", "duration 1"]
    lst = CALIB / "concat_list.txt"
    lst.write_text("\n".join(lines), encoding="utf-8")
    vf = "fps=1"
    if padded:
        vf += f",tpad=stop_mode=clone:stop={padded}"
    vf += f",tile={COLS}x{ROWS}:padding=2:margin=2"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", str(lst),
           "-vf", vf, str(CALIB / "sheet_%02d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return "error", r.stderr.strip()[:300]
    got = len(list(CALIB.glob("sheet_*.jpg")))
    if got != n_sheets:
        return "error", f"sheet 数不符: {got} != {n_sheets}"
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok", ""


def cmd_extract():
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))["files"]
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    missing_inv = [n for n in pilot if n not in inv]
    if missing_inv:
        print(f"inventory 缺 {len(missing_inv)} 条: {missing_inv[:3]}")
        return 1
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    items = [(n, float(inv[n]["duration"])) for n in pilot]
    results = {"skip": 0, "ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for stem, status, err in ex.map(extract_one, items):
            if status == "error":
                results["error"].append(f"{stem}: {err}")
            else:
                results[status] += 1
    print(f"抽帧: skip={results['skip']} ok={results['ok']} error={len(results['error'])}")
    for e in results["error"]:
        print(f"  {e}")
    if results["error"]:
        return 1

    stems = [Path(n).stem for n in pilot]
    status, err = build_sheets(stems, force=results["ok"] > 0)
    print(f"拼 sheet: {status}" + (f" — {err}" if err else ""))
    return 1 if status == "error" else 0


def check_one(item):
    """对单个 hoop 抽 25% 帧并 crop S×S（中心 clamp 到画面内）后缩放到 320×320。"""
    name, hoop, duration, width, height = item
    stem = Path(name).stem
    hid, s = hoop["id"], int(hoop["crop"])
    out = CHECK_DIR / f"{stem}_{hid}.jpg"
    left = min(max(int(hoop["x"]) - s // 2, 0), width - s)
    top = min(max(int(hoop["y"]) - s // 2, 0), height - s)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{duration * CHECK_TS:.3f}", "-i", str(RAW / name),
           "-map", "0:v:0", "-frames:v", "1",
           "-vf", f"crop={s}:{s}:{left}:{top},scale={CHECK_CELL}:{CHECK_CELL}",
           "-q:v", "2", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and out.exists():
        return stem, hid, "ok", ""
    return stem, hid, "error", r.stderr.strip()[:200]


def build_check_sheets(cells, force=False):
    """cells = [(stem, hid)]，与 build_sheets 同法拼 check_%02d.jpg，
    克隆格在 check_meta order 中标 null；order 记录格序→(file, hoop) 映射。"""
    n_sheets = math.ceil(len(cells) / PER_SHEET)
    padded = n_sheets * PER_SHEET - len(cells)
    order = [{"file": f"{s}.MP4", "hoop": h} for s, h in cells] + [None] * padded
    meta = {"cell": [CHECK_CELL, CHECK_CELL], "ts": CHECK_TS,
            "order": order, "padded": padded}
    sheets = sorted(CALIB.glob("check_*.jpg"))
    if not force and CHECK_META.exists() and len(sheets) == n_sheets:
        try:
            if json.loads(CHECK_META.read_text(encoding="utf-8")) == meta:
                return "skip", ""
        except json.JSONDecodeError:
            pass
    for sh in sheets:
        sh.unlink()
    lines = []
    for s, h in cells:
        lines += [f"file '{CHECK_DIR / (s + '_' + h + '.jpg')}'", "duration 1"]
    lst = CALIB / "check_concat_list.txt"
    lst.write_text("\n".join(lines), encoding="utf-8")
    vf = "fps=1"
    if padded:
        vf += f",tpad=stop_mode=clone:stop={padded}"
    vf += f",tile={COLS}x{ROWS}:padding=2:margin=2"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", str(lst),
           "-vf", vf, str(CALIB / "check_%02d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return "error", r.stderr.strip()[:300]
    got = len(list(CALIB.glob("check_*.jpg")))
    if got != n_sheets:
        return "error", f"check sheet 数不符: {got} != {n_sheets}"
    CHECK_META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok", ""


def cmd_check():
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))["files"]
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    hoops = json.loads(HOOPS.read_text(encoding="utf-8"))
    missing = [n for n in pilot if n not in hoops]
    if missing:
        print(f"hoops.json 缺 {len(missing)} 个 pilot 文件: {missing[:3]}")
        return 1
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    items, cells = [], []
    for n in pilot:  # 格序 = pilot 顺序，文件内按 hoops 列表顺序
        stem = Path(n).stem
        for h in hoops[n]["hoops"]:
            items.append((n, h, float(inv[n]["duration"]),
                          int(inv[n]["width"]), int(inv[n]["height"])))
            cells.append((stem, h["id"]))
    if not items:
        print("hoops.json 中没有任何 hoop")
        return 1
    results = {"ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for stem, hid, status, err in ex.map(check_one, items):
            if status == "error":
                results["error"].append(f"{stem}_{hid}: {err}")
            else:
                results["ok"] += 1
    print(f"check 抽帧: ok={results['ok']} error={len(results['error'])}")
    for e in results["error"]:
        print(f"  {e}")
    if results["error"]:
        return 1
    status, err = build_check_sheets(cells, force=True)
    print(f"拼 check sheet: {status}" + (f" — {err}" if err else ""))
    return 1 if status == "error" else 0


def main():
    ap = argparse.ArgumentParser(description="篮筐标定帧抽取")
    ap.add_argument("command", choices=["extract", "check"])
    args = ap.parse_args()
    if args.command == "extract":
        return cmd_extract()
    if args.command == "check":
        return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
