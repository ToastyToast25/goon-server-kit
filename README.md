# Goon Server Kit

Host-side companion for the **Land of Goons: Economy** Project Zomboid mod
([Steam Workshop 3780050823](https://steamcommunity.com/sharedfiles/filedetails/?id=3780050823)). The mod gives your server the in-game platform -
economy, bounties, casino, contracts, territory war, radio. This kit runs ON
YOUR HOST and adds the parts a mod can't: a live status website, scheduled
world events with creepy announcements, automated restarts, and in-game tips.

Everything is a template: search for `YOUR_` placeholders and fill in your
own values. Nothing here contains our server's secrets - or yours, until you
add them. **Never commit your filled-in secrets to a public repo** (see below).

## What's inside

| Path | What it does |
|---|---|
| `ops/rcon.py` | Minimal Source-RCON client the other scripts use. Set `YOUR_RCON_PASSWORD` and `YOUR_CONTAINER_ID` (or replace `container_ip()` with your server's IP if you don't run Docker/Pelican). |
| `ops/goon-ops.sh` | Toolkit: rotating in-game tips (`tips.txt`), daily restart with player countdown, Siren Saturday event. |
| `ops/goon-events.sh` | The live-events engine: Blood Moon, Knox Fog, The Gathering, Bandit Siege, Wanted, Supply Drop, The Peddler, The Purge, Double XP weekend. Each event = escalating announcements + real RCON atmosphere (sirens, gunshots, chopper, weather). |
| `ops/events-schedule.json` | The weekly calendar. Drives the website's "upcoming events" AND documents your cron times - keep both in sync. |
| `ops/eventsgen.py` | Computes active + upcoming events into `web/events.json` for the site. |
| `ops/statusgen.py` | Builds `web/status.json`: online players, slots, mod list with real Steam names, population history. Point `INI` at your server's ini. |
| `ops/modwatch.py` | Caches Steam Workshop titles for the mod list (daily). |
| `web/index.html` | Complete single-file website: live status, events board, lore, economy guide, commands, mod list, join instructions. Serve it with any static web server (nginx, caddy, GitHub Pages won't work for the live JSON unless you also host the generators' output). |
| `ops/sampler.py` | Samples player count every 10 min into sqlite - feeds the website's population chart. |
| `ops/tips.txt` | The rotating in-game tip lines `goon-ops.sh tip` broadcasts - rewrite for your server. |
| `ops/goon-bounty` | Toggles bounty-weekend kill rates by editing your SandboxVars file (used by the Fri/Mon restart). Install to /usr/local/bin or adjust the path in goon-ops.sh. |
| `crontab.example` | Every schedule wired up, ready to adapt. |

## Setup

1. Copy `ops/` and `web/` somewhere on the machine that runs (or can reach)
   your PZ server. The examples use `/opt/goon-kit/`.
2. Fill in every `YOUR_*` placeholder: RCON password/port, container id or
   server IP, server name (ini file name), website domain.
3. Enable RCON on your PZ server (RCONPort= and RCONPassword= in the ini).
4. Test: `python3 ops/rcon.py players` should list who's online.
5. Serve `web/` with your web server of choice; the generators write
   `status.json` / `events.json` next to `index.html`.
6. Install the cron lines from `crontab.example` (`crontab -e`).
7. Match the mod: install the Workshop mod on your server (see its page for
   the Storm javaagent step) and set your branding in the "Goon Platform"
   sandbox pages so the website, radio, and in-game Terminal all tell the
   same story.

## Rebrand checklist (web/index.html)

The website is a complete working example, deliberately full of our lore so
you can see how everything fits. Before going live, rewrite: the header and
tagline, "The Story So Far" lore, the economy tables (currency name, prices),
the commands table, the join instructions (IP/port), and the House Rules.
Search the file for "Goon" to catch every mention. The live-data script tags
(status.json / events.json) work unchanged.

## Links

- **[Land of Goons: Economy](https://steamcommunity.com/sharedfiles/filedetails/?id=3780050823)** - the in-game platform this kit pairs with (Terminal, bounties, casino, contracts, territory war, radio)
- **[Land of Goons: Gag Emporium](https://steamcommunity.com/sharedfiles/filedetails/?id=3780051574)** - companion mod: global jumpscare gags as a Goonmark sink
- **[Storm Mod Framework b42](https://steamcommunity.com/sharedfiles/filedetails/?id=3670772371)** - required by both mods; needs a server-side javaagent (see the Economy page for the one-line setup)
- **[Jumpscare Ban by Gus Puffy](https://steamcommunity.com/sharedfiles/filedetails/?id=3716129274)** - required by the Gag Emporium

## Putting this on GitHub

To publish your own copy (recommended - it version-controls your server ops):

```bash
cd goon-server-kit
git init
git add .
git commit -m "feat: initial server kit"
# create a repo on github.com (web UI: New repository), then:
git remote add origin git@github.com:YOURNAME/YOURREPO.git
git branch -M main
git push -u origin main
```

**Before your first push**, protect your secrets:

```bash
cat > .gitignore <<'EOF'
# local state the scripts write
*.log
*.jsonl
*.sqlite
modwatch-snapshot.json
.tip_index
# your filled-in secrets live in a local override, never in git
ops/secrets.conf
EOF
git add .gitignore
```

Keep the committed files holding `YOUR_*` placeholders; put your real values
in a local copy (or an untracked `ops/secrets.conf` you source). If you ever
accidentally commit a real password: rotate it immediately - deleting the
commit is not enough.

## License / credit

Built for the Land of Goons PZ server. Use, adapt, and rebrand freely for
your own community. The in-game mod this pairs with is a fork of After The
Fall: Economy by SentientSimulations/Gus Puffy - credit stays with them for
the foundation.
