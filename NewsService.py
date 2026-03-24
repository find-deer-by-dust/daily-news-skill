import logging
import datetime
from MysqlConnector import MysqlConnector
from NewsGetter import NewsGetter
from AiBot import AiBot
from EmailSender import EmailSender
from config import Config

logger = logging.getLogger(__name__)

class NewsService:
    def __init__(self, ai_news_coverage_days: int = 7):
        self.ai_news_coverage_days = ai_news_coverage_days
        self.news_getter = NewsGetter()
        self.ai_bot = AiBot()
        self.email_sender = EmailSender()

    def run_daily_task(self) -> None:
        """
        主调度方法。
        检查今天的新闻是否已存在；如果不存在且时间合适，则获取、处理并发送它。
        """
        today_date = datetime.date.today()
        current_hour = datetime.datetime.now().hour

        # 检查是否太早（早于上午 9 点）
        if current_hour < 9:
            logger.info("获取新闻的时间太早（早于上午 9 点）。跳过执行。")
            return

        with MysqlConnector() as db:
            if db.haveNews(today_date):
                logger.info(f"{today_date} 的新闻已经存在。跳过执行。")
                return

            logger.info(f"未找到 {today_date} 的新闻。开始获取流程。")

            # 1. 获取新闻
            news_content = self.news_getter.get_daily_news()
            if not news_content:
                logger.error("获取新闻内容失败。中止每日任务。")
                return

            # 2. 获取给 AI 提供的上下文（前几日的新闻）
            nearest_news = db.getNearestNews(self.ai_news_coverage_days - 1)

            # 3. 获取 AI 总结点评
            prompt = f"{today_date}:\n{news_content}\n\n历史参考:\n{nearest_news}"
            ai_reply = self.ai_bot.chat(prompt)

            # 4. 保存至数据库
            try:
                db.insert(today_date, news_content, ai_reply)
            except Exception as e:
                logger.error(f"保存新闻至数据库失败: {e}")
                logger.warning("数据库插入失败，但我们将继续发送邮件。")
                # 虽然存入数据库失败，但为了保证读者能按时收到新闻，我们继续执行发送邮件的流程。
                # 注意：如果这是一个被频繁轮询的脚本，数据库写入失败可能会导致下一次轮询时继续触发该任务。
                # 但考虑到通常这只是一个通过 crontab 每天执行一次的脚本，确保交付比静默失败更好。

            # 5. 发送邮件
            subject = f"每日60秒早报 - {today_date}"
            email_body = (
                f"{news_content}\n\n"
                f"{'='*30}\n"
                f"【AI 独家点评】:\n\n"
                f"{ai_reply}"
            )
            self.email_sender.sendEmail(Config.USERS, subject, email_body)

            logger.info("每日任务执行成功。")
