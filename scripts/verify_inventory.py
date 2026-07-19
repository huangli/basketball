# Task 0.1 验收脚本：校验 work\file_inventory.json
import json
import random
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
INV = ROOT / "work" / "file_inventory.json"

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


check("inventory 文件存在", INV.exists())
if not INV.exists():
    print(f"\n{len(failures)} 项失败")
    sys.exit(1)

inv = json.loads(INV.read_text(encoding="utf-8"))

check("头部含 encoder 字段", bool(inv.get("encoder")), f"encoder={inv.get('encoder')}")

mp4s = {p.name for p in RAW.rglob("*.MP4")} | {p.name for p in RAW.rglob("*.mp4")}
files = inv.get("files", {})
check("inventory 条目数 = 扫描 MP4 数", len(files) == len(mp4s), f"{len(files)} vs {len(mp4s)}")
check("inventory 覆盖全部 MP4", set(files) == mp4s)

required = {"fps", "pix_fmt", "duration", "width", "height", "lrf"}
bad = [n for n, e in files.items() if not required <= set(e) or any(e[k] is None for k in ("fps", "pix_fmt", "duration"))]
check("每条含 fps/pix_fmt/duration/width/height/lrf 且关键字段非空", not bad, f"异常 {len(bad)} 条: {bad[:3]}")

lrfs = {p.name for p in RAW.rglob("*.LRF")} | {p.name for p in RAW.rglob("*.lrf")}
expected_missing = sorted(n for n in mp4s if Path(n).with_suffix(".LRF").name not in lrfs)
check("missing_lrf 清单与实际一致", sorted(inv.get("missing_lrf", [])) == expected_missing,
      f"{len(expected_missing)} 个缺 LRF")

sample = random.sample(sorted(mp4s), min(3, len(mp4s)))
for name in sample:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,pix_fmt",
         "-show_entries", "format=duration", "-of", "json", str(RAW / name)],
        capture_output=True, text=True, check=True)
    p = json.loads(out.stdout)
    st = p["streams"][0]
    e = files[name]
    num, den = st["avg_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    ok = (abs(e["fps"] - fps) < 0.01 and e["width"] == st["width"]
          and e["height"] == st["height"] and e["pix_fmt"] == st["pix_fmt"]
          and abs(e["duration"] - float(p["format"]["duration"])) < 0.05)
    check(f"抽查 {name} 与 ffprobe 一致", ok)

print(f"\n{len(failures)} 项失败" if failures else "\n全部通过")
sys.exit(1 if failures else 0)
