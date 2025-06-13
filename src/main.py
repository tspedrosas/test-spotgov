import argparse, os, logging
from dotenv import load_dotenv
from src.nlp.openai_parser import parse_user_prompt
from src.nlp.resolver import league_name_to_id, team_name_to_id, player_name_to_id
from src.api_client import (get_standings, get_fixtures, get_match_events, get_player_stats, infer_league_from_h2h, fetch_uefa_standings, fetch_uefa_bracket, final_ranks_from_bracket, is_league_phase_format, get_fixture_statistics)
from src.nlp.intent_schema import Intent, Sport
from src.response_formatter import fmt_standings, fmt_fixture_score, fmt_events, fmt_player_stats, fmt_group_table, fmt_bracket, fmt_stats, fmt_player_season, fmt_fixture_row, fmt_fixture_list
from src.nlp.resolver import load_standings_cache, cache_standings
from src.utils import normalize_season, SUPPORTED_LEAGUES_IDS, UEFA_IDS, SUPPORTED_LEAGUES, ordinal, convert, pull_and_cache_domestic_table, deduce_season_from_date, standardize_date
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Dict, Any, Optional, List, Tuple

load_dotenv()

PENDING: dict | None = None

SUPPORTED_LEAGUES_LC = {l.lower(): l for l in SUPPORTED_LEAGUES}

console = Console()

def print_welcome():
    """Print a welcome message and explain the chatbot's capabilities."""
    welcome_text = """
    [bold blue]Welcome to the Football Information Chatbot![/bold blue]
    
    I can help you with various football-related queries. Here's what I can do:
    
    [bold]League Information:[/bold]
    • Show league standings
    • Display upcoming fixtures
    • Show past results
    
    [bold]Match Details:[/bold]
    • Get match events and statistics
    • View head-to-head records
    • Check team form
    
    [bold]Player Statistics:[/bold]
    • View player performance
    • Check goal scorers
    • Get assist leaders
    
    [bold]UEFA Competitions:[/bold]
    • Champions League standings
    • Conference League results
    
    [bold]Examples:[/bold]
    • "Show me the Premier League standings"
    • "What are the next 5 Benfica matches?"
    • "Show me the last 3 games between Real Madrid and Barcelona"
    • "What were the events in the last Manchester United Chelsea match?"
    • "Show me Haaland's stats for the 23/24 season"
    
    Type 'exit' or 'quit' to end the session.
    """
    
    console.print(Panel(welcome_text, title="[bold green]Football Chatbot[/bold green]", border_style="blue"))
    console.print("\n")

def print_help():
    """Print help information."""
    help_text = """
    [bold]Available Commands:[/bold]
    
    [bold]League Queries:[/bold]
    • "standings [league]" - Show league standings
    • "next [team] [n]" - Show next n matches for a team
    • "last [team] [n]" - Show last n matches for a team
    • "h2h [team1] vs [team2]" - Show head-to-head record
    
    [bold]Match Queries:[/bold]
    • "match [team1] vs [team2] [date]" - Show specific match
    • "events [team1] vs [team2] [date]" - Show match events
    • "stats [team1] vs [team2] [date]" - Show match statistics
    
    [bold]Player Queries:[/bold]
    • "player [name] [league] [season]" - Show player statistics
    • "top scorers [league] [season]" - Show top goal scorers
    • "top assists [league] [season]" - Show top assist providers
    
    [bold]UEFA Queries:[/bold]
    • "ucl standings" - Show Champions League standings
    • "europa standings" - Show Europa League standings
    • "conference standings" - Show Conference League standings
    • "ucl bracket" - Show Champions League bracket
    """
    
    console.print(Panel(help_text, title="[bold green]Help[/bold green]", border_style="blue"))
    console.print("\n")

def format_response(response: str, title: Optional[str] = None) -> None:
    """Format and print the response with a title if provided."""
    if title:
        console.print(Panel(response, title=f"[bold green]{title}[/bold green]", border_style="blue"))
    else:
        console.print(response)
    console.print("\n")

def ask_for_league(parsed):
    """Stores context and returns the clarification question."""
    global PENDING
    PENDING = {"need": "league", "intent": parsed["intent"], "parsed": parsed}
    return ("League not recognised.\nSupported leagues: "
            f"{', '.join(SUPPORTED_LEAGUES)}.\n"
            "Which league were you referring to?")

