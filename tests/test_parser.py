from nlp.openai_parser import parse_user_prompt
from nlp.intent_schema import Intent

def test_basic_standings():
    res = parse_user_prompt("where is Man City in the premier league?")
    assert res["intent"] == Intent.STANDINGS
    assert "Manchester City" in res["team_a"] or "Man City" in res["team_a"]
