# 音频峰值检测（变体B）：找出欢呼时刻 → 指引用户只看峰值附近的接触表
import array
import json
import math
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
INV = ROOT / "work" / "file_inventory.json"
HOOPS = ROOT / "work" / "hoops.json"
OUT = ROOT / "work" / "review"
SAMPLE_RATE = 8000
WINDOW = 0.5
MERGE_DIST = 3.0

PILOT = [
    "DJI_20250419184740_0005_D.MP4",
    "DJI_20250419185047_0006_D.MP4",
    "DJI_20250419185121_0007_D.MP4",
    "DJI_20250419185204_0008_D.MP4",
    "DJI_20250419185252_0009_D.MP4",
    "DJI_20250419185341_0010_D.MP4",
    "DJI_20250419185729_0011_D.MP4",
    "DJI_20250419185747_0012_D.MP4",
    "DJI_20250419185805_0013_D.MP4",
    "DJI_20250419185825_0014_D.MP4",
]


def short_name(name):
    return name.split("_")[2]


def extract_pcm(name):
    tmp = OUT / ("_tmp_" + short_name(name) + ".raw")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(RAW / name), "-vn", "-ac", "1",
           "-ar", str(SAMPLE_RATE), "-f", "s16le", str(tmp)]
    subprocess.run(cmd, check=True)
    data = array.array("h")
    sz = tmp.stat().st_size // 2
    with open(tmp, "rb") as f:
        data.fromfile(f, sz)
    tmp.unlink()
    return data


def find_peaks(data, duration):
    win = int(SAMPLE_RATE * WINDOW)
    n_win = len(data) // win
    if n_win == 0:
        return []
    db = []
    for i in range(n_win):
        chunk = data[i * win:(i + 1) * win]
        s = sum(int(x) * int(x) for x in chunk)
        rms = math.sqrt(s / win)
        db.append(20 * math.log10(rms / 32768 + 1e-10))
    mean_db = sum(db) / len(db)
    std_db = math.sqrt(sum((d - mean_db) ** 2 for d in db) / len(db)) if db else 0
    threshold = mean_db + 1.5 * std_db
    hits = [(i * WINDOW, db[i]) for i in range(n_win) if db[i] > threshold]
    clusters = []
    for t, d in hits:
        if clusters and t - clusters[-1][-1][0] < MERGE_DIST:
            clusters[-1].append((t, d))
        else:
            clusters.append([(t, d)])
    peaks = [max(c, key=lambda x: x[1])[0] for c in clusters]
    return peaks


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inv = json.loads(INV.read_text(encoding="utf-8"))["files"]
    hoops = json.loads(HOOPS.read_text(encoding="utf-8"))
    result = {}
    for name in PILOT:
        if name not in inv:
            continue
        sn = short_name(name)
        dur = float(inv[name]["duration"])
        data = extract_pcm(name)
        peaks = find_peaks(data, dur)
        hoop_ids = [h["id"] for h in hoops.get(name, {}).get("hoops", [])
                    if not h.get("dropped")]
        sheets = sorted(set(int(t // 6) + 1 for t in peaks))
        result[sn] = {
            "file": name, "duration": dur, "peaks": peaks,
            "hoop_ids": hoop_ids,
            "check_sheets": sheets,
        }
    jpath = OUT / "audio_peaks.json"
    jpath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    guide = []
    total_peaks = 0
    total_sheets = 0
    for sn in sorted(result):
        r = result[sn]
        total_peaks += len(r["peaks"])
        total_sheets += len(r["check_sheets"])
        peak_str = ", ".join(str(t) + "s" for t in r["peaks"]) or "(none)"
        sheet_str = ", ".join(str(s) for s in r["check_sheets"]) or "(none)"
        hoops_str = "/".join(r["hoop_ids"])
        guide.append(sn + " | peaks: " + peak_str + " | check sheets: " + sheet_str +
                     " | hoops: " + hoops_str)
    gpath = OUT / "peak_guide.txt"
    gpath.write_text(
        "AUDIO PEAK GUIDE (variant B)\n" +
        "Each sheet covers 6s. Sheet N covers t=" + str(0) + ".." + str(6) +
        "*(N)\n" +
        "=" * 50 + "\n" +
        "\n".join(guide) + "\n" +
        "=" * 50 + "\n" +
        "Total peaks: " + str(total_peaks) + "  Total sheets to check: " +
        str(total_sheets) + "\n", encoding="utf-8")
    print("files=" + str(len(result)) + " peaks=" + str(total_peaks) +
          " sheets_to_check=" + str(total_sheets))
    print("Guide: " + str(gpath))


if __name__ == "__main__":
    sys.exit(main())
