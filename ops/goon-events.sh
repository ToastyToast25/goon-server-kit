#!/bin/bash
# Your Server Name live-events engine. Cron-driven; each subcommand is one event.
# Fires escalating, themed announcements + RCON atmosphere (sounds draw the
# existing 7k horde toward players - no risky mass-spawns), and records its
# active window to events-log.jsonl so eventsgen.py can surface it on the site.
set -u
DIR=/opt/goon-kit/ops
RCON="python3 $DIR/rcon.py"
LOG="$DIR/ops.log"
EVLOG="$DIR/events-log.jsonl"

log()  { echo "$(date '+%F %T') [event] $*" >> "$LOG"; }
say()  { $RCON "servermsg \"$1\"" >/dev/null 2>&1; }
nap()  { sleep $(( ${1:-1} * 60 )); }
players_online() { $RCON players 2>/dev/null | head -1 | grep -oE "\([0-9]+\)" | tr -d "()"; }

# Record an active window for the website. begin_event <key> <duration_min>
begin_event() {
    local key="$1" dur="$2" start end
    start=$(date +%s); end=$(( start + dur * 60 ))
    printf '{"key":"%s","start":%s,"end":%s}\n' "$key" "$start" "$end" >> "$EVLOG"
    log "$key started (${dur}m window)"
}

# A random Knox County place name for flavor.
PLACES=("Muldraugh" "West Point" "Rosewood" "Riverside" "March Ridge" "the Fossoil station" "Dixie Highway" "Fallas Lake" "the Crossroads Mall")
place() { echo "${PLACES[$RANDOM % ${#PLACES[@]}]}"; }

# A random online player's name (for Wanted). Empty if nobody on.
random_player() { $RCON players 2>/dev/null | grep -E "^-" | sed "s/^-//" | shuf -n1; }

case "${1:-}" in

bloodmoon)
    begin_event bloodmoon 120
    say "🌑 [BLOOD MOON] The moon came up wrong tonight — red as an open wound. They see better in this light. Lock your doors, Goon."
    nap 5
    $RCON "alarm"   >/dev/null 2>&1
    say "🌑 [BLOOD MOON] Every alarm in Knox County just tripped at once. Something woke them. All of them."
    nap 30; $RCON "gunshot" >/dev/null 2>&1
    say "🌑 [BLOOD MOON] The horde is moving under the red light. Douse your fires. Don't run — they hear running."
    nap 40; $RCON "chopper" >/dev/null 2>&1
    say "🌑 [BLOOD MOON] A chopper crosses the blood moon and doesn't circle back. Whatever it saw, it left you to it."
    nap 30; $RCON "thunder" >/dev/null 2>&1; $RCON "gunshot" >/dev/null 2>&1
    nap 13
    say "🌑 [BLOOD MOON] The red moon sets. If you're reading this, you made it through. Most nights, most don't."
    log "bloodmoon complete"
    ;;

fog)
    begin_event fog 120
    say "🌫️ [KNOX FOG] A cold fog is rolling up off the river. You won't see them until they're on you. Stay close to a wall."
    nap 40; $RCON "startrain" >/dev/null 2>&1
    say "🌫️ [KNOX FOG] Visibility's gone to arm's length. Somewhere in the grey, something is dragging its feet toward the sound of your heart."
    nap 45; $RCON "thunder" >/dev/null 2>&1
    say "🌫️ [KNOX FOG] Thunder in the fog. Use it — they can't hear you over it either."
    nap 33; $RCON "stoprain" >/dev/null 2>&1
    say "🌫️ [KNOX FOG] The fog is thinning. Count your fingers. Count your friends. Hope both numbers held."
    log "fog complete"
    ;;

megahorde)
    P=$(place)
    begin_event megahorde 90
    say "💀 [THE GATHERING] Something is pulling them together at $P — a tide of the dead, thousands strong, all shuffling the same way. First crew to break it earns a place on the wall."
    nap 5;  $RCON "alarm"   >/dev/null 2>&1
    nap 30; $RCON "gunshot" >/dev/null 2>&1
    say "💀 [THE GATHERING] The mass at $P is thick enough to blot out the road. Bring more bullets than you think you need."
    nap 40; $RCON "chopper" >/dev/null 2>&1
    say "💀 [THE GATHERING] Air support paints $P and peels away. It's yours to hold or bury."
    nap 15
    say "💀 [THE GATHERING] The horde at $P is thinning. Whoever's still standing — the county owes you a drink at the jukebox."
    log "megahorde complete ($P)"
    ;;

