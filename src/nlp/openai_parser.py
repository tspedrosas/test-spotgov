import json, os, openai, re, logging
from .intent_schema import Intent, Sport, ParsedQuery
from .prompt_sanitizer import is_safe_prompt

SYSTEM_TEMPLATE = """You are a football-statistics assistant.
Return ONLY valid JSON conforming to the following schema:
{{
 "intent": "<one of: {intents}>",
 "sport": "<one of: {sports}>",
 "league_name": "<text|null>",
 "team_a": "<text|null>",
 "team_b": "<text|null>",
 "player_name": "<text|null>",
 "season": "<text|null>",
 "date": "<YYYY-MM-DD|null>",
 "stats_requested": "<list|null>",
 "player_stats_requested": "<list|null>"   // e.g. ["goals","assists"]
 "which": "<next|last|specific|season|null>",
"count": "<int|null>"
}}
Do not wrap the JSON in triple backticks or explanations.
If the user doesn’t mention the league or season
but the teams usually play in a well-known league,
infer the likely league and season.  Example:
User: "chelsea vs man united score 2025-05-16"
Assistant JSON: {{ … "league_name":"Premier League", "season":"2024", … }}.
Recognise the phrases “match facts”, “statistics”, “shots”, “cards”, “subs”
and map them to the stats_requested list with tokens such as
"yellow_cards", "shots_on_goal", "substitutions".
If the user says “all match facts”, leave stats_requested null.
When talking about player stats, map wording like "goals & assists", "yellow card count", "average rating"
to the list ["goals","assists","yellow_cards","rating"].
Use snake_case tokens shown above.
You should always output the original team name, rather than translating it to english.
"""

SYSTEM_TEMPLATE = SYSTEM_TEMPLATE.format(
    intents=", ".join([e.value for e in Intent]),
    sports=", ".join([s.value for s in Sport])
)

