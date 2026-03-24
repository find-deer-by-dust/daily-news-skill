import os
import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables
load_dotenv(override=True)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        TimedRotatingFileHandler("app.log", when='D', interval=1, backupCount=7, encoding='utf-8')
    ]
)

class Config:
    # Database Config
    DB_HOST: Optional[str] = os.getenv('DB_HOST', 'nas')
    DB_USER: Optional[str] = os.getenv('DB_USER', 'root')
    DB_PASSWORD: Optional[str] = os.getenv('DB_PASSWORD')
    DB_NAME: Optional[str] = os.getenv('DB_NAME')

    # AI Config
    AI_API_KEY: Optional[str] = os.getenv('AI_API_KEY')
    AI_BASE_URL: Optional[str] = os.getenv('AI_BASE_URL')
    AI_MODEL: str = os.getenv('AI_MODEL', 'gpt-3.5-turbo')

    # Email Config
    EMAIL_ADDRESS: Optional[str] = os.getenv('EMAIL_ADDRESS')
    EMAIL_PASSWORD: Optional[str] = os.getenv('EMAIL_PASSWORD')

    # News Config
    NEWS_API_KEY: Optional[str] = os.getenv('NEWS_API_KEY')
    NEWS_API_URL: str = os.getenv('NEWS_API_URL', "https://v3.alapi.cn/api/zaobao")

    # App Config
    # Default to empty list if USERS is empty or not provided
    USERS: List[str] = json.loads(os.getenv('USERS', '[]'))

    @classmethod
    def validate(cls) -> None:
        """Simple validation to ensure critical env vars are present."""
        missing: List[str] = []
        if not cls.DB_PASSWORD: missing.append("DB_PASSWORD")
        if not cls.DB_NAME: missing.append("DB_NAME")
        if not cls.AI_API_KEY: missing.append("AI_API_KEY")
        if not cls.EMAIL_ADDRESS: missing.append("EMAIL_ADDRESS")
        if not cls.EMAIL_PASSWORD: missing.append("EMAIL_PASSWORD")
        if not cls.NEWS_API_KEY: missing.append("NEWS_API_KEY")

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# Validate on import/start
try:
    Config.validate()
except ValueError as e:
    logging.error(e)
    sys.exit(1)
