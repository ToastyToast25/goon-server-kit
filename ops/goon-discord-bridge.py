#!/usr/bin/env python3
"""Goon Discord Bridge: posts the mod's county events to a Discord webhook.

The Land of Goons: Economy mod appends one JSON line per event to
Lua/goondiscord.jsonl in the server cachedir (it cannot speak HTTP itself).
This script tails that file through docker and posts rich embeds. Pure
stdlib - no pip installs.

Setup:
  1. Discord server -> channel -> Integrations -> Webhooks -> New Webhook,
     copy the URL.
  2. Put it in discord-bridge.json next to this script (created with a
     placeholder on first run). Optional per-category webhooks let you route
     e.g. "emergency" to an announcements channel.
  3. Run it forever:  nohup ./goon-discord-bridge.py >/dev/null 2>&1 &
     and add the @reboot line from crontab.example.

State: .discord-bridge-state.json remembers the last posted seq, so restarts
never double-post and the mod's periodic feed truncation is loss-free.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "discord-bridge.json")
STATE_PATH = os.path.join(HERE, ".discord-bridge-state.json")
PLACEHOLDER = "PASTE_WEBHOOK_URL_HERE"

DEFAULT_CONFIG = {
    "webhook": PLACEHOLDER,
    "webhooks": {},          # optional per-category overrides, e.g. {"emergency": "https://..."}
    "mention": {"emergency": ""},  # e.g. {"emergency": "@here"} to ping on overrides
    "disabled": [],          # categories to drop entirely, e.g. ["contracts"]
    "container": "YOUR_CONTAINER_ID",
    "feed_path": "/home/container/.cache/Lua/goondiscord.jsonl",
    "poll_seconds": 10,
    "server_name": "Land of Goons",
}

COLORS = {
    "emergency": 0xD9432B, "war": 0xE67E22, "bounty": 0xD4A017,
    "lottery": 0x58A93A, "casino": 0x8E5FBF, "season": 0x3E7BC4,
    "faction": 0x2E9E8F, "cred": 0xEDEDE3, "dispatch": 0x8A8A82,
    "contracts": 0x6B7C8C,
}
EMOJI = {
    "emergency": "\U0001F6A8", "war": "⚔️", "bounty": "\U0001F480",
    "lottery": "\U0001F3AB", "casino": "\U0001F3B0", "season": "\U0001F3C6",
    "faction": "\U0001F3F4", "cred": "\U0001F396️", "dispatch": "\U0001F4FB",
    "contracts": "\U0001F4CB",
}


def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg, flush=True)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        log(f"wrote starter config to {CONFIG_PATH} - paste your webhook URL there")
    with open(CONFIG_PATH) as f:
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(json.load(f))
        return cfg


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"last_seq": 0}


def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)


def read_feed(cfg):
    """The whole feed file (the mod truncates it periodically, so it stays small)."""
    try:
        out = subprocess.run(
            ["docker", "exec", cfg["container"], "cat", cfg["feed_path"]],
            capture_output=True, text=True, timeout=20)
        if out.returncode != 0:
            return []
        events = []
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if isinstance(e.get("seq"), int) and e.get("text"):
                    events.append(e)
            except json.JSONDecodeError:
                continue
        return events
    except Exception as exc:
        log(f"feed read failed: {exc}")
        return []


def post(url, payload):
    """One webhook POST with Discord 429 handling. Returns True on success."""
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json",
                                     "User-Agent": "goon-discord-bridge/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15):
                return True
        except urllib.error.HTTPError as err:
            if err.code == 429:
                try:
                    retry = float(json.loads(err.read()).get("retry_after", 2))
                except Exception:
                    retry = 2.0
                time.sleep(min(retry + 0.5, 30))
                continue
            log(f"webhook HTTP {err.code}: {err.read()[:200]!r}")
            return False
        except Exception as exc:
            log(f"webhook error (attempt {attempt + 1}): {exc}")
            time.sleep(5)
    return False


def make_embed(cfg, event):
    cat = event.get("cat", "dispatch")
    text = str(event.get("text", ""))[:3900]
    embed = {
        "description": f"{EMOJI.get(cat, '')} {text}".strip(),
        "color": COLORS.get(cat, 0x8A8A82),
        "footer": {"text": f"{cfg['server_name']} • {cat}"},
    }
    ts = event.get("ts")
    if isinstance(ts, (int, float)) and ts > 0:
        embed["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    return embed


def deliver(cfg, events):
    """Group new events per destination webhook, 10 embeds per POST."""
    ok_all = True
    by_url = {}
    for e in events:
        cat = e.get("cat", "dispatch")
        if cat in cfg["disabled"]:
            continue
        url = cfg["webhooks"].get(cat) or cfg["webhook"]
        if not url or url == PLACEHOLDER:
            continue
        by_url.setdefault(url, []).append(e)
    for url, evs in by_url.items():
        for i in range(0, len(evs), 10):
            chunk = evs[i:i + 10]
            payload = {"embeds": [make_embed(cfg, e) for e in chunk]}
            mentions = {cfg["mention"].get(e.get("cat", ""), "") for e in chunk}
            mentions.discard("")
            if mentions:
                payload["content"] = " ".join(sorted(mentions))
            if not post(url, payload):
                ok_all = False
            time.sleep(0.5)  # stay far under Discord's per-webhook rate limit
    return ok_all


def main():
    cfg = load_config()
    state = load_state()
    warned_placeholder = 0.0
    log(f"bridge up - container {cfg['container']}, poll {cfg['poll_seconds']}s, "
        f"last seq {state['last_seq']}")
    while True:
        try:
            cfg = load_config()  # hot-reload so webhook pasting needs no restart
            events = read_feed(cfg)
            if events and max(e["seq"] for e in events) < state["last_seq"]:
                # seq went backwards: the world (and its ModData) was reset
                log("feed seq reset detected - starting cursor over")
                state["last_seq"] = 0
            fresh = [e for e in events if e["seq"] > state["last_seq"]]
            if fresh:
                fresh.sort(key=lambda e: e["seq"])
                if cfg["webhook"] == PLACEHOLDER and not cfg["webhooks"]:
                    # no destination yet: advance the cursor (don't flood later)
                    if time.time() - warned_placeholder > 600:
                        warned_placeholder = time.time()
                        log(f"{len(fresh)} event(s) skipped - webhook not configured "
                            f"in {CONFIG_PATH}")
                    state["last_seq"] = fresh[-1]["seq"]
                    save_state(state)
                elif deliver(cfg, fresh):
                    state["last_seq"] = fresh[-1]["seq"]
                    save_state(state)
                # on delivery failure: cursor stays, next poll retries
        except Exception as exc:
            log(f"loop error: {exc}")
        time.sleep(cfg["poll_seconds"])


if __name__ == "__main__":
    main()
