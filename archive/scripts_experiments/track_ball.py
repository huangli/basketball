from ultralytics import YOLO
import glob, sys, re

model_path = sys.argv[1] if len(sys.argv) > 1 else 'basketball_yolo11.pt'
pattern = sys.argv[2] if len(sys.argv) > 2 else 'work/net_test/seq_*.jpg'
t_start = float(sys.argv[3]) if len(sys.argv) > 3 else 28.0
fps_seq = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0

model = YOLO(model_path)
imgs = sorted(glob.glob(pattern))
for img in imgs:
    r = model(img, conf=0.04, imgsz=1280, verbose=False)
    balls = []
    for b in r[0].boxes:
        cls = model.names[int(b.cls)]
        if cls != 'sports ball': continue
        conf = float(b.conf)
        x1,y1,x2,y2 = [round(v) for v in b.xyxy[0].tolist()]
        cx, cy = (x1+x2)//2, (y1+y2)//2
        balls.append((conf, cx, cy, x2-x1))
    balls.sort(key=lambda x: -x[0])
    name = img.split('\\')[-1]
    m = re.search(r'_(\d+)\.', name)
    idx = int(m.group(1)) if m else 0
    t = t_start + (idx-1)/fps_seq
    if balls:
        top = balls[0]
        print(f"t={t:.1f}s: 球({top[0]:.2f})@({top[1]},{top[2]}) {top[3]}px" + (f" +{len(balls)-1}其他" if len(balls)>1 else ""))
    else:
        print(f"t={t:.1f}s: ---")
