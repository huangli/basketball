# Task 0.2a 验收脚本：校验 work\sessions.json 草案
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
SES = ROOT / "work" / "sessions.json"
INV = ROOT / "work" / "file_inventory.json"

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def ftime(name):
    return datetime.strptime(name[4:18], "%Y%m%d%H%M%S")


check("sessions.json 存在", SES.exists())
if not SES.exists():
    print(f"\n{len(failures)} 项失败")
    sys.exit(1)

ses = json.loads(SES.read_text(encoding="utf-8"))
inv = json.loads(INV.read_text(encoding="utf-8"))
mp4s = sorted(inv["files"])

sessions = ses.get("sessions", [])
check("至少 1 个场次", len(sessions) >= 1, f"{len(sessions)} 个")

all_files = [f for s in sessions for f in s["files"]]
check("每个 MP4 恰好属于一个场次", sorted(all_files) == mp4s and len(all_files) == len(set(all_files)),
      f"{len(all_files)} 条归属 / {len(mp4s)} 文件")

for s in sessions:
    check(f"场次 {s['id']} 字段完整", all(k in s for k in ("id", "start", "end", "files")) and bool(s["files"]))
    ts = [ftime(f) for f in s["files"]]
    check(f"场次 {s['id']} 起止时间与文件一致",
          s["start"] == min(ts).isoformat() and s["end"] == max(ts).isoformat())

# 同一场次内相邻文件间隔必须 <= 阈值；不同场次（同日期）边界间隔必须 > 阈值
th = ses.get("split_threshold_hours", 2)
for s in sessions:
    ts = sorted(ftime(f) for f in s["files"])
    gaps = [(ts[i + 1] - ts[i]).total_seconds() / 3600 for i in range(len(ts) - 1)]
    check(f"场次 {s['id']} 内无超 {th}h 间隔", all(g <= th for g in gaps),
          f"最大 {max(gaps, default=0):.2f}h")

by_date = {}
for s in sessions:
    by_date.setdefault(s["id"][:8], []).append(s)
for date, group in by_date.items():
    group = sorted(group, key=lambda x: x["start"])
    for a, b in zip(group, group[1:]):
        gap = (datetime.fromisoformat(b["start"]) - datetime.fromisoformat(a["end"])).total_seconds() / 3600
        check(f"{date} 场次边界 {a['id']}→{b['id']} 间隔 > {th}h", gap > th, f"{gap:.2f}h")

check("suggestions 字段存在（可为空列表）", isinstance(ses.get("suggestions"), list))
check("status 为 draft 或 confirmed", ses.get("status") in ("draft", "confirmed"), ses.get("status"))

print(f"\n{len(failures)} 项失败" if failures else "\n全部通过")
sys.exit(1 if failures else 0)
