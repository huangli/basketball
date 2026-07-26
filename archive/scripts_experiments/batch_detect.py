from ultralytics import YOLO
import glob, re, sys

model = YOLO('basketball_yolo11.pt')
fids = sys.argv[1:] if len(sys.argv) > 1 else ["0011","0020","0030","0040","0128"]

for fid in fids:
    frames = sorted(glob.glob(f'work/frames/{fid}/f_*.jpg'))
    if not frames:
        print(f"\n{fid}: 无帧"); continue
    print(f"\n=== {fid} ({len(frames)}帧) ===")
    dets = []
    for img in frames:
        r = model(img, conf=0.04, imgsz=1280, classes=[32], verbose=False)
        m = re.search(r'f_(\d+)', img)
        idx = int(m.group(1)) if m else 0
        t = round((idx-1) / 5.0, 1)
        best = None
        for b in r[0].boxes:
            conf = float(b.conf)
            x1,y1,x2,y2 = [round(v) for v in b.xyxy[0].tolist()]
            cx, cy = (x1+x2)//2, (y1+y2)//2
            if best is None or conf > best["conf"]:
                best = {"t":t,"conf":round(conf,2),"cx":cx,"cy":cy,"size":x2-x1}
        dets.append(best)
    # 统计
    has_ball = [d for d in dets if d]
    high = [d for d in has_ball if d["conf"] >= 0.3]
    print(f"  有球帧:{len(has_ball)}/{len(dets)}, conf>=0.3:{len(high)}")
    if not has_ball:
        print("  ❌ 全程未检测到球"); continue
    maxconf = max(has_ball, key=lambda x: x["conf"])
    print(f"  最高conf: {maxconf['conf']} @ t={maxconf['t']}s ({maxconf['cx']},{maxconf['cy']}) {maxconf['size']}px")
    # 找静止点候选：连续>=4帧有球且位置聚集
    for i in range(len(dets)-3):
        seg = dets[i:i+4]
        if any(d is None for d in seg): continue
        cxs = [d["cx"] for d in seg]; cys = [d["cy"] for d in seg]
        cx_range = max(cxs)-min(cxs); cy_range = max(cys)-min(cys)
        if cx_range < 40 and cy_range < 40:
            avg_conf = sum(d["conf"] for d in seg)/4
            t0, t1 = seg[0]["t"], seg[-1]["t"]
            conf_min = min(d["conf"] for d in seg)
            occ = "遮挡" if conf_min < avg_conf*0.5 else "非遮挡"
            print(f"  ⭐候选 t={t0}-{t1}s @({sum(cxs)//4},{sum(cys)//4}) avg={avg_conf:.2f} min={conf_min:.2f} [{occ}]")
