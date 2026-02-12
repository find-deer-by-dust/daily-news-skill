from NewsService import NewsService
import logging
from config import Config # Ensure config is loaded and logging configured

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting EmailBot application...")
    try:
        service = NewsService(ai_news_coverage_days=7)
        service.run_daily_task()
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)

if __name__ == "__main__":
    main()
