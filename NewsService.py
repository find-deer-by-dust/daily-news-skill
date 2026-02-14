import logging
import datetime
from MysqlConnector import MysqlConnector
from NewsGetter import NewsGetter
from AiBot import AiBot
from EmailSender import EmailSender
from config import Config

logger = logging.getLogger(__name__)

class NewsService:
    def __init__(self, ai_news_coverage_days=7):
        self.ai_news_coverage_days = ai_news_coverage_days
        self.news_getter = NewsGetter()
        self.ai_bot = AiBot()
        self.email_sender = EmailSender()

    def run_daily_task(self):
        """
        Main orchestration method.
        Checks if news for today exists; if not and time is right, fetches, processes, and sends it.
        """
        today_date = datetime.date.today()
        current_hour = datetime.datetime.now().hour
        
        # Check if it's too early (before 9 AM)
        if current_hour <= 9:
            logger.info("It is too early to fetch news (before 9 AM). Skipping.")
            return

        with MysqlConnector() as db:
            if db.haveNews(today_date):
                logger.info(f"News for {today_date} already exists. Skipping.")
                return

            logger.info(f"No news found for {today_date}. Starting fetch process.")
            
            # 1. Get News
            news_content = self.news_getter.get_daily_news()
            if not news_content:
                logger.error("Failed to fetch news content. Aborting.")
                return

            # 2. Get Context for AI (previous news)
            # The original code passed (self.aiNewsCoverageDays-1) to getNearestNews
            nearest_news = db.getNearestNews(self.ai_news_coverage_days - 1)
            
            # 3. Get AI Summary
            prompt = f"{today_date}:{news_content}\n{nearest_news}"
            ai_reply = self.ai_bot.chat(prompt)

            # 4. Save to Database
            try:
                db.insert(today_date, news_content, ai_reply)
            except Exception as e:
                logger.error(f"Failed to save news to database: {e}")
                # We might want to continue to send email even if DB save fails, 
                # but usually DB failure is critical. Let's attempt email anyway?
                # For now, I'll assume if DB fails, we might not want to spam email if it retries later.
                # But looking at the logic, if we don't save, 'haveNews' will be false next time, causing a loop.
                # So we should probably not send email if DB save fails to avoid potential spamming if the script loops.
                return 

            # 5. Send Email
            subject = f"每日60秒新闻 {today_date}"
            email_body = f"{news_content}\n\nai新闻总结:\n\n{ai_reply}"
            self.email_sender.sendEmail(Config.USERS, subject, email_body)
            
            logger.info("Daily task completed successfully.")
