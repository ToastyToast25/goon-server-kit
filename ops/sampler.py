#!/usr/bin/env python3
"""Player-count sampler: one row per invocation into SQLite.

Cron runs this every 10 minutes; the website chart reads the last 7 days.
A down server records -1 so outages are visible in the chart, not gaps.
"""
import sqlite3
import subprocess
import time
from pathlib import Path

DIR = Path("/opt/goon-kit/ops")
DB = DIR / "stats.sqlite"


def player_count():
    try:
        out = subprocess.run(
            ["python3", str(DIR / "rcon.py"), "players"],
            capture_output=True, text=True, timeout=20)
        first = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
        if "(" in first and ")" in first:
            return int(first.split("(")[1].split(")")[0])
    except Exception:
        pass
    return -1


def main():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS samples (ts INTEGER PRIMARY KEY, players INTEGER)")
    con.execute("INSERT OR REPLACE INTO samples VALUES (?, ?)",
                (int(time.time()), player_count()))
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
