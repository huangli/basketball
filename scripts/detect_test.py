import sys
from ultralytics import YOLO

img_path = sys.argv[1] if len(sys.argv) > 1 else 'work/net_test/frame_31s.jpg'
imgsz = int(sys.argv[2]) if len(sys.argv) > 2 else 1280
model_path = sys.argv[3] if len(sys.argv) > 3 else 'yolov8n.pt'

model = YOLO(model_path)
results = model(img_path, conf=0.1, imgsz=imgsz, verbose=False)
print(f"Model: {model_path} | Image: {img_path} (imgsz={imgsz})")
boxes = results[0].boxes
print(f"Detected {len(boxes)} objects:")
for box in boxes:
    cls_id = int(box.cls)
    cls = model.names[cls_id]
    conf = float(box.conf)
    x1, y1, x2, y2 = [round(v) for v in box.xyxy[0].tolist()]
    ox1, oy1, ox2, oy2 = x1*2, y1*2, x2*2, y2*2
    print(f"  {cls} (id={cls_id}) conf={conf:.2f} img=[{x1},{y1},{x2},{y2}] orig=[{ox1},{oy1},{ox2},{oy2}] size={x2-x1}x{y2-y1}")
