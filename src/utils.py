# src/utils.py
import re
from datetime import datetime
from typing import List, Dict
from src.api_client import get_standings
from src.nlp.resolver import cache_standings, load_standings_cache

SUPPORTED_LEAGUES = [
    "Premier League",          # id 39
    "La Liga",                 # id 140
    "Bundesliga",              # id 78
    "Serie A",                 # id 135
    "Ligue 1",                 # id 61
    "Eredivisie",              # id 88
    "Primeira Liga",           # id 94
    "UEFA Champions League",   # id 2
    "UEFA Europa League",      # id 3
    "UEFA Conference League"   # id 848
]

SUPPORTED_LEAGUES_IDS = [39, 140, 78, 135, 61, 88, 94, 2, 3, 848]

UEFA_IDS = {2, 3, 848}

def normalize_season(season_raw: str | int | None) -> str | None:
    """
    Accepts a variety of season strings and returns the 4-digit starting
    year (as str). Returns None if cannot parse.
    Examples:
        "2022/2023" -> "2022"
        "2021/22"   -> "2021"
        "22/23"     -> "2022"  (assumes 2000-2099 window)
        2024        -> "2024"
    """
    if season_raw is None:
        return None
    if isinstance(season_raw, int):
        return str(season_raw)
    season_raw = season_raw.strip()

    # 2022/2023 or 2022-2023
    m = re.match(r"^(?P<yy1>\d{4})\D+\d{2,4}$", season_raw)
    if m:
        return m.group("yy1")

    # 2021/22 or 2021-22
    m = re.match(r"^(?P<yy1>\d{4})\D+\d{2}$", season_raw)
    if m:
        return m.group("yy1")

    # 22/23 style (two-digit years)
    m = re.match(r"^(?P<yy1>\d{2})\D+\d{2}$", season_raw)
    if m:
        yy = int(m.group("yy1"))
        # heuristic: anything >= 50 => 1900s, else 2000s
        century = 1900 if yy >= 50 else 2000
        return str(century + yy)

    # already plain "2024"
    if re.fullmatch(r"\d{4}", season_raw):
        return season_raw

    return None

def ordinal(n: int) -> str:
    """
    Convert a number to its ordinal form (1st, 2nd, 3rd, etc.).
    
    Args:
        n: The number to convert
        
    Returns:
        The ordinal form of the number as a string
        
    Examples:
        >>> ordinal(1)
        '1st'
        >>> ordinal(2)
        '2nd'
        >>> ordinal(3)
        '3rd'
        >>> ordinal(4)
        '4th'
        >>> ordinal(11)
        '11th'
        >>> ordinal(12)
        '12th'
        >>> ordinal(13)
        '13th'
        >>> ordinal(21)
        '21st'
    """
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

def convert(api_row: Dict) -> Dict:
    """
    API-Football row (from league or group table)  ->  internal row
    Keeps the exact keys your fmt_standings() expects.
    """
    return {
        "rank":  api_row["rank"],
        "team":  api_row["team"]["name"],
        "stats": api_row["all"],           # played / win / draw / lose
        "gd":    api_row["goalsDiff"],
        "pts":   api_row["points"],
    }

def pull_and_cache_domestic_table(league_id: int, season: str) -> List[Dict]:
    """
    1) Hit /standings for this domestic league+season
    2) Convert each row via convert()
    3) Cache rows to SQLite (resolver.cache_standings)
    4) Return the rows list
    """
    api = get_standings(league_id, season)
    raw_rows = api["response"][0]["league"]["standings"][0]   # single table
    rows = [convert(r) for r in raw_rows]
    cache_standings(league_id, season, rows)
    return rows

def standardize_date(date_str: str) -> str | None:
    """
    Converts various date formats into YYYY-MM-DD format.
    Handles multiple input formats:
    - DD-MM-YYYY
    - DD/MM/YYYY
    - DD-MM-YY
    - DD/MM/YY
    - YYYY-MM-DD
    - YYYY/MM/DD
    - MM-DD-YYYY
    - MM/DD/YYYY
    
    Returns None if date cannot be parsed.
    """
    if not date_str:
        return None
        
    # Remove any whitespace
    date_str = date_str.strip()
    
    # Common separators
    separators = ['-', '/', '.']
    
    # Try different date formats
    formats = [
        # Full year formats
        '%Y-%m-%d', '%Y/%m/%d',  # YYYY-MM-DD, YYYY/MM/DD
        '%d-%m-%Y', '%d/%m/%Y',  # DD-MM-YYYY, DD/MM/YYYY
        '%m-%d-%Y', '%m/%d/%Y',  # MM-DD-YYYY, MM/DD/YYYY
        
        # Two-digit year formats
        '%d-%m-%y', '%d/%m/%y',  # DD-MM-YY, DD/MM/YY
        '%m-%d-%y', '%m/%d/%y',  # MM-DD-YY, MM/DD/YY
        '%y-%m-%d', '%y/%m/%d',  # YY-MM-DD, YY/MM/DD
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            # Convert to YYYY-MM-DD format
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
            
    return None

def deduce_season_from_date(date_str: str) -> str | None:
    """
    Deduces the season from a date string in YYYY-MM-DD format.
    Returns the 4-digit starting year as a string, or None if invalid.
    
    Season rules:
    - If date is between July-December: season is current year
    - If date is between January-June: season is previous year
    
    Examples:
        "2024-08-15" -> "2024" (summer/fall date -> current year)
        "2024-02-15" -> "2023" (winter/spring date -> previous year)
    """
    # First standardize the date format
    standardized_date = standardize_date(date_str)
    if not standardized_date:
        return None
        
    try:
        date = datetime.strptime(standardized_date, "%Y-%m-%d")
        year = date.year
        # If date is in first half of year (Jan-Jun), season started previous year
        if date.month <= 6:
            year -= 1
        return str(year)
    except (ValueError, TypeError):
        return None
