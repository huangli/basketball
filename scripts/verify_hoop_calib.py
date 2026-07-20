# Task 2 验收脚本：校验 work\frames\_calib\（单帧数 / sheet 数 / sheet 尺寸 / meta.json 可溯源）
import json
import math
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CALIB = ROOT / "work" / "frames" / "_calib"
FRAMES_DIR = CALIB / "frames"
META = CALIB / "meta.json"
PILOT = ROOT / "work" / "pilot_files.json"
CELL = [480, 360]
MULTIPLIER = 8
PER_SHEET = 12
MAX_DIM = 2000

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


pilot = json.loads(PILOT.read_text(encoding="utf-8"))["files"]
stems = [Path(n).stem for n in pilot]
n = len(stems)
want_sheets = math.ceil(n / PER_SHEET)

jpgs = {p.stem for p in FRAMES_DIR.glob("*.jpg")} if FRAMES_DIR.exists() else set()
check(f"单帧数 = {n}", len(jpgs) == n, f"{len(jpgs)} vs {n}")
check("单帧与 pilot 清单一一对应", jpgs == set(stems),
      f"缺 {sorted(set(stems) - jpgs)[:3]} 多 {sorted(jpgs - set(stems))[:3]}")

sheets = sorted(CALIB.glob("sheet_*.jpg"))
check(f"sheet 数 = {want_sheets}", len(sheets) == want_sheets, f"{len(sheets)} vs {want_sheets}")

for sh in sheets:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(sh)],
        capture_output=True, text=True)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(","))
        ok = r.returncode == 0 and 0 < w <= MAX_DIM and 0 < h <= MAX_DIM
        check(f"{sh.name} 宽高 ≤{MAX_DIM}", ok, f"{w}x{h}")
    except ValueError:
        check(f"{sh.name} ffprobe 可读", False, r.stderr.strip()[:120])

check("meta.json 存在", META.exists())
if META.exists():
    try:
        meta = json.loads(META.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        meta = {}
        check("meta.json 可解析", False, str(e))
    if meta:
        padded = want_sheets * PER_SHEET - n
        check("meta.cell = [480,360]", meta.get("cell") == CELL, str(meta.get("cell")))
        check("meta.multiplier = 8", meta.get("multiplier") == MULTIPLIER)
        check("meta.padded 正确", meta.get("padded") == padded,
              f"{meta.get('padded')} vs {padded}")
        order = meta.get("order")
        check("meta.order 长度 = n + padded",
              isinstance(order, list) and len(order) == n + padded,
              f"{len(order) if isinstance(order, list) else '?'} vs {n + padded}")
        if isinstance(order, list):
            real = [s for s in order if s is not None]
            check("order 前 50 格 = pilot 格序（可溯源）", real == stems,
                  f"real={len(real)}")
            check("克隆格均标 null 且全部在尾部", order[n:] == [None] * (len(order) - n))
            check("order 中 stem 均有对应单帧", all(s in jpgs for s in real))

print(f"\n{len(failures)} 项失败" if failures else "\n全部通过")
sys.exit(1 if failures else 0)
