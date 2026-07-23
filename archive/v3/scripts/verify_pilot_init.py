# Task 1 (v3.1) 验证试点初始化产物：pilot_files.json / goals_v2_archive.json / goals.json
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "work" / "file_inventory.json"
PILOT = ROOT / "work" / "pilot_files.json"
GOALS = ROOT / "goals.json"
ARCHIVE = ROOT / "work" / "goals_v2_archive.json"
PILOT_SIZE = 50
ARCHIVE_GOAL_COUNT = 306
GROUND_TRUTH_SEQ = ["0005", "0006", "0007", "0008", "0009", "0010"]


def main():
    errors = []

    inv = json.loads(INV.read_text(encoding="utf-8"))
    inv_files = set(inv["files"])

    # ① pilot_files.json：恰好 50 个、全部 ∈ inventory、含 ground truth 0005~0010
    if not PILOT.exists():
        errors.append(f"缺少 {PILOT}")
    else:
        pilot = json.loads(PILOT.read_text(encoding="utf-8")).get("files", [])
        if len(pilot) != PILOT_SIZE:
            errors.append(f"pilot_files.json 应有 {PILOT_SIZE} 个文件，实际 {len(pilot)}")
        not_in_inv = [f for f in pilot if f not in inv_files]
        if not_in_inv:
            errors.append(f"pilot 含 inventory 之外的文件: {not_in_inv[:3]}")
        for seq in GROUND_TRUTH_SEQ:
            if not any(f"_{seq}_D" in f for f in pilot):
                errors.append(f"pilot 缺少 ground truth 文件 _{seq}_D")

    # ② 归档存在且含 306 条记录
    if not ARCHIVE.exists():
        errors.append(f"缺少 {ARCHIVE}")
    else:
        arc = json.loads(ARCHIVE.read_text(encoding="utf-8"))
        n = len(arc.get("goals", []))
        if n != ARCHIVE_GOAL_COUNT:
            errors.append(f"归档应有 {ARCHIVE_GOAL_COUNT} 条记录，实际 {n}")

    # ③ goals.json 为 version 3、goals 为空数组
    goals = json.loads(GOALS.read_text(encoding="utf-8"))
    if goals.get("version") != 3:
        errors.append(f"goals.json version 应为 3，实际 {goals.get('version')}")
    if goals.get("goals") != []:
        errors.append(f"goals.json goals 应为空数组，实际 {len(goals.get('goals', []))} 条")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("OK: pilot 50 文件齐全且 ∈ inventory，含 0005~0010；归档 306 条；goals.json 为 v3 空")
    return 0


if __name__ == "__main__":
    sys.exit(main())
