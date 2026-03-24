import pymysql
import logging
from typing import Optional, Any, Dict, List
from config import Config
from DailyNews import DailyNews
import datetime

logger = logging.getLogger(__name__)

class MysqlConnector:

    def __init__(self) -> None:
        self.connection: Optional[pymysql.connections.Connection] = None
        self.cursor: Optional[pymysql.cursors.DictCursor] = None

    def __enter__(self) -> 'MysqlConnector':
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def connect(self) -> None:
        try:
            # pymysql 并不总是具备完美的严格类型，因此我们使用 Any 作为 DictCursor 的后备类型
            cursor_cls: Any = pymysql.cursors.DictCursor
            self.connection = pymysql.connect(
                host=Config.DB_HOST or 'nas',
                user=Config.DB_USER or 'root',
                password=Config.DB_PASSWORD or '',
                database=Config.DB_NAME or '',
                cursorclass=cursor_cls
            )
            self.cursor = self.connection.cursor()
            logger.info("已连接到数据库。")
        except pymysql.MySQLError as e:
            logger.error(f"连接数据库时出错: {e}")
            raise

    def dir2dailyNews(self, data: Optional[Dict[str, Any]]) -> Optional[DailyNews]:
        if not data:
            return None
        return DailyNews(
            id=data['id'],
            date=data['date'],
            news=data['news'],
            aiReply=data['aiReply']
        )

    def insert(self, date: datetime.date, news: str, aiReply: str) -> None:
        if not self.connection or not self.cursor:
            raise RuntimeError("数据库连接未初始化。")

        sql = "INSERT INTO dailyNews(date, news, aiReply) VALUES (%s, %s, %s);"
        val = (date, news, aiReply)
        try:
            self.cursor.execute(sql, val)
            self.connection.commit()
            logger.info("已将新闻插入数据库。")
        except pymysql.MySQLError as e:
            logger.error(f"插入新闻时出错: {e}")
            self.connection.rollback()
            raise

    def selectByDate(self, date: datetime.date) -> Optional[DailyNews]:
        if not self.cursor:
            return None

        sql = "select * from dailyNews where date = %s;"
        val = (date,) # 元组
        try:
            self.cursor.execute(sql, val)
            # 根据游标类型，fetchone 会返回字典或元组，我们设置了 DictCursor 所以它返回字典
            result = self.cursor.fetchone()
            # 在严格模式下，我们必须断言它是一个字典，或者转换它
            if result and isinstance(result, dict):
                return self.dir2dailyNews(result)
            return None
        except pymysql.MySQLError as e:
            logger.error(f"按日期查询时出错: {e}")
            return None

    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭。")

    def haveNews(self, date: datetime.date) -> bool:
        result = self.selectByDate(date)
        return result is not None

    def getNearestNews(self, limit: int) -> str:
        if not self.cursor:
            return ""

        sql = "select * from dailyNews order by date desc LIMIT %s;"
        val = (limit,)
        try:
            self.cursor.execute(sql, val)
            result = self.cursor.fetchall()

            if not result or not isinstance(result, (list, tuple)):
                return ""

            newsText = "\n".join(
                f"{item['date'].isoformat()}:{item['news']}"
                for item in result if isinstance(item, dict) and 'date' in item and 'news' in item
            )
            return newsText
        except pymysql.MySQLError as e:
            logger.error(f"获取最近新闻时出错: {e}")
            return ""
