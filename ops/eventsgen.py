#!/usr/bin/env python3
"""events.json generator for your-server-site.example.com.

Reads the weekly schedule (events-schedule.json) and the live-event log
(events-log.jsonl, written by goon-events.sh) and produces events.json with:
  - active:   events happening right now (from the log, end > now)
  - upcoming: the next occurrence of each scheduled event (computed from dow/hour)

All timestamps are absolute epoch seconds; the website computes live countdowns
client-side, so this only needs to run every few minutes (cron).
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

OPS = Path("/opt/goon-kit/ops")
WEB = Path("/opt/goon-kit/web")
SCHEDULE = OPS / "events-schedule.json"
EVLOG = OPS / "events-log.jsonl"
OUT = WEB / "events.json"

UPCOMING_LIMIT = 6
LOG_RETENTION_DAYS = 14


def load_schedule():
    data = json.loads(SCHEDULE.read_text())
    return {e["key"]: e for e in data["events"]}


def load_active(meta, now):
    """Active windows from the log: end > now, newest record per key wins."""
    if not EVLOG.exists():
        return [], []
    kept_lines, by_key = [], {}
    cutoff = now - LOG_RETENTION_DAYS * 86400
    for line in EVLOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("end", 0) < cutoff:
            continue  # prune ancient records
        kept_lines.append(line)
        if rec.get("end", 0) > now:
            by_key[rec["key"]] = rec  # newest wins (log is append-order)

    active = []
    for key, rec in by_key.items():
        m = meta.get(key)
        if not m:
            continue
        active.append({
            "key": key, "emoji": m["emoji"], "title": m["title"],
            "blurb": m["blurb"], "start": rec["start"], "end": rec["end"],
        })
    active.sort(key=lambda e: e["end"])
    return active, kept_lines


def next_occurrence(dow, hour, minute, now_dt):
    """Soonest future datetime matching weekday dow (Mon=0..Sun=6) at hour:minute."""
    for add in range(0, 8):
        cand = (now_dt + timedelta(days=add)).replace(
            hour=hour, minute=minute, second=0, microsecond=0)
        if cand.weekday() == dow and cand > now_dt:
            return cand
    return None


def schedule_active(meta, now_dt, now):
    """Events whose current scheduled window contains 'now'. Robust to a script
    that failed to record: the calendar itself decides what's live. Looks back a
    few days to cover long windows (e.g. the 60h Double Knowledge weekend)."""
    active = {}
    for key, e in meta.items():
        for add in range(-3, 1):
            cand = (now_dt + timedelta(days=add)).replace(
                hour=e["hour"], minute=e["minute"], second=0, microsecond=0)
            if cand.weekday() != e["dow"]:
                continue
            start = cand.timestamp()
            end = start + e["duration_min"] * 60
            if start <= now < end:
                active[key] = {
                    "key": key, "emoji": e["emoji"], "title": e["title"],
                    "blurb": e["blurb"], "start": int(start), "end": int(end),
                }
    return active


def build_upcoming(meta, active_keys, now_dt):
    items = []
    for key, e in meta.items():
        if key in active_keys:
            continue  # already live; don't double-list
        cand = next_occurrence(e["dow"], e["hour"], e["minute"], now_dt)
        if not cand:
            continue
        items.append({
            "key": key, "emoji": e["emoji"], "title": e["title"],
            "blurb": e["blurb"], "start": int(cand.timestamp()),
            "duration_min": e["duration_min"],
        })
    items.sort(key=lambda e: e["start"])
    return items[:UPCOMING_LIMIT]


def main():
    now = time.time()
    now_dt = datetime.now()
    meta = load_schedule()

    log_active, kept_lines = load_active(meta, now)
    merged = schedule_active(meta, now_dt, now)
    for a in log_active:
        merged[a["key"]] = a  # a real recorded window refines the calendar guess
    active = sorted(merged.values(), key=lambda e: e["end"])
    upcoming = build_upcoming(meta, set(merged.keys()), now_dt)

    OUT.write_text(json.dumps({
        "generated": int(now),
        "active": active,
        "upcoming": upcoming,
    }, indent=2))

    # Rewrite the log with only retained records (keeps the file bounded).
    if EVLOG.exists():
        EVLOG.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""))


if __name__ == "__main__":
    main()
