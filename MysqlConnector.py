import pymysql
from dotenv import load_dotenv
from DailyNews import DailyNews
import os

load_dotenv(override=True)

class MysqlConnector:

    def __init__(self):
        self.db = pymysql.connect(
            host="nas",
            user="root",
            password=os.getenv('password'),
            database=os.getenv('database'),
            cursorclass=pymysql.cursors.DictCursor 
        )
        self.cursor = self.db.cursor()
        
    def dir2dailyNews(self, dir):
        if not dir: return None
        dailyNews = DailyNews(
            id=dir['id'],
            date=dir['date'],        # MySQL DATE 类型会映射成 datetime.date
            news=dir['news'],
            aiReply=dir['aiReply']
        )
        return dailyNews
    
    def insert(self, news, aiReply):
        sql = "INSERT dailyNews(date,news,aiReply) VALUES (CURDATE(), %s, %s);"
        val = (news, aiReply)
        self.cursor.execute(sql, val)
        self.db.commit()
    
    def selectByDate(self,date):
        sql = "select * from dailyNews where date = %s;"
        val = (date)
        self.cursor.execute(sql, val)
        result = self.cursor.fetchone()
        
        obj = self.dir2dailyNews(result)
        return obj
        
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.db:
            self.db.close()
            
    def haveNews(self, date):
        result = self.selectByDate(date)
        if result:
            return True
        else:
            return False
    
    def getNearestNews(self,x):
        sql = "select * from dailyNews order by date desc LIMIT %s;"
        val = (x)
        self.cursor.execute(sql, val)
        result = self.cursor.fetchall()
        newsText = "\n".join(
            f"{item['date'].isoformat()}:{item['news']}"
            for item in result
        )   
        return newsText