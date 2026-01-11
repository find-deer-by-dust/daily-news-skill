from openai import OpenAI
import json
import os
from dotenv import load_dotenv
load_dotenv(override=True)

class AiBot:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv('aiApiKey'),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.systemContent = "你是一个专业新闻点评人,用通俗易懂的语言,减少专业性描述,给你最近几日新闻，你做出总体点评,不需要对每一条新闻点评,用纯文本的方式回答我,不用markdown,但是同样需要做好分段"
        
    def chat(self, content):
        completion = self.client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": self.systemContent},
                {"role": "user", "content": content},
            ],
        )
        return json.loads(completion.model_dump_json()).get("choices")[0].get("message").get("content")