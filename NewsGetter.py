import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

class NewsGetter:
    def __init__(self):
        self.url = Config.NEWS_API_URL
        self.payload = Config.NEWS_API_KEY
        self.headers = {'Content-Type': "application/x-www-form-urlencoded"}

    def get_daily_news(self):
        """
        Fetches daily news from the API.
        Returns a formatted string of news items, or None if failed.
        """
        try:
            logger.info("Fetching news from API...")
            response = requests.post(self.url, data={'token': self.payload}, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('code') != 200:
                logger.error(f"API returned error: {data.get('msg', 'Unknown error')}")
                return None
            
            news_items = data.get('data', {}).get('news', [])
            if not news_items:
                logger.warning("No news items found in API response.")
                return None

            # Format news: Remove the prefix before the first '、' (like "1、")
            formatted_news = []
            for item in news_items:
                # Find the first occurrence of "、"
                separator_index = item.find("、")
                if separator_index != -1:
                    clean_item = item[separator_index + 1:].strip()
                else:
                    clean_item = item.strip()
                formatted_news.append(clean_item)
            
            return "\n\n".join(formatted_news)

        except requests.RequestException as e:
            logger.error(f"Network error while fetching news: {e}")
            return None
        except ValueError as e:
            logger.error(f"Error parsing JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in NewsGetter: {e}")
            return None