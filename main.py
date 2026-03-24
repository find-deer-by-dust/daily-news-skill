from NewsService import NewsService
import logging
from config import Config # 确保已加载配置和日志

logger = logging.getLogger(__name__)

def main():
    logger.info("正在启动 EmailBot 应用程序...")
    try:
        service = NewsService(ai_news_coverage_days=7)
        service.run_daily_task()
    except Exception as e:
        logger.critical(f"主程序发生未处理的异常: {e}", exc_info=True)

if __name__ == "__main__":
    main()
