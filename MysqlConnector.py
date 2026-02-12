import pymysql
import logging
from config import Config
from DailyNews import DailyNews

logger = logging.getLogger(__name__)

class MysqlConnector:

    def __init__(self):
        self.connection = None
        self.cursor = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        try:
            self.connection = pymysql.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            logger.info("Connected to database.")
        except pymysql.MySQLError as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def dir2dailyNews(self, data):
        if not data: return None
        return DailyNews(
            id=data['id'],
            date=data['date'],
            news=data['news'],
            aiReply=data['aiReply']
        )
    
    def insert(self, date, news, aiReply):
        sql = "INSERT INTO dailyNews(date, news, aiReply) VALUES (%s, %s, %s);"
        val = (date, news, aiReply)
        try:
            self.cursor.execute(sql, val)
            self.connection.commit()
            logger.info("Inserted news into database.")
        except pymysql.MySQLError as e:
            logger.error(f"Error inserting news: {e}")
            self.connection.rollback()
            raise
    
    def selectByDate(self, date):
        sql = "select * from dailyNews where date = %s;"
        val = (date,) # Tuple
        try:
            self.cursor.execute(sql, val)
            result = self.cursor.fetchone()
            return self.dir2dailyNews(result)
        except pymysql.MySQLError as e:
            logger.error(f"Error selecting by date: {e}")
            return None
        
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed.")
            
    def haveNews(self, date):
        result = self.selectByDate(date)
        return result is not None
    
    def getNearestNews(self, limit):
        sql = "select * from dailyNews order by date desc LIMIT %s;"
        val = (limit,)
        try:
            self.cursor.execute(sql, val)
            result = self.cursor.fetchall()
            newsText = "\n".join(
                f"{item['date'].isoformat()}:{item['news']}"
                for item in result
            )   
            return newsText
        except pymysql.MySQLError as e:
            logger.error(f"Error getting nearest news: {e}")
            return ""
