from openai import OpenAI
import logging
from config import Config

logger = logging.getLogger(__name__)

class AiBot:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_BASE_URL,
        )
        self.systemContent = "你是一个专业新闻点评人,用通俗易懂的语言,减少专业性描述,给你最近几日新闻，你做出总体点评,不需要对每一条新闻点评,用纯文本的方式回答我,不用markdown,但是同样需要做好分段"
        
    def chat(self, content):
        logger.info("Sending request to AI model...")
        try:
            completion = self.client.chat.completions.create(
                model=Config.AI_MODEL,
                messages=[
                    {"role": "system", "content": self.systemContent},
                    {"role": "user", "content": content},
                ],
            )
            response_content = completion.choices[0].message.content
            logger.info("Received response from AI model.")
            return response_content
        except Exception as e:
            logger.error(f"Error communicating with AI: {e}")
            return "AI summary unavailable due to an error."
