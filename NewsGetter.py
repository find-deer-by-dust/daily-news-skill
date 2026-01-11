import requests
from MysqlConnector import MysqlConnector
import time
from AiBot import AiBot
import os
from dotenv import load_dotenv
from EmailSender import EmailSender

load_dotenv(override=True)

class NewsGetter:
    def __init__(self,aiNewsCoverageDays):
        self.subject = ""
        self.contentText = ""
        self.payload = os.getenv('newsApiKey')
        self.url = "https://v3.alapi.cn/api/zaobao"
        self.headers = {'Content-Type': "application/x-www-form-urlencoded"}
        self.aiNewsCoverageDays = aiNewsCoverageDays
    
    def sendNews(self, users):
        
        aiBot = AiBot()
        mysqlConnector = MysqlConnector()
        today=time.strftime('%Y-%m-%d', time.localtime())
        hour=int(time.strftime('%H', time.localtime()))
        emailSender = EmailSender()

        if not mysqlConnector.haveNews(today) and hour > 9 :
            self.subject="每日60秒新闻 "+today
            response = requests.request("POST", self.url, data="token="+self.payload, headers=self.headers)
            
            tmp = response.json()

            for i in tmp['data']['news']:
                self.contentText = self.contentText+i[i.find("、")+1:]+'\n\n'
                
            nearestNews = mysqlConnector.getNearestNews(self.aiNewsCoverageDays-1)
            aiReply=aiBot.chat(today+":"+self.contentText+"\n"+nearestNews)
            
            mysqlConnector.insert(self.contentText,aiReply)
            
            emailSender.sendEmail(users, self.subject, self.contentText+"\nai新闻总结:\n\n"+aiReply)
            
        mysqlConnector.close()
