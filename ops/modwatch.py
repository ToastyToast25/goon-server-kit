#!/usr/bin/env python3
"""Daily mod-update watcher for the Your Server Name server.

Reads WorkshopItems= from the live ini, asks Steam for each item's
time_updated, and diffs against the last snapshot. Changes land in
ops.log and updates.log so a breaking mod update is never a surprise.
Unlisted items return result=9 from the anonymous API - tracked as
'unqueryable', not treated as changed.
"""
import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path("/opt/goon-kit/ops")
SNAP = DIR / "modwatch-snapshot.json"
LOG = DIR / "ops.log"
UPDATES = DIR / "updates.log"
CONTAINER = "YOUR_CONTAINER_ID"
API = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"


def log(msg):
    stamp = time.strftime("%F %T")
    with LOG.open("a") as f:
        f.write(f"{stamp} modwatch: {msg}\n")


def installed_ids():
    out = subprocess.run(
        ["docker", "exec", CONTAINER, "grep", "-E", "^WorkshopItems=",
         "/home/container/.cache/Server/YOUR_SERVER_NAME.ini"],
        capture_output=True, text=True, timeout=30)
    line = out.stdout.strip()
    if "=" not in line:
        raise SystemExit("could not read WorkshopItems from ini")
    return [i for i in line.split("=", 1)[1].split(";") if i]


def fetch_details(ids):
    data = {"itemcount": str(len(ids))}
    for n, i in enumerate(ids):
        data[f"publishedfileids[{n}]"] = i
    req = urllib.request.Request(API, urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.load(resp)["response"]["publishedfiledetails"]


def main():
    ids = installed_ids()
    current, unqueryable = {}, []
    for chunk_start in range(0, len(ids), 100):
        for f in fetch_details(ids[chunk_start:chunk_start + 100]):
            pid = f["publishedfileid"]
            if f.get("result") != 1:
                unqueryable.append(pid)
                continue
            current[pid] = {
                "updated": int(f.get("time_updated", 0)),
                "title": f.get("title", "?")[:60],
            }
    old = json.loads(SNAP.read_text()) if SNAP.exists() else {}
    changed = []
    for pid, info in current.items():
        prev = old.get(pid)
        if prev and info["updated"] > prev["updated"]:
            changed.append((pid, info["title"]))
    SNAP.write_text(json.dumps(current, indent=0))
    if changed:
        stamp = time.strftime("%F %T")
        with UPDATES.open("a") as f:
            for pid, title in changed:
                f.write(f"{stamp} UPDATED {pid} {title}\n")
        log(f"{len(changed)} mod(s) updated on the workshop: "
            + ", ".join(t for _, t in changed[:6])
            + (" ..." if len(changed) > 6 else ""))
    else:
        log(f"checked {len(current)} items, no updates"
            + (f" ({len(unqueryable)} unqueryable/unlisted)" if unqueryable else ""))


if __name__ == "__main__":
    main()
