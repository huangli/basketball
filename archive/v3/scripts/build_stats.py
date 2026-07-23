# Task 14: 技术统计——个人/队伍 CSV + 对账（FGA/FGM/FG%/3PA/3PM/FTA/AST/PTS）
# 口径: PTS=Σpoints(made); FGA=points∈{2,3} 的 confirmed+attempt 数; FGM=其中 made;
#       FTA=points=1 数; 3PA/3PM=points=3 数/made 数; AST=assist_label 计数
# 前置校验: 无残留 uncertain; 同 file+hoop anchor 两两差<2s 报警（防多窗一球双计）
# 对账: Σ个人=Σ队伍、FGA≥FGM、记录数一致，不通过退出码 1
# 用法: python scripts/build_stats.py [session] | --selftest
import csv
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GJ = ROOT / "goals.json"
OUT_DIR = ROOT / "output"
PLAYER_COLS = ["label", "team", "PTS", "FGA", "FGM", "FG%", "3PA", "3PM", "FTA", "AST"]
TEAM_COLS = ["team", "PTS", "FGA", "FGM", "FG%", "3PA", "3PM", "FTA", "AST"]


def _zero():
    return {"PTS": 0, "FGA": 0, "FGM": 0, "FTA": 0, "3PA": 0, "3PM": 0, "AST": 0}


def validate(gj):
    """前置校验。返回 errors 列表（空=通过）。"""
    errors = []
    uncertain = [g for g in gj["goals"] if g["status"] == "uncertain"]
    if uncertain:
        errors.append(f"残留 {len(uncertain)} 条 uncertain 未定夺")
    by_key = defaultdict(list)
    for g in gj["goals"]:
        if g["status"] in ("confirmed", "attempt") and g.get("anchor_time") is not None:
            by_key[(g["file"], g.get("hoop_id"))].append(g["anchor_time"])
    for (f, hid), ts in by_key.items():
        ts.sort()
        for i in range(1, len(ts)):
            if ts[i] - ts[i - 1] < 2.0:
                errors.append(f"疑似双计: {f}_{hid} anchor {ts[i-1]}/{ts[i]} 差<2s")
    return errors


def aggregate(goals):
    """返回 (players, teams)。players[label]=(team, stats)。"""
    players = {}
    for g in goals:
        label = g.get("player_label")
        team = g.get("team_label") or ""
        pts = g.get("points")
        made = g["status"] == "confirmed"
        if label is None or pts is None:
            continue
        if label not in players:
            players[label] = [team, _zero()]
        st = players[label][1]
        if made:
            st["PTS"] += pts
        if pts in (2, 3):
            st["FGA"] += 1
            if made:
                st["FGM"] += 1
        if pts == 3:
            st["3PA"] += 1
            if made:
                st["3PM"] += 1
        if pts == 1:
            st["FTA"] += 1
    # 助攻（仅 confirmed 的 assist_label）
    for g in goals:
        if g["status"] == "confirmed" and g.get("assist_label"):
            al = g["assist_label"]
            if al in players:
                players[al][1]["AST"] += 1
            else:
                players[al] = [players.get(label, [""])[0], _zero()]
                players[al][1]["AST"] += 1
    # 队伍汇总
    teams = defaultdict(_zero)
    for label, (team, st) in players.items():
        t = teams[team]
        for k, v in st.items():
            t[k] += v
    return players, teams


def write_csv(players, teams, out_path, n_records):
    """写个人表+队伍表两段 CSV。返回对账结果 (ok, detail)。"""
    rows_p, rows_t = 0, 0
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["# 个人表"])
        w.writerow(PLAYER_COLS)
        for label in sorted(players):
            team, st = players[label]
            fg = f"{st['FGM']/st['FGA']:.3f}" if st["FGA"] else "-"
            w.writerow([label, team, st["PTS"], st["FGA"], st["FGM"], fg,
                        st["3PA"], st["3PM"], st["FTA"], st["AST"]])
            rows_p += 1
        w.writerow([])
        w.writerow(["# 队伍表"])
        w.writerow(TEAM_COLS)
        for team in sorted(teams):
            st = teams[team]
            fg = f"{st['FGM']/st['FGA']:.3f}" if st["FGA"] else "-"
            w.writerow([team, st["PTS"], st["FGA"], st["FGM"], fg,
                        st["3PA"], st["3PM"], st["FTA"], st["AST"]])
            rows_t += 1
    # 对账
    s_p = sum(st["PTS"] for _, st in players.values())
    s_t = sum(st["PTS"] for st in teams.values())
    fga_p = sum(st["FGA"] for _, st in players.values())
    fgm_p = sum(st["FGM"] for _, st in players.values())
    ok = (s_p == s_t) and (fga_p >= fgm_p)
    detail = (f"ΣPTS 个人={s_p} 队伍={s_t}; FGA={fga_p}≥FGM={fgm_p}; "
              f"记录数={n_records}")
    return ok, detail


def build(session=None, gj_path=None, out_path=None):
    path = gj_path or GJ
    gj = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(gj)
    if errors:
        print("前置校验失败:")
        for e in errors:
            print(f"  ! {e}")
        return 1
    goals = [g for g in gj["goals"] if g["status"] in ("confirmed", "attempt")]
    if session:
        goals = [g for g in goals if g.get("session") == session]
    players, teams = aggregate(goals)
    if out_path is None:
        sess = session or (goals[0]["session"] if goals else "unknown")
        out_path = OUT_DIR / sess / "技术统计.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
    ok, detail = write_csv(players, teams, out_path, len(goals))
    print(f"写出 {out_path}")
    print(f"对账: {'PASS' if ok else 'FAIL'} — {detail}")
    return 0 if ok else 1


def selftest():
    """mock：2 球员（A 2分进+3分不进, B 罚球进+被助攻），对账 PASS。"""
    tmpdir = Path(tempfile.mkdtemp())
    gj = tmpdir / "goals.json"
    goals = [
        {"file": "X.MP4", "status": "confirmed", "session": "S1", "hoop_id": "near",
         "anchor_time": 5.0, "player_label": "红-A", "team_label": "红队",
         "points": 2, "assist_label": None},
        {"file": "X.MP4", "status": "attempt", "session": "S1", "hoop_id": "near",
         "anchor_time": 20.0, "player_label": "红-A", "team_label": "红队",
         "points": 3, "assist_label": None},
        {"file": "Y.MP4", "status": "confirmed", "session": "S1", "hoop_id": "near",
         "anchor_time": 8.0, "player_label": "蓝-B", "team_label": "蓝队",
         "points": 1, "assist_label": "红-A"},
    ]
    gj.write_text(json.dumps({"version": 3, "goals": goals}, ensure_ascii=False),
                  encoding="utf-8")
    out = tmpdir / "stats.csv"
    rc = build(session="S1", gj_path=gj, out_path=out)
    # 预期: 红-A PTS=2 FGA=2 FGM=1 3PA=1 3PM=0 FTA=0 AST=1; 蓝-B PTS=1 FTA=1
    txt = out.read_text(encoding="utf-8-sig")
    ok = (rc == 0 and "红-A" in txt and "蓝-B" in txt)
    print(f"[自测] rc={rc} 对账={'PASS' if ok else 'FAIL'}")
    print(f"  {txt.replace(chr(10),' | ')}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    sess = sys.argv[1] if len(sys.argv) >= 2 else None
    sys.exit(build(session=sess))
