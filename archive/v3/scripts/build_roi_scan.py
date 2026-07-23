# Task 4: 粗扫 tile——按 hoops.json 对每文件每 hoop（跳 dropped）生成 2fps crop tile
# 模板 build_tiles.py：ThreadPoolExecutor max_workers=4、幂等按 glob 计数跳过、错误汇总退出码 1
# 产物: work/frames/<stem>/roi_<hoop_id>_%04d.jpg（4x3 tile=12帧=6s）
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
COLS, ROWS = 4, 3
PER_TILE = COLS * ROWS  # 12 帧/张


def gen(item):
    name, hoop, dur = item
    stem = Path(name).stem
    hid = hoop["id"]
    s = int(hoop["crop"])
    d = FRAMES / stem
    want = math.floor(round(dur * 2) / PER_TILE)  # 2fps×dur 帧 ÷ 12
    if want == 0:
        return name, "short", ""
    existing = len(list(d.glob(f"roi_{hid}_*.jpg"))) if d.exists() else 0
    if existing >= want:
        return f"{stem}_{hid}", "skip", ""
    d.mkdir(parents=True, exist_ok=True)
    cx, cy = int(hoop["x"]), int(hoop["y"])
    x0 = min(max(cx - s // 2, 0), 3840 - s)
    y0 = min(max(cy - s // 2, 0), 2880 - s)
    vf = (f"crop={s}:{s}:{x0}:{y0},fps=2,scale=480:480,"
          f"tile={COLS}x{ROWS}:padding=2:margin=2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(RAW / name), "-map", "0:v:0", "-vf", vf, "-q:v", "4",
           str(d / f"roi_{hid}_%04d.jpg")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return f"{stem}_{hid}", "ok" if r.returncode == 0 else "error", r.stderr.strip()[:200]


def main():
    hoops = json.loads(HOOPS.read_text(encoding="utf-8"))
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    items = []
    for name, h in hoops.items():
        if name not in inv or not h["hoops"]:
            continue
        dur = float(inv[name]["duration"])
        for hoop in h["hoops"]:
            if hoop.get("dropped"):
                continue
            items.append((name, hoop, dur))
    results = {"skip": 0, "ok": 0, "error": []}
    short = set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for key, status, err in ex.map(gen, items):
            if status == "short":
                short.add(key)
            elif status == "error":
                results["error"].append(f"{key}: {err}")
            else:
                results[status] += 1
    print(f"skip={results['skip']} ok={results['ok']} error={len(results['error'])}")
    if short:
        print(f"时长<6s 无完整 tile 文件({len(short)}): {sorted(short)[:10]}")
    for e in results["error"]:
        print(f"  {e}")
    return 1 if results["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
