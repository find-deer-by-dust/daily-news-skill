import re


class NewsClient:
    def __init__(self, settings, http):
        self.settings, self.http = settings, http

    def fetch(self, day):
        result = self.http.post(self.settings.news_url,
                                {'token': self.settings.news_key, 'format': 'json'})
        if result.get('code') != 200:
            raise RuntimeError(f"新闻 API 业务错误，code={result.get('code')}")
        data = result.get('data', {})
        if data.get('date') != day:
            raise RuntimeError(f"新闻日期不匹配：请求 {day}，返回 {data.get('date')}；暂不生成或发送")
        items = data.get('news')
        if not isinstance(items, list) or not items or not all(isinstance(i, str) and i.strip() for i in items):
            raise RuntimeError('新闻 API 返回的新闻列表为空或格式无效')
        cleaned = [re.sub(r'^\d+[、.．]\s*', '', item).strip() for item in items]
        return '\n'.join(cleaned), {'date': day, 'items': cleaned,
            'weiyu': data.get('weiyu', ''), 'source_url': self.settings.news_url}
