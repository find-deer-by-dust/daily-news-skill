import logging
import time
import requests

log = logging.getLogger(__name__)


class ApiError(RuntimeError):
    pass


class JsonHTTP:
    """Only retry read-oriented API requests, never SMTP delivery."""
    def __init__(self, retries=3, timeout=90):
        self.retries, self.timeout = retries, timeout
        self.session = requests.Session()

    def post(self, url, payload, headers=None):
        for attempt in range(self.retries):
            try:
                response = self.session.post(url, json=payload, headers=headers,
                                             timeout=(15, self.timeout))
                if response.status_code >= 400:
                    # Do not log API response bodies: they may echo credentials.
                    if response.status_code not in {408, 429} and response.status_code < 500:
                        raise ApiError(f'API HTTP {response.status_code}')
                    response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ApiError('API 未返回 JSON 对象')
                return result
            except (requests.RequestException, ValueError):
                if attempt + 1 == self.retries:
                    raise ApiError('API 网络或 JSON 错误；重试已用完') from None
                log.warning('API 请求重试 %s/%s', attempt + 1, self.retries)
                time.sleep(min(2 ** (attempt + 1), 15))
