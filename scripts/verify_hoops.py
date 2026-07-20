# Task 3：hoops.json 校验——schema 全量校验 + 用 meta.json 倍率反推抽查 3 个 hoop
# 抽查方式：原片坐标 ÷ multiplier 得格内坐标；机位移动文件按 25% 帧标定，
#           故 patch 统一取 25% 帧（静态机位 25%≈50%），裁小图供 AI 目检确认筐在附近
# 用法: python scripts/verify_hoops.py
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
HOOPS = ROOT / "work" / "hoops.json"
PILOT = ROOT / "work" / "pilot_files.json"
INV = ROOT / "work" / "file_inventory.json"
CALIB = ROOT / "work" / "frames" / "_calib"
META = CALIB / "meta.json"
PATCH = 120  # 抽查 patch 边长（格内像素）
SPOT_TS = 0.25  # 抽查帧位置：与 check / 移动机位标定一致取 25% 时长

ORIG_W, ORIG_H = 3840, 2880
CROP_MIN, CROP_MAX = 700, 1700
IDS = {"near", "far"}


def check_schema(pilot, hoops):
    """返回 (errors, warnings)。无球场文件（hoops 为空且有 note）记 warning 不算错误。"""
    errors, warnings = [], []
    for name in pilot:
        if name not in hoops:
            errors.append(f"{name}: hoops.json 缺失")
            continue
        entry = hoops[name]
        hs = entry.get("hoops")
        if not isinstance(hs, list):
            errors.append(f"{name}: hoops 不是列表")
            continue
        if len(hs) == 0:
            if entry.get("note"):
                warnings.append(f"{name}: 0 个 hoop（{entry['note']}）")
            else:
                errors.append(f"{name}: hoops 为空且无 note 说明")
            continue
        if len(hs) > 2:
            errors.append(f"{name}: hoops 数 {len(hs)} > 2")
        seen = set()
        for h in hs:
            hid = h.get("id")
            tag = f"{name}[{hid}]"
            if hid not in IDS:
                errors.append(f"{tag}: id 非法")
            if hid in seen:
                errors.append(f"{tag}: id 重复")
            seen.add(hid)
            x, y, crop = h.get("x"), h.get("y"), h.get("crop")
            if not isinstance(x, int) or not 0 <= x <= ORIG_W:
                errors.append(f"{tag}: x={x} 越界 [0,{ORIG_W}]")
            if not isinstance(y, int) or not 0 <= y <= ORIG_H:
                errors.append(f"{tag}: y={y} 越界 [0,{ORIG_H}]")
            if not isinstance(crop, int) or not CROP_MIN <= crop <= CROP_MAX:
                errors.append(f"{tag}: crop={crop} 越界 [{CROP_MIN},{CROP_MAX}]")
    extra = [n for n in hoops if n not in set(pilot)]
    for n in extra:
        warnings.append(f"{n}: 不在 pilot 清单中（多余条目）")
    return errors, warnings


def spot_check(pilot, hoops, meta, inv):
    """按 pilot 顺序取首/中/尾 3 个有 hoop 的文件，倍率反推格内坐标并裁 patch。"""
    mult = meta["multiplier"]
    cw, ch = meta["cell"]
    order_stems = {s for s in meta["order"] if s}
    candidates = [n for n in pilot if hoops.get(n, {}).get("hoops")]
    picks = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    ok = True
    for i, name in enumerate(picks):
        stem = Path(name).stem
        h = hoops[name]["hoops"][0]
        cx, cy = h["x"] / mult, h["y"] / mult
        tag = f"{stem}[{h['id']}] 原片({h['x']},{h['y']}) → 格内({cx:.1f},{cy:.1f})"
        if stem not in order_stems:
            print(f"  [FAIL] {tag}: 不在 meta.json order 中")
            ok = False
            continue
        if not (0 <= cx <= cw and 0 <= cy <= ch):
            print(f"  [FAIL] {tag}: 超出格范围 {cw}x{ch}")
            ok = False
            continue
        dur = float(inv[name]["duration"])
        frame = CALIB / f"verify_frame_{stem}.jpg"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", f"{dur * SPOT_TS:.3f}", "-i", str(RAW / name),
                            "-map", "0:v:0", "-frames:v", "1",
                            "-vf", f"scale={cw}:{ch}", "-q:v", "2", str(frame)],
                           capture_output=True, text=True)
        if r.returncode != 0 or not frame.exists():
            print(f"  [FAIL] {tag}: 25% 帧抽取失败 {r.stderr.strip()[:120]}")
            ok = False
            continue
        left = min(max(int(cx) - PATCH // 2, 0), cw - PATCH)
        top = min(max(int(cy) - PATCH // 2, 0), ch - PATCH)
        out = CALIB / f"verify_patch_{i}_{stem}.jpg"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(frame),
               "-vf", f"crop={PATCH}:{PATCH}:{left}:{top}", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            print(f"  [FAIL] {tag}: patch 裁切失败 {r.stderr.strip()[:120]}")
            ok = False
            continue
        print(f"  [OK] {tag} → {out.name}（25% 帧，patch 中心应见筐）")
    return ok


def main():
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))["files"]
    hoops = json.loads(HOOPS.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]

    errors, warnings = check_schema(pilot, hoops)
    print(f"schema 校验: {len(pilot)} 文件")
    for w in warnings:
        print(f"  [WARN] {w}")
    for e in errors:
        print(f"  [FAIL] {e}")

    print("倍率反推抽查 3 个 hoop:")
    spot_ok = spot_check(pilot, hoops, meta, inv) if not errors else False

    if errors or not spot_ok:
        print("结果: FAIL")
        return 1
    print(f"结果: PASS（{len(warnings)} 条 warning）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
