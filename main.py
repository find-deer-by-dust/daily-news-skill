"""Repository shortcut to the daily-news Skill helpers. No automatic email action."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    script = Path(__file__).resolve().parent / '.agents/skills/daily-news/scripts/news.py'
    import sys
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name='__main__')
