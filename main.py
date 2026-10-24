"""Repository shortcut to the daily-news Skill helpers. No automatic email action."""
from pathlib import Path
import os
import runpy

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    if not os.environ.get('DAILY_NEWS_HOME'):
        os.environ['DAILY_NEWS_HOME'] = str(root)
    script = root / '.agents/skills/daily-news/scripts/news.py'
    import sys
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name='__main__')
