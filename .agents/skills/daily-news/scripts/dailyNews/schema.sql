CREATE TABLE IF NOT EXISTS reports (
    date TEXT PRIMARY KEY, news TEXT NOT NULL DEFAULT '',
    report TEXT NOT NULL DEFAULT '', research TEXT NOT NULL DEFAULT '[]',
    news_metadata TEXT NOT NULL DEFAULT '{}',
    origin TEXT NOT NULL DEFAULT 'local',
    report_origin TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
    date TEXT NOT NULL REFERENCES reports(date), recipient TEXT NOT NULL,
    status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    message_id TEXT NOT NULL, error TEXT, updated_at TEXT NOT NULL,
    PRIMARY KEY (date,recipient)
);
CREATE TABLE IF NOT EXISTS imports (
    source TEXT PRIMARY KEY, imported_at TEXT NOT NULL
);
