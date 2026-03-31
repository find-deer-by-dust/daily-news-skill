import requests
import logging
import re
import time
import datetime
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class NewsGetter:
    def __init__(self):
        self.url = Config.NEWS_API_URL
        self.payload = Config.NEWS_API_KEY
        self.headers = {'Content-Type': "application/x-www-form-urlencoded"}

    def get_daily_news(self, max_retries: int = 10) -> Optional[str]:
        """
        从 API 获取每日新闻，并带有重试机制。
        返回格式化后的新闻字符串，如果失败则返回 None。
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"正在从 API 获取新闻... (第 {attempt}/{max_retries} 次尝试)")
                response = requests.post(self.url, data={'token': self.payload}, headers=self.headers, timeout=15)
                response.raise_for_status()

                data = response.json()
                if data.get('code') != 200:
                    logger.error(f"API 返回错误: {data.get('msg', '未知错误')}")
                    return None

                news_data = data.get('data', {})
                news_date = news_data.get('date')
                today_str = datetime.date.today().strftime('%Y-%m-%d')

                if news_date and news_date != today_str:
                    logger.warning(f"获取到的新闻日期 ({news_date}) 不是今天 ({today_str})")
                    raise Exception(f"新闻尚未更新，当前日期: {news_date}")

                news_items = news_data.get('news', [])
                if not news_items:
                    logger.warning("API 响应中未找到新闻项。")
                    return None

                # 格式化新闻：使用正则去除新闻开头的数字序号和顿号（例如："1、", "12、"）
                formatted_news = []
                for item in news_items:
                    # 正则 r'^\d+、\s*' 匹配：行首的数字 + 顿号 + 可能存在的空白字符
                    clean_item = re.sub(r'^\d+、\s*', '', item).strip()
                    formatted_news.append(clean_item)

                return "\n\n".join(formatted_news)

            except requests.RequestException as e:
                logger.error(f"获取新闻时发生网络错误: {e}")
            except ValueError as e:
                logger.error(f"解析 JSON 响应出错: {e}")
            except Exception as e:
                logger.error(f"NewsGetter 中发生意外错误: {e}")

            if attempt < max_retries:
                sleep_time = 2 ** attempt  # 指数退避：2s, 4s, 8s...
                logger.info(f"将在 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)

        logger.error("所有获取新闻的尝试均失败。")
        return None
