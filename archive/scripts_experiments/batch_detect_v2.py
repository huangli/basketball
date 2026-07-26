from ultralytics import YOLO
import glob, re, sys

ball_model = YOLO('basketball_yolo11.pt')
person_model = YOLO('yolov8n.pt')

def iou(b1, b2):
    x1=max(b1[0],b2[0]); y1=max(b1[1],b2[1])
    x2=min(b1[2],b2[2]); y2=min(b1[3],b2[3])
    if x2<=x1 or y2<=y1: return 0.0
    inter=(x2-x1)*(y2-y1)
    a1=(b1[2]-b1[0])*(b1[3]-b1[1]); a2=(b2[2]-b2[0])*(b2[3]-b2[1])
    return inter/(a1+a2-inter)

fids = sys.argv[1:] if len(sys.argv) > 1 else ["0011","0020","0030"]

for fid in fids:
    frames = sorted(glob.glob(f'work/frames/{fid}/f_*.jpg'))
    if not frames: print(f"\n{fid}: 无帧"); continue
    print(f"\n=== {fid} ({len(frames)}帧) ===")
    dets = []
    for img in frames:
        rb = ball_model(img, conf=0.04, imgsz=1280, classes=[32], verbose=False)
        rp = person_model(img, conf=0.3, imgsz=640, classes=[0], verbose=False)
        m = re.search(r'f_(\d+)', img); idx = int(m.group(1)) if m else 0
        t = round((idx-1)/5.0, 1)
        ball = None
        for b in rb[0].boxes:
            conf=float(b.conf); box=[round(v) for v in b.xyxy[0].tolist()]
            if ball is None or conf > ball["conf"]: ball={"conf":round(conf,2),"box":box}
        persons=[[round(v) for v in b.xyxy[0].tolist()] for b in rp[0].boxes]
        dets.append({"t":t,"ball":ball,"persons":persons})
    # 找4帧窗口位置聚集
    raw=[]
    for i in range(len(dets)-3):
        seg=dets[i:i+4]
        if any(d["ball"] is None for d in seg): continue
        cxs=[(d["ball"]["box"][0]+d["ball"]["box"][2])//2 for d in seg]
        cys=[(d["ball"]["box"][1]+d["ball"]["box"][3])//2 for d in seg]
        if max(cxs)-min(cxs)<40 and max(cys)-min(cys)<40: raw.append(i)
    if not raw: print("  无静止段"); continue
    # 合并相邻起始点（<=4帧间隔）
    merged=[]; s=raw[0]; p=raw[0]
    for idx in raw[1:]:
        if idx-p<=4: p=idx
        else: merged.append((s,p+4)); s=idx; p=idx
    merged.append((s,p+4))
    # 计算属性 + 过滤
    cands=[]
    for ms,me in merged:
        me=min(me,len(dets)); sd=[d for d in dets[ms:me] if d["ball"]]
        if len(sd)<4: continue
        t0=sd[0]["t"]; dur=round(sd[-1]["t"]-t0,1)
        ac=round(sum(d["ball"]["conf"] for d in sd)/len(sd),2)
        cx=sum((d["ball"]["box"][0]+d["ball"]["box"][2])//2 for d in sd)//len(sd)
        cy=sum((d["ball"]["box"][1]+d["ball"]["box"][3])//2 for d in sd)//len(sd)
        cands.append({"t0":t0,"dur":dur,"ac":ac,"cx":cx,"cy":cy,"s":ms,"e":me})
    print(f"  静止段（合并后）:{len(cands)}")
    # 过滤：死球>3s + person IoU>0.3
    kept=[]; rm_held=0; rm_dead=0
    for c in cands:
        if c["dur"]>3.0: rm_dead+=1; continue
        held=False
        for k in range(c["s"],c["e"]):
            if dets[k]["ball"] is None: continue
            bb=dets[k]["ball"]["box"]
            for pb in dets[k]["persons"]:
                if iou(bb,pb)>0.3: held=True; break
            if held: break
        if held: rm_held+=1
        else: kept.append(c)
    print(f"  排除: 持球{rm_held} + 死球{rm_dead} => 过滤后:{len(kept)}")
    for c in kept:
        print(f"    ⭐ t={c['t0']}s dur={c['dur']}s conf={c['ac']} @({c['cx']},{c['cy']})")