def league_not_supported_msg(name: str) -> str:
    leagues_str = ", ".join(x.title() for x in SUPPORTED_LEAGUES)
    return (f"Sorry, '{name}' is not currently supported.\n"
            f"Supported leagues: {leagues_str}.")

def handle_query(user_msg: str):
    global PENDING

    # ---------- 1. Parse and validate input -------------------
    parsed, intent = _parse_input(user_msg)
    if isinstance(parsed, str):  # Error message
        return parsed

    # ---------- 2. Extract common parameters -----------------
    league_name = parsed["league_name"]    
    lg_id = league_name_to_id(league_name) if league_name else None
    date = parsed.get("date")
    
    # Standardize date if present
    if date:
        standardized_date = standardize_date(date)
        if not standardized_date:
            return "Invalid date format. Please use a valid date format (e.g., DD-MM-YYYY, YYYY-MM-DD)."
        parsed["date"] = standardized_date
    
    # Determine season
    season = deduce_season_from_date(date) if date else normalize_season(parsed.get("season"))
    if season is None:
        season = "2024"  # Default to current season
    season_i = int(season)

    # ---------- 3. Handle different intents -----------------
    intent_handlers = {
        Intent.BRACKET: lambda: _handle_bracket(parsed, lg_id, season_i),
        Intent.STANDINGS: lambda: _handle_standings(parsed, lg_id, season_i),
        Intent.FIXTURE: lambda: _handle_fixture(parsed, lg_id, season_i, date),
        Intent.MATCH_EVENTS: lambda: _handle_match_events(parsed, lg_id, season_i, date),
        Intent.PLAYER_STATS: lambda: _handle_player_stats(parsed, lg_id, season_i)
    }

    handler = intent_handlers.get(intent)
    if handler:
        return handler()
    
    return "I didn't understand that request."

def _parse_input(user_msg: str) -> tuple[dict | str, Intent | None]:
    """Parse user input and return parsed data or error message."""
    global PENDING

    if PENDING and PENDING["need"] == "league":
        league_name = user_msg.strip()
        if league_name.lower() not in SUPPORTED_LEAGUES_LC:
            return league_not_supported_msg(league_name), None

        parsed = PENDING["parsed"]
        parsed["league_name"] = SUPPORTED_LEAGUES_LC[league_name.lower()]
        intent = PENDING["intent"]
        PENDING = None
    else:
        parsed = parse_user_prompt(user_msg)
        intent = parsed["intent"]

    if parsed["sport"] != Sport.FOOTBALL:
        s = parsed["sport"]

        # a) roadmap sports -------------------------------------------------
        if s in (Sport.BASKETBALL, Sport.RUGBY, Sport.F1):
            return (f"Support for {s.capitalize()} will be available soon!", None)

        # b) known-but-unsupported sports -----------------------------------
        if s == Sport.OTHER:          # e.g., tennis, cricket
            return ("Sorry, that sport isn't available yet.", None)

        # c) not a sport at all ---------------------------------------------
        return ("I am a SPORTS chatbot! I answer questions about football, "
                "and soon basketball, rugby and Formula-1. "
                "Your question seems to be outside that scope.", None)

    return parsed, intent

def _handle_bracket(parsed: dict, lg_id: int | None, season: int) -> str:
    """Handle bracket-related queries."""
    if parsed["league_name"] is None:
        return ask_for_league(parsed)

    if lg_id not in SUPPORTED_LEAGUES_IDS:
        return league_not_supported_msg(parsed["league_name"])

    if lg_id not in UEFA_IDS:
        return "Bracket queries currently supported only for UEFA competitions."

    bracket = fetch_uefa_bracket(lg_id, season)
    return fmt_bracket(bracket)

