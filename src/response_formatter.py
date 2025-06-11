# Very small helpers that keep main.py clean
from typing import Dict, List

def fmt_standings(rows):
    out = ["Pos  Club                     P  W  D  L  GD  Pts"]
    for r in rows:
        s = r["stats"]
        out.append(f"{r['rank']:>2}  {r['team']:<22} "
                   f"{s['played']:^2} {s['win']:^2} {s['draw']:^2} {s['lose']:^2} "
                   f"{r['gd']:^3} {r['pts']:^3}")
    return "\n".join(out)

def fmt_fixture_score(f: Dict) -> str:
    home, away = f["teams"]["home"], f["teams"]["away"]
    g = f["goals"]
    return f"{home['name']} {g['home']}–{g['away']} {away['name']}"

def fmt_events(events: List[Dict]) -> str:
    parts = []
    for e in events:
        minute = e['time']['elapsed']
        team   = e['team']['name']
        player = e['player']['name']
        typ    = e['type']
        detail = e['detail']
        parts.append(f"{minute:>2}′  {team}: {player}  ({typ} – {detail})")
    return "\n".join(parts) or "No notable events."

def fmt_player_stats(p: Dict, season: int) -> str:
    stats = p["statistics"][0]
    goals = stats["goals"]["total"] or 0
    shots = stats["shots"]["total"] or 0
    return (f"{p['player']['name']} – Season {season}\n"
            f"Goals: {goals}  |  Shots: {shots}")
