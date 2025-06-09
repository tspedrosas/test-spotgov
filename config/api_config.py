# config/api_config.py
import os
from dotenv import load_dotenv

load_dotenv()

FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
