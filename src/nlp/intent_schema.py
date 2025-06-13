"""
Defines the canonical intents and entity keys
returned by the GPT parser so downstream
modules can rely on a strict schema.
"""
from enum import Enum, auto
from typing import TypedDict, Literal, Optional


class Intent(str, Enum):
    STANDINGS       = "standings"
    FIXTURE         = "fixture"
    MATCH_EVENTS    = "match_events"
    PLAYER_STATS    = "player_stats"
    BONUS_ODDS      = "odds"
    BRACKET      = "bracket"  
    BONUS_H2H       = "head_to_head"
    UNSUPPORTED     = "unsupported"

class Sport(str, Enum):
    FOOTBALL = "football"
    BASKETBALL = "basketball"
    RUGBY = "rugby"
    F1 = "f1"
    OTHER = "other"
    NONSPORT = "nonsport" 

class ParsedQuery(TypedDict, total=False):
    intent: Intent
    sport: Sport
    league_name: Optional[str]
    team_a: Optional[str]
    team_b: Optional[str]
    player_name: Optional[str]
    season: Optional[str]  # "2023", "2021/22", "current", etc.
    date: Optional[str]    # ISO YYYY-MM-DD for specific fixture
    stage: Optional[str]
    stats_requested: Optional[list[str]]
    player_stats_requested: Optional[list[str]]
    which: Optional[Literal["next","last","specific","season","team_next","team_last"]]
    count: Optional[int]