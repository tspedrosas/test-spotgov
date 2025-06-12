# Very small helpers that keep main.py clean
from typing import Dict, List

def fmt_standings(rows, league:str, season:str, team_filter:str|None=None):
    """Return pretty CLI table; filter to single team if requested."""
    if team_filter:
        rows = [r for r in rows if r["team"].lower() == team_filter.lower()]
        if not rows:
            return f"{team_filter} not found in {league} {season}."

    header  = f"{league} {season}/{int(season)+1 if season else ''}".strip()
    table_h = "Pos  Club                       P   W   D   L   GD  Pts"
    lines   = [header, table_h]

    for r in rows:
        s = r["stats"]
        lines.append(f"{r['rank']:>2}  "
                     f"{r['team']:<26.26} "
                     f"{s['played']:>2}  {s['win']:>2}  {s['draw']:>2}  "
                     f"{s['lose']:>2}  {r['gd']:>3}  {r['pts']:>3}")
    return "\n".join(lines)


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
