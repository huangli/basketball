# Task 1.1 实现：幂等生成全部视频的 2fps 5x4 tile 接触表
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
FRAMES = ROOT / "work" / "frames"
INV = ROOT / "work" / "file_inventory.json"
VF = "fps=2,scale=320:240,tile=5x4:padding=2:margin=2"


def gen(item):
    name, e = item
    stem = Path(name).stem
    d = FRAMES / stem
    import math
    want = math.ceil(round(e["duration"] * 2) / 20)
    if d.exists() and len(list(d.glob("tile_*.jpg"))) == want:
        return stem, "skip", ""
    d.mkdir(parents=True, exist_ok=True)
    src = RAW / e["lrf"] if e.get("lrf") else RAW / name
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-map", "0:v:0", "-vf", VF, "-q:v", "4", str(d / "tile_%04d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return stem, "ok" if r.returncode == 0 else "error", r.stderr.strip()[:200]


def main():
    inv = json.loads(INV.read_text(encoding="utf-8"))
    items = sorted(inv["files"].items())
    results = {"skip": 0, "ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for stem, status, err in ex.map(gen, items):
            if status == "error":
                results["error"].append(f"{stem}: {err}")
            else:
                results[status] += 1
    print(f"skip={results['skip']} ok={results['ok']} error={len(results['error'])}")
    for e in results["error"]:
        print(f"  {e}")
    return 1 if results["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
