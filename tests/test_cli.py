from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.agents/skills/daily-news'
sys.path.insert(0, str(SKILL / 'scripts'))

from dailyNews.cli import cli
from dailyNews.settings import Settings
from dailyNews.store import Store


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = self.root / '.env'
        self.env.write_text('HISTORY_DAYS=3\n', encoding='utf-8')
        with patch.dict(os.environ, {}, clear=True):
            self.settings = Settings.load(self.env)
        self.day = '2026-10-24'
        self.report = '中文报告 📰🔍🔗📌📋，生僻字𠮷，重音é。'
        self.store = Store(self.settings.db_path)
        self.addCleanup(self.store.close)
        for day in ('2026-10-21', '2026-10-22', '2026-10-23', self.day):
            self.store.save_news(day, '新闻📰', {'date': day})
            self.store.save_report(day, self.report, {'sources': [{'title': '来源🔗'}]})
        for mocked in (patch('dailyNews.cli.Settings.load', return_value=self.settings),
                       patch('dailyNews.cli.RotatingFileHandler'), patch('dailyNews.cli.logging.basicConfig')):
            mocked.start()
            self.addCleanup(mocked.stop)

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli(list(args))
        return code, stdout.getvalue()

    def test_context_defaults_and_explicit_window(self):
        code, output = self.run_cli('context', '--date', self.day)
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result['history_days'], 3)
        self.assertEqual(result['history_page']['detail'], 'summary')
        self.assertEqual(len(result['history']), 3)
        self.assertNotIn('report', result['history'][0])
        code, output = self.run_cli('context', '--date', self.day, '--days', '1')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['history_days'], 1)

    def test_context_full_page_arguments(self):
        code, output = self.run_cli('context', '--date', self.day, '--history-detail', 'full',
                                    '--history-offset', '1', '--history-limit', '1')
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result['history'][0]['date'], '2026-10-22')
        self.assertEqual(result['history'][0]['report'], self.report)
        self.assertEqual(result['history_page']['next_offset'], 2)
        self.assertEqual(result['history_coverage']['news_days'], 3)

    def test_invalid_numeric_values_exit_one_without_json(self):
        for option, value in (('--days', '0'), ('--days', '-5'), ('--history-limit', '0'),
                              ('--history-limit', '-1'), ('--history-offset', '-1')):
            with self.subTest(option=option, value=value), patch('dailyNews.cli.logging.error') as error:
                code, output = self.run_cli('context', option, value)
                self.assertEqual(code, 1)
                self.assertEqual(output, '')
                error.assert_called_once()

    def test_argument_errors_exit_two(self):
        for args in ([], ['unknown'], ['context', '--days', 'bad'],
                     ['context', '--date', 'bad'], ['context', '--history-detail', 'bad'],
                     ['save-report'], ['resolve-delivery', '--recipient', 'one@example.com']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli(args)
                self.assertEqual(raised.exception.code, 2)

    def test_show_success_and_missing_report_exit_codes(self):
        code, output = self.run_cli('show', '--date', self.day)
        self.assertEqual(code, 0)
        self.assertEqual(output, self.report + '\n')
        with patch('dailyNews.cli.logging.error'):
            self.assertEqual(self.run_cli('show', '--date', '1999-01-01'), (1, ''))

    def test_save_reads_utf8_bom_and_reports_invalid_sources(self):
        report, sources = self.root / 'input.md', self.root / 'sources.json'
        report.write_text(self.report + '修改', encoding='utf-8-sig')
        sources.write_text('{"sources": []}', encoding='utf-8-sig')
        code, output = self.run_cli('save-report', '--date', self.day,
                                    '--file', str(report), '--sources', str(sources))
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)['saved'])
        self.assertEqual(self.store.get(self.day)['report'], self.report + '修改')
        sources.write_text('invalid json', encoding='utf-8')
        with patch('dailyNews.cli.logging.error'):
            code, output = self.run_cli('save-report', '--date', self.day,
                                        '--file', str(report), '--sources', str(sources))
        self.assertEqual((code, output), (1, ''))

    def test_manual_retry_unlocks_failed_delivery_but_sent_resolution_locks(self):
        recipient = 'one@example.com'
        for action, locked in (('retry', False), ('sent', True)):
            with self.subTest(action=action):
                self.store.begin_delivery(self.day, recipient, '<id@example.com>')
                self.store.finish_delivery(self.day, recipient, 'unknown')
                code, output = self.run_cli('resolve-delivery', '--date', self.day,
                                            '--recipient', recipient, '--action', action)
                self.assertEqual(code, 0)
                self.assertTrue(json.loads(output)['resolved'])
                self.assertEqual(self.store.report_locked(self.day), locked)
                if not locked:
                    from dailyNews.workflow import save_report
                    save_report(self.settings, self.day, '修正报告')
        with patch('dailyNews.cli.logging.error'):
            self.assertEqual(self.run_cli('resolve-delivery', '--date', self.day,
                                          '--recipient', recipient, '--action', 'retry'), (1, ''))

    def run_process(self, args, encoding='utf-8', script=None, home=None):
        variables = {key: value for key, value in os.environ.items()
                     if key not in {'DAILY_NEWS_HOME', 'SQLITE_DB_PATH', 'DB_PATH', 'REPORT_DIR',
                                    'HISTORY_DAYS', 'NEWS_API_KEY', 'EMAIL_RECIPIENT'}}
        variables['PYTHONIOENCODING'] = encoding
        if home is not None:
            variables['DAILY_NEWS_HOME'] = str(home)
        return subprocess.run([sys.executable, '-B', str(script or ROOT / 'main.py'), *args],
                              cwd=self.root, env=variables, capture_output=True)

    def test_gbk_and_utf8_subprocess_outputs_preserve_json_values(self):
        for encoding in ('gbk', 'utf-8', 'ascii'):
            for command in (['context', '--history-detail', 'full'], ['fetch'], ['send', '--dry-run']):
                with self.subTest(encoding=encoding, command=command):
                    result = self.run_process(['--env-file', str(self.env), *command, '--date', self.day], encoding)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = json.loads(result.stdout.decode(encoding))
                    field = 'report' if command[0] == 'send' else 'saved_report'
                    self.assertEqual(data[field], self.report)

    def test_gbk_show_does_not_crash_and_database_keeps_unicode(self):
        result = self.run_process(['--env-file', str(self.env), 'show', '--date', self.day], 'gbk')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('中文报告', result.stdout.decode('gbk'))
        self.assertIn('\\U0001f4f0', result.stdout.decode('gbk'))
        self.assertEqual(self.store.get(self.day)['report'], self.report)

    def test_portable_skill_in_agents_uses_own_config_and_honors_overrides(self):
        portable = self.root / 'home/.agents/skills/daily-news'
        shutil.copytree(SKILL, portable, ignore=shutil.ignore_patterns('__pycache__'))
        (portable / '.env').write_text('NEWS_API_KEY=own-config\n', encoding='utf-8')
        (self.root / 'home/.env').write_text('SQLITE_DB_PATH=wrong-home.db\n', encoding='utf-8')
        script = portable / 'scripts/news.py'
        for args, home, expected in ((['check', '--scope', 'fetch'], None, portable / 'data/daily-news.db'),
                                      (['--env-file', str(self.env), 'status'], None, self.settings.db_path),
                                      (['status'], self.root, self.settings.db_path)):
            with self.subTest(args=args, home=home):
                result = self.run_process(args, script=script, home=home)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                if args[0] == 'check':
                    self.assertEqual(Path(data['database']), expected)
                else:
                    self.assertEqual(data['reports'][0]['date'], self.day)
        self.assertFalse((self.root / 'home/wrong-home.db').exists())

    def test_repository_entry_uses_root_unless_home_is_overridden(self):
        # Load just settings in a subprocess; no production database is opened.
        code = f'''import runpy
from unittest.mock import patch
launch = runpy.run_path
with patch('runpy.run_path'):
    launch({str(ROOT / 'main.py')!r}, run_name='__main__')
from dailyNews.settings import ROOT
print(ROOT)
'''
        variables = {key: value for key, value in os.environ.items() if key != 'DAILY_NEWS_HOME'}
        variables['PYTHONIOENCODING'] = 'utf-8'
        for home, expected in ((None, ROOT), (self.root, self.root)):
            with self.subTest(home=home):
                env = dict(variables)
                if home is not None:
                    env['DAILY_NEWS_HOME'] = str(home)
                result = subprocess.run([sys.executable, '-B', '-c', code], cwd=self.root,
                                        env=env, capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(result.stdout.strip()), expected)


if __name__ == '__main__':
    unittest.main()
