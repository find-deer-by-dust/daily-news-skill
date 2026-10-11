from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import smtplib
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/daily-news/scripts'))
from emailbot.delivery import Delivery
from emailbot.news import NewsClient
from emailbot.settings import Settings
from emailbot.store import Store, run_lock
from emailbot.workflow import context, fetch, save_report, send_report


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(
            db_path=self.root/'test.db', report_dir=self.root/'reports', timezone='Asia/Shanghai',
            news_url='https://news.invalid', news_key='test-news',
            email_address='bot@example.com', email_password='test-password',
            recipients=('one@example.com','two@example.com'),
            smtp_host='smtp.invalid', smtp_port=25, smtp_security='starttls')
        self.store = Store(self.settings.db_path)
        self.addCleanup(self.store.close)
        self.day = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        self.store.save_news(self.day,'今天的新闻',{'date':self.day})
        self.store.save_report(self.day,'已保存报告')

    def test_legacy_duplicates_merge_without_erasing_original(self):
        legacy=self.root/'legacy.db'
        with sqlite3.connect(legacy) as c:
            c.execute('CREATE TABLE dailyNews(id INTEGER PRIMARY KEY,date TEXT,news TEXT,aiReply TEXT)')
            c.executemany('INSERT INTO dailyNews VALUES (?,?,?,?)',[
                (1,'2026-10-10','原始新闻',''),(2,'2026-10-10','','完整报告'),(3,'2026-10-10','','')])
        self.store.import_history(legacy)
        self.store.import_history(legacy)
        row=self.store.get('2026-10-10')
        self.assertEqual((row['news'],row['report']),('原始新闻','完整报告'))
        self.assertEqual(self.store.conn.execute("SELECT count(*) FROM reports WHERE date='2026-10-10'").fetchone()[0],1)
        with sqlite3.connect(legacy) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM dailyNews').fetchone()[0],3)

    def test_news_refresh_preserves_report(self):
        self.store.save_news(self.day,'更新新闻',{})
        self.assertEqual(self.store.get(self.day)['report'],'已保存报告')

    def test_full_yesterday_and_thirty_natural_days(self):
        for i in range(1,32):
            day=f'2026-08-{i:02d}'
            self.store.save_news(day,f'新闻{i}',{})
            self.store.save_report(day,'昨天主题'*500)
        result=context(self.store,'2026-09-01',30)
        self.assertEqual(len(result['history']),30)
        self.assertEqual(result['history'][-1]['date'],'2026-08-02')
        self.assertEqual(len(result['yesterday_report']),2000)

    def test_import_preserves_local_reports(self):
        legacy=self.root/'legacy.db'
        with sqlite3.connect(legacy) as c:
            c.execute('CREATE TABLE dailyNews(id,date,news,aiReply)')
            c.execute('INSERT INTO dailyNews VALUES (1,?,?,?)',(self.day,'旧新闻','旧报告'))
        self.store.import_history(legacy)
        self.assertEqual(self.store.get(self.day)['report'],'已保存报告')

    def test_fetch_cache_without_credentials_or_external_calls(self):
        with patch('emailbot.workflow.NewsClient') as client:
            result=fetch(replace(self.settings,news_key=''),self.day)
        client.assert_not_called()
        self.assertTrue(result['cached'])
        self.assertEqual(result['news'],'今天的新闻')

    def test_fetch_saves_raw_news_and_leaves_analysis_to_agent(self):
        self.store.conn.execute('DELETE FROM reports WHERE date=?',(self.day,)); self.store.conn.commit()
        client=MagicMock(); client.fetch.return_value=('新新闻',{'date':self.day})
        with patch('emailbot.workflow.NewsClient',return_value=client):
            result=fetch(self.settings,self.day)
        self.assertFalse(result['cached'])
        self.assertEqual(result['news'],'新新闻')
        self.assertEqual(result['saved_report'],'')
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM deliveries').fetchone()[0],0)

    def test_save_agent_report_without_semantic_checks_or_network(self):
        sources={'sources':[{'url':'https://example.com/article','claim':'Agent 已核查的说法'}]}
        with patch('emailbot.http.requests.Session.post') as network:
            result=save_report(self.settings,self.day,'Agent 提供的简短纯文本报告',sources)
        network.assert_not_called()
        self.assertTrue(result['saved'])
        self.assertEqual(self.store.get(self.day)['report'],'Agent 提供的简短纯文本报告')
        self.assertEqual(json.loads(self.store.get(self.day)['research']),sources)
        self.assertEqual(Path(result['path']).read_text(encoding='utf-8'),'Agent 提供的简短纯文本报告')

    def test_empty_report_preserves_existing_data(self):
        with self.assertRaisesRegex(ValueError,'报告为空'):
            save_report(self.settings,self.day,'   ')
        self.assertEqual(self.store.get(self.day)['report'],'已保存报告')

    def test_save_requires_original_news(self):
        with self.assertRaisesRegex(ValueError,'先 fetch'):
            save_report(self.settings,'1999-01-01','报告')

    def test_dry_run_never_connects_smtp_or_marks_sent(self):
        with patch('emailbot.delivery.smtplib.SMTP') as smtp:
            result=send_report(self.settings,self.day,dry_run=True)
        self.assertEqual(result['status'],'preview'); smtp.assert_not_called()
        self.assertIsNone(self.store.delivery(self.day,'one@example.com'))

    def test_send_without_report_does_not_generate_one(self):
        self.store.conn.execute("UPDATE reports SET report='' WHERE date=?",(self.day,)); self.store.conn.commit()
        with patch('emailbot.http.requests.Session.post') as network, patch('emailbot.delivery.smtplib.SMTP') as smtp:
            with self.assertRaisesRegex(ValueError,'Agent 分析'):
                send_report(self.settings,self.day)
        network.assert_not_called(); smtp.assert_not_called()

    def test_imported_report_is_not_resent_by_default(self):
        self.store.conn.execute("UPDATE reports SET origin='hermes' WHERE date=?",(self.day,)); self.store.conn.commit()
        with patch('emailbot.delivery.smtplib.SMTP') as smtp:
            self.assertEqual(send_report(self.settings,self.day)['status'],'imported')
        smtp.assert_not_called()

    def test_partial_delivery_only_retries_failed_recipient(self):
        good=MagicMock(); good.send_message.return_value={}
        bad=MagicMock(); bad.login.side_effect=smtplib.SMTPAuthenticationError(535,b'denied')
        with patch('emailbot.delivery.smtplib.SMTP',side_effect=[good,bad]):
            with self.assertRaises(RuntimeError): Delivery(self.settings,self.store).send(self.day,'report')
        again=MagicMock(); again.send_message.return_value={}
        with patch('emailbot.delivery.smtplib.SMTP',return_value=again) as factory:
            Delivery(self.settings,self.store).send(self.day,'report')
            factory.assert_called_once()
            self.assertEqual(again.send_message.call_args.kwargs['to_addrs'],['two@example.com'])
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['attempts'],1)
        self.assertEqual(self.store.delivery(self.day,'two@example.com')['attempts'],2)

    def test_lost_ack_blocks_blind_resend(self):
        settings=replace(self.settings,recipients=('one@example.com',))
        server=MagicMock(); server.send_message.side_effect=smtplib.SMTPServerDisconnected('lost ack')
        with patch('emailbot.delivery.smtplib.SMTP',return_value=server):
            with self.assertRaises(RuntimeError): Delivery(settings,self.store).send(self.day,'report')
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['status'],'unknown')
        with patch('emailbot.delivery.smtplib.SMTP') as factory:
            with self.assertRaises(RuntimeError): Delivery(settings,self.store).send(self.day,'report',resend=True)
            factory.assert_not_called()

    def test_quit_failure_does_not_undo_acceptance(self):
        settings=replace(self.settings,recipients=('one@example.com',))
        server=MagicMock(); server.send_message.return_value={}
        server.quit.side_effect=smtplib.SMTPServerDisconnected('quit failed')
        with patch('emailbot.delivery.smtplib.SMTP',return_value=server):
            Delivery(settings,self.store).send(self.day,'report')
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['status'],'sent')

    def test_send_only_needs_mail_credentials(self):
        server=MagicMock(); server.send_message.return_value={}
        with patch('emailbot.workflow.NewsClient') as news, patch('emailbot.delivery.smtplib.SMTP',return_value=server):
            result=send_report(replace(self.settings,news_key=''),self.day)
        news.assert_not_called(); self.assertEqual(result['status'],'sent')

    def test_delivery_blocks_report_and_source_changes(self):
        self.store.begin_delivery(self.day,'one@example.com','<id@example.com>')
        with self.assertRaisesRegex(ValueError,'不能覆盖'):
            save_report(self.settings,self.day,'新报告')
        with self.assertRaisesRegex(ValueError,'不能覆盖'):
            save_report(self.settings,self.day,'已保存报告',{'sources':[]})
        with self.assertRaisesRegex(ValueError,'不能刷新'):
            fetch(self.settings,self.day,refresh=True)

    def test_stale_news_not_accepted(self):
        http=MagicMock(); http.post.return_value={'code':200,'data':{'date':'1999-01-01','news':['旧闻']}}
        with self.assertRaisesRegex(RuntimeError,'日期不匹配'):
            NewsClient(self.settings,http).fetch(self.day)

    def test_same_database_cannot_run_concurrently(self):
        with run_lock(self.settings.db_path):
            with self.assertRaisesRegex(RuntimeError,'已有任务'):
                with run_lock(self.settings.db_path): pass

    def test_only_news_and_mail_config_needed_and_env_precedence(self):
        env=self.root/'.env'
        env.write_text('NEWS_API_KEY=old\nEMAIL_ADDRESS=bot@example.com\nEMAIL_PASSWORD=mail-token\nEMAIL_RECIPIENT=a@example.com\n',encoding='utf-8')
        with patch.dict('os.environ',{'NEWS_API_KEY':'new'},clear=True):
            settings=Settings.load(env)
        settings.validate()
        self.assertEqual(settings.news_key,'new')
        self.assertEqual(settings.db_path,self.root/'data/emailbot.db')
        self.assertEqual(settings.report_dir,self.root/'data/reports')


if __name__=='__main__': unittest.main()
