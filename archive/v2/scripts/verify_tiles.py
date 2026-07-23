# Task 1.1 验收脚本：校验 work\frames\<basename>\tile_*.jpg 完整性
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "work" / "frames"
INV = ROOT / "work" / "file_inventory.json"

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


inv = json.loads(INV.read_text(encoding="utf-8"))
files = inv["files"]

# 有可粗扫源（LRF 或 MP4）的文件都应有 tile 目录；时长 <10s 允许 0 张
expected = {Path(n).stem: e for n, e in files.items()}
dirs = {p.name: len(list(p.glob("tile_*.jpg"))) for p in FRAMES.iterdir() if p.is_dir()} if FRAMES.exists() else {}

missing = [b for b in expected if b not in dirs]
check("tile 目录数 = 可粗扫文件数", not missing, f"缺 {len(missing)}: {missing[:3]}")

bad_count = []
for b, e in expected.items():
    if b not in dirs:
        continue
    # fps=2 输出帧数 ≈ round(时长×2)；tile 在 EOF 会冲刷尾张 → 张数 = ceil(帧数/20)
    want = math.ceil(round(e["duration"] * 2) / 20)
    got = dirs[b]
    if e["duration"] < 10 and got == 0:
        continue
    if got != want:
        bad_count.append(f"{b}: got {got} want {want}")
check("每目录 tile 数 = ceil(round(时长×2)/20)", not bad_count, f"{len(bad_count)} 个不符: {bad_count[:3]}")

total = sum(dirs.values())
print(f"\ntile 总数 = {total}")
print(f"{len(failures)} 项失败" if failures else "全部通过")
sys.exit(1 if failures else 0)
