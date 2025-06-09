import pytest
from src.api_client import get_standings

def test_get_standings():
    response = get_standings(league=39, season=2023)  # Premier League example
    assert response["response"] is not None
    assert len(response["response"]) > 0
