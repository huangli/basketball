# Task 10: 投篮者帧——对 confirmed/attempt 取 anchor 前 3/2/1s 全画帧（scale=1600:1200）
# 一次抽取三合一：认人 + 判 2/3 分 + 判助攻。t<0 跳过。
# 产物: work/roster/raw/<goal_id>_<t>.jpg，goal_id=<stem>_<anchor>
# 用法: python scripts/build_shooter_frames.py | --selftest
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "0_raw_videos"
GJ = ROOT / "goals.json"
RAW_DIR = ROOT / "work" / "roster" / "raw"
OFFSETS = [3, 2, 1]  # anchor 前 3/2/1 秒


def shoot_one(item, out_dir=None):
    """item=(name,anchor)。抽 anchor 前 3/2/1s 帧。out_dir 供自测重定向。返回 (goal_id,status,info)。"""
    name, anchor = item
    stem = Path(name).stem
    goal_id = f"{stem}_{anchor}"
    target = out_dir or RAW_DIR
    if out_dir is None:
        target.mkdir(parents=True, exist_ok=True)
    frames = []
    for off in OFFSETS:
        t = round(anchor - off, 1)
        if t < 0:
            continue
        out = target / f"{goal_id}_{t}.jpg"
        if out.exists():
            frames.append(f"skip@{t}")
            continue
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", f"{t}", "-i", str(RAW / name), "-map", "0:v:0",
               "-frames:v", "1", "-vf", "scale=1600:1200", "-q:v", "3", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return goal_id, "error", f"t={t}: {r.stderr.strip()[:150]}"
        frames.append(str(t))
    return goal_id, "ok", frames


def main():
    gj = json.loads(GJ.read_text(encoding="utf-8"))
    items = [(g["file"], g["anchor_time"]) for g in gj["goals"]
             if g["status"] in ("confirmed", "attempt")
             and g.get("anchor_time") is not None]
    if not items:
        print("无 confirmed/attempt 记录（需 Task 8 先判定）")
        return 0
    results = {"ok": 0, "error": []}
    total_frames = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for goal_id, status, info in ex.map(shoot_one, items):
            if status == "error":
                results["error"].append(f"{goal_id}: {info}")
            else:
                results["ok"] += 1
                total_frames += len(info)
    print(f"ok={results['ok']} error={len(results['error'])} 帧总数={total_frames}")
    for e in results["error"]:
        print(f"  {e}")
    return 1 if results["error"] else 0


def selftest():
    """用真实 0007（anchor=4.5）抽 3 帧（1.5/2.5/3.5）到临时目录，验证命名与张数。"""
    tmpdir = Path(tempfile.mkdtemp())
    name = "DJI_20250419185121_0007_D.MP4"
    if not (RAW / name).exists():
        print("[自测] 跳过：0007 原片不存在")
        return 0
    goal_id, status, frames = shoot_one((name, 4.5), out_dir=tmpdir)
    produced = sorted(p.name for p in tmpdir.glob("*.jpg"))
    expect_names = [f"DJI_20250419185121_0007_D_4.5_{t}.jpg" for t in (1.5, 2.5, 3.5)]
    ok = (status == "ok" and len(frames) == 3
          and produced == sorted(expect_names))
    print(f"[自测] goal_id={goal_id} frames={frames} → {'PASS' if ok else 'FAIL'}")
    print(f"  产出: {produced}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    sys.exit(main())
