"""高帧率 rim-plane 验证：原片 30fps 抽帧 + 球检测，看盲区穿越判别力。

对比 8 个确认进球 vs 8 个候选，每帧选「距筐最近的球」，算盲区/穿越/下落。
"""
import glob
import json
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from ultralytics import YOLO

RAW = "20260722地平线/2026 年 7月22 日 地平线"
MODEL = "models/abdullahtarek_ball.pt"
BALL_CLS = 0
CONF = 0.15
IMGSZ = 1280
FPS = 30
HALF_WIN = 1.5
RADIUS = 280
FRAMES_DIR = "test/hifi_frames"
os.makedirs(FRAMES_DIR, exist_ok=True)

print("loading model...")
model = YOLO(MODEL)


def extract(src, t0, outdir):
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)
    start = max(0.0, t0 - HALF_WIN)
    cmd = ["ffmpeg", "-y", "-ss", f"{start}", "-t", f"{HALF_WIN * 2}",
           "-i", src, "-vf", f"scale=1920:-2,fps={FPS}", "-q:v", "2",
           os.path.join(outdir, "f_%04d.jpg")]
    subprocess.run(cmd, capture_output=True)


def detect_dir(outdir):
    imgs = sorted(glob.glob(os.path.join(outdir, "f_*.jpg")))
    per_frame = []
    for img in imgs:
        r = model(img, imgsz=IMGSZ, conf=CONF, classes=[BALL_CLS], verbose=False)[0]
        dets = []
        if r.boxes is not None:
            for b in r.boxes:
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                dets.append(((x1 + x2) / 2, (y1 + y2) / 2, float(b.conf[0])))
        per_frame.append(dets)
    return per_frame


def analyze_hifi(sample, tag):
    fid, t0, hcx, hcy = sample["fid"], sample["t0"], sample["cx"], sample["cy"]
    src = os.path.join(RAW, fid + ".mp4")
    if not os.path.exists(src):
        return {"tag": tag, "fid": fid[-12:], "t0": t0, "err": "no src"}
    outdir = os.path.join(FRAMES_DIR, f"{tag}_{fid[-12:]}_{int(t0 * 10)}")
    extract(src, t0, outdir)
    pf = detect_dir(outdir)
    seq = []
    for i, dets in enumerate(pf):
        t = round(i / FPS - HALF_WIN, 2)
        cands = [((x - hcx) ** 2 + (y - hcy) ** 2, x, y, c) for (x, y, c) in dets
                 if (x - hcx) ** 2 + (y - hcy) ** 2 < RADIUS ** 2]
        if cands:
            _, x, y, c = min(cands)
            seq.append((t, round(x), round(y), round(c, 2)))
    if len(seq) < 3:
        return {"tag": tag, "fid": fid[-12:], "t0": t0, "err": f"few {len(seq)}",
                "nframes": len(pf), "seq": seq}
    maxgap, gi = 0.0, 0
    for i in range(len(seq) - 1):
        g = seq[i + 1][0] - seq[i][0]
        if g > maxgap:
            maxgap, gi = g, i
    by, ay = seq[gi][2], seq[gi + 1][2]
    crossing = ay > by
    pre = seq[: gi + 1]
    fall_n = sum(1 for i in range(1, len(pre)) if pre[i][2] > pre[i - 1][2])
    falling = fall_n >= max(1, len(pre) - 1) * 0.6 if len(pre) > 1 else False
    return {"tag": tag, "fid": fid[-12:], "t0": t0, "hcx": hcx, "hcy": hcy,
            "nframes": len(pf), "nball": len(seq), "blind": round(maxgap, 2),
            "by": by, "ay": ay, "crossing": crossing, "falling": falling,
            "seq": [(t, y) for (t, x, y, c) in seq]}


yes = json.load(open("work/20260722/candidates_yes.json", encoding="utf-8"))
rev = json.load(open("work/20260722/candidates_review_v3.json", encoding="utf-8"))
yk = {(x["fid"], round(x["t0"], 1)) for x in yes}
neg = [x for x in rev if (x["fid"], round(x["t0"], 1)) not in yk][:8]
pos = yes[:8]

results = []
print("## POSITIVE")
for s in pos:
    r = analyze_hifi(s, "POS")
    results.append(r)
    print(json.dumps({k: v for k, v in r.items() if k != "seq"}, ensure_ascii=False))
    print("  seq(t,y):", r.get("seq"))
print("## NEGATIVE")
for s in neg:
    r = analyze_hifi(s, "NEG")
    results.append(r)
    print(json.dumps({k: v for k, v in r.items() if k != "seq"}, ensure_ascii=False))
    print("  seq(t,y):", r.get("seq"))

json.dump(results, open("test/hifi_result.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n## SUMMARY")
pr = [r for r in results if r.get("tag") == "POS" and "err" not in r]
nr = [r for r in results if r.get("tag") == "NEG" and "err" not in r]
if pr:
    print(f"POS n={len(pr)} crossing={sum(r['crossing'] for r in pr)} "
          f"falling={sum(r['falling'] for r in pr)} "
          f"blind_avg={sum(r['blind'] for r in pr)/len(pr):.2f} "
          f"nball_avg={sum(r['nball'] for r in pr)/len(pr):.0f}")
if nr:
    print(f"NEG n={len(nr)} crossing={sum(r['crossing'] for r in nr)} "
          f"falling={sum(r['falling'] for r in nr)} "
          f"blind_avg={sum(r['blind'] for r in nr)/len(nr):.2f} "
          f"nball_avg={sum(r['nball'] for r in nr)/len(nr):.0f}")
