# 人工审阅接触表生成（变体A）：按 hoops.json crop + 烧时间戳 + 4x3 tile
# 用法: python scripts\build_review_sheets.py
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
HOOPS = ROOT / "work" / "hoops.json"
INV = ROOT / "work" / "file_inventory.json"
OUT = ROOT / "work" / "review" / "sheets"

PILOT = [
    "DJI_20250419184740_0005_D.MP4",
    "DJI_20250419185047_0006_D.MP4",
    "DJI_20250419185121_0007_D.MP4",
    "DJI_20250419185204_0008_D.MP4",
    "DJI_20250419185252_0009_D.MP4",
    "DJI_20250419185341_0010_D.MP4",
    "DJI_20250419185729_0011_D.MP4",
    "DJI_20250419185747_0012_D.MP4",
    "DJI_20250419185805_0013_D.MP4",
    "DJI_20250419185825_0014_D.MP4",
]

DRAWTEXT = ("drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
            "text='%{pts}':x=8:y=8:fontcolor=yellow:"
            "box=1:boxcolor=black@0.7:fontsize=28")


def short_name(name):
    parts = name.split("_")
    return parts[2] if len(parts) >= 3 else Path(name).stem


def gen(job):
    name, hoop, dur = job
    sn = short_name(name)
    hid = hoop["id"]
    S = int(hoop["crop"])
    cx, cy = int(hoop["x"]), int(hoop["y"])
    x0 = min(max(cx - S // 2, 0), 3840 - S)
    y0 = min(max(cy - S // 2, 0), 2880 - S)
    d = OUT / sn
    want = int(dur * 2 // 12)
    if want == 0:
        return sn + "_" + hid, "short", ""
    if d.exists() and len(list(d.glob(hid + "_*.jpg"))) >= want:
        return sn + "_" + hid, "skip", ""
    d.mkdir(parents=True, exist_ok=True)
    vf = ("crop=" + str(S) + ":" + str(S) + ":" + str(x0) + ":" + str(y0) +
          ",fps=2,scale=480:480," + DRAWTEXT +
          ",tile=4x3:padding=2:margin=2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(RAW / name), "-map", "0:v:0", "-vf", vf, "-q:v", "3",
           str(d / (hid + "_%04d.jpg"))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return sn + "_" + hid, "ok" if r.returncode == 0 else "error", r.stderr.strip()[:200]


def main():
    hoops = json.loads(HOOPS.read_text(encoding="utf-8"))
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    items = []
    for name in PILOT:
        if name not in hoops or not hoops[name]["hoops"] or name not in inv:
            continue
        dur = float(inv[name]["duration"])
        for hoop in hoops[name]["hoops"]:
            if hoop.get("dropped"):
                continue
            items.append((name, hoop, dur))
    results = {"skip": 0, "ok": 0, "error": []}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for key, status, err in ex.map(gen, items):
            if status == "error":
                results["error"].append(key + ": " + err)
            elif status == "skip":
                results["skip"] += 1
            elif status == "short":
                pass
            else:
                results["ok"] += 1
    total = 0
    for d in sorted(OUT.iterdir()) if OUT.exists() else []:
        total += len(list(d.glob("*.jpg")))
    print("skip=" + str(results["skip"]) + " ok=" + str(results["ok"]) +
          " error=" + str(len(results["error"])) + " total_sheets=" + str(total))
    for e in results["error"]:
        print("  " + e)
    return 1 if results["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
