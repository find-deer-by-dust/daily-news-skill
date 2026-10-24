from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import json

from .delivery import Delivery
from .http import JsonHTTP
from .news import NewsClient
from .store import Store, run_lock


def today(settings):
    return datetime.now(ZoneInfo(settings.timezone)).date().isoformat()


def context(store, day, days=30, *, history_detail='summary', history_offset=0, history_limit=None):
    if days < 1: raise ValueError('days 必须为正整数')
    if history_detail not in {'summary', 'full'}: raise ValueError('无效的 history-detail')
    if history_offset < 0: raise ValueError('history-offset 不能为负数')
    if history_limit is None:
        history_limit = 3 if history_detail == 'full' else 30
    if history_limit < 1: raise ValueError('history-limit 必须为正整数')
    record = store.get(day)
    index = store.history(day, days, summary=True)
    end = date.fromisoformat(day)
    window = [(end - timedelta(days=i)).isoformat() for i in range(days, 0, -1)]
    news_dates = {item['date'] for item in index if item['news'].strip()}
    coverage = {'start_date': window[0], 'end_date': window[-1],
                'news_days': len(news_dates),
                'report_days': sum(item['report_chars'] > 0 for item in index),
                'missing_news_dates': [d for d in window if d not in news_dates]}
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    previous = store.get(yesterday)
    history = (store.history(day, days, offset=history_offset, limit=history_limit)
               if history_detail == 'full' else index[history_offset:history_offset + history_limit])
    for item in history:
        item['news_metadata'] = json.loads(item['news_metadata'])
        if history_detail == 'full':
            item['research'] = json.loads(item['research'])
            if item['date'] == yesterday:
                del item['report']
                item['report_ref'] = 'yesterday_report'
    next_offset = history_offset + len(history)
    return {'date': day, 'news': record['news'] if record else '',
            'news_metadata': json.loads(record['news_metadata']) if record else {},
            'saved_report': record['report'] if record else '',
            'origin': record['origin'] if record else None,
            'yesterday_report': previous['report'] if previous else '', 'history_days': days,
            'history_coverage': coverage, 'history': history,
            'history_page': {'detail': history_detail, 'offset': history_offset, 'limit': history_limit,
                             'total': len(index), 'has_more': next_offset < len(index),
                             'next_offset': next_offset if next_offset < len(index) else None}}


def export_report(settings, day, report, sources):
    # Some legacy reports are UTF-8 BLOBs; decode for export without rewriting history.
    if isinstance(report, bytes): report = report.decode('utf-8')
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    target = settings.report_dir / f'{day}.md'
    for path, text in [(target, report),
                       (target.with_suffix('.sources.json'), json.dumps(sources, ensure_ascii=False, indent=2))]:
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(text, encoding='utf-8')
        temp.replace(path)
    return target


def export_reports(settings, *, start_date=None, end_date=None):
    start_date = date.fromisoformat(start_date).isoformat() if start_date else None
    end_date = date.fromisoformat(end_date).isoformat() if end_date else None
    if start_date and end_date and start_date > end_date:
        raise ValueError('start-date 不能晚于 end-date')
    with run_lock(settings.db_path):
        store = Store(settings.db_path)
        try:
            dates = []
            for record in store.reports_for_export(start_date, end_date):
                day = date.fromisoformat(record['date']).isoformat()
                export_report(settings, day, record['report'], json.loads(record['research']))
                dates.append(day)
            return {'exported_count': len(dates), 'report_dir': str(settings.report_dir), 'dates': dates}
        finally: store.close()


def fetch(settings, day=None, *, refresh=False):
    day = day or today(settings)
    with run_lock(settings.db_path):
        store = Store(settings.db_path)
        try:
            record = store.get(day)
            cached = bool(record and record['news'] and not refresh)
            if not cached:
                if day != today(settings): raise ValueError('新闻 API 只抓取当天，历史日期需先导入')
                if refresh and store.report_locked(day):
                    raise ValueError('已有成功或待确认的投递，不能刷新该日期的新闻')
                settings.validate('fetch')
                news, metadata = NewsClient(settings, JsonHTTP(settings.retries, settings.timeout)).fetch(day)
                store.save_news(day, news, metadata)
            return {'cached': cached, **context(store, day, settings.history_days)}
        finally: store.close()


def save_report(settings, day, content, sources=None):
    if not content.strip(): raise ValueError('报告为空，未保存')
    if sources is not None and not isinstance(sources, (dict, list)):
        raise ValueError('来源记录必须是 JSON 对象或数组')
    with run_lock(settings.db_path):
        store = Store(settings.db_path)
        try:
            record = store.get(day)
            if not record or not record['news']: raise ValueError('请先 fetch 获取并保存该日期的新闻')
            if store.report_locked(day):
                if record['report'] != content or (sources is not None and json.loads(record['research']) != sources):
                    raise ValueError('已有成功或待确认的投递，不能覆盖报告或来源记录')
            else:
                store.save_report(day, content, sources)
            record = store.get(day)
            path = export_report(settings, day, record['report'], json.loads(record['research']))
            return {'date': day, 'saved': True, 'report_chars': len(content), 'path': str(path)}
        finally: store.close()


def send_report(settings, day=None, *, dry_run=False, resend=False):
    day = day or today(settings)
    with run_lock(settings.db_path):
        store = Store(settings.db_path)
        try:
            record = store.get(day)
            if not record or not record['report']: raise ValueError('没有已保存报告；请由 Agent 分析后先 save-report')
            if dry_run:
                path = settings.report_dir / f'{day}.md'
                return {'date': day, 'status': 'preview', 'path': str(path), 'email_submitted': False,
                        'report': record['report'], 'sources': json.loads(record['research'])}
            if record['origin'] != 'local' and not resend:
                return {'date': day, 'status': 'imported', 'email_submitted': False,
                        'note': '导入报告的旧投递状态未知，默认不重发；明确需要重发时使用 --resend'}
            settings.validate('send')
            export_report(settings, day, record['report'], json.loads(record['research']))
            result = Delivery(settings, store).send(day, record['report'], resend=resend)
            states = [store.delivery(day, r) for r in settings.recipients]
            return {'date': day, 'status': 'sent' if result['email_submitted'] else 'skipped',
                    **result, 'deliveries': states}
        finally: store.close()
