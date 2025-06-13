# src/api_client.py
import os
import requests
from typing import Any, Dict, Optional, List
from functools import lru_cache
import time

from config.api_config import FOOTBALL_API_KEY

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": FOOTBALL_API_KEY}
TIMEOUT = 10  # seconds

class ApiError(Exception):
    """Custom exception for API-related errors."""
    pass

def _call(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shared wrapper for API calls with error handling, rate limiting, and timeout.
    
    Args:
        endpoint: API endpoint to call
        params: Query parameters
        
    Returns:
        API response as dictionary
        
    Raises:
        ApiError: If the API call fails
    """
    try:
        r = requests.get(
            f"{BASE_URL}/{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=TIMEOUT
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        if r.status_code == 429:  # Rate limit exceeded
            raise ApiError("API rate limit exceeded. Please try again in a minute.") from exc
        elif r.status_code == 404:
            raise ApiError("The requested data was not found.") from exc
        elif r.status_code >= 500:
            raise ApiError("The API server is currently unavailable. Please try again later.") from exc
        else:
            raise ApiError(f"API error: {exc}") from exc
    except ValueError as exc:
        raise ApiError(f"Invalid response from API: {exc}") from exc


# ---------------------------  Public helpers  --------------------------- #

def is_league_phase_format(season: int) -> bool:
    """
    Check if the season uses the league phase format.
    
    Args:
        season: Season year
        
    Returns:
        True if using league phase format, False otherwise
    """
    return season >= 2024

@lru_cache(maxsize=128)
def get_standings(league_id: int, season: int) -> Dict[str, Any]:
    """
    Get league standings with caching.
    
    Args:
        league_id: League ID
        season: Season year
        
    Returns:
        League standings data
    """
    return _call("standings", {"league": league_id, "season": season})

@lru_cache(maxsize=128)
def get_fixtures(
    league_id: Optional[int] = None,
    season: Optional[int] = None,
    date: Optional[str] = None,
    h2h: Optional[str] = None,
    fixture_id: Optional[int] = None,
    stage: Optional[str] = None,
    last: Optional[int] = None,
    next: Optional[int] = None,
    team_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get fixtures with flexible parameters and caching.
    
    Args:
        league_id: League ID
        season: Season year
        date: Match date
        h2h: Head-to-head teams (format: "team1_id-team2_id")
        fixture_id: Specific fixture ID
        stage: Competition stage
        last: Number of last matches
        next: Number of next matches
        team_id: Team ID
        
    Returns:
        Fixtures data
    """
    if fixture_id:
        return _call("fixtures", {"id": fixture_id})

    params: Dict[str, Any] = {}
    if league_id: params["league"] = league_id
    if date:      params["date"]   = date
    if stage:     params["stage"]  = stage
    if last:      params["last"]   = last
    if next:      params["next"]   = next
    if season:    params["season"] = season
    if team_id:   params["team"]   = team_id
    
    if h2h and "None" not in h2h:
        params["h2h"] = h2h
        return _call("fixtures/headtohead", params)
    
    return _call("fixtures", params)



@lru_cache(maxsize=64)
def get_match_events(fixture_id: int) -> Dict[str, Any]:
    """
    Get match events with caching.
    
    Args:
        fixture_id: Fixture ID
        
    Returns:
        Match events data
    """
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

def fetch_uefa_standings(league_id:int, season:int):
    data = get_standings(league_id, season)
    # API returns list-of-lists; each inner list is either
    # • one "total" table  (league phase)
    # • or 8 group tables  (Group A…H)
    tables = data["response"][0]["league"]["standings"]
    
    if is_league_phase_format(season):
        return {"phase": "league", "table": tables[0]}
    else:
        groups = {grp[0]["group"]: grp for grp in tables}
        return {"phase": "groups", "groups": groups}

def fetch_uefa_bracket(league_id: int, season: int):
    # 1. Ask the API which stages exist
    stages_resp = _call("fixtures/stages",
                        {"league": league_id, "season": season})
    stage_names = stages_resp["response"]

    # 2. Keep only knock-out stages (they contain a dash or 'Final')
    knockouts = [s for s in stage_names
                 if "Final" in s or "-" in s]

    bracket = {}
    for st in knockouts:
        fx = get_fixtures(league_id=league_id,
                          season=season,
                          stage=st)["response"]
        bracket[st] = fx
    return bracket


def final_ranks_from_bracket(bracket):
    
    """
    Extract final rankings from a bracket.
    
    Args:
        bracket: Bracket data
        
    Returns:
        Dictionary mapping team names to their final ranks
    """

    final  = bracket["Final"][0]
    winner = final["teams"]["home" if final["teams"]["home"]["winner"] else "away"]
    runner = final["teams"]["away" if final["teams"]["home"]["winner"] else "home"]

    semi = bracket["Semi-finals"]
    semi_losers = [t for f in semi for t in 
                   (f["teams"]["home"], f["teams"]["away"])
                   if not t["winner"]]
    return {
        winner["name"]: 1,
        runner["name"]: 2,
        semi_losers[0]["name"]: 3,
        semi_losers[1]["name"]: 4,
        quarter_losers[0]["name"]: 5,
        quarter_losers[1]["name"]: 6,
        quarter_losers[2]["name"]: 7,
        quarter_losers[3]["name"]: 8,
    }

@lru_cache(maxsize=64)
def get_fixture_statistics(fixture_id: int) -> Dict[str, Any]:
    """
    Get fixture statistics with caching.
    
    Args:
        fixture_id: Fixture ID
        
    Returns:
        Fixture statistics data
    """
    return _call("fixtures/statistics", {"fixture": fixture_id})

