import requests
from config.api_config import FOOTBALL_API_KEY

BASE_URL = "https://v3.football.api-sports.io"

headers = {
    "x-apisports-key": FOOTBALL_API_KEY
}

def get_standings(league, season):
    endpoint = f"{BASE_URL}/standings"
    params = {"league": league, "season": season}
    response = requests.get(endpoint, headers=headers, params=params)
    return response.json()