FEW_SHOT = [
    # 1. Standings
    {"role": "user", "content": "Show me the Premier League standings for 2024/25."},
    {"role": "assistant", "content": json.dumps({
        "intent":"standings","sport":"football","league_name":"Premier League",
        "team_a":None,"team_b":None,"player_name":None,"season":"2024","date":None
    })},
    # 2. Fixture score by date
    {"role": "user", "content": "What was the score for Chelsea vs Manchester United on 2025-05-16?"},
    {"role": "assistant", "content": json.dumps({
        "intent":"fixture","sport":"football","league_name":"Premier League",
        "team_a":"Chelsea","team_b":"Manchester United",
        "player_name":None,"season":None,"date":"2025-05-16"
    })},
    # 3. Player stats
    {"role": "user", "content": "How many goals did Lionel Messi score in Ligue 1 in 2020?"},
    {"role": "assistant", "content": json.dumps({
        "intent":"player_stats","sport":"football","league_name":"Ligue 1",
        "team_a":None,"team_b":None,"player_name":"Lionel Messi",
        "season":"2020","date":None
    })},
    # 4. Match events
    {"role": "user", "content": "Give me the yellow cards in Real Madrid vs Barcelona on 2024-10-28 in La Liga."},
    {"role": "assistant", "content": json.dumps({
        "intent":"match_events","sport":"football","league_name":"La Liga",
        "team_a":"Real Madrid","team_b":"Barcelona",
        "player_name":None,"season":None,"date":"2024-10-28"
    })},
    # 5. Unsupported sport
    {"role": "user", "content": "Show me NBA standings."},
    {"role": "assistant", "content": json.dumps({
        "intent":"unsupported","sport":"basketball","league_name":None,
        "team_a":None,"team_b":None,"player_name":None,"season":None,"date":None
    })},
    # 23. Unsupported sport => other_sport
    {"role":"user","content":"latest cricket rankings"},
    {"role":"assistant","content": json.dumps({
    "intent":"unsupported","sport":"other"})},

    # 24. Non-sport question => nonsport
    {"role":"user","content":"What's the best pasta recipe?"},
    {"role":"assistant","content": json.dumps({
    "intent":"unsupported","sport":"nonsport"})},
    # 6. Missing league but well-known teams
    {"role":"user","content":"chelsea vs man united score 2025-05-16"},
    {"role":"assistant","content": json.dumps({
        "intent":"fixture","sport":"football",
        "league_name":"Premier League",
        "team_a":"Chelsea","team_b":"Manchester United",
        "player_name":None,"season":"2024","date":"2025-05-16"
    })},
    {"role":"user","content":"Where was Sporting CP in Primeira Liga 2023/24?"},
    {"role":"assistant","content": json.dumps({
        "intent":"standings","sport":"football",
        "league_name":"Primeira Liga","team_a":"Sporting CP",
        "team_b":None,"player_name":None,"season":"2023","date":None
    })},
    # 7. Play-off bracket query
    {"role":"user","content":"Play-off bracket for the 2024/25 Champions League."},
    {"role":"assistant","content": json.dumps({
        "intent":"bracket","sport":"football","league_name":"UEFA Champions League",
        "team_a":None,"team_b":None,"player_name":None,"season":"2024","date":None
    })},
    # 8. Group-stage query without the word "standings"
    {"role": "user", "content": "europa league 21/22 group stage"},
    {"role": "assistant", "content": json.dumps({
        "intent":"standings","sport":"football",
        "league_name":"UEFA Europa League",
        "team_a":None,"team_b":None,"player_name":None,
        "season":"2021","date":None,
        "stage":"group_stage"                   # ← NEW optional field
    })},
    # 9. Knock-out request wording
    {"role":"user","content":"uefa champions league 24/25 knockout stage"},
    {"role":"assistant","content": json.dumps({
        "intent":"bracket","sport":"football",
        "league_name":"UEFA Champions League",
        "team_a":None,"team_b":None,"player_name":None,
        "season":"2024","date":None
    })},
    # 10. Yellow cards only
    {"role":"user","content":"yellow cards only barcelona vs madrid 2024-10-28"},
    {"role":"assistant","content": json.dumps({
        "intent":"match_events","sport":"football","league_name":"La Liga",
        "team_a":"Barcelona","team_b":"Real Madrid","player_name":None,
        "season":None,"date":"2024-10-28",
        "stats_requested":["yellow_cards"]
    })},
    # 11. Yellow cards and substitutions
    {"role":"user","content":"show yellow cards and substitutions for psg bayern 2023-02-14"},
    {"role":"assistant","content": json.dumps({
        "intent":"match_events","sport":"football","league_name":None,
        "team_a":"PSG","team_b":"Bayern Munchen","player_name":None,
        "season":None,"date":"2023-02-14",
        "stats_requested":["yellow_cards","substitutions"]
    })},
    # 12. All match facts
    {"role":"user","content":"give me all match facts chelsea vs arsenal 2024-03-01"},
    {"role":"assistant","content": json.dumps({
        "intent":"match_events","sport":"football","league_name":None,
        "team_a":"Chelsea","team_b":"Arsenal","player_name":None,
        "season":None,"date":"2024-03-01",
        "stats_requested":None
    })},
    # 13. Goals in a season (club-agnostic)
    {"role":"user","content":"Messi goals 2022/23"},
    {"role":"assistant","content": json.dumps({
        "intent":"player_stats","sport":"football","league_name":None,
        "team_a":None,"team_b":None,"player_name":"Lionel Messi",
        "season":"2022","date":None,
        "player_stats_requested":["goals"]
    })},
    # 14. Goals & assists in Premier League 21/22
    {"role":"user","content":"How many goals and assists did Salah get in Premier League 21/22"},
    {"role":"assistant","content": json.dumps({
        "intent":"player_stats","sport":"football","league_name":"Premier League",
        "team_a":None,"team_b":None,"player_name":"Mohamed Salah",
        "season":"2021","date":None,
        "player_stats_requested":["goals","assists"]
    })},
    # 15. All stats
    {"role":"user","content":"show all stats for Haaland 23/24"},
    {"role":"assistant","content": json.dumps({
        "intent":"player_stats","sport":"football","league_name":None,
        "team_a":None,"team_b":None,"player_name":"Erling Haaland",
        "season":"2023","date":None,
        "player_stats_requested":None
    })},
    # 16. Goals across all competitions
    {"role":"user","content":"Messi goals 2022/23"},
    {"role":"assistant","content": json.dumps({
    "intent":"player_stats","sport":"football","league_name":None,
    "team_a":None,"team_b":None,"player_name":"Lionel Messi",
    "season":"2022","date":None,
    "player_stats_requested":["goals"]
    })},
    # Upcoming
    {"role":"user","content":"when do chelsea and arsenal play next?"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":"Premier League",
        "team_a":"Chelsea","team_b":"Arsenal","season":None,"date":None,
        "which":"next","count":None})},

    {"role":"user","content":"last 5 psg bayern matches"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":None,
        "team_a":"PSG","team_b":"Bayern Munich","season":None,"date":None,
        "which":"last","count":5})},

    {"role":"user","content":"sporting and porto past 3 games"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":None,
        "team_a":"Sporting CP","team_b":"FC Porto","season":None,"date":None,
        "which":"last","count":3})},

    # Season + competition
    {"role":"user","content":"show me the benfica vs sporting match for the 2023/24 primeira liga"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":"Primeira Liga",
        "team_a":"Benfica","team_b":"Sporting CP","season":"2023",
        "date":None,"which":"season","count":None})},

    # Specific fixture
    {"role":"user","content":"benfica sporting portuguese league 2025-05-10"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":"Primeira Liga",
        "team_a":"Benfica","team_b":"Sporting CP","season":None,
        "date":"2025-05-10","which":"specific","count":None})},

        # 17. Team next N
    {"role":"user","content":"show me bayern munchen next 5 matches"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":None,
        "team_a":"Bayern Munich","team_b":None,"season":None,"date":None,
        "which":"team_next","count":5})},

    # 18. Team last N with league
    {"role":"user","content":"PSV last 10 Primeira Liga matches"},
    {"role":"assistant","content":json.dumps({
        "intent":"fixture","sport":"football","league_name":"Primeira Liga",
        "team_a":"PSV Eindhoven","team_b":None,"season":None,"date":None,
        "which":"team_last","count":10})},
        # 19. Last N with single team (no 'matches' keyword)
    {"role":"user","content":"last 5 benfica encounters or meetings"},
    {"role":"assistant","content":json.dumps({
    "intent":"fixture","sport":"football","league_name":None,
    "team_a":"Benfica","team_b":None,"season":None,"date":None,
    "which":"team_last","count":5})},


]
# --- model pricing (USD per 1 000 tokens) ---
MODEL_PRICE_PER_1K = 0.0015          # gpt-3.5-turbo-1106 June-2025 public price
LOG_COST = os.getenv("LOG_COST") == "1"

