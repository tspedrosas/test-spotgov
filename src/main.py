from src.api_client import get_standings

def main():
    print("Welcome to Football Chatbot ⚽")
    league = input("Enter League ID: ")
    season = input("Enter Season (e.g. 2023): ")

    standings = get_standings(league, season)
    print(standings)

if __name__ == "__main__":
    main()
