# Task 7: 精判 tile 三模式 + 幂等
#   默认      : goals.json 全部 candidate，窗口 t±2.7（t=窗口中点），-frames:v 6
#   --from <j>: 读 audio_recheck.json [{file,t}]，对该文件全部未 dropped hoop 各开一窗（t±2.7）
#   --full <f>: 全段模式（窗口=整文件，连续 tile），输出 roifull_<hoop>_%03d.jpg
# 产物: work/frames/<stem>/roifine_<hoop>_<ws>_%03d.jpg 或 roifull_<hoop>_%03d.jpg
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
FRAMES = ROOT / "work" / "frames"
INV = ROOT / "work" / "file_inventory.json"
HOOPS = ROOT / "work" / "hoops.json"
GJ = ROOT / "goals.json"
COLS, ROWS = 3, 3
WIN_HALF = 2.7


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def crop_origin(hoop):
    s = int(hoop["crop"])
    x0 = min(max(int(hoop["x"]) - s // 2, 0), 3840 - s)
    y0 = min(max(int(hoop["y"]) - s // 2, 0), 2880 - s)
    return s, x0, y0


def fine_one(item):
    """item=(name,hoop,win_start,win_end,prefix,frames)。frames=None→全段连续 tile。"""
    name, hoop, ws, we, prefix, frames = item
    stem = Path(name).stem
    hid = hoop["id"]
    s, x0, y0 = crop_origin(hoop)
    d = FRAMES / stem
    ws1 = f"{ws:.1f}"
    if prefix == "roifine":
        glob_pat = f"roifine_{hid}_{ws1}_*.jpg"
        out_tmpl = f"roifine_{hid}_{ws1}_%03d.jpg"
    else:
        glob_pat = f"roifull_{hid}_*.jpg"
        out_tmpl = f"roifull_{hid}_%03d.jpg"
    existing = len(list(d.glob(glob_pat))) if d.exists() else 0
    expect = frames if frames else math.floor(round(float(we - ws) * 10) / 9) or 1
    if existing >= expect:
        return f"{stem}_{hid}_{ws1}", "skip", ""
    d.mkdir(parents=True, exist_ok=True)
    vf = (f"crop={s}:{s}:{x0}:{y0},fps=10,scale=640:640,"
          f"tile={COLS}x{ROWS}:padding=2:margin=2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{ws:.3f}", "-to", f"{we:.3f}", "-i", str(RAW / name),
           "-map", "0:v:0", "-vf", vf, "-q:v", "3"]
    if frames:
        cmd += ["-frames:v", str(frames)]
    cmd += [str(d / out_tmpl)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return f"{stem}_{hid}_{ws1}", "ok" if r.returncode == 0 else "error", r.stderr.strip()[:200]


def run(items):
    results = {"skip": 0, "ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for key, status, err in ex.map(fine_one, items):
            if status == "error":
                results["error"].append(f"{key}: {err}")
            else:
                results[status] += 1
    print(f"skip={results['skip']} ok={results['ok']} error={len(results['error'])}")
    for e in results["error"]:
        print(f"  {e}")
    return 1 if results["error"] else 0


def cmd_default():
    gj = load("goals.json")
    hoops = load("work/hoops.json")
    inv = load("work/file_inventory.json")["files"]
    items = []
    for g in gj["goals"]:
        if g["status"] != "candidate" or not g.get("hoop_id"):
            continue
        name = g["file"]
        hoop = next((h for h in hoops.get(name, {}).get("hoops", [])
                     if h["id"] == g["hoop_id"] and not h.get("dropped")), None)
        if not hoop or name not in inv:
            continue
        dur = float(inv[name]["duration"])
        t = (g["window_start"] + g["window_end"]) / 2
        ws = max(0.0, t - WIN_HALF)
        we = min(dur, t + WIN_HALF)
        items.append((name, hoop, round(ws, 1), we, "roifine", 6))
    return run(items)


def cmd_from(path):
    recheck = json.loads(Path(path).read_text(encoding="utf-8"))
    hoops = load("work/hoops.json")
    inv = load("work/file_inventory.json")["files"]
    items = []
    for r in recheck:
        name, t = r["file"], r["t"]
        if name not in inv:
            continue
        dur = float(inv[name]["duration"])
        ws = max(0.0, t - WIN_HALF)
        we = min(dur, t + WIN_HALF)
        for hoop in hoops.get(name, {}).get("hoops", []):
            if hoop.get("dropped"):
                continue
            items.append((name, hoop, round(ws, 1), we, "roifine", 6))
    return run(items)


def cmd_full(name):
    hoops = load("work/hoops.json")
    inv = load("work/file_inventory.json")["files"]
    if name not in inv:
        print(f"文件不在 inventory: {name}")
        return 1
    dur = float(inv[name]["duration"])
    items = [(name, hoop, 0.0, dur, "roifull", None)
             for hoop in hoops.get(name, {}).get("hoops", [])
             if not hoop.get("dropped")]
    return run(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_json")
    ap.add_argument("--full")
    args = ap.parse_args()
    if args.full:
        return cmd_full(args.full)
    if args.from_json:
        return cmd_from(args.from_json)
    return cmd_default()


if __name__ == "__main__":
    sys.exit(main())
