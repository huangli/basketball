# Task 2.1 实现：对 goals.json 候选窗口做原片 10fps 精抽拼 5x4 tile（幂等）
# 用法: python scripts\build_fine.py [--limit N]   # --limit 只处理前 N 个 candidate（试点用）
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
GOALS = ROOT / "goals.json"
VF = "fps=10,scale=960:720,tile=5x4:padding=2:margin=2"


def want_tiles(win_start, win_end, duration):
    end = min(win_end, duration)
    return max(1, math.ceil(round((end - win_start) * 10) / 20))


def gen(job):
    g, duration = job
    name, ws, we = g["file"], g["window_start"], g["window_end"]
    stem = Path(name).stem
    d = FRAMES / stem
    prefix = f"fine_{ws}_"
    want = want_tiles(ws, we, duration)
    if d.exists() and len(list(d.glob(f"{prefix}*.jpg"))) == want:
        return f"{stem}|{ws}", "skip", ""
    for old in d.glob(f"{prefix}*.jpg") if d.exists() else []:
        old.unlink()
    d.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", str(ws), "-to", str(we), "-i", str(RAW / name),
           "-map", "0:v:0", "-vf", VF, "-q:v", "3",
           str(d / f"{prefix}%03d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return f"{stem}|{ws}", "ok" if r.returncode == 0 else "error", r.stderr.strip()[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个 candidate（0=全部）")
    args = ap.parse_args()
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    gj = json.loads(GOALS.read_text(encoding="utf-8"))
    cands = [g for g in gj["goals"] if g["status"] == "candidate"]
    if args.limit:
        cands = cands[: args.limit]
    jobs = [(g, inv[g["file"]]["duration"]) for g in cands if g["file"] in inv]
    missing = [g["file"] for g in cands if g["file"] not in inv]
    for m in sorted(set(missing)):
        print(f"warn: 素材缺失跳过 {m}")
    results = {"skip": 0, "ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for key, status, err in ex.map(gen, jobs):
            if status == "error":
                results["error"].append(f"{key}: {err}")
            else:
                results[status] += 1
    print(f"candidates={len(jobs)} skip={results['skip']} ok={results['ok']} error={len(results['error'])}")
    for e in results["error"]:
        print(f"  {e}")
    return 1 if results["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
