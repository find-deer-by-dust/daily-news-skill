from openai import OpenAI
import logging
import time
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

class AiBot:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_BASE_URL,
        )
        self.systemContent = "你是一个专业新闻点评人,用通俗易懂的语言,减少专业性描述,给你最近几日新闻，你做出总体点评,不需要对每一条新闻点评,用纯文本的方式回答我,不用markdown,但是同样需要做好分段"

    def chat(self, content: str, max_retries: int = 3) -> str:
        """
        发送内容给 AI 进行总结，带有防止网络波动的重试机制。
        """
        for attempt in range(1, max_retries + 1):
            logger.info(f"正在发送请求至 AI 模型... (第 {attempt}/{max_retries} 次尝试)")
            try:
                completion = self.client.chat.completions.create(
                    model=Config.AI_MODEL,
                    messages=[
                        {"role": "system", "content": self.systemContent},
                        {"role": "user", "content": content},
                    ],
                    timeout=60  # 防止无限期挂起
                )
                response_content = completion.choices[0].message.content
                logger.info("已收到 AI 模型响应。")
                return response_content or "AI 返回了空内容。"
            except Exception as e:
                logger.error(f"与 AI 通信时出错: {e}")
                if attempt < max_retries:
                    sleep_time = 2 ** attempt
                    logger.info(f"将在 {sleep_time} 秒后重试 AI 请求...")
                    time.sleep(sleep_time)

        return "很抱歉，今日 AI 点评因网络或接口错误暂时无法生成。"
