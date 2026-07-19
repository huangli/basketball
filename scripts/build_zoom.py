# 存疑锚点高清复看抽帧：1920x1440 单帧，锚点 ±0.6s @10fps（幂等）
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
FRAMES = ROOT / "work" / "frames"
GOALS = ROOT / "goals.json"
INV = ROOT / "work" / "file_inventory.json"
FPS = 10


def gen(job, before, after):
    g, a, duration = job
    stem = Path(g["file"]).stem
    d = FRAMES / stem
    prefix = f"zoom_{g['window_start']}_{a}_"
    start, end = max(0.0, a - before), min(duration, a + after)
    want = round((end - start) * FPS)
    if d.exists() and len(list(d.glob(f"{prefix}*.jpg"))) >= want - 1:
        return f"{stem}|{a}", "skip", ""
    for old in d.glob(f"{prefix}*.jpg") if d.exists() else []:
        old.unlink()
    d.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", str(round(start, 2)), "-to", str(round(end, 2)), "-i", str(RAW / g["file"]),
           "-map", "0:v:0", "-vf", f"fps={FPS},scale=1920:1440", "-q:v", "3",
           str(d / f"{prefix}%02d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return f"{stem}|{a}", "ok" if r.returncode == 0 else "error", r.stderr.strip()[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=float, default=0.6)
    ap.add_argument("--after", type=float, default=0.6)
    ap.add_argument("--only", type=str, default="", help="只处理这些 file|anchor，逗号分隔")
    args = ap.parse_args()
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    gj = json.loads(GOALS.read_text(encoding="utf-8"))
    only = set(filter(None, args.only.split(",")))
    jobs = [(g, a, inv[g["file"]]["duration"])
            for g in gj["goals"] if g.get("zoom_anchors") and g["file"] in inv
            for a in g["zoom_anchors"]
            if not only or f"{g['file']}|{a}" in only]
    results = {"skip": 0, "ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for key, status, err in ex.map(lambda j: gen(j, args.before, args.after), jobs):
            if status == "error":
                results["error"].append(f"{key}: {err}")
            else:
                results[status] += 1
    print(f"anchors={len(jobs)} skip={results['skip']} ok={results['ok']} error={len(results['error'])}")
    for e in results["error"]:
        print(f"  {e}")
    return 1 if results["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
