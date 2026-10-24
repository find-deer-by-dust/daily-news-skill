# Daily News

每日新闻 Skill：Agent 获取今日新闻，结合近一个月相关新闻还原事件脉络，分析驱动逻辑、影响路径与后续发展，使用自己的搜索能力核查和写作，再保存报告并完成已授权的邮件投递。Python 工具负责新闻 API、SQLite、文件和 SMTP；配置中只需要新闻和邮箱凭据。

## 结构

```text
.agents/skills/daily-news/
  SKILL.md                    Agent 工作流程
  agents/openai.yaml          Skill 展示信息
  references/report-guide.md  报告和来源要求
  scripts/news.py             工具入口
  scripts/requirements.txt    唯一的依赖版本清单
  scripts/dailyNews/          新闻、存储和邮件实现
tests/                        临时数据库和模拟 SMTP 测试
data/                         本地运行数据，Git 忽略
  daily-news.db               新闻、报告和投递状态
  reports/                    报告及来源文件
  logs/                       运行日志
  backups/                    数据库快照（迁移前自动创建，也可手动创建）
main.py                       仓库快捷入口
requirements.txt              引用 Skill 的依赖清单
.env.example                  配置模板
```

实际 `.env` 和 `.venv/` 留在仓库根目录，均被 Git 忽略。Skill 是完整的可复制目录；迁移到其他 Agent 时，复制 `daily-news/` 并指定配置和数据位置。

收件人使用 `EMAIL_RECIPIENT` 配置，多个邮箱用英文逗号分隔，例如 `EMAIL_RECIPIENT=a@example.com,b@example.com`。发送邮件时该项不能为空。


数据库使用 `reports` 保存新闻、报告及核查来源，`deliveries` 保存投递状态，`imports` 记录历史导入。历史导入和补写报告默认不重发；旧任务的投递状态无法追溯时，不会补造成功记录。

`fetch` / `context` 默认返回今日新闻、已保存的当日报告、完整昨日报告，以及报告日期前30个自然日至昨天的历史新闻、新闻元数据和报告/来源长度索引（`report_chars` / `research_chars`），包括未被选入旧报告的新闻。历史报告和来源正文按需用 `context --history-detail full` 分页读取，默认每页3条；摘要模式默认每页30条。`--history-offset` / `--history-limit` 控制页数，`history_page.next_offset` 指出下一页，按日期倒序排列。完整模式中昨天的条目以 `report_ref: "yesterday_report"` 引用顶层昨日报告，避免重复传输。

`history_coverage` 始终统计整个历史窗口，给出新闻/报告天数及缺少原始新闻的日期；`HISTORY_DAYS` 或 `context --days` 可调整窗口。新闻 API 仅抓取当天，不会自动回补历史；Agent 按今日事件搜索补齐近月关键进展，说明仍存在的覆盖缺口。历史选题用于发现线索和避免重复复述，历史结论须回到来源复核。同一主题出现重要进展或反证时继续分析，并明确今日增量。

`origin` 保留历史导入来源，`report_origin` 单独记录报告来源。补写导入报告后仍需明确使用 `send --resend` 才能发送，再次导入旧数据也不会覆盖已补写的报告。旧数据库首次打开时自动补充 `report_origin`，保留原报告、来源和投递状态。

修改报告正文但未提供 `--sources` 时会清空旧来源；正文不变且未提供来源时保留已有记录。提供 `--sources` 时以新记录为准，导出的来源文件与数据库保持一致。

交接历史数据时另外携带 `data/daily-news.db`，库内已包含报告和来源；`data/reports/` 是可用 `export-reports` 重新导出的文件。Git 忽略 `data/`，因此克隆仓库或只复制 Skill 目录不会携带历史数据库。目标环境自行提供 `.env` 并重建虚拟环境；`data/backups/` 中的旧快照按回滚需要保留。

旧表结构升级或首次自动导入本库的 `dailyNews` 表前，工具先在数据库旁的 `backups/` 目录创建快照；备份失败则停止迁移。`backup` 可随时手动创建数据库快照，JSON 返回实际路径。快照通过 [SQLite 备份 API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup) 创建，包含已提交的 WAL 数据。新库及无需迁移的正常打开不会自动备份；没有定期或异地备份，也不自动复制 `.env`、外部历史导入来源或报告文件。

## Linux 使用

需要 Python 3.10 或更新版本。在目标 Linux 机器上重新创建虚拟环境，然后安装依赖。以下仓库命令从仓库根目录执行。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# 首次部署创建配置文件，然后填写新闻和邮箱配置
test -f .env || cp .env.example .env
chmod 600 .env
.venv/bin/python main.py check
```

让 Agent 阅读 [.agents/skills/daily-news/SKILL.md](.agents/skills/daily-news/SKILL.md)，或在支持 Skill 的宿主中调用 `$daily-news`。

```bash
# 获取新闻与历史索引；按需分页读取历史报告和来源
.venv/bin/python main.py fetch
.venv/bin/python main.py context
.venv/bin/python main.py context --history-detail full --history-offset 0 --history-limit 3
# Agent 将报告与来源写入本次专用系统临时目录，保存成功后清理临时输入
.venv/bin/python main.py save-report --date YYYY-MM-DD --file /absolute/task-temp/report.md --sources /absolute/task-temp/sources.json
# 预览数据库中的报告及来源；不连接 SMTP，不创建或改写导出文件
.venv/bin/python main.py send --date YYYY-MM-DD --dry-run
# 已有邮件任务授权时投递
.venv/bin/python main.py send --date YYYY-MM-DD
# 手动备份当前数据库；建议在历史导入前执行
.venv/bin/python main.py backup
# 旧库须含 dailyNews(id,date,news,aiReply) 表，来源只读
.venv/bin/python main.py import-history /absolute/path/legacy.db
# 重新导出全部非空报告及来源，也可指定包含首尾日期的范围
.venv/bin/python main.py export-reports
.venv/bin/python main.py export-reports --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

