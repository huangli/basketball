"""汇总高帧率 rim-plane 实验结果。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
r = json.load(open("test/hifi_result.json", encoding="utf-8"))
for tag in ("POS", "NEG"):
    grp = [x for x in r if x.get("tag") == tag]
    ok = [x for x in grp if "err" not in x]
    err = [x for x in grp if "err" in x]
    print(f"=== {tag}: {len(ok)} ok, {len(err)} err ===")
    for x in ok:
        print(f"  {x['fid']} t0={x['t0']} blind={x['blind']}s by={x['by']} ay={x['ay']} "
              f"CROSS={int(x['crossing'])} FALL={int(x['falling'])} "
              f"nball={x['nball']}/{x['nframes']}")
        ys = [y for (t, y) in x["seq"]]
        print(f"     y_range=[{min(ys)}..{max(ys)}] hoop_y={x['hcy']} seq_n={len(x['seq'])}")
    for x in err:
        print(f"  ERR {x.get('fid')} t0={x.get('t0')}: {x.get('err')}")
    if ok:
        cr = sum(x["crossing"] for x in ok)
        fl = sum(x["falling"] for x in ok)
        ba = sum(x["blind"] for x in ok) / len(ok)
        nb = sum(x["nball"] for x in ok) / len(ok)
        both = sum(x["crossing"] and x["falling"] for x in ok)
        print(f"  >> crossing={cr}/{len(ok)} falling={fl}/{len(ok)} "
              f"cross&fall={both}/{len(ok)} blind_avg={ba:.2f}s nball_avg={nb:.0f}")
