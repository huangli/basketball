"""探针：确认 work/detect 缓存的 balls 结构（frames 是 int 计数）。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = "work/detect/{}_mot_cache.json"
fid = "dji_mimo_20260722_190412_0_1784829856306_video"
d = json.load(open(CACHE.format(fid), encoding="utf-8"))
print("top keys:", list(d.keys()), "| frames(int):", d["frames"])
ba = d["balls"]
print("balls type:", type(ba).__name__, "len:", len(ba) if hasattr(ba, "__len__") else "?")
if isinstance(ba, list) and ba:
    for i in (0, 1, 2):
        if i < len(ba):
            print(f"balls[{i}]:", json.dumps(ba[i], ensure_ascii=False)[:300])
elif isinstance(ba, dict):
    ks = list(ba.keys())[:5]
    print("balls dict keys:", ks)
    if ks:
        print("balls[first]:", json.dumps(ba[ks[0]], ensure_ascii=False)[:300])
