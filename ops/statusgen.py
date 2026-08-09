#!/usr/bin/env python3
"""status.json generator v2: live server data for your-server-site.example.com.

Pulls player count (RCON), slots/name/description (live ini), the mod list
(ini WorkshopItems joined against modwatch's cached Steam titles), and the
7-day population series. Read-only against the prod container.
"""
import json
import sqlite3
import subprocess
import time
from pathlib import Path

OPS = Path("/opt/goon-kit/ops")
WEB = Path("/opt/goon-kit/web")
CONTAINER = "YOUR_CONTAINER_ID"
INI = "/home/container/.cache/Server/YOUR_SERVER_NAME.ini"

FORK_TITLES = {
    "3780050823": "Your Server Name: Economy",
    "3780051574": "Your Server Name: Gag Emporium",
}


def rcon_players():
    try:
        out = subprocess.run(
            ["python3", str(OPS / "rcon.py"), "players"],
            capture_output=True, text=True, timeout=20)
        first = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
        if "(" in first and ")" in first:
            return int(first.split("(")[1].split(")")[0])
    except Exception:
        pass
    return -1


def ini_fields():
    fields = {}
    try:
        out = subprocess.run(
            ["docker", "exec", CONTAINER, "grep", "-E",
             "^(MaxPlayers|PublicName|PublicDescription|Mods|WorkshopItems)=", INI],
            capture_output=True, text=True, timeout=20)
        for line in out.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k] = v.strip()
    except Exception:
        pass
    return fields


def mod_titles(workshop_ids):
    snap_file = OPS / "modwatch-snapshot.json"
    snap = json.loads(snap_file.read_text()) if snap_file.exists() else {}
    titles = []
    for wid in workshop_ids:
        if wid in FORK_TITLES:
            titles.append(FORK_TITLES[wid])
        elif wid in snap:
            titles.append(snap[wid]["title"])
    # dedupe, keep order
    seen, out = set(), []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def leaderboard():
    try:
        out = subprocess.run(
            ["docker", "exec", CONTAINER, "cat", "/home/container/.cache/goonstats.json"],
            capture_output=True, text=True, timeout=20)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        stats = json.loads(out.stdout)
        players = stats.get("players", [])
        slayers = sorted(players, key=lambda p: -p.get("kills", 0))[:10]
        iron = sorted(players, key=lambda p: -p.get("hours", 0))[:10]
        return {
            "slayers": [{"name": p["name"], "kills": p.get("kills", 0)} for p in slayers if p.get("kills")],
            "iron": [{"name": p["name"], "hours": round(p.get("hours", 0), 1)} for p in iron if p.get("hours")],
        }
    except Exception:
        return None


import re


def ticker():
    """Recent county events from the user/pvp logs. Never reads
    connections.txt - that file carries IP addresses."""
    events = []
    try:
        find = subprocess.run(
            ["docker", "exec", CONTAINER, "sh", "-c",
             "ls -t /home/container/.cache/Logs/*user.txt 2>/dev/null | head -1"],
            capture_output=True, text=True, timeout=20)
        path = find.stdout.strip()
        if not path:
            return events
        out = subprocess.run(
            ["docker", "exec", CONTAINER, "tail", "-n", "300", path],
            capture_output=True, text=True, timeout=20)
        for line in out.stdout.splitlines():
            m = re.match(r"\[(\d\d)-(\d\d)-(\d\d) (\d\d:\d\d):\d\d[^\]]*\]\s*(.*)", line)
            if not m:
                continue
            mo, dy, yr, hhmm, rest = m.groups()
            when = f"20{yr}-{mo}-{dy} {hhmm}"
            m2 = re.search(r'"([^"]+)" fully connected', rest)
            if m2:
                events.append({"t": when, "text": m2.group(1) + " arrived in Knox County"})
                continue
            m2 = re.search(r"user (\S+) died at \((\d+),(\d+)", rest)
            if m2:
                events.append({"t": when, "text": m2.group(1) + " died at " + m2.group(2) + "," + m2.group(3)})
                continue
            m2 = re.search(r"user (\S+) just ate poisoned food", rest)
            if m2:
                events.append({"t": when, "text": m2.group(1) + " ate something they shouldn't have"})
    except Exception:
        pass
    return events[-12:]


def series():
    db = OPS / "stats.sqlite"
    if not db.exists():
        return []
    con = sqlite3.connect(db)
    cutoff = int(time.time()) - 7 * 86400
    rows = list(con.execute(
        "SELECT ts, players FROM samples WHERE ts > ? ORDER BY ts", (cutoff,)))
    con.close()
    step = max(1, len(rows) // 200)
    return [[r[0], r[1]] for r in rows[::step]]


def main():
    n = rcon_players()
    ini = ini_fields()
    wids = [w for w in ini.get("WorkshopItems", "").split(";") if w]
    desc = ini.get("PublicDescription", "").replace("\\n", "\n")
    payload = {
        "online": n >= 0,
        "players": max(n, 0),
        "maxSlots": int(ini.get("MaxPlayers", "70") or 70),
        "name": ini.get("PublicName", "Your Server Name"),
        "description": desc,
        "modCount": len([m for m in ini.get("Mods", "").split(";") if m]),
        "mods": mod_titles(wids),
        "ts": int(time.time()),
        "series": series(),
        "leaderboard": leaderboard(),
        "events": ticker(),
    }
    WEB.mkdir(exist_ok=True)
    tmp = WEB / "status.json.tmp"
    tmp.write_text(json.dumps(payload))
    tmp.replace(WEB / "status.json")


if __name__ == "__main__":
    main()
