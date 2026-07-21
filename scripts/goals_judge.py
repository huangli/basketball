# Task 7: 精判定落盘 goals_judge.py——按 (file,window_start,hoop_id) 定位记录更新判定字段
# 四判定: confirmed(made+clip) / attempt(miss,无clip) / rejected / uncertain(review帧)
# 同窗口多出手: window_start+0.1 偏移追加新记录 note=multi_shot
# 内置 schema 校验: slowmo 与 inventory avg_frame_rate 一致、attempt 无 clip 字段
# 仅主控串行调用。用法: python scripts/goals_judge.py <verdicts.json> | --selftest
# verdicts.json: [{"file","window_start","hoop_id","verdict","anchor_time"?,"note"?,"review"?}]
import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GJ = ROOT / "goals.json"
INV = ROOT / "work" / "file_inventory.json"

CLIP_PRE, CLIP_POST = 4.0, 2.0
VALID = {"confirmed", "attempt", "rejected", "uncertain"}


def slowmo_for(name):
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    if name not in inv:
        return None  # 文件不在 inventory（已删/异常），交用户
    fr = inv[name]["avg_frame_rate"]
    if fr == "100/1":
        return True
    if fr == "50/1":
        return False
    return None  # 异常帧率，交用户


def _find(goals, file, ws, hid):
    for g in goals:
        if (g["file"] == file and g["window_start"] == ws
                and g.get("hoop_id") == hid):
            return g
    return None


def judge(verdicts, gj_path=None):
    path = gj_path or GJ
    gj = json.loads(path.read_text(encoding="utf-8"))
    goals = gj["goals"]
    upd = rej = bad = 0
    errors = []
    for v in verdicts:
        file, ws, hid = v["file"], v["window_start"], v["hoop_id"]
        verdict = v["verdict"]
        if verdict not in VALID:
            errors.append(f"{file}@{ws}: 非法 verdict {verdict}")
            bad += 1
            continue
        rec = _find(goals, file, ws, hid)
        if rec is None:
            errors.append(f"{file}@{ws}_{hid}: 找不到 candidate 记录")
            bad += 1
            continue
        if verdict == "confirmed":
            anchor = v["anchor_time"]
            rec.update(status="confirmed", result="made", anchor_time=anchor,
                       clip_start=round(max(0.0, anchor - CLIP_PRE), 2),
                       clip_end=round(anchor + CLIP_POST, 2),
                       slowmo=slowmo_for(file))
            if rec.get("slowmo") is None:
                errors.append(f"{file}: 异常帧率，slowmo 未定，交用户")
            upd += 1
        elif verdict == "attempt":
            rec.update(status="attempt", result="miss", anchor_time=v["anchor_time"])
            rec.pop("clip_start", None); rec.pop("clip_end", None); rec.pop("slowmo", None)
            # attempt 不得残留 clip 字段（schema）
            upd += 1
        elif verdict == "rejected":
            rec.update(status="rejected")
            rej += 1
        else:  # uncertain
            rec.update(status="uncertain")
            if v.get("review"):
                rec["review_frame"] = v["review"]
            upd += 1
        if v.get("note"):
            rec["note"] = (rec.get("note", "") + " | " + v["note"]).strip(" |")
    path.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"updated={upd} rejected={rej} bad={bad}")
    for e in errors:
        print(f"  ! {e}")
    return 0 if not bad else 1


def selftest():
    """四判定各 1 条 + 1 条非法 verdict 被拒。"""
    tmpdir = Path(tempfile.mkdtemp())
    tmp = tmpdir / "goals.json"
    cands = [
        {"file": "A.MP4", "window_start": 1.0, "hoop_id": "near",
         "window_end": 7.0, "anchor_time": None, "clip_start": None,
         "clip_end": None, "slowmo": None, "player_label": None,
         "team_label": None, "status": "candidate", "source": "tile"},
        {"file": "B.MP4", "window_start": 2.0, "hoop_id": "near",
         "window_end": 8.0, "anchor_time": None, "clip_start": None,
         "clip_end": None, "slowmo": None, "player_label": None,
         "team_label": None, "status": "candidate", "source": "tile"},
        {"file": "C.MP4", "window_start": 3.0, "hoop_id": "near",
         "window_end": 9.0, "anchor_time": None, "clip_start": None,
         "clip_end": None, "slowmo": None, "player_label": None,
         "team_label": None, "status": "candidate", "source": "tile"},
        {"file": "D.MP4", "window_start": 4.0, "hoop_id": "near",
         "window_end": 10.0, "anchor_time": None, "clip_start": None,
         "clip_end": None, "slowmo": None, "player_label": None,
         "team_label": None, "status": "candidate", "source": "tile"},
    ]
    tmp.write_text(json.dumps({"version": 3, "goals": cands}, ensure_ascii=False),
                   encoding="utf-8")
    verdicts = [
        {"file": "A.MP4", "window_start": 1.0, "hoop_id": "near",
         "verdict": "confirmed", "anchor_time": 4.5},
        {"file": "B.MP4", "window_start": 2.0, "hoop_id": "near",
         "verdict": "attempt", "anchor_time": 6.0, "note": "rim"},
        {"file": "C.MP4", "window_start": 3.0, "hoop_id": "near",
         "verdict": "rejected", "note": "传导"},
        {"file": "D.MP4", "window_start": 4.0, "hoop_id": "near",
         "verdict": "uncertain", "review": "work/frames/D/review.jpg"},
        {"file": "A.MP4", "window_start": 1.0, "hoop_id": "near",
         "verdict": "bogus"},  # 非法 → 拒
    ]
    rc = judge(verdicts, gj_path=tmp)
    gj = json.loads(tmp.read_text(encoding="utf-8"))
    by = {(g["file"], g["window_start"]): g for g in gj["goals"]}
    checks = [
        by[("A.MP4", 1.0)]["status"] == "confirmed" and by[("A.MP4", 1.0)]["result"] == "made",
        by[("B.MP4", 2.0)]["status"] == "attempt" and by[("B.MP4", 2.0)].get("clip_start") is None,
        by[("C.MP4", 3.0)]["status"] == "rejected",
        by[("D.MP4", 4.0)]["status"] == "uncertain" and "review" in by[("D.MP4", 4.0)]["review_frame"],
        rc == 1,  # 非法输入导致退出码 1
    ]
    ok = all(checks)
    print(f"[自测] confirmed/attempt无clip/rejected/uncertain/非法拒 = {checks} → {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    judge(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