直接运行 `main.py` 显示帮助。`status` 查看状态，`show --date YYYY-MM-DD` 读取报告。脚本不会自行分析或核查新闻。

`import-history` 合并旧库同一日期的非空新闻和报告，保留本地生成、补写或已有投递记录的内容，不修改来源库、不导入旧投递状态。重复执行可安全合并；`imported_dates` 表示本次处理的日期数。`export-reports` 以数据库为准覆盖所选日期的 `.md` 和 `.sources.json`，跳过没有报告的日期，返回 `exported_count` 和 `dates`；不会发邮件或改写投递记录。

新闻、报告、来源和投递状态持久化到 SQLite。`fetch` / `context` 输出在内存中处理，不另存上下文缓存；报告和来源的临时输入保存后立即清理，任务失败结束前也清理。`data/reports/` 仅保留工具导出的正式日期报告及来源文件。

定时任务中使用 Python 和脚本的绝对路径，例如 `/opt/daily-news/.venv/bin/python /opt/daily-news/main.py`。

数据库和报告的相对路径以 `.env` 所在目录为基准，默认是 `data/daily-news.db` 和 `data/reports`；环境变量优先于 `.env`。复制 Skill 后使用：

```bash
/opt/daily-news/.venv/bin/python /opt/agent/skills/daily-news/scripts/news.py --env-file /opt/daily-news/.env check
# 全局参数放在子命令之前
/opt/daily-news/.venv/bin/python /opt/agent/skills/daily-news/scripts/news.py --env-file /opt/daily-news/.env --db data/archive.db --report-dir /opt/daily-news/exports export-reports
```

| 全局参数 | 含义与路径基准 |
| --- | --- |
| `--env-file PATH` | 指定配置文件，优先于默认入口和 `DAILY_NEWS_HOME`；相对路径基于当前工作目录 |
| `--db PATH` | 覆盖数据库位置；相对路径基于 `.env` 所在目录 |
| `--report-dir PATH` | 覆盖导出目录；相对路径基于当前工作目录。配置项 `REPORT_DIR` 的相对路径仍基于 `.env` 所在目录 |

`DAILY_NEWS_HOME` 可指定默认配置目录；未指定时，仓库快捷入口 `main.py` 使用仓库根目录，直接运行 Skill 的 `scripts/news.py` 使用 Skill 自身目录，包括安装在 `~/.agents/skills/daily-news/` 下的情况。`--env-file` 始终优先。

JSON 输出在当前终端编码无法表示部分字符时使用 ASCII 转义，`json.loads` 可完整还原中文和 emoji；UTF-8 终端仍直接显示原文。`show` 的纯文本输出将无法编码的字符显示为反斜杠转义。详见 [Python JSON 编码说明](https://docs.python.org/3/library/json.html#json.dump)。

Linux 的 `.env` 应仅供运行账户读写（`chmod 600`）；Windows 使用 [文件 ACL](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls) 限制访问，`chmod` 无法替代 Windows ACL。配置中的 `HTTP_TIMEOUT`（秒）同时用于新闻 HTTP 请求和 SMTP 连接。

## 投递与定时运行

邮件发送前使用 `markdown-it-py` 将已保存的 Markdown 转为 HTML，支持标题、加粗、列表、引用、表格、代码、图片和来源链接，采用单栏布局和内联样式。正文使用 `multipart/alternative`，同时包含 UTF-8 的 `text/plain` 原文与 `text/html` 排版版本；QQ 邮箱网页版和 iOS「邮件」可显示 HTML 正文。Markdown 中的原始 HTML 按文本显示，不执行其中的标签。

实现方式参考 [Python 官方邮件示例](https://docs.python.org/3/library/email.examples.html)和 [markdown-it-py 文档](https://markdown-it-py.readthedocs.io/en/latest/using.html)。客户端最终显示效果需实际试收确认。

按日期和收件人去重；成功投递的收件人默认跳过，失败重试只处理未成功者。仅有 `failed` 投递记录时允许修改报告、来源或刷新新闻后重试；任何收件人已成功或仍为 `unknown` / `sending` 时锁定该日期内容。成功时间 `sent_at` 会保留，后续重发失败也不会解锁；旧库自动迁移现有 `sent` 记录的成功时间。导入历史报告默认不重发。

`send` 成功返回本次的 `accepted_count`、`skipped_count` 和 `email_submitted`。全部跳过时为 `status: "skipped"`、`email_submitted: false`；本次至少一封获 SMTP 接受且没有失败时为 `status: "sent"`、`email_submitted: true`。部分跳过、部分发送的数量分别统计；`deliveries` 保留各收件人的持久化状态。`sent` 只说明 SMTP 已接受，收件箱是否实际收到仍需另行确认；任何失败或待确认状态继续以命令失败报告。

SMTP 提交后断线或记账前崩溃会留下 `unknown` / `sending`。核对实际投递后，用 `resolve-delivery --date YYYY-MM-DD --recipient address --action sent|retry` 修正。`send --resend` 仅用于明确要求重发的情况。

定时触发由宿主 Agent 负责，触发后执行 Skill 完整流程。

## 验证

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

测试使用临时数据和模拟 SMTP，不提交真实邮件。

## 许可证

本项目采用 [MIT License](LICENSE)。