# --------------------------------------------------------------------
# Schema hard-validator (runs after GPT response)
# --------------------------------------------------------------------
_allowed_intents = {e.value for e in Intent}
_allowed_sports  = {s.value for s in Sport}
_allowed_which   = {"next","last","specific","season",
                    "team_next","team_last", "head_to_head"}

def _validate(parsed: dict) -> ParsedQuery | None:
    """
    Return parsed dict if it passes all structural checks,
    else a minimal UNSUPPORTED object.
    """
    try:
        if parsed.get("intent") not in _allowed_intents:
            raise ValueError
        if parsed.get("sport") not in _allowed_sports:
            raise ValueError

        # limit stats_requested & player_stats_requested length
        for key in ("stats_requested", "player_stats_requested"):
            if key in parsed and parsed[key] is not None:
                if not isinstance(parsed[key], list):
                    raise ValueError
                if len(parsed[key]) > 10:
                    raise ValueError

        # which token
        w = parsed.get("which")
        if w and w not in _allowed_which:
            # downgrade to default 'last'
            parsed["which"] = "last"

        return parsed
    except Exception:
        return {"intent": Intent.UNSUPPORTED, "sport": Sport.OTHER}


def parse_user_prompt(prompt: str) -> ParsedQuery | None:
    """High-level NLP entry point"""
    if not is_safe_prompt(prompt):
        return {"intent": Intent.UNSUPPORTED, "sport": Sport.OTHER}

    # Create a client using your API key (from env variable)
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_TEMPLATE}, *FEW_SHOT,
            {"role": "user",   "content": prompt}
        ]
    )

    # cost logging
    if os.getenv("LOG_COST") == "1":
        usage = response.usage                 # Dict with prompt_tokens, completion_tokens, total_tokens
        total_tokens = usage.total_tokens
        cost_usd = (total_tokens / 1000) * MODEL_PRICE_PER_1K
        projected_1k_msg = cost_usd * 1000     # same-size messages

        print(f"[OpenAI] tokens={total_tokens}  cost=${cost_usd:0.5f}  "
            f"(≈ ${projected_1k_msg:0.2f} per 1 000 msgs)")

    raw_json = response.choices[0].message.content
    # Defensive JSON extraction (handles accidental code fences)
    match = re.search(r"\{.*\}", raw_json, re.S)
    data = json.loads(match.group(0)) if match else {}
    return _validate(data)            # <-- NEW

