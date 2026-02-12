import os
import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv

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
    DB_HOST = os.getenv('DB_HOST', 'nas')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    
    # AI Config
    AI_API_KEY = os.getenv('AI_API_KEY')
    AI_BASE_URL = os.getenv('AI_BASE_URL')
    AI_MODEL = os.getenv('AI_MODEL')
    
    # Email Config
    EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    
    # News Config
    NEWS_API_KEY = os.getenv('NEWS_API_KEY')
    NEWS_API_URL = os.getenv('NEWS_API_URL', "https://v3.alapi.cn/api/zaobao")
    
    # App Config
    USERS = json.loads(os.getenv('USERS', '[]'))
    
    @classmethod
    def validate(cls):
        """Simple validation to ensure critical env vars are present."""
        missing = []
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