siege)
    P=$(place)
    begin_event siege 90
    say "🎖️ [SIEGE] Radio chatter puts a bandit column moving on $P — armed, organized, and coming fast. Defenders split the pot at the Ledger."
    nap 5;  $RCON "gunshot" >/dev/null 2>&1
    nap 35; $RCON "gunshot" >/dev/null 2>&1; $RCON "alarm" >/dev/null 2>&1
    say "🎖️ [SIEGE] Gunfire at $P. They're in the streets now. Hold the line or lose it."
    nap 35
    say "🎖️ [SIEGE] The bandits are pulling back from $P — for now. Strip the bodies before someone else does."
    log "siege complete ($P)"
    ;;

wanted)
    TARGET=$(random_player)
    begin_event wanted 120
    if [ -z "$TARGET" ]; then
        log "wanted: nobody online, window logged only"; exit 0
    fi
    say "🎯 [WANTED] A price just went up on $TARGET's head. Dead or… well. Dead. Collect at the Ledger. $TARGET — start running."
    nap 60
    say "🎯 [WANTED] $TARGET is still breathing. The bounty stands. Somebody's getting paid tonight."
    nap 60
    say "🎯 [WANTED] The contract on $TARGET just expired. Lucky. This time."
    log "wanted complete ($TARGET)"
    ;;

supplydrop)
    P=$(place)
    begin_event supplydrop 45
    say "📦 [SUPPLY DROP] A bird just dropped a crate somewhere over $P. Everything you need and a few things you don't. First one there keeps it."
    $RCON "chopper" >/dev/null 2>&1
    nap 25
    say "📦 [SUPPLY DROP] Word is the crate near $P is still out there. Or it isn't. Only one way to find out."
    nap 20
    say "📦 [SUPPLY DROP] That crate's been found or lost by now. Eyes up for the next bird."
    log "supplydrop complete ($P)"
    ;;

merchant)
    begin_event merchant 60
    say "🛒 [THE PEDDLER] A stranger with a loaded truck just pulled into the hub. Rare stock, cash only, gone in an hour. Don't ask where he got any of it."
    nap 30
    say "🛒 [THE PEDDLER] The Peddler's still at the hub, tapping his watch. Half hour left before he rolls out."
    nap 30
    say "🛒 [THE PEDDLER] The Peddler packed up and disappeared down Dixie. Back when he's back."
    log "merchant complete"
    ;;

purge)
    begin_event purge 60
    say "🔥 [THE PURGE] For the next hour the old rules are off. Safehouse doors mean nothing. Bounties pay double. Settle your debts, Goon — everyone else is."
    nap 30; $RCON "alarm" >/dev/null 2>&1
    say "🔥 [THE PURGE] Thirty minutes of lawlessness left. Watch your back and your bank."
    nap 30
    say "🔥 [THE PURGE] The Purge is over. Safehouses are sacred again. Bury who you have to and shake on the rest."
    log "purge complete"
    ;;

doublexp)
    # Announcement + website window. NOTE: the actual XPMultiplierGlobal swap
    # (2x -> 4x) is a follow-up wired into the Fri/Mon restart; see README.
    begin_event doublexp 3600
    say "⚡ [DOUBLE KNOWLEDGE] The Syndicate is paying double all weekend. Every swing, every stitch, every page read — worth twice as much until Monday morning. Get to work, Goon."
    log "doublexp weekend announced"
    ;;

doublexp-end)
    say "⚡ [DOUBLE KNOWLEDGE] The double-knowledge weekend is over. Back to earning it the hard way. You made good use of it — right?"
    log "doublexp weekend ended"
    ;;

*)
    echo "usage: goon-events.sh {bloodmoon|fog|megahorde|siege|wanted|supplydrop|merchant|purge|doublexp|doublexp-end}"
    exit 1
    ;;
esac
