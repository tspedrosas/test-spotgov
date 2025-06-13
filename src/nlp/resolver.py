# src/nlp/resolver.py   ← rename if needed
import os, sqlite3, requests
from functools import lru_cache
from typing import Optional, Dict, Any

from config.api_config import FOOTBALL_API_KEY

HEADERS = {"x-apisports-key": FOOTBALL_API_KEY}
BASE    = "https://v3.football.api-sports.io"

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cache", "mapping.sqlite")


# ---------------------------------------------------------------------
#  DB bootstrap
# ---------------------------------------------------------------------
def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS team (
                id      INTEGER PRIMARY KEY,
                name    TEXT,
                country TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_team_name
                ON team(name COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS player (
                id      INTEGER PRIMARY KEY,
                name    TEXT,
                common  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_player_name
                ON player(name COLLATE NOCASE);

            /*  NEW — standings season cache  */
            CREATE TABLE IF NOT EXISTS standings_cache (
                league INTEGER,
                season TEXT,
                json   TEXT,
                PRIMARY KEY (league, season)
            );
            """
        )

@lru_cache(maxsize=2048)
def league_name_to_id(name: str) -> Optional[int]:
    """Resolve league name → numeric ID using live API search."""
    r = requests.get(f"{BASE}/leagues", headers=HEADERS, params={"search": name})
    data = r.json().get("response", [])
    return data[0]["league"]["id"] if data else None

@lru_cache(maxsize=4096)
def team_name_to_id(
    name: str,
    league_id: Optional[int] = None,
    season: Optional[int] = None
) -> Optional[int]:
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM team WHERE name = ? COLLATE NOCASE LIMIT 1;",
            (name,),
        ).fetchone()
        if row:
            return row[0]

    # Not cached → API search
    params: Dict[str, Any] = {"name": name}
    if league_id:
        params["league"] = league_id
    if season:
        params["season"] = season

    resp = requests.get(f"{BASE}/teams", headers=HEADERS, params=params).json()
    data = resp.get("response", [])
    if data:
        t = data[0]["team"]
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO team(id, name, country) VALUES(?,?,?);",
                (t["id"], t["name"], t["country"]),
            )
        return t["id"]
    return None

@lru_cache(maxsize=4096)
def player_name_to_id(
    name: str,
    league_id: Optional[int] = None,
    season: Optional[int] = None
) -> Optional[int]:
    """
    Resolve player full name (or common short name) to numeric ID.
    Cached locally in the 'player' table.
    """
    _init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM player WHERE name = ? COLLATE NOCASE LIMIT 1;",
            (name,),
        ).fetchone()
        if row:
            return row[0]

    params: Dict[str, Any] = {"search": name}
    if league_id:
        params["league"] = league_id

    if season:
        params["season"] = season
    
    resp = requests.get(f"{BASE}/players", headers=HEADERS, params=params).json()
    
    data = resp.get("response", [])
    if data:
        p = data[0]["player"]
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO player(id, name, common) VALUES(?,?,?);",
                (p["id"], p["name"], p.get("firstname")),
            )
        return p["id"]
    return None

def cache_standings(league_id: int, season: str, rows):
    _init_db()
    import json, sqlite3
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT OR REPLACE INTO standings_cache VALUES (?,?,?)",
                  (league_id, season, json.dumps(rows)))


def load_standings_cache(league_id:int, season:str):
    _init_db()
    import json, sqlite3
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT json FROM standings_cache "
                        "WHERE league=? AND season=?", (league_id, season)
                        ).fetchone()
        return json.loads(row[0]) if row else None