def _handle_standings(parsed: dict, lg_id: int | None, season: int) -> str:
    """Handle standings-related queries."""
    if lg_id is None:
        return ask_for_league(parsed)

    if lg_id not in SUPPORTED_LEAGUES_IDS:
        return league_not_supported_msg(parsed["league_name"])

    # Fetch standings data
    res = fetch_uefa_standings(lg_id, season) if lg_id in UEFA_IDS else None

    if res is None:  # domestic league
        rows = load_standings_cache(lg_id, season)
        if rows is None:
            rows = pull_and_cache_domestic_table(lg_id, season)
    else:
        if res["phase"] == "league":
            rows = [convert(row) for row in res["table"]]
        else:  # group phase
            rows_by_group = {g: [convert(t) for t in group_rows] for g, group_rows in res["groups"].items()}

    # Handle single team query
    team_filter = parsed.get("team_a")
    if team_filter:
        if lg_id in UEFA_IDS and not is_league_phase_format(season):
            rank_map = final_ranks_from_bracket(fetch_uefa_bracket(lg_id, season))
            rank = rank_map.get(team_filter)
        else:
            rows_flat = rows if isinstance(rows, list) else sum(rows_by_group.values(), [])
            match = next((r for r in rows_flat if r["team"].lower() == team_filter.lower()), None)
            rank = match["rank"] if match else None

        if rank is None:
            return f"{team_filter} not found in {parsed['league_name']} {season}/{season+1}."
        return f"{team_filter} finished {ordinal(rank)} in {parsed['league_name']} {season}/{season+1}."

    # Format full standings
    header = f"{parsed['league_name']} {season}/{season+1}"
    if lg_id in UEFA_IDS and not is_league_phase_format(season):
        sections = [header]
        for grp_name, grp_rows in rows_by_group.items():
            sections.append(fmt_group_table(grp_name, grp_rows))
        return "\n\n".join(sections)
    else:
        return fmt_standings(rows, parsed['league_name'], str(season), team_filter=None)

def _handle_fixture(parsed: dict, lg_id: int | None, season: int, date: str | None) -> str:
    """Handle fixture-related queries."""
    which = parsed.get("which") or "specific"
    count = parsed.get("count") or 1
    team_a = parsed.get("team_a")
    team_b = parsed.get("team_b")
    
    a_id = team_name_to_id(team_a) if team_a else None
    b_id = team_name_to_id(team_b) if team_b else None

    # Auto-upgrade and canonicalize query type
    if which in ("last", "next") and not team_b:
        which = "team_" + which

    ALLOWED = {"next", "last", "specific", "season", "team_next", "team_last"}
    if which not in ALLOWED:
        which = "team_last" if "last" in which else "team_next" if not team_b else "last" if "last" in which else "next"

    # Handle team-specific queries
    if which in ("team_next", "team_last"):
        if not a_id:
            return "I need the team name."
        if parsed["league_name"] and not lg_id:
            return ask_for_league(parsed)

        lst = get_fixtures(
            team_id=a_id,
            league_id=lg_id,
            last=count if which == "team_last" else None,
            next=count if which == "team_next" else None,
        )["response"]

        header = (f"Next {count} " if which=="team_next" else f"Last {count} ") \
                + (parsed["league_name"]+" " if lg_id else "") \
                + f"matches for {team_a}"
        return fmt_fixture_list(lst, header)

    # Handle head-to-head queries
    if not lg_id and a_id and b_id:
        lg_id = infer_league_from_h2h(a_id, b_id)
    if which in ("season", "specific") and not lg_id:
        return ask_for_league(parsed)

    if which == "next":
        fixtures = get_fixtures(h2h=f"{a_id}-{b_id}", league_id=lg_id, next=1)
        return fmt_fixture_list(fixtures["response"], f"Next {team_a} vs {team_b}")

    if which == "last":
        fixtures = get_fixtures(h2h=f"{a_id}-{b_id}", league_id=lg_id, last=count)
        return fmt_fixture_list(fixtures["response"], f"Last {count} meetings")

    if which == "season":
        fixtures = get_fixtures(h2h=f"{a_id}-{b_id}", league_id=lg_id, season=season, last=20)
        return fmt_fixture_list(fixtures["response"], f"{team_a} vs {team_b} – Season {season}")

    # Handle specific fixture by date
    fixtures = get_fixtures(h2h=f"{a_id}-{b_id}", league_id=lg_id, season=season)
    lst = [f for f in fixtures["response"] if f["fixture"]["date"].startswith(date)] if date else fixtures["response"]
    if not lst:
        return "No fixture found matching that query."
    return fmt_fixture_row(lst[0])

