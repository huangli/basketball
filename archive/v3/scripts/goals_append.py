# Task 4: 目检落盘工具 v3——向 goals.json 追加 candidate 记录
# v3 变更（vs v2）: 窗口 t±3（v2 为 t±5）、新增 hoop_id/source、同 file+hoop_id |Δt|<3s 去重合并取中点
# 幂等键不变: (file, window_start)。脚本仅由主控串行调用，禁止并发。
# 用法:
#   python scripts/goals_append.py <candidates.json>     # [{file,t,hoop_id,source?,note?}]
#   python scripts/goals_append.py --selftest            # 自测去重合并（3 条含 1 重叠 → 2 条）
import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GJ = ROOT / "goals.json"
SES = ROOT / "work" / "sessions.json"
HALF_WIN = 3.0          # 窗口半径 t±3
MERGE_GAP = 3.0         # 同 file+hoop_id candidate |Δt|<3s 合并


def load_sessions():
    d = json.loads(SES.read_text(encoding="utf-8"))
    return {f: s["id"] for s in d["sessions"] for f in s["files"]}


def _new_rec(c, f2s):
    ws = round(max(0.0, c["t"] - HALF_WIN), 1)
    return {
        "file": c["file"],
        "session": f2s.get(c["file"]),
        "window_start": ws,
        "window_end": round(c["t"] + HALF_WIN, 1),
        "anchor_time": None,
        "clip_start": None,
        "clip_end": None,
        "slowmo": None,
        "player_label": None,
        "team_label": None,
        "status": "candidate",
        "hoop_id": c["hoop_id"],
        "source": c.get("source", "tile"),
        **({"note": c["note"]} if c.get("note") else {}),
    }


def append(cands, gj_path=None):
    """合并候选到 goals.json。返回 (added, merged)。gj_path 供自测重定向。"""
    path = gj_path or GJ
    gj = json.loads(path.read_text(encoding="utf-8"))
    f2s = load_sessions()
    goals = gj["goals"]
    added = merged = 0
    for c in cands:
        file, t, hid = c["file"], c["t"], c["hoop_id"]
        # 去重合并: 同 file+hoop_id 的 candidate，|Δt|<MERGE_GAP → 取中点更新窗口，不新增
        for g in goals:
            if (g["file"] == file and g.get("hoop_id") == hid
                    and g["status"] == "candidate"):
                t_ex = (g["window_start"] + g["window_end"]) / 2
                if abs(t - t_ex) < MERGE_GAP:
                    t_mid = (t + t_ex) / 2
                    g["window_start"] = round(max(0.0, t_mid - HALF_WIN), 1)
                    g["window_end"] = round(t_mid + HALF_WIN, 1)
                    merged += 1
                    break
        else:
            # 无可合并项 → 新增（幂等键 file+window_start 去重）
            ws = round(max(0.0, t - HALF_WIN), 1)
            if any(g["file"] == file and g["window_start"] == ws for g in goals):
                continue
            goals.append(_new_rec(c, f2s))
            added += 1
    path.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"added={added} merged={merged} total={len(goals)}")
    return added, merged


def selftest():
    """构造 3 条候选（同 file+hoop，含 1 条 Δt=1<3 重叠），期望合并后 2 条记录。"""
    tmpdir = Path(tempfile.mkdtemp())
    tmp = tmpdir / "goals.json"
    tmp.write_text(json.dumps({"version": 3, "goals": []}, ensure_ascii=False),
                   encoding="utf-8")
    cands = [
        {"file": "X.MP4", "t": 5.0, "hoop_id": "near"},   # 新增 ws=2.0
        {"file": "X.MP4", "t": 6.0, "hoop_id": "near"},   # Δt=1<3 → 合并中点 5.5
        {"file": "X.MP4", "t": 20.0, "hoop_id": "near"},  # 独立 → 新增 ws=17.0
    ]
    added, merged = append(cands, gj_path=tmp)
    gj = json.loads(tmp.read_text(encoding="utf-8"))
    n = len(gj["goals"])
    ok = (added == 2 and merged == 1 and n == 2)
    print(f"[自测] added={added} merged={merged} 记录数={n} 期望(2,1,2) → {'PASS' if ok else 'FAIL'}")
    for g in gj["goals"]:
        print(f"  ws={g['window_start']} we={g['window_end']} hoop={g['hoop_id']} src={g['source']}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    src = Path(sys.argv[1])
    append(json.loads(src.read_text(encoding="utf-8")))
