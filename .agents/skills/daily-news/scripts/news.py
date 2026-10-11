"""Portable entry point for the daily-news Skill helpers."""
import sys
from emailbot.cli import cli

if __name__ == '__main__':
    raise SystemExit(cli(sys.argv[1:] or ['--help']))
