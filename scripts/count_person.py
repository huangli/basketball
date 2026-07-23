from ultralytics import YOLO
import glob, sys

model = YOLO('yolov8n.pt')
imgs = sorted(glob.glob('work/net_test/seq_*.jpg'))
print("筐区域800x800内 person 数量变化 (28-33.4s):")
for img in imgs:
    r = model(img, conf=0.25, imgsz=1280, classes=[0], verbose=False)
    n = len(r[0].boxes)
    name = img.split('\\')[-1]
    idx = int(name.split('_')[1].split('.')[0])
    t = 28.0 + (idx-1)*0.2
    bar = '#' * n
    mark = ' <<<进球' if abs(t - 31.0) < 0.15 else ''
    print(f"t={t:.1f}s: {n:2d}人 {bar}{mark}")