def _handle_match_events(parsed: dict, lg_id: int | None, season: int, date: str | None) -> str:
    """Handle match events queries."""
    a_id = team_name_to_id(parsed["team_a"])
    b_id = team_name_to_id(parsed["team_b"])
    
    if not lg_id and a_id and b_id:
        lg_id = infer_league_from_h2h(a_id, b_id)
    if not lg_id and not (a_id and b_id):
        return ask_for_league(parsed)

    # Locate fixture
    fx = get_fixtures(h2h=f"{a_id}-{b_id}", season=season)
    if date:
        fx["response"] = [f for f in fx["response"] if f["fixture"]["date"].startswith(date)]
    if not fx["response"]:
        return "No such fixture."
    
    fixture_id = fx["response"][0]["fixture"]["id"]
    want = [w.lower() for w in (parsed.get("stats_requested") or [])]

    # Get events
    raw_events = get_match_events(fixture_id)["response"]
    EVENT_MAP = {
        "yellow_cards": lambda e: e["type"]=="Card" and e["detail"].startswith("Yellow"),
        "red_cards": lambda e: e["type"]=="Card" and e["detail"].startswith("Red"),
        "substitutions": lambda e: e["type"]=="subst",
        "goals": lambda e: e["type"]=="Goal",
    }

    selected_events = raw_events
    if want:
        selected_events = [e for e in raw_events if any(EVENT_MAP.get(w, lambda x: False)(e) for w in want)]

    out_parts = []
    if not want or any(w in EVENT_MAP for w in want):
        out_parts.append(fmt_events(selected_events))

    # Get statistics if requested
    NUMERIC_MAP = {
        "shots_on_goal": "Shots on Goal",
        "shots_off_goal": "Shots off Goal",
        "shots_insidebox": "Shots insidebox",
        "shots_outsidebox": "Shots outsidebox",
        "total_shots": "Total Shots",
        "blocked_shots": "Blocked Shots",
        "fouls": "Fouls",
        "corner_kicks": "Corner Kicks",
        "offsides": "Offsides",
        "ball_possession": "Ball Possession",
        "goalkeeper_saves": "Goalkeeper Saves",
        "total_passes": "Total passes",
        "passes_accurate": "Passes accurate",
        "passes_percent": "Passes %",
    }

    numeric_requested = [w for w in want if w in NUMERIC_MAP] if want else NUMERIC_MAP.keys()
    if numeric_requested:
        stats_raw = get_fixture_statistics(fixture_id)["response"]
        out_parts.append(fmt_stats(stats_raw))

    return "\n\n".join(p for p in out_parts if p.strip())

def _handle_player_stats(parsed: dict, lg_id: int | None, season: int) -> str:
    """Handle player statistics queries."""
    player = parsed.get("player_name")
    if player and len(player.split()) > 1:
        player = player.split()[1]

    if not lg_id or parsed["league_name"] == 'Unknown League':
        return ask_for_league(parsed)

    if lg_id not in SUPPORTED_LEAGUES_IDS:
        return league_not_supported_msg(parsed["league_name"])

    pl_id = player_name_to_id(player, lg_id, season)
    if not pl_id:
        return f"I couldn't find player '{parsed['player_name']}'."

    raw = get_player_stats(pl_id, season, lg_id)
    if not raw["response"]:
        return "No stats available for that query."

    want = parsed.get("player_stats_requested")
    return fmt_player_season(raw["response"][0], want, season)

def main():
    """Main function to run the chatbot."""
    print_welcome()
    
    while True:
        try:
            # Get user input with rich prompt
            message = Prompt.ask("[bold blue]You[/bold blue]")
            
            # Handle exit commands
            if message.lower() in ['exit', 'quit', 'bye']:
                console.print("[bold green]Goodbye! Thanks for using the Football Chatbot![/bold green]")
                break
            
            # Handle help command
            if message.lower() == 'help':
                print_help()
                continue
            
            # Process the query
            response = handle_query(message)
            format_response(response)
            
        except KeyboardInterrupt:
            console.print("\n[bold green]Goodbye! Thanks for using the Football Chatbot![/bold green]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Football chatbot CLI")
    parser.add_argument("-cost", action="store_true",
                        help="Print OpenAI token-cost info per query")
    args = parser.parse_args()

    if args.cost:
        # a simple env flag the parser module can check
        os.environ["LOG_COST"] = "1"

    main()
