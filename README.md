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
  backups/                    原始数据库、配置和迁移来源备份
main.py                       仓库快捷入口
requirements.txt              引用 Skill 的依赖清单
.env.example                  配置模板
```

实际 `.env` 和 `.venv/` 留在仓库根目录，均被 Git 忽略。Skill 是完整的可复制目录；迁移到其他 Agent 时，复制 `daily-news/` 并指定配置和数据位置。


数据库使用 `reports` 保存新闻、报告及核查来源，`deliveries` 保存投递状态，`imports` 记录历史导入。历史导入和补写报告默认不重发；旧任务的投递状态无法追溯时，不会补造成功记录。

`fetch` / `context` 默认返回报告日期前30个自然日至昨天的原始新闻、新闻元数据、报告和已保存的核查来源（`history[].research`），包括未被选入旧报告的新闻。`history_coverage` 给出本地窗口、新闻/报告天数及缺少原始新闻的日期；`HISTORY_DAYS` 或 `context --days` 可调整窗口。新闻 API 仅抓取当天，不会自动回补历史；Agent 按今日事件搜索补齐近月关键进展，说明仍存在的覆盖缺口。历史选题用于发现线索和避免重复复述，历史结论须回到来源复核。同一主题出现重要进展或反证时继续分析，并明确今日增量。

`origin` 保留历史导入来源，`report_origin` 单独记录报告来源。补写导入报告后仍需明确使用 `send --resend` 才能发送，再次导入旧数据也不会覆盖已补写的报告。旧数据库首次打开时自动补充 `report_origin`，保留原报告、来源和投递状态。

修改报告正文但未提供 `--sources` 时会清空旧来源；正文不变且未提供来源时保留已有记录。提供 `--sources` 时以新记录为准，导出的来源文件与数据库保持一致。

交接历史数据时另外携带 `data/daily-news.db`，库内已包含报告和来源；`data/reports/` 是可重新导出的文件。Git 忽略 `data/`，因此克隆仓库或只复制 Skill 目录不会携带历史数据库。目标环境自行提供 `.env` 并重建虚拟环境，原机器的 `.venv/` 和 `data/backups/` 无需复制。

## Linux 使用

需要 Python 3.10 或更新版本。在目标 Linux 机器上重新创建虚拟环境，然后安装依赖。以下仓库命令从仓库根目录执行。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# 首次部署创建配置文件，然后填写新闻和邮箱配置
test -f .env || cp .env.example .env
.venv/bin/python main.py check
```

让 Agent 阅读 [.agents/skills/daily-news/SKILL.md](.agents/skills/daily-news/SKILL.md)，或在支持 Skill 的宿主中调用 `$daily-news`。

```bash
# 获取新闻与完整历史上下文
.venv/bin/python main.py fetch
.venv/bin/python main.py context
# Agent 将报告与来源写入本次专用系统临时目录，保存成功后清理临时输入
.venv/bin/python main.py save-report --date YYYY-MM-DD --file /absolute/task-temp/report.md --sources /absolute/task-temp/sources.json
# 预览；不连接 SMTP
.venv/bin/python main.py send --date YYYY-MM-DD --dry-run
# 已有邮件任务授权时投递
.venv/bin/python main.py send --date YYYY-MM-DD
```

直接运行 `main.py` 显示帮助。`status` 查看状态，`show --date YYYY-MM-DD` 读取报告。脚本不会自行分析或核查新闻。

新闻、报告、来源和投递状态持久化到 SQLite。`fetch` / `context` 输出在内存中处理，不另存上下文缓存；报告和来源的临时输入保存后立即清理，任务失败结束前也清理。`data/reports/` 仅保留工具导出的正式日期报告及来源文件。

定时任务中使用 Python 和脚本的绝对路径，例如 `/opt/daily-news/.venv/bin/python /opt/daily-news/main.py`。

数据库和报告的相对路径以 `.env` 所在目录为基准，默认是 `data/daily-news.db` 和 `data/reports`；环境变量优先于 `.env`。复制 Skill 后使用：

```bash
/opt/daily-news/.venv/bin/python /opt/agent/skills/daily-news/scripts/news.py --env-file /opt/daily-news/.env check
```

`DAILY_NEWS_HOME` 可指定默认配置目录；未指定时，仓库内使用根目录，独立 Skill 使用自身目录。

## 投递与定时运行

邮件发送前使用 `markdown-it-py` 将已保存的 Markdown 转为 HTML，支持标题、加粗、列表、引用、表格、代码、图片和来源链接，采用单栏布局和内联样式。正文使用 `multipart/alternative`，同时包含 UTF-8 的 `text/plain` 原文与 `text/html` 排版版本；QQ 邮箱网页版和 iOS「邮件」可显示 HTML 正文。Markdown 中的原始 HTML 按文本显示，不执行其中的标签。

实现方式参考 [Python 官方邮件示例](https://docs.python.org/3/library/email.examples.html)和 [markdown-it-py 文档](https://markdown-it-py.readthedocs.io/en/latest/using.html)。客户端最终显示效果需实际试收确认。

按日期和收件人去重；成功投递的收件人默认跳过，失败重试只处理未成功者。出现投递记录后禁止修改该日期的报告、来源或新闻。导入历史报告默认不重发。

SMTP 提交后断线或记账前崩溃会留下 `unknown` / `sending`。核对实际投递后，用 `resolve-delivery --date YYYY-MM-DD --recipient address --action sent|retry` 修正。`send --resend` 仅用于明确要求重发的情况。

定时触发由宿主 Agent 负责，触发后执行 Skill 完整流程。Hermes 原有北京时间每天 12:05 的新闻任务尚未切换；迁移调度时停用该旧任务，避免重复投递。

## 验证

```bash
.venv/bin/python -B -m unittest discover -s tests -v
```

测试使用临时数据和模拟 SMTP，不提交真实邮件。
