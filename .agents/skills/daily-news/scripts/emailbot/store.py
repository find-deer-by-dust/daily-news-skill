from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3


def stamp():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def run_lock(db_path):
    """OS-held lock releases automatically after a crash, including on Windows."""
    path = Path(str(db_path) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if __import__('os').name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('已有任务在运行，请稍后重试') from None
        try:
            yield
        finally:
            handle.seek(0)
            if __import__('os').name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
        legacy = self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='dailyNews'").fetchone()
        if legacy and not self.conn.execute("SELECT 1 FROM imports WHERE source='local-legacy'").fetchone():
            self._import_rows(self.conn.execute('SELECT date,news,aiReply FROM dailyNews ORDER BY id'),
                              'local-legacy')

    def close(self):
        self.conn.close()

    def get(self, day):
        row = self.conn.execute('SELECT * FROM reports WHERE date=?', (day,)).fetchone()
        return dict(row) if row else None

    def save_news(self, day, news, metadata):
        with self.conn:
            self.conn.execute('''INSERT INTO reports(date,news,news_metadata,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(date) DO UPDATE SET news=excluded.news,
                news_metadata=excluded.news_metadata,updated_at=excluded.updated_at''',
                (day, news, json.dumps(metadata, ensure_ascii=False), stamp()))

    def save_report(self, day, text, sources=None):
        with self.conn:
            self.conn.execute("UPDATE reports SET report=?,origin='local',updated_at=? WHERE date=?",
                              (text, stamp(), day))
            if sources is not None:
                self.conn.execute('UPDATE reports SET research=? WHERE date=?',
                                  (json.dumps(sources, ensure_ascii=False), day))

    def history(self, day, days=30):
        cutoff = (date.fromisoformat(day) - timedelta(days=days)).isoformat()
        return [dict(row) for row in self.conn.execute(
            'SELECT date,news,report FROM reports WHERE date>=? AND date<? ORDER BY date DESC',
            (cutoff, day))]

    def delivery(self, day, recipient):
        row = self.conn.execute('SELECT * FROM deliveries WHERE date=? AND recipient=?',
                                (day, recipient)).fetchone()
        return dict(row) if row else None

    def begin_delivery(self, day, recipient, message_id):
        with self.conn:
            self.conn.execute('''INSERT INTO deliveries
                (date,recipient,status,attempts,message_id,updated_at) VALUES (?,?,'sending',1,?,?)
                ON CONFLICT(date,recipient) DO UPDATE SET status='sending',attempts=attempts+1,
                error=NULL,updated_at=excluded.updated_at''', (day, recipient, message_id, stamp()))

    def finish_delivery(self, day, recipient, status, error=None):
        with self.conn:
            self.conn.execute('UPDATE deliveries SET status=?,error=?,updated_at=? WHERE date=? AND recipient=?',
                              (status, error, stamp(), day, recipient))

    def has_delivery(self, day):
        return self.conn.execute('SELECT 1 FROM deliveries WHERE date=?', (day,)).fetchone() is not None

    def import_history(self, source):
        source = Path(source).resolve()
        if source == self.path.resolve():
            raise ValueError('不能从当前数据库导入自身')
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as old:
            old.row_factory = sqlite3.Row
            rows = old.execute('SELECT date,news,aiReply FROM dailyNews ORDER BY id').fetchall()
        return self._import_rows(rows, str(source))

    def _import_rows(self, rows, source):
        # Legacy fetch + delivery can create multiple rows. Merge nonempty fields.
        grouped = {}
        for row in rows:
            day = date.fromisoformat(row['date']).isoformat()
            record = grouped.setdefault(day, {'news': '', 'report': ''})
            if row['news']: record['news'] = row['news']
            if row['aiReply']: record['report'] = row['aiReply']
        count = 0
        with self.conn:
            for day, record in grouped.items():
                current = self.get(day)
                # Preserve reports generated or delivered by this project.
                if current and (current['origin'] == 'local' or self.has_delivery(day)):
                    continue
                self.conn.execute('''INSERT INTO reports(date,news,report,origin,updated_at)
                    VALUES (?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET
                    news=CASE WHEN excluded.news!='' THEN excluded.news ELSE reports.news END,
                    report=CASE WHEN excluded.report!='' THEN excluded.report ELSE reports.report END,
                    origin=excluded.origin,updated_at=excluded.updated_at''',
                    (day, record['news'], record['report'], source, stamp()))
                count += 1
            self.conn.execute('INSERT OR REPLACE INTO imports VALUES (?,?)', (source, stamp()))
        return count

    def status(self):
        return {
            'reports': [dict(r) for r in self.conn.execute(
                'SELECT date,length(news) news_chars,length(report) report_chars,origin FROM reports ORDER BY date DESC LIMIT 7')],
            'deliveries': [dict(r) for r in self.conn.execute(
                'SELECT * FROM deliveries ORDER BY updated_at DESC LIMIT 10')],
        }
