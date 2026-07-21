# Task 4 验收：按 inventory 时长逐 (文件,hoop) 核对 roi tile 张数 ∈ {floor(round(dur*2)/12), +1}
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "work" / "frames"
INV = ROOT / "work" / "file_inventory.json"
HOOPS = ROOT / "work" / "hoops.json"
PER = 12  # 4x3 tile

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
hoops = json.loads(HOOPS.read_text(encoding="utf-8"))
bad, total = [], 0
for name, h in hoops.items():
    if name not in inv or not h["hoops"]:
        continue
    dur = float(inv[name]["duration"])
    want = math.floor(round(dur * 2) / PER)
    stem = Path(name).stem
    for hoop in h["hoops"]:
        if hoop.get("dropped"):
            continue
        hid = hoop["id"]
        d = FRAMES / stem
        got = len(list(d.glob(f"roi_{hid}_*.jpg"))) if d.exists() else 0
        if want == 0:
            if got != 0:
                bad.append(f"{stem}_{hid}: 短文件却 got {got}")
            continue
        total += got
        if got not in (want, want + 1):
            bad.append(f"{stem}_{hid}: got {got} expect {want}~{want + 1}")

check("每(文件,hoop) roi tile 数 ∈ {want, want+1}", not bad,
      f"{len(bad)} 不符: {bad[:4]}")
print(f"\nroi tile 总数 = {total}")
print(f"{len(failures)} 项失败" if failures else "全部通过")
sys.exit(1 if failures else 0)
