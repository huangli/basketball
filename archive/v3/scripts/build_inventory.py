# Task 0.1 实现：扫描 0_raw_videos，逐 MP4 ffprobe，写 work\file_inventory.json
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
OUT = ROOT / "work" / "file_inventory.json"


def detect_encoder():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and any(
            k in out.stdout for k in ("GeForce", "RTX", "Quadro", "Tesla", "GTX")
        ):
            return "h264_nvenc", ["-cq", "20", "-preset", "p5"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "libx264", ["-crf", "20", "-preset", "medium"]


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,avg_frame_rate,pix_fmt",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    p = json.loads(out.stdout)
    st = p["streams"][0]
    num, den = st["avg_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return {
        "codec": st["codec_name"],
        "width": st["width"],
        "height": st["height"],
        "avg_frame_rate": st["avg_frame_rate"],
        "fps": round(fps, 3),
        "pix_fmt": st["pix_fmt"],
        "duration": round(float(p["format"]["duration"]), 3),
    }


def main():
    mp4s = sorted([*RAW.rglob("*.MP4"), *RAW.rglob("*.mp4")])
    lrfs = {p.stem for p in [*RAW.rglob("*.LRF"), *RAW.rglob("*.lrf")]}
    encoder, encoder_params = detect_encoder()

    files = {}
    missing_lrf = []
    errors = []

    def work(path):
        try:
            return path.name, probe(path), None
        except Exception as e:  # noqa: BLE001 - 记录后继续，不中断全量
            return path.name, None, str(e)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for name, info, err in ex.map(work, mp4s):
            if err:
                errors.append({"file": name, "error": err})
                continue
            stem = Path(name).stem
            info["lrf"] = f"{stem}.LRF" if stem in lrfs else None
            if info["lrf"] is None:
                missing_lrf.append(name)
            files[name] = info

    OUT.parent.mkdir(parents=True, exist_ok=True)
    inv = {
        "encoder": encoder,
        "encoder_params": encoder_params,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "raw_dir": "0_raw_videos",
        "file_count": len(files),
        "missing_lrf": sorted(missing_lrf),
        "errors": errors,
        "files": dict(sorted(files.items())),
    }
    OUT.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"encoder={encoder} files={len(files)} missing_lrf={len(missing_lrf)} errors={len(errors)}")
    if errors:
        for e in errors:
            print(f"  ERROR {e['file']}: {e['error']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
