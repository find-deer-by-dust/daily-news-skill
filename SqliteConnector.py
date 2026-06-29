import datetime
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

from config import Config
from DailyNews import DailyNews

logger = logging.getLogger(__name__)


class SqliteConnector:
    def __init__(self) -> None:
        self.connection: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def __enter__(self) -> 'SqliteConnector':
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def connect(self) -> None:
        try:
            db_path = Config.SQLITE_DB_PATH
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            self.connection = sqlite3.connect(db_path)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            self._ensure_schema()
            logger.info(f"已连接到 SQLite 数据库: {db_path}")
        except sqlite3.Error as e:
            logger.error(f"连接 SQLite 数据库时出错: {e}")
            raise

    def _ensure_schema(self) -> None:
        if not self.connection:
            raise RuntimeError("数据库连接未初始化。")

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS dailyNews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                news TEXT NOT NULL,
                aiReply TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def dir2dailyNews(self, data: Optional[Dict[str, Any]]) -> Optional[DailyNews]:
        if not data:
            return None

        news_date = data['date']
        if isinstance(news_date, str):
            news_date = datetime.date.fromisoformat(news_date)

        return DailyNews(
            id=data['id'],
            date=news_date,
            news=data['news'],
            aiReply=data['aiReply']
        )

    def insert(self, date: datetime.date, news: str, aiReply: str) -> None:
        if not self.connection or not self.cursor:
            raise RuntimeError("数据库连接未初始化。")

        sql = "INSERT INTO dailyNews(date, news, aiReply) VALUES (?, ?, ?);"
        val = (date.isoformat(), news, aiReply)
        try:
            self.cursor.execute(sql, val)
            self.connection.commit()
            logger.info("已将新闻插入数据库。")
        except sqlite3.Error as e:
            logger.error(f"插入新闻时出错: {e}")
            self.connection.rollback()
            raise

    def selectByDate(self, date: datetime.date) -> Optional[DailyNews]:
        if not self.cursor:
            return None

        sql = "SELECT * FROM dailyNews WHERE date = ?;"
        val = (date.isoformat(),)
        try:
            self.cursor.execute(sql, val)
            result = self.cursor.fetchone()
            if result:
                return self.dir2dailyNews(dict(result))
            return None
        except sqlite3.Error as e:
            logger.error(f"按日期查询时出错: {e}")
            return None

    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已关闭。")

    def haveNews(self, date: datetime.date) -> bool:
        result = self.selectByDate(date)
        return result is not None

    def getNearestNews(self, limit: int) -> str:
        if not self.cursor:
            return ""

        sql = "SELECT * FROM dailyNews ORDER BY date DESC LIMIT ?;"
        val = (limit,)
        try:
            self.cursor.execute(sql, val)
            result = self.cursor.fetchall()

            if not result:
                return ""

            news: List[DailyNews] = [
                item
                for item in (
                    self.dir2dailyNews(dict(row))
                    for row in result
                )
                if item is not None
            ]

            return "\n".join(
                f"{item.date.isoformat()}:{item.news}"
                for item in news
            )
        except sqlite3.Error as e:
            logger.error(f"获取最近新闻时出错: {e}")
            return ""
