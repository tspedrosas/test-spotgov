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

def fmt_group_table(group_name, rows):
    lines = [f"{group_name}", "Pos Team  P  W  D  L  GD  Pts"]
    for r in rows:
        s = r["stats"]
        lines.append(f"{r['rank']:>2}  "
                    f"{r['team']:<20.20} "
                    f"{s['played']:>2}  {s['win']:>2}  {s['draw']:>2}  "
                    f"{s['lose']:>2}  {r['gd']:>3}  {r['pts']:>3}")
    return "\n".join(lines)

def fmt_bracket(bracket):
    out = []
    for stage, fx in bracket.items():
        if not fx:
            continue                            # skip empty round
        out.append(f"\n{stage.upper()}")
        for f in fx:
            h, a = f["teams"]["home"]["name"], f["teams"]["away"]["name"]
            g = f["goals"]
            out.append(f" {h} {g['home']}–{g['away']} {a}")
    return "\n".join(out) or "No knock-out fixtures found yet."

def fmt_stats(raw_stats: List[Dict]) -> str:
    """
    raw_stats: list of two dicts (home, away) from /fixtures/statistics
    Returns a nice home / away numeric table for requested categories.
    """
    if not raw_stats:
        return "Statistics not available."
    
    home, away = raw_stats
    lines = ["\nTeam                       Home   Away"]
    
    # Get all unique stat types from both teams
    stat_types = set()
    for team_stats in [home["statistics"], away["statistics"]]:
        for stat in team_stats:
            stat_types.add(stat["type"])
    
    # Sort stat types for consistent display
    for stat_type in sorted(stat_types):
        # Find values for both teams
        home_val = next((stat["value"] for stat in home["statistics"] 
                        if stat["type"] == stat_type), "-")
        away_val = next((stat["value"] for stat in away["statistics"] 
                        if stat["type"] == stat_type), "-")
        
        lines.append(f"{stat_type:<25} {str(home_val):>5}  {str(away_val):>5}")
    
    return "\n".join(lines)

def fmt_player_season(stats: Dict, want: list[str]|None, season:str) -> str:
    st = stats["statistics"][0]
    wanted = set(want or ["goals","assists","yellow_cards","red_cards","rating"])
    lines = [f"{stats['player']['name']} – Season {season} ({st['league']['name']})"]

    if "goals" in wanted:
        lines.append(f"Goals: {st['goals']['total'] or 0}")
    if "assists" in wanted:
        lines.append(f"Assists: {st['goals']['assists'] or 0}")
    if "yellow_cards" in wanted:
        lines.append(f"Yellow Cards: {st['cards']['yellow'] or 0}")
    if "red_cards" in wanted:
        lines.append(f"Red Cards: {st['cards']['red'] or 0}")
    if "rating" in wanted:
        lines.append(f"Average Rating: {st['games']['rating'] or 'N/A'}")
    return " | ".join(lines)

def fmt_player_season_multi(resp_list: list, want: list[str]|None, season:str) -> str:
    want = set(want or ["goals","assists","yellow_cards","red_cards","rating"])
    out = []
    for entry in resp_list:
        st = entry["statistics"][0]
        comp = st["league"]["name"]
        line = [f"{comp}:"]
        if "goals" in want:
            line.append(f"Goals {st['goals']['total'] or 0}")
        if "assists" in want:
            line.append(f"Assists {st['goals']['assists'] or 0}")
        if "yellow_cards" in want:
            line.append(f"YC {st['cards']['yellow'] or 0}")
        if "red_cards" in want:
            line.append(f"RC {st['cards']['red'] or 0}")
        if "rating" in want:
            line.append(f"Rating {st['games']['rating'] or 'N/A'}")
        out.append(" | ".join(line))
    header = f"{resp_list[0]['player']['name']} – Season {season}"
    return header + "\n" + "\n".join(out)

def fmt_fixture_row(f):
    h,a = f["teams"]["home"]["name"], f["teams"]["away"]["name"]
    d   = f["fixture"]["date"][:10]
    g   = f["goals"]
    return f"{d}  {h} {g['home']}–{g['away']} {a}"

def fmt_fixture_list(lst, header:str):
    return header + "\n" + "\n".join(fmt_fixture_row(f) for f in lst) \
           if lst else header + "\n( none )"
