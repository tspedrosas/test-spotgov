# src/api_client.py
import os
import requests
from typing import Any, Dict, Optional

from config.api_config import FOOTBALL_API_KEY

BASE_URL = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": FOOTBALL_API_KEY}
TIMEOUT  = 8        # seconds – stay well under the 20-s requirement

class ApiError(RuntimeError):
    ...

def _call(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Shared wrapper with basic error handling & timeout."""
    try:
        r = requests.get(
            f"{BASE_URL}/{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=TIMEOUT
        )
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ApiError(f"API-Football error → {exc}") from exc


# ---------------------------  Public helpers  --------------------------- #

def get_standings(league_id: int, season: str | int) -> Dict[str, Any]:
    return _call("standings", {"league": league_id, "season": season})


def get_fixtures(
    league_id: Optional[int] = None,
    season:    Optional[str | int] = None,
    date:      Optional[str] = None,
    h2h:       Optional[str] = None,
    fixture_id: Optional[int] = None,
) -> Dict[str, Any]:
    if fixture_id:
        return _call("fixtures", {"id": fixture_id})

    params: Dict[str, Any] = {}
    if league_id: params["league"] = league_id
    if date:      params["date"]   = date
    if "season" in params and not any(k in params for k in ("league", "team", "id", "h2h")):
        params.pop("season")
    if h2h and "None" not in h2h:   # <-- guard
        params["h2h"] = h2h
        return _call("fixtures/headtohead", params)    
    return _call("fixtures", params)

def get_match_events(fixture_id: int) -> Dict[str, Any]:
    # events, line-ups, stats live under /fixtures?id=<fixture_id>&... endpoints
    return _call("fixtures/events", {"fixture": fixture_id})

def infer_league_from_h2h(team_a_id: int, team_b_id: int) -> int | None:
    resp = _call("fixtures",
                 {"h2h": f"{team_a_id}-{team_b_id}", "last": 1})
    data = resp["response"]
    return data[0]["league"]["id"] if data else None


def get_player_stats(
    player_id: int,
    season: str | int,
    league_id: Optional[int] = None
) -> Dict[str, Any]:
    params = {"id": player_id, "season": season}
    if league_id:
        params["league"] = league_id
    return _call("players", params)
