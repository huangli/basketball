# Task 6: 音频峰值——ebur128 解析逐秒响度，标定阈值，产 work/audio_peaks.json
# ebur128 每 0.1s 输出: t / M(momentary loudness LUFS) / FTPK(逐块 true peak dBFS) / TPK(累积)
# 欢呼是持续能量 → 主指标用 M（FTPK 易被单次拍手/撞击触发假阳，作备查）。
# 用法:
#   python scripts/build_audio_peaks.py probe <file>          # 打印该文件逐秒 M/FTPK 分布，供标定阈值
#   python scripts/build_audio_peaks.py run --threshold <dB>   # 全量按 M 阈值筛峰、3s 合并取峰尖，产 json
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
PILOT = ROOT / "work" / "pilot_files.json"
INV = ROOT / "work" / "file_inventory.json"
OUT = ROOT / "work" / "audio_peaks.json"

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
RE_T = re.compile(r"t:\s*([0-9.]+)")
RE_M = re.compile(r"M:\s*(-?[0-9.]+)\s+S:")
RE_FTPK = re.compile(r"FTPK:\s*(-?[0-9.]+)\s")
MERGE_GAP = 3.0  # 相邻峰 <3s 合并


def parse_ebur128(path):
    """跑 ebur128，返回 [(t, M, ftpk)] 每 0.1s 一条。M/ftpk 静音记 -120.0。"""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
           "-af", "ebur128=peak=true", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    rows = []
    for line in r.stderr.splitlines():
        line = ANSI.sub("", line)
        if "Parsed_ebur128" not in line or "Summary" in line:
            continue
        mt = RE_T.search(line)
        mm = RE_M.search(line)
        if not (mt and mm):
            continue
        t = float(mt.group(1))
        m = float(mm.group(1))
        mf = RE_FTPK.search(line)
        ftpk = float(mf.group(1)) if mf else -120.0
        rows.append((t, m, ftpk))
    return rows


def per_second(rows):
    """按 1s 桶聚合。返回 {sec:(max_M, max_FTPK, t_at_maxM)}。"""
    buckets = {}
    for t, m, ftpk in rows:
        sec = int(t)
        cur = buckets.get(sec)
        if cur is None or m > cur[0]:
            buckets[sec] = (m, ftpk if cur is None else max(ftpk, cur[1]), t)
        else:
            buckets[sec] = (cur[0], max(ftpk, cur[1]), cur[2])
    return buckets


def detect_peaks(buckets, threshold):
    """按 M 阈值筛秒，<MERGE_GAP 相邻合并，每组取 M 最大的 t 为峰尖。返回 [t,...]。"""
    peak_secs = sorted(s for s, (m, _f, _t) in buckets.items() if m >= threshold)
    out = []
    group = []
    for s in peak_secs:
        if group and s - group[-1] > MERGE_GAP:
            out.append(_peak_tip(group, buckets))
            group = []
        group.append(s)
    if group:
        out.append(_peak_tip(group, buckets))
    return out


def _peak_tip(group, buckets):
    best = max(group, key=lambda s: buckets[s][0])
    return round(buckets[best][2], 1)


def cmd_probe(args):
    name = args.file
    if not name.endswith(".MP4"):
        name = name + ".MP4"
    path = RAW / name
    if not path.exists():
        print(f"文件不存在: {path}")
        return 1
    rows = parse_ebur128(path)
    buckets = per_second(rows)
    print(f"# {name}  逐秒 M(momentary loudness LUFS) / FTPK(true peak dBFS)")
    print(f"{'sec':>4} {'M':>8} {'FTPK':>8}")
    max_m = max((m for m, _f, _t in buckets.values()), default=-120.0)
    for sec in sorted(buckets):
        m, ftpk, _t = buckets[sec]
        mark = "  <== 目标窗(0007@4.5)" if name.startswith("DJI_20250419185121_0007") and 2.5 <= sec <= 6.5 else ""
        print(f"{sec:>4} {m:>8.1f} {ftpk:>8.1f}{mark}")
    print(f"\n全段 max M = {max_m:.1f} LUFS")
    return 0


def scan_one(name):
    path = RAW / name
    if not path.exists():
        return name, []
    rows = parse_ebur128(path)
    buckets = per_second(rows)
    return name, detect_peaks(buckets, args_threshold_holder["thr"])


args_threshold_holder = {"thr": -23.0}


def cmd_run(args):
    args_threshold_holder["thr"] = args.threshold
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))["files"]
    files = {name: [] for name in pilot}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, peaks in ex.map(scan_one, pilot):
            files[name] = peaks
    doc = {"metric": "M_momentary_loudness_LUFS", "threshold": args.threshold,
           "merge_gap_s": MERGE_GAP,
           "calibration": "0007@4.5s 已知进球应有峰（见 probe 输出）",
           "files": files}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in files.values())
    nonzero = sum(1 for v in files.values() if v)
    print(f"threshold={args.threshold} 文件数={len(files)} 有峰文件={nonzero} 峰总数={total}")
    print(f"0007 峰: {files.get('DJI_20250419185121_0007_D.MP4')}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_probe = sub.add_parser("probe")
    p_probe.add_argument("file")
    p_run = sub.add_parser("run")
    p_run.add_argument("--threshold", type=float, required=True)
    args = ap.parse_args()
    if args.cmd == "probe":
        return cmd_probe(args)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
