# Task 2.1 验证：candidate 窗口的精抽 tile 数量符合预期
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "work" / "frames"
INV = ROOT / "work" / "file_inventory.json"
GOALS = ROOT / "goals.json"


def main():
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    gj = json.loads(GOALS.read_text(encoding="utf-8"))
    bad, total = [], 0
    for g in gj["goals"]:
        if g["status"] != "candidate" or g["file"] not in inv:
            continue
        total += 1
        stem = Path(g["file"]).stem
        ws, we = g["window_start"], g["window_end"]
        frames = round((min(we, inv[g["file"]]["duration"]) - ws) * 10)
        want = max(1, math.ceil(frames / 20))
        floor_want = max(1, frames // 20)
        got = len(list((FRAMES / stem).glob(f"fine_{ws}_*.jpg"))) if (FRAMES / stem).exists() else 0
        if not (floor_want <= got <= want):
            bad.append(f"{stem}|{ws}: want={floor_want}..{want} got={got}")
    print(f"checked={total} bad={len(bad)}")
    for b in bad[:20]:
        print(f"  {b}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
