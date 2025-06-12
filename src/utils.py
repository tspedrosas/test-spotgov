# src/utils.py
import re
from datetime import datetime

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
