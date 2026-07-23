# Task 1 (v3.1) 试点初始化：生成试点 50 文件清单，归档旧 goals.json，重置为 version 3
# 幂等：归档已存在则跳过归档步骤；pilot_files.json 每次按 inventory 重算（内容一致）
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "work" / "file_inventory.json"
PILOT = ROOT / "work" / "pilot_files.json"
GOALS = ROOT / "goals.json"
ARCHIVE = ROOT / "work" / "goals_v2_archive.json"
PILOT_SIZE = 50


def main():
    inv = json.loads(INV.read_text(encoding="utf-8"))
    files = sorted(inv["files"])
    pilot = files[:PILOT_SIZE]
    if len(pilot) < PILOT_SIZE:
        print(f"error: inventory 仅 {len(pilot)} 个文件，不足 {PILOT_SIZE}")
        return 1
    PILOT.write_text(json.dumps({"files": pilot}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"pilot_files.json: {len(pilot)} 个文件（{pilot[0]} ~ {pilot[-1]}）")

    goals = json.loads(GOALS.read_text(encoding="utf-8"))
    if goals.get("goals") and not ARCHIVE.exists():
        shutil.copyfile(GOALS, ARCHIVE)
        print(f"已归档 goals.json -> {ARCHIVE.name}（{len(goals['goals'])} 条）")
    elif ARCHIVE.exists():
        print("归档已存在，跳过")
    else:
        print("goals.json 为空，无需归档")

    GOALS.write_text(json.dumps({"version": 3, "goals": []}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print("goals.json 已重置为 version 3（空）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
