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
 "date": "<YYYY-MM-DD|null>"
}}
Do not wrap the JSON in triple backticks or explanations.
If the user doesn’t mention the league or season
but the teams usually play in a well-known league,
infer the likely league and season.  Example:
User: "chelsea vs man united score 2025-05-16"
Assistant JSON: {{ … "league_name":"Premier League", "season":"2024", … }}"""

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
]

# --- model pricing (USD per 1 000 tokens) ---
MODEL_PRICE_PER_1K = 0.0015          # gpt-3.5-turbo-1106 June-2025 public price
LOG_COST = os.getenv("LOG_COST") == "1"

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
    return data
