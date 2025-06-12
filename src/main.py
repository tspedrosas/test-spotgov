import argparse, os, logging
from dotenv import load_dotenv
from src.nlp.openai_parser import parse_user_prompt
from src.nlp.resolver import league_name_to_id, team_name_to_id, player_name_to_id
from src.api_client import (get_standings, get_fixtures, get_match_events, get_player_stats, infer_league_from_h2h)
from src.nlp.intent_schema import Intent, Sport
from src.response_formatter import fmt_standings, fmt_fixture_score, fmt_events, fmt_player_stats
from src.nlp.resolver import load_standings_cache, cache_standings
from src.utils import normalize_season

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PENDING: dict | None = None

def handle_query(user_msg: str):
    global PENDING

    # --- Step 0: Was the previous turn waiting for a league? ------------
    if PENDING and PENDING["need"] == "league_for_player":
        # user_msg is assumed to be the league answer
        league_name = user_msg.strip()
        PENDING["parsed"]["league_name"] = league_name
        parsed = PENDING["parsed"]
        PENDING = None
    else:
        parsed = parse_user_prompt(user_msg)

    if parsed["sport"] != Sport.FOOTBALL:
        # graceful sport switch message
        s = parsed["sport"]
        if s in (Sport.BASKETBALL, Sport.RUGBY, Sport.F1):
            return f"Support for {s.capitalize()} will be available soon!"
        return "Sorry, that sport isn't supported."

    intent = parsed["intent"]
    logging.info(f"Detected intent: {intent}")

    if intent == Intent.STANDINGS:
        date  = parsed.get("date")
        lg_id  = league_name_to_id(parsed["league_name"])
        league = parsed["league_name"] or "Unknown League"
        season = normalize_season(parsed.get("season") or current_season_key())

        rows = load_standings_cache(lg_id, season)
        if rows is None:
            api = get_standings(lg_id, season)
            rows = [{
                "rank": e["rank"],
                "team": e["team"]["name"],
                "stats": e["all"],
                "gd":   e["goalsDiff"],
                "pts":  e["points"]
            } for e in api["response"][0]["league"]["standings"][0]]
            cache_standings(lg_id, season, rows)

        # full vs single-team
        return fmt_standings(rows, league, season, team_filter=parsed.get("team_a"))


    if intent == Intent.FIXTURE:
        lg_id = league_name_to_id(parsed["league_name"])
        a_id  = team_name_to_id(parsed["team_a"])
        b_id  = team_name_to_id(parsed["team_b"])
        
        if lg_id is None and a_id and b_id:
            lg_id = infer_league_from_h2h(a_id, b_id)
        
        date  = parsed.get("date")
        season = normalize_season(parsed.get("season"))
        logging.info(f"Requesting fixture for teams: {parsed['team_a']} vs {parsed['team_b']}, date={date}, season={season}")

        if a_id and b_id:
            # Must also send league if we include season
            kwargs = {"h2h": f"{a_id}-{b_id}"}
            if lg_id:    kwargs["league_id"] = lg_id
            if season:   kwargs["season"]    = season
            fixtures = get_fixtures(h2h=f"{a_id}-{b_id}", season=season, date=date)
        else:
            # Fallback: league+date or league+season
            fixtures = get_fixtures(league_id=lg_id, season=season, date=date)
        
        if not fixtures["response"]:
            return "No fixture found matching that query."
        print('fixtures', fixtures)
        f = fixtures["response"][0]
        score = f["goals"]
        home  = f["teams"]["home"]["name"]
        away  = f["teams"]["away"]["name"]
        return f"{home} {score['home']}–{score['away']} {away}"

    if intent == Intent.MATCH_EVENTS:
        lg_id = league_name_to_id(parsed["league_name"])
        a_id  = team_name_to_id(parsed["team_a"])
        b_id  = team_name_to_id(parsed["team_b"])
        if lg_id is None and a_id and b_id:
            lg_id = infer_league_from_h2h(a_id, b_id)
        date  = parsed.get("date")
        season = normalize_season(parsed.get("season"))
        logging.info(f"Requesting match events for teams: {parsed['team_a']} vs {parsed['team_b']}, date={date}, season={season}")
        fx    = get_fixtures(h2h=f"{a_id}-{b_id}", season=season)
        if date:
            fx["response"] = [f for f in fx["response"]
                            if f["fixture"]["date"].startswith(date)]
        if not fx["response"]:
            return "No such fixture."
        fixture_id = fx["response"][0]["fixture"]["id"]
        ev  = get_match_events(fixture_id)
        events = ev["response"]
        return fmt_events(events)

    if intent == Intent.PLAYER_STATS:
        league_name = parsed.get("league_name")
        season = normalize_season(parsed.get("season"))
        player = parsed.get("player_name")

        # 1. if league missing ➜ ask and store context
        if league_name is None:
            PENDING = {"need": "league_for_player", "parsed": parsed}
            return f"Which competition are you talking about?"

        # 2. proceed as before
        lg_id  = league_name_to_id(league_name)
        pl_id  = player_name_to_id(player, lg_id, season)
        if not pl_id:
            return f"I couldn’t find player '{player}'."

        stats = get_player_stats(pl_id, season, lg_id)
        if not stats["response"]:
            return f"No stats found for {player} in {league_name} {season}/{int(season)+1}."
        return fmt_player_stats(stats["response"][0], season)

    return "I didn't understand that request."


def cli():
    print("⚽  Football Chatbot (Type 'quit' to exit)")
    while True:
        q = input("> ")
        if q.lower() in ("quit", "exit"):
            break
        print(handle_query(q))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Football chatbot CLI")
    parser.add_argument("-cost", action="store_true",
                        help="Print OpenAI token-cost info per query")
    args = parser.parse_args()

    if args.cost:
        # a simple env flag the parser module can check
        os.environ["LOG_COST"] = "1"

    cli()
