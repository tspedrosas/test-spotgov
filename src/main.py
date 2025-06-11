import argparse, os, logging
from dotenv import load_dotenv
from src.nlp.openai_parser import parse_user_prompt
from src.nlp.resolver import league_name_to_id, team_name_to_id
from src.api_client import (
    get_standings, get_fixtures, get_match_events, get_player_stats
)
from src.nlp.intent_schema import Intent, Sport

load_dotenv()

def handle_query(user_msg: str):
    parsed = parse_user_prompt(user_msg)
    if parsed["sport"] != Sport.FOOTBALL:
        # graceful sport switch message
        s = parsed["sport"]
        if s in (Sport.BASKETBALL, Sport.RUGBY, Sport.F1):
            return f"Support for {s.value.capitalize()} will be available soon!"
        return "Sorry, that sport isn't supported."

    intent = parsed["intent"]

    if intent == Intent.STANDINGS:
        lg_id = league_name_to_id(parsed["league_name"])
        season = parsed.get("season") or "2023"
        return get_standings(lg_id, season)

    if intent == Intent.FIXTURE:
        lg_id = league_name_to_id(parsed["league_name"])
        a_id  = team_name_to_id(parsed["team_a"], lg_id)
        b_id  = team_name_to_id(parsed["team_b"], lg_id)
        date  = parsed.get("date")

        if a_id and b_id:
            fixtures = get_fixtures(h2h=f"{a_id}-{b_id}",
                                    season=parsed.get("season"))
        else:
            fixtures = get_fixtures(league_id=lg_id,
                                    season=parsed.get("season"),
                                    date=date)

        if date:
            fixtures["response"] = [
                f for f in fixtures["response"]
                if f["fixture"]["date"].startswith(date)
            ]

        if not fixtures["response"]:
            return "No fixture found matching that query."

        f = fixtures["response"][0]
        score = f["goals"]
        home  = f["teams"]["home"]["name"]
        away  = f["teams"]["away"]["name"]
        return f"{home} {score['home']}–{score['away']} {away}"

    if intent == Intent.MATCH_EVENTS:
        # similar …
        pass

    # … handle other intents

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
