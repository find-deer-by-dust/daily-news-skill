from dataclasses import dataclass
from pathlib import Path
import os
from zoneinfo import ZoneInfo

from dotenv import dotenv_values


SKILL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOME = SKILL_ROOT.parents[2] if SKILL_ROOT.parent.parent.name == '.agents' else SKILL_ROOT
ROOT = Path(os.environ.get('DAILY_NEWS_HOME') or DEFAULT_HOME).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    db_path: Path
    report_dir: Path
    timezone: str
    news_url: str
    news_key: str
    email_address: str
    email_password: str
    recipients: tuple[str, ...]
    smtp_host: str
    smtp_port: int
    smtp_security: str
    retries: int = 3
    timeout: int = 30
    history_days: int = 30

    @classmethod
    def load(cls, env_file: Path | None = None, db_path: Path | None = None):
        env_file = (env_file or ROOT / '.env').expanduser().resolve()
        values = {**dotenv_values(env_file), **os.environ}
        base = env_file.parent

        def get(name, default=''):
            return str(values.get(name) or default).strip()

        def path(value):
            p = Path(value).expanduser()
            return p if p.is_absolute() else base / p

        recipients = [r.strip() for r in get('EMAIL_RECIPIENT').split(',') if r.strip()]
        if any('@' not in r or '\n' in r or '\r' in r for r in recipients):
            raise ValueError('收件人邮箱格式无效')
        result = cls(
            db_path=path(str(db_path) if db_path else get('SQLITE_DB_PATH', get('DB_PATH', 'data/daily-news.db'))),
            report_dir=path(get('REPORT_DIR', 'data/reports')),
            timezone=get('TIMEZONE', 'Asia/Shanghai'),
            news_url=get('NEWS_API_URL', 'https://v3.alapi.cn/api/zaobao'),
            news_key=get('NEWS_API_KEY'),
            email_address=get('EMAIL_ADDRESS'), email_password=get('EMAIL_PASSWORD'),
            recipients=tuple(dict.fromkeys(recipients)),
            smtp_host=get('SMTP_HOST', 'smtp.163.com'), smtp_port=int(get('SMTP_PORT', '25')),
            smtp_security=get('SMTP_SECURITY', 'starttls').lower(),
            retries=int(get('HTTP_RETRIES', '3')), timeout=int(get('HTTP_TIMEOUT', '30')),
            history_days=int(get('HISTORY_DAYS', '30')),
        )
        ZoneInfo(result.timezone)
        if result.smtp_security not in {'starttls', 'ssl'}:
            raise ValueError('SMTP_SECURITY 必须是 starttls 或 ssl')
        if min(result.retries, result.timeout, result.history_days) < 1:
            raise ValueError('超时、重试和历史天数必须为正整数')
        return result

    def validate(self, scope='all'):
        required = {}
        if scope in {'fetch', 'all'}: required['NEWS_API_KEY'] = self.news_key
        if scope in {'send', 'all'}:
            required.update(EMAIL_ADDRESS=self.email_address,
                            EMAIL_PASSWORD=self.email_password, EMAIL_RECIPIENT=self.recipients)
        missing = [name for name, value in required.items() if not value]
        if missing: raise ValueError('缺少配置: ' + ', '.join(missing))
