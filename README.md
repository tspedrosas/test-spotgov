# Football Chatbot

A command-line interface (CLI) chatbot that provides real-time football information using the API-Football API and OpenAI's GPT-3.5 for natural language processing.

## Features

- **Natural Language Understanding**: Interact with the bot using natural language queries
- **Comprehensive Football Data**:
  - League standings and team rankings
  - Match fixtures and results
  - Head-to-head statistics
  - Player statistics
  - Match events and statistics
- **Smart Date Handling**:
  - Supports multiple date formats (DD-MM-YYYY, YYYY-MM-DD, etc.)
  - Automatic season deduction based on dates
- **League Support**:
  - Top 7 Leagues
  - UEFA competitions

## Prerequisites

- Python 3.8 or higher
- API-Football API key
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd test-spotgov
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your API keys:
```
FOOTBALL_API_KEY=your_api_football_key
OPENAI_API_KEY=your_openai_key
```

## Usage

Run the chatbot:
```bash
python -m src.main
```

You can also run the chatbot with the `-cost` flag to see the cost of each query and the estimated cost per 1000 requests:
```bash
python -m src.main.py -cost
```

### Example Queries

- **League Standings**:
  - "Show me the Premier League standings for the 23/24 season"
  - "What's Benfica's position in the league?"

- **Fixtures and Results**:
  - "When is the next match between Benfica and Porto?"
  - "Show me the last 5 benfica porto games"
  - "What were the results between Benfica and Porto in the 2023/24 season?"

- **Match Events**:
  - "Show me the events from the PSV vs Ajax match on 2025-03-30"
  - "What were the yellow cards in the last Estoril vs Porto match?"

- **Player Statistics**:
  - "Show me Messi stats in La Liga 20/21"
  - "What are Salah goals and assists this season?"

- **UEFA Competitions**:
  - "What's the current Champions League group standings?"
  - "Show me the group standings for the 24/25 Champions League league phase"
  - "In what place did Barcelona finish in Champions league in the 24/25 season?"

## Project Structure

```
test-spotgov/
├── src/
│   ├── api_client.py      # API-Football client implementation
│   ├── main.py           # Main application entry point
│   ├── nlp/
│   │   ├── openai_parser.py  # OpenAI integration for NLP
│   │   ├── intent_schema.py  # Intent definitions
│   │   └── resolver.py       # Entity resolution
│   ├── response_formatter.py # Response formatting utilities
│   └── utils.py          # Utility functions
├── config/
│   └── api_config.py     # API configuration
├── tests/               # Test files
├── requirements.txt     # Python dependencies
└── .env                # Environment variables (not in repo)
```

## Development

- The project uses OpenAI's GPT-3.5 for natural language understanding
- API-Football provides real-time football data
- The codebase is structured for easy extension and maintenance
- Includes comprehensive error handling and input validation

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## Known Issues and Future Work

### Current Issues
- The knockout stages bracket for European competitions (Champions League, Europa League, Conference League) are bugged and do not display correctly
- Player name resolution has limitations when multiple players share the same name in the same league, which can lead to incorrect player information being retrieved
- Natural Language Processing has limitations in understanding certain phrasings and word choices, which can make some queries difficult for the chatbot to interpret correctly

### Future Work
- Add support for additional sports (Basketball, Rugby, F1)
- Implement features for:
  - Match odds and betting information
  - Player transfers and transfer rumors
  - Coach statistics and history
  - Team and player trophy records
- Expand league coverage to include more competitions worldwide
- Improve player name resolution for better accuracy
- Fix European competition bracket display issues

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
