import argparse
from dataclasses import replace
from datetime import date
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import Settings
from .store import Store, run_lock
from .workflow import context, fetch, save_report, send_report, today


def cli(argv=None):
    parser = argparse.ArgumentParser(description='daily-news Skill 数据与邮件工具；核查和分析由 Agent 完成')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--db', type=Path, help='数据库路径；相对路径以 .env 所在目录为基准')
    parser.add_argument('--report-dir', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='检查新闻/邮箱配置，不访问网络')
    check.add_argument('--scope', choices=['all', 'fetch', 'send'], default='all')
    news = sub.add_parser('fetch', help='获取并保存当天新闻，输出 Agent 上下文 JSON')
    news.add_argument('--refresh', action='store_true')
    ctx = sub.add_parser('context', help='读取今日新闻、完整昨日报告和历史，不调用外部服务')
    ctx.add_argument('--days', type=int)
    save = sub.add_parser('save-report', help='保存 Agent 提供的报告与来源记录，不生成或核查内容')
    save.add_argument('--file', type=Path, required=True, help='Agent 写好的 UTF-8 报告')
    save.add_argument('--sources', type=Path, help='Agent 写好的来源 JSON')
    send = sub.add_parser('send', help='只投递已保存报告，不获取新闻或生成内容')
    send.add_argument('--dry-run', action='store_true')
    send.add_argument('--resend', action='store_true')
    show = sub.add_parser('show', help='输出已保存报告')
    resolve = sub.add_parser('resolve-delivery', help='核对不确定投递后修正状态')
    resolve.add_argument('--recipient', required=True)
    resolve.add_argument('--action', required=True, choices=['sent', 'retry'])
    for command in [news, ctx, save, send, show, resolve]:
        command.add_argument('--date', type=lambda d: date.fromisoformat(d).isoformat())
    sub.add_parser('status', help='查看最近报告与投递状态')
    history = sub.add_parser('import-history', help='导入旧 dailyNews 表')
    history.add_argument('source', type=Path)
    args = parser.parse_args(argv)
    try:
        settings = Settings.load(args.env_file, args.db)
        logs = settings.db_path.parent / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
            handlers=[logging.StreamHandler(), RotatingFileHandler(logs / 'emailbot.log',
                maxBytes=2_000_000, backupCount=5, encoding='utf-8')])
        if args.report_dir: settings = replace(settings, report_dir=args.report_dir.resolve())
        day = getattr(args, 'date', None) or today(settings)
        if args.command == 'check':
            settings.validate(args.scope)
            result = {'configured': True, 'scope': args.scope, 'timezone': settings.timezone,
                'database': str(settings.db_path), 'recipient_count': len(settings.recipients)}
        elif args.command == 'fetch': result = fetch(settings, day, refresh=args.refresh)
        elif args.command == 'save-report':
            sources = json.loads(args.sources.read_text(encoding='utf-8-sig')) if args.sources else None
            result = save_report(settings, day, args.file.read_text(encoding='utf-8-sig'), sources)
        elif args.command == 'send': result = send_report(settings, day, dry_run=args.dry_run, resend=args.resend)
        else:
            with run_lock(settings.db_path):
                store = Store(settings.db_path)
                try:
                    if args.command == 'context':
                        days = args.days or settings.history_days
                        if days < 1: raise ValueError('days 必须为正整数')
                        result = context(store, day, days)
                    elif args.command == 'status': result = store.status()
                    elif args.command == 'show':
                        record = store.get(day)
                        if not record or not record['report']: raise ValueError('该日期没有报告')
                        print(record['report'])
                        return 0
                    elif args.command == 'import-history':
                        result = {'imported_dates': store.import_history(args.source)}
                    elif args.command == 'resolve-delivery':
                        row = store.delivery(day, args.recipient)
                        if not row or row['status'] not in {'unknown', 'sending'}:
                            raise ValueError('只能人工修正 unknown/sending 状态')
                        store.finish_delivery(day, args.recipient,
                            'sent' if args.action == 'sent' else 'failed', 'manual resolution')
                        result = {'resolved': True, 'date': day, 'action': args.action}
                finally: store.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        logging.error('%s: %s', type(exc).__name__, exc)
        return 1
