import os
import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from typing import List, Optional

# 加载环境变量
load_dotenv(override=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        TimedRotatingFileHandler("app.log", when='D', interval=1, backupCount=7, encoding='utf-8')
    ]
)

class Config:
    # 数据库配置
    DB_HOST: Optional[str] = os.getenv('DB_HOST', 'nas')
    DB_USER: Optional[str] = os.getenv('DB_USER', 'root')
    DB_PASSWORD: Optional[str] = os.getenv('DB_PASSWORD')
    DB_NAME: Optional[str] = os.getenv('DB_NAME')

    # AI 配置
    AI_API_KEY: Optional[str] = os.getenv('AI_API_KEY')
    AI_BASE_URL: Optional[str] = os.getenv('AI_BASE_URL')
    AI_MODEL: str = os.getenv('AI_MODEL', 'gpt-3.5-turbo')

    # 邮箱配置
    EMAIL_ADDRESS: Optional[str] = os.getenv('EMAIL_ADDRESS')
    EMAIL_PASSWORD: Optional[str] = os.getenv('EMAIL_PASSWORD')

    # 新闻配置
    NEWS_API_KEY: Optional[str] = os.getenv('NEWS_API_KEY')
    NEWS_API_URL: str = os.getenv('NEWS_API_URL', "https://v3.alapi.cn/api/zaobao")

    # 应用配置
    # 如果 USERS 为空或未提供，默认使用空列表
    USERS: List[str] = json.loads(os.getenv('USERS', '[]'))

    @classmethod
    def validate(cls) -> None:
        """简单的验证，确保关键的环境变量存在。"""
        missing: List[str] = []
        if not cls.DB_PASSWORD: missing.append("DB_PASSWORD")
        if not cls.DB_NAME: missing.append("DB_NAME")
        if not cls.AI_API_KEY: missing.append("AI_API_KEY")
        if not cls.EMAIL_ADDRESS: missing.append("EMAIL_ADDRESS")
        if not cls.EMAIL_PASSWORD: missing.append("EMAIL_PASSWORD")
        if not cls.NEWS_API_KEY: missing.append("NEWS_API_KEY")

        if missing:
            raise ValueError(f"缺少必需的环境变量: {', '.join(missing)}")

# 在导入或启动时进行验证
try:
    Config.validate()
except ValueError as e:
    logging.error(e)
    sys.exit(1)
