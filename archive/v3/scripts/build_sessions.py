# Task 0.2a 实现：按文件名时间分组生成场次草案 work\sessions.json
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "work" / "file_inventory.json"
OUT = ROOT / "work" / "sessions.json"
THRESHOLD_H = 2


def ftime(name):
    return datetime.strptime(name[4:18], "%Y%m%d%H%M%S")


def main():
    inv = json.loads(INV.read_text(encoding="utf-8"))
    mp4s = sorted(inv["files"])

    by_date = {}
    for f in mp4s:
        by_date.setdefault(f[4:12], []).append(f)

    sessions = []
    suggestions = []
    for date in sorted(by_date):
        files = by_date[date]
        groups = [[files[0]]]
        for prev, cur in zip(files, files[1:]):
            gap_h = (ftime(cur) - ftime(prev)).total_seconds() / 3600
            if gap_h > THRESHOLD_H:
                suggestions.append(
                    f"{date} {prev[12:14]}:{prev[14:16]}:{prev[16:18]} → "
                    f"{cur[12:14]}:{cur[14:16]}:{cur[16:18]} 间隔 {gap_h:.2f}h > {THRESHOLD_H}h，建议拆分")
                groups.append([])
            groups[-1].append(cur)
        suffixes = [chr(ord("a") + i) for i in range(len(groups))]
        for g, sfx in zip(groups, suffixes):
            sid = date if len(groups) == 1 else f"{date}-{sfx}"
            sessions.append({
                "id": sid,
                "start": ftime(g[0]).isoformat(),
                "end": ftime(g[-1]).isoformat(),
                "file_count": len(g),
                "files": g,
            })

    doc = {
        "version": 1,
        "status": "draft",
        "split_threshold_hours": THRESHOLD_H,
        "suggestions": suggestions,
        "sessions": sessions,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sessions={len(sessions)}")
    for s in sessions:
        print(f"  {s['id']}: {s['start'][11:19]}~{s['end'][11:19]} 文件数={s['file_count']}")
    for g in suggestions:
        print(f"  建议: {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
