"""rim-plane 信号探针：用 5fps 缓存对比确认进球 vs 候选的盲区穿越模式。

判据：
  crossing = 最大无检测盲区后球的 y > 盲区前球的 y（下落穿越）
  straddle = 锚点窗口内球既出现在筐 hoop_cy 上方又下方
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = "work/detect/{}_mot_cache.json"
WIN = 2.0
GAP_THRESH = 0.4


def load_dets(fid: str):
    p = CACHE.format(fid)
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    out = []
    for fr in d["balls"]:
        if not fr:
            continue
        best = max(fr, key=lambda x: x["conf"])
        out.append((best["sec"], best["cx"], best["cy"], best["conf"]))
    return out


def analyze(sample):
    fid, t0, hoop_cy = sample["fid"], sample["t0"], sample["cy"]
    dets = load_dets(fid)
    if dets is None:
        return {"fid": fid, "t0": t0, "err": "no cache"}
    win = [w for w in dets if t0 - WIN <= w[0] <= t0 + WIN]
    if len(win) < 2:
        return {"fid": fid, "t0": t0, "err": f"few dets n={len(win)}"}
    max_gap, gi = 0.0, 0
    for i in range(len(win) - 1):
        dg = win[i + 1][0] - win[i][0]
        if dg > max_gap:
            max_gap, gi = dg, i
    before_y = win[gi][2]
    after_y = win[gi + 1][2]
    crossing = after_y > before_y
    above = sum(1 for w in win if w[2] < hoop_cy)
    below = sum(1 for w in win if w[2] > hoop_cy)
    straddle = above > 0 and below > 0
    return {
        "fid": fid[-14:], "t0": t0, "hoop_cy": hoop_cy,
        "blind": round(max_gap, 2), "before_y": before_y, "after_y": after_y,
        "crossing": crossing, "straddle": straddle,
        "above": above, "below": below,
    }


def run(samples, label):
    print(f"==== {label} ====")
    rows = []
    for s in samples:
        r = analyze(s)
        if "err" in r:
            print(f"  {r['fid'][-14:]} t0={r['t0']:.1f} SKIP {r['err']}")
            continue
        rows.append(r)
        print(f"  {r['fid']} t0={r['t0']:.1f} hoop_y={r['hoop_cy']} blind={r['blind']}s "
              f"before_y={r['before_y']} after_y={r['after_y']} "
              f"CROSS={int(r['crossing'])} STRADDLE={int(r['straddle'])} "
              f"abov/below={r['above']}/{r['below']}")
    n = len(rows)
    cr = sum(r["crossing"] for r in rows)
    st = sum(r["straddle"] for r in rows)
    both = sum(r["crossing"] and r["straddle"] for r in rows)
    print(f"  --> crossing={cr}/{n}  straddle={st}/{n}  cross&straddle={both}/{n}\n")
    return cr, st, both, n


yes = json.load(open("work/20260722/candidates_yes.json", encoding="utf-8"))
rev = json.load(open("work/20260722/candidates_review_v3.json", encoding="utf-8"))
yes_keys = {(x["fid"], round(x["t0"], 1)) for x in yes}
neg = [x for x in rev if (x["fid"], round(x["t0"], 1)) not in yes_keys][:30]

pcr, pst, pboth, pn = run(yes, "POSITIVE (confirmed goals)")
ncr, nst, nboth, nn = run(neg, "NEGATIVE (candidates, unconfirmed)")

print("==== SUMMARY ====")
print(f"positive: crossing={pcr}/{pn} straddle={pst}/{pn} both={pboth}/{pn}")
print(f"negative: crossing={ncr}/{nn} straddle={nst}/{nn} both={nboth}/{nn}")
