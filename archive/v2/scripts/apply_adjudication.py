# Task 2.2 落盘：把裁决 JSON 应用到 goals.json
# 输入: [{"file","window_start","goals":[{anchor_time,note}] | "rejected":"原因" | "uncertain":[{anchor_time,note}]}]
# goals 首条更新原记录、多余条克隆新增；uncertain 保持 candidate 并写 zoom_anchors 待高清复看
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GJ = ROOT / "goals.json"
INV = ROOT / "work" / "file_inventory.json"


def apply(gj, inv, items):
    n_conf, n_rej, n_unc = 0, 0, 0
    for it in items:
        rec = next((g for g in gj["goals"]
                    if g["file"] == it["file"] and g["window_start"] == it["window_start"]), None)
        if rec is None:
            print(f"warn: 未找到 {it['file']}|{it['window_start']}")
            continue
        if "rejected" in it:
            rec["status"] = "rejected"
            rec["note"] = (rec.get("note", "") + " | rejected: " + it["rejected"]).strip(" |")
            n_rej += 1
            continue
        if "uncertain" in it:
            rec["zoom_anchors"] = [u["anchor_time"] for u in it["uncertain"]]
            rec["note"] = (rec.get("note", "") + " | 存疑待高清复看: "
                           + "; ".join(f"{u['anchor_time']}s {u.get('note', '')}" for u in it["uncertain"])).strip(" |")
            n_unc += 1
            continue
        goals = it.get("goals", [])
        if not goals:
            rec["status"] = "rejected"
            rec["note"] = (rec.get("note", "") + " | rejected: 空裁决").strip(" |")
            n_rej += 1
            continue
        finfo = inv.get(rec["file"], {})
        dur, fps = finfo.get("duration", 1e9), finfo.get("fps", 50.0)
        for i, gl in enumerate(goals):
            a = round(gl["anchor_time"], 1)
            target = rec if i == 0 else dict(rec)
            target.update({
                "anchor_time": a,
                "clip_start": round(max(0.0, a - 4), 1),
                "clip_end": round(min(dur, a + 2), 1),
                "slowmo": bool(fps >= 100),
                "status": "confirmed",
                "note": (rec.get("note", "") + " | " + gl.get("note", "")).strip(" |"),
            })
            target.pop("zoom_anchors", None)
            if i > 0:
                gj["goals"].append(target)
            n_conf += 1
    return n_conf, n_rej, n_unc


if __name__ == "__main__":
    src = Path(sys.argv[1])
    items = json.loads(src.read_text(encoding="utf-8"))
    gj = json.loads(GJ.read_text(encoding="utf-8"))
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    c, r, u = apply(gj, inv, items)
    GJ.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"confirmed+={c} rejected+={r} uncertain={u} total={len(gj['goals'])}")
