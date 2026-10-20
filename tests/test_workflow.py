from dataclasses import replace
from contextlib import closing
from datetime import datetime
from email import policy
from email.parser import BytesParser
import json
import os
from pathlib import Path
import smtplib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/daily-news/scripts'))
from dailyNews.delivery import Delivery
from dailyNews.news import NewsClient
from dailyNews.settings import Settings
from dailyNews.store import Store, run_lock
from dailyNews.workflow import context, fetch, save_report, send_report


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
        self.assertEqual(result['history_coverage'],{
            'start_date':'2026-08-02','end_date':'2026-08-31',
            'news_days':30,'report_days':30,'missing_news_dates':[]})

    def test_history_includes_unselected_news_and_verification_sources(self):
        metadata={'url':'https://example.com/raw','date':'2026-08-30'}
        research={'sources':[{'url':'https://example.com/release','claim':'历史事件事实'}],
                  'limitations':['历史判断仍需复核']}
        self.store.save_news('2026-08-30','政策新闻；未被选入报告的产业新闻',metadata)
        self.store.save_report('2026-08-30','只分析政策新闻',research)
        self.store.save_news('2026-08-31','尚未生成报告的新闻',{})
        result=context(self.store,'2026-09-01',2)
        self.assertEqual([r['date'] for r in result['history']],['2026-08-31','2026-08-30'])
        recent,earlier=result['history']
        self.assertEqual(earlier['news'],'政策新闻；未被选入报告的产业新闻')
        self.assertEqual(earlier['news_metadata'],metadata)
        self.assertEqual(earlier['research'],research)
        self.assertEqual(recent['news'],'尚未生成报告的新闻')
        self.assertEqual(recent['report'],'')
        self.assertEqual(recent['research'],[])
        self.assertEqual(result['yesterday_report'],'')
        # Context parsing must not alter the persisted source records.
        self.assertEqual(json.loads(self.store.get('2026-08-30')['research']),research)

    def test_history_coverage_reports_gaps_instead_of_assuming_full_month(self):
        self.store.save_news('2026-08-29','窗口外新闻',{})
        self.store.save_news('2026-08-30','历史新闻',{})
        self.store.save_news('2026-08-31','',{})
        self.store.save_report('2026-08-31','仅有报告，没有原始新闻')
        self.store.save_news('2026-09-01','当日新闻',{})
        self.store.save_news('2026-09-02','未来新闻',{})
        result=context(self.store,'2026-09-01',2)
        self.assertEqual(len(result['history']),2)
        self.assertEqual(result['history_coverage'],{
            'start_date':'2026-08-30','end_date':'2026-08-31',
            'news_days':1,'report_days':1,'missing_news_dates':['2026-08-31']})
        empty=context(self.store,'2000-01-03',2)
        self.assertEqual(empty['history'],[])
        self.assertEqual(empty['history_coverage'],{
            'start_date':'2000-01-01','end_date':'2000-01-02',
            'news_days':0,'report_days':0,'missing_news_dates':['2000-01-01','2000-01-02']})

    def test_import_preserves_local_reports(self):
        legacy=self.root/'legacy.db'
        with sqlite3.connect(legacy) as c:
            c.execute('CREATE TABLE dailyNews(id,date,news,aiReply)')
            c.execute('INSERT INTO dailyNews VALUES (1,?,?,?)',(self.day,'旧新闻','旧报告'))
        self.store.import_history(legacy)
        self.assertEqual(self.store.get(self.day)['report'],'已保存报告')

    def test_fetch_cache_without_credentials_or_external_calls(self):
        with patch('dailyNews.workflow.NewsClient') as client:
            result=fetch(replace(self.settings,news_key=''),self.day)
        client.assert_not_called()
        self.assertTrue(result['cached'])
        self.assertEqual(result['news'],'今天的新闻')

    def test_fetch_saves_raw_news_and_leaves_analysis_to_agent(self):
        self.store.conn.execute('DELETE FROM reports WHERE date=?',(self.day,)); self.store.conn.commit()
        client=MagicMock(); client.fetch.return_value=('新新闻',{'date':self.day})
        with patch('dailyNews.workflow.NewsClient',return_value=client):
            result=fetch(self.settings,self.day)
        self.assertFalse(result['cached'])
        self.assertEqual(result['news'],'新新闻')
        self.assertEqual(result['saved_report'],'')
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM deliveries').fetchone()[0],0)

    def test_save_agent_report_without_semantic_checks_or_network(self):
        sources={'sources':[{'url':'https://example.com/article','claim':'Agent 已核查的说法'}]}
        with patch('dailyNews.http.requests.Session.post') as network:
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

    def test_rewriting_report_without_sources_clears_previous_sources(self):
        sources={'sources':[{'url':'https://example.com/old','claim':'旧报告事实'}]}
        save_report(self.settings,self.day,'旧报告',sources)
        result=save_report(self.settings,self.day,'新报告')
        self.assertEqual(json.loads(self.store.get(self.day)['research']),[])
        source_file=Path(result['path']).with_suffix('.sources.json')
        self.assertEqual(json.loads(source_file.read_text(encoding='utf-8')),[])
        send_report(self.settings,self.day,dry_run=True)
        self.assertEqual(json.loads(source_file.read_text(encoding='utf-8')),[])

    def test_saving_unchanged_report_without_sources_preserves_sources(self):
        sources={'sources':[{'url':'https://example.com/article','claim':'报告事实'}]}
        save_report(self.settings,self.day,'相同报告',sources)
        for delivered in (False,True):
            with self.subTest(delivered=delivered):
                if delivered:
                    self.store.begin_delivery(self.day,'one@example.com','<id@example.com>')
                result=save_report(self.settings,self.day,'相同报告')
                self.assertEqual(json.loads(self.store.get(self.day)['research']),sources)
                source_file=Path(result['path']).with_suffix('.sources.json')
                self.assertEqual(json.loads(source_file.read_text(encoding='utf-8')),sources)

    def test_save_requires_original_news(self):
        with self.assertRaisesRegex(ValueError,'先 fetch'):
            save_report(self.settings,'1999-01-01','报告')

    def test_dry_run_never_connects_smtp_or_marks_sent(self):
        with patch('dailyNews.delivery.smtplib.SMTP') as smtp:
            result=send_report(self.settings,self.day,dry_run=True)
        self.assertEqual(result['status'],'preview'); smtp.assert_not_called()
        self.assertIsNone(self.store.delivery(self.day,'one@example.com'))

    def test_send_without_report_does_not_generate_one(self):
        self.store.conn.execute("UPDATE reports SET report='' WHERE date=?",(self.day,)); self.store.conn.commit()
        with patch('dailyNews.http.requests.Session.post') as network, patch('dailyNews.delivery.smtplib.SMTP') as smtp:
            with self.assertRaisesRegex(ValueError,'Agent 分析'):
                send_report(self.settings,self.day)
        network.assert_not_called(); smtp.assert_not_called()

    def test_imported_report_is_not_resent_by_default(self):
        self.store.conn.execute("UPDATE reports SET origin='hermes' WHERE date=?",(self.day,)); self.store.conn.commit()
        with patch('dailyNews.delivery.smtplib.SMTP') as smtp:
            self.assertEqual(send_report(self.settings,self.day)['status'],'imported')
        smtp.assert_not_called()

    def test_rewritten_imported_report_requires_explicit_resend(self):
        legacy=self.root/'legacy.db'
        with closing(sqlite3.connect(legacy)) as c, c:
            c.execute('CREATE TABLE dailyNews(id,date,news,aiReply)')
            c.executemany('INSERT INTO dailyNews VALUES (?,?,?,?)',[
                (1,'2000-01-01','旧新闻','旧报告'),(2,'2000-01-02','旧新闻','')])
        self.store.import_history(legacy)
        sources={'sources':[{'url':'https://example.com/article','claim':'补写事实'}]}
        for day in ('2000-01-01','2000-01-02'):
            with self.subTest(day=day):
                save_report(self.settings,day,'补写报告',sources)
                self.assertEqual(self.store.get(day)['origin'],str(legacy.resolve()))
                with patch('dailyNews.delivery.smtplib.SMTP') as smtp:
                    result=send_report(self.settings,day)
                self.assertEqual(result['status'],'imported')
                self.assertFalse(result['email_submitted'])
                smtp.assert_not_called()
                self.assertFalse(self.store.has_delivery(day))
                server=MagicMock(); server.send_message.return_value={}
                with patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
                    result=send_report(self.settings,day,resend=True)
                self.assertEqual(result['status'],'sent')
                self.assertTrue(all(r['status']=='sent' for r in result['deliveries']))
                self.assertEqual(server.send_message.call_count,len(self.settings.recipients))

    def test_reimport_preserves_locally_edited_imported_report(self):
        legacy=self.root/'legacy.db'
        day='2000-01-01'
        with closing(sqlite3.connect(legacy)) as c, c:
            c.execute('CREATE TABLE dailyNews(id,date,news,aiReply)')
            c.execute('INSERT INTO dailyNews VALUES (1,?,?,?)',(day,'旧新闻','旧报告'))
        self.store.import_history(legacy)
        sources={'sources':[{'url':'https://example.com/article','claim':'补写事实'}]}
        save_report(self.settings,day,'补写报告',sources)
        with closing(sqlite3.connect(legacy)) as c, c:
            c.execute("UPDATE dailyNews SET aiReply='再次导入的旧报告'")
        self.store.import_history(legacy)
        record=self.store.get(day)
        self.assertEqual(record['report'],'补写报告')
        self.assertEqual(json.loads(record['research']),sources)
        with patch('dailyNews.delivery.smtplib.SMTP') as smtp:
            smtp.return_value.send_message.return_value={}
            self.assertEqual(send_report(self.settings,day)['status'],'imported')
        smtp.assert_not_called()

    def test_existing_schema_migrates_and_preserves_delivery_and_provenance(self):
        old=self.root/'old-schema.db'
        sources={'sources':[{'url':'https://example.com/old','claim':'原报告事实'}]}
        with closing(sqlite3.connect(old)) as c, c:
            c.execute('''CREATE TABLE reports (
                date TEXT PRIMARY KEY, news TEXT NOT NULL DEFAULT '',
                report TEXT NOT NULL DEFAULT '', research TEXT NOT NULL DEFAULT '[]',
                news_metadata TEXT NOT NULL DEFAULT '{}',
                origin TEXT NOT NULL DEFAULT 'local', updated_at TEXT NOT NULL)''')
            c.execute('''CREATE TABLE deliveries (
                date TEXT NOT NULL REFERENCES reports(date), recipient TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                message_id TEXT NOT NULL, error TEXT, updated_at TEXT NOT NULL,
                PRIMARY KEY (date,recipient))''')
            c.executemany('INSERT INTO reports VALUES (?,?,?,?,?,?,?)',[
                ('2000-01-01','旧新闻','旧报告',json.dumps(sources),'{}','hermes','old-stamp'),
                ('2000-01-02','本地新闻','本地报告','[]','{}','local','old-stamp')])
            c.execute('INSERT INTO deliveries VALUES (?,?,?,?,?,?,?)',
                ('2000-01-02','one@example.com','sent',1,'<old@example.com>',None,'old-stamp'))
        settings=replace(self.settings,db_path=old,report_dir=self.root/'old-reports')
        # Open twice to verify migration is safe to repeat.
        for _ in range(2):
            store=Store(old)
            try:
                record=store.get('2000-01-01')
                self.assertEqual(record['origin'],'hermes')
                self.assertEqual(record['report'],'旧报告')
                self.assertEqual(json.loads(record['research']),sources)
                self.assertEqual(store.delivery('2000-01-02','one@example.com')['status'],'sent')
            finally: store.close()
        save_report(settings,'2000-01-01','补写报告')
        with patch('dailyNews.delivery.smtplib.SMTP') as smtp:
            smtp.return_value.send_message.return_value={}
            self.assertEqual(send_report(settings,'2000-01-01')['status'],'imported')
        smtp.assert_not_called()

    def test_partial_delivery_only_retries_failed_recipient(self):
        good=MagicMock(); good.send_message.return_value={}
        bad=MagicMock(); bad.login.side_effect=smtplib.SMTPAuthenticationError(535,b'denied')
        with patch('dailyNews.delivery.smtplib.SMTP',side_effect=[good,bad]):
            with self.assertRaises(RuntimeError): Delivery(self.settings,self.store).send(self.day,'report')
        again=MagicMock(); again.send_message.return_value={}
        with patch('dailyNews.delivery.smtplib.SMTP',return_value=again) as factory:
            Delivery(self.settings,self.store).send(self.day,'report')
            factory.assert_called_once()
            self.assertEqual(again.send_message.call_args.kwargs['to_addrs'],['two@example.com'])
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['attempts'],1)
        self.assertEqual(self.store.delivery(self.day,'two@example.com')['attempts'],2)

    def test_lost_ack_blocks_blind_resend(self):
        settings=replace(self.settings,recipients=('one@example.com',))
        server=MagicMock(); server.send_message.side_effect=smtplib.SMTPServerDisconnected('lost ack')
        with patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
            with self.assertRaises(RuntimeError): Delivery(settings,self.store).send(self.day,'report')
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['status'],'unknown')
        with patch('dailyNews.delivery.smtplib.SMTP') as factory:
            with self.assertRaises(RuntimeError): Delivery(settings,self.store).send(self.day,'report',resend=True)
            factory.assert_not_called()

    def test_new_delivery_uses_daily_news_message_id(self):
        settings=replace(self.settings,recipients=('one@example.com',))
        server=MagicMock(); server.send_message.return_value={}
        with patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
            Delivery(settings,self.store).send(self.day,'report')
        message_id=str(server.send_message.call_args.args[0]['Message-ID'])
        self.assertTrue(message_id.startswith('<daily-news.'))
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['message_id'],message_id)

    def test_send_report_submits_utf8_plain_and_html_alternatives(self):
        report='# 中文早报\n\n## 今日摘要\n\n- **重要消息** [来源](https://example.com/news)\n'
        save_report(self.settings,self.day,report)
        server=MagicMock(); server.send_message.return_value={}
        with patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
            result=send_report(self.settings,self.day)
        self.assertEqual(result['status'],'sent')
        self.assertEqual(server.send_message.call_count,2)
        for call in server.send_message.call_args_list:
            message=BytesParser(policy=policy.default).parsebytes(call.args[0].as_bytes())
            self.assertEqual(message.get_content_type(),'multipart/alternative')
            parts=list(message.iter_parts())
            self.assertEqual([p.get_content_type() for p in parts],['text/plain','text/html'])
            self.assertTrue(all(p.get_content_charset()=='utf-8' for p in parts))
            self.assertEqual(parts[0].get_content(),report)
            self.assertIn('中文早报',parts[1].get_content())
            self.assertIn('<h1 style=',parts[1].get_content())
            self.assertIn('href="https://example.com/news"',parts[1].get_content())
            self.assertEqual(str(message['To']),call.kwargs['to_addrs'][0])

    def test_render_failure_does_not_connect_or_create_delivery(self):
        with patch('dailyNews.delivery.render_report_html',side_effect=ValueError('render failed')):
            with patch('dailyNews.delivery.smtplib.SMTP') as smtp:
                with self.assertRaisesRegex(ValueError,'render failed'):
                    Delivery(self.settings,self.store).send(self.day,'report')
        smtp.assert_not_called()
        self.assertFalse(self.store.has_delivery(self.day))

    def test_retry_preserves_previously_stored_message_id(self):
        settings=replace(self.settings,recipients=('one@example.com',))
        message_id='<historical-message@example.com>'
        self.store.begin_delivery(self.day,'one@example.com',message_id)
        self.store.finish_delivery(self.day,'one@example.com','failed')
        server=MagicMock(); server.send_message.return_value={}
        with patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
            Delivery(settings,self.store).send(self.day,'report')
        self.assertEqual(str(server.send_message.call_args.args[0]['Message-ID']),message_id)
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['message_id'],message_id)

    def test_quit_failure_does_not_undo_acceptance(self):
        settings=replace(self.settings,recipients=('one@example.com',))
        server=MagicMock(); server.send_message.return_value={}
        server.quit.side_effect=smtplib.SMTPServerDisconnected('quit failed')
        with patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
            Delivery(settings,self.store).send(self.day,'report')
        self.assertEqual(self.store.delivery(self.day,'one@example.com')['status'],'sent')

    def test_send_only_needs_mail_credentials(self):
        server=MagicMock(); server.send_message.return_value={}
        with patch('dailyNews.workflow.NewsClient') as news, patch('dailyNews.delivery.smtplib.SMTP',return_value=server):
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
        self.assertEqual(settings.db_path,self.root/'data/daily-news.db')
        self.assertEqual(settings.report_dir,self.root/'data/reports')

    def test_email_recipient_parses_multiple_addresses_and_ignores_users(self):
        env=self.root/'.env'
        env.write_text('EMAIL_RECIPIENT= one@example.com, ,two@example.com,one@example.com,\n'
                       'USERS=not-json\n',encoding='utf-8')
        with patch.dict('os.environ',{'USERS':'["ignored@example.com"]'},clear=True):
            settings=Settings.load(env)
        self.assertEqual(settings.recipients,('one@example.com','two@example.com'))

    def test_users_cannot_replace_missing_email_recipient(self):
        env=self.root/'.env'
        for recipient in ('','EMAIL_RECIPIENT=\n','EMAIL_RECIPIENT=   \n'):
            with self.subTest(recipient=recipient):
                env.write_text('NEWS_API_KEY=test-news\nEMAIL_ADDRESS=bot@example.com\n'
                               'EMAIL_PASSWORD=test-password\nUSERS=["old@example.com"]\n'
                               +recipient,encoding='utf-8')
                with patch.dict('os.environ',{'USERS':'["ignored@example.com"]'},clear=True):
                    settings=Settings.load(env)
                settings.validate('fetch')
                with self.assertRaisesRegex(ValueError,'^缺少配置: EMAIL_RECIPIENT$'):
                    settings.validate('send')

    def test_daily_news_home_locates_config_from_another_directory(self):
        env=self.root/'.env'
        env.write_text('NEWS_API_KEY=test-news\nEMAIL_ADDRESS=bot@example.com\nEMAIL_PASSWORD=test-password\nEMAIL_RECIPIENT=one@example.com\n',encoding='utf-8')
        variables={**os.environ,'DAILY_NEWS_HOME':str(self.root),
                   'SQLITE_DB_PATH':'data/daily-news.db','PYTHONIOENCODING':'utf-8'}
        script=Path(__file__).resolve().parents[1]/'main.py'
        result=subprocess.run([sys.executable,'-B',str(script),'check'],
                              cwd=self.root,env=variables,capture_output=True,encoding='utf-8',check=True)
        configured=json.loads(result.stdout)
        self.assertTrue(configured['configured'])
        self.assertEqual(Path(configured['database']),self.root/'data/daily-news.db')
        self.assertTrue((self.root/'data/logs/daily-news.log').is_file())


if __name__=='__main__': unittest.main()
