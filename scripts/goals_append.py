# 目检落盘工具：向 goals.json 追加 candidate 记录（幂等：同 file+window 不重复）
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GJ = ROOT / "goals.json"
SES = ROOT / "work" / "sessions.json"


def load_sessions():
    d = json.loads(SES.read_text(encoding="utf-8"))
    return {f: s["id"] for s in d["sessions"] for f in s["files"]}


def append(cands):
    gj = json.loads(GJ.read_text(encoding="utf-8"))
    f2s = load_sessions()
    existing = {(g["file"], g["window_start"]) for g in gj["goals"]}
    added = 0
    for c in cands:
        key = (c["file"], round(c["t"] - 5 if c["t"] >= 5 else 0.0, 1))
        if key in existing:
            continue
        gj["goals"].append({
            "file": c["file"],
            "session": f2s.get(c["file"]),
            "window_start": round(max(0.0, c["t"] - 5), 1),
            "window_end": round(c["t"] + 5, 1),
            "anchor_time": None,
            "clip_start": None,
            "clip_end": None,
            "slowmo": None,
            "player_label": None,
            "team_label": None,
            "status": "candidate",
            **({"note": c["note"]} if c.get("note") else {}),
        })
        existing.add(key)
        added += 1
    GJ.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"added={added} total={len(gj['goals'])}")


if __name__ == "__main__":
    # 用法: python scripts\goals_append.py <candidates.json 文件路径>
    # 文件内容: [{"file":"...MP4","t":5.5,"note":"可选"}]
    src = Path(sys.argv[1])
    append(json.loads(src.read_text(encoding="utf-8")))
