from src.api_client import get_standings, get_fixtures, get_match_events
import time
import os
import sqlite3
from src.nlp.resolver import team_name_to_id, player_name_to_id, _init_db, DB_PATH

def clear_all_caches():
    """Clear both LRU and SQLite caches"""
    # Clear SQLite cache
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    _init_db()
    
    # Clear LRU caches by accessing their cache dictionaries
    get_standings.cache_clear()
    get_fixtures.cache_clear()
    get_match_events.cache_clear()

def test_caching():
    print("\n=== Testing Both Caching Mechanisms ===")
    
    # Clear all caches first
    print("\nClearing all caches...")
    clear_all_caches()
    
    # Test 1: Team Lookup (SQLite Cache)
    print("\n1. Testing Team Lookup (SQLite Cache):")
    print("First lookup (should be slow - API call):")
    start = time.time()
    team_id1 = team_name_to_id("Manchester United")
    first_time = time.time() - start
    print(f"Time taken: {first_time:.3f} seconds")
    
    print("\nSecond lookup (should be fast - SQLite cache):")
    start = time.time()
    team_id2 = team_name_to_id("Manchester United")
    second_time = time.time() - start
    print(f"Time taken: {second_time:.3f} seconds")
    print(f"Cache working: {second_time < first_time}")
    print(f"Team IDs match: {team_id1 == team_id2}")
    
    # Verify SQLite storage
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT name FROM team WHERE id = ?", (team_id1,))
        stored_team = cursor.fetchone()
        print(f"Team stored in SQLite: {stored_team[0] if stored_team else 'Not found'}")
    
    # Test 2: Standings (LRU Cache)
    print("\n2. Testing Standings (LRU Cache):")
    print("First call (should be slow - API call):")
    start = time.time()
    standings1 = get_standings(39, 2024)  # Premier League 2024
    first_time = time.time() - start
    print(f"Time taken: {first_time:.3f} seconds")
    
    print("\nSecond call (should be fast - LRU cache):")
    start = time.time()
    standings2 = get_standings(39, 2024)
    second_time = time.time() - start
    print(f"Time taken: {second_time:.3f} seconds")
    print(f"Cache working: {second_time < first_time}")
    print(f"Results match: {standings1 == standings2}")
    
    # Test 3: Player Lookup (Both Caches)
    print("\n3. Testing Player Lookup (Both Caches):")
    print("First lookup (should be slow - API call):")
    start = time.time()
    player_id1 = player_name_to_id("Haaland", 39, 2024)
    first_time = time.time() - start
    print(f"Time taken: {first_time:.3f} seconds")
    
    print("\nSecond lookup (should be fast - SQLite cache):")
    start = time.time()
    player_id2 = player_name_to_id("Haaland", 39, 2024)
    second_time = time.time() - start
    print(f"Time taken: {second_time:.3f} seconds")
    print(f"Cache working: {second_time < first_time}")
    print(f"Player IDs match: {player_id1 == player_id2}")
    
    # Verify SQLite storage
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT name FROM player WHERE id = ?", (player_id1,))
        stored_player = cursor.fetchone()
        print(f"Player stored in SQLite: {stored_player[0] if stored_player else 'Not found'}")
    
    # Test 4: Cache Persistence
    print("\n4. Testing Cache Persistence:")
    print("Running the same lookups again (should all be fast):")
    
    # Team lookup
    start = time.time()
    team_id3 = team_name_to_id("Manchester United")
    team_time = time.time() - start
    print(f"Team lookup time: {team_time:.3f} seconds")
    
    # Standings lookup
    start = time.time()
    standings3 = get_standings(39, 2024)
    standings_time = time.time() - start
    print(f"Standings lookup time: {standings_time:.3f} seconds")
    
    # Player lookup
    start = time.time()
    player_id3 = player_name_to_id("Haaland", 39, 2024)
    player_time = time.time() - start
    print(f"Player lookup time: {player_time:.3f} seconds")
    
    print("\nAll subsequent lookups should be fast:")
    print(f"Team lookup fast: {team_time < 0.1}")
    print(f"Standings lookup fast: {standings_time < 0.1}")
    print(f"Player lookup fast: {player_time < 0.1}")

if __name__ == "__main__":
    print("Starting comprehensive cache tests...")
    test_caching()