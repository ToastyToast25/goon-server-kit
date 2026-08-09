#!/bin/bash
# Your Server Name server ops toolkit. One entrypoint, subcommands via $1.
# Cron-driven; every action logs to ops.log. RCON via rcon.py (resolves the
# container IP per call, so container recreation never breaks it).
set -u
DIR=/opt/goon-kit/ops
RCON="python3 $DIR/rcon.py"
LOG="$DIR/ops.log"

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

say() { # broadcast one server message
    $RCON "servermsg \"$1\"" >/dev/null 2>&1
}

players_online() {
    $RCON players 2>/dev/null | head -1 | grep -oE "\([0-9]+\)" | tr -d "()"
}

case "${1:-}" in

tip)
    # Rotate through tips.txt, one line per invocation.
    IDX_FILE="$DIR/.tip_index"
    TOTAL=$(grep -c . "$DIR/tips.txt")
    IDX=$(cat "$IDX_FILE" 2>/dev/null || echo 0)
    IDX=$(( (IDX % TOTAL) + 1 ))
    echo "$IDX" > "$IDX_FILE"
    TIP=$(sed -n "${IDX}p" "$DIR/tips.txt")
    N=$(players_online || echo 0)
    if [ "${N:-0}" -gt 0 ]; then
        say "[Goon Tip] $TIP"
        log "tip #$IDX broadcast to $N players"
    else
        log "tip #$IDX skipped (empty server)"
    fi
    ;;

restart)
    # Daily maintenance restart with countdown. Fri flips bounty weekend ON,
    # Mon flips it OFF (goon-bounty is a root helper approved via sudoers).
    N=$(players_online || echo 0)
    if [ -f "$DIR/staging-veto" ]; then
        log "RESTART SKIPPED - staging-veto is set (workshop updates failed staging test)"
        say "[SERVER] Tonight's maintenance restart is postponed while a mod update is checked. Play on."
        exit 0
    fi
    if [ -f "$DIR/pending-tune" ]; then
        while read -r tok; do
            case "$tok" in
                los100) sudo -n /usr/local/bin/goon-tune los100 >> "$LOG" 2>&1 && log "applied pending tune: los100" ;;
                *) log "unknown pending tune token: $tok" ;;
            esac
        done < "$DIR/pending-tune"
        rm -f "$DIR/pending-tune"
    fi
    log "daily restart begins ($N players online)"
    if [ "${N:-0}" -gt 0 ]; then
        say "[SERVER] Daily restart in 15 minutes. Find somewhere safe."
        sleep 600
        say "[SERVER] Restart in 5 minutes. Park the car, close the door."
        sleep 240
        say "[SERVER] Restart in 60 seconds!"
        sleep 60
    fi
    DOW=$(date +%u)   # 1=Mon .. 7=Sun
    if [ "$DOW" = "5" ]; then
        sudo -n /usr/local/bin/goon-bounty weekend && log "bounty weekend ON"
        MODE=" Bounty Weekend is ON - double payouts per kill!"
    elif [ "$DOW" = "1" ]; then
        sudo -n /usr/local/bin/goon-bounty normal && log "bounty weekend OFF"
        MODE=""
    else
        MODE=""
    fi
    T=$(mktemp)
    cat > "$T" <<'PHP'
$s=App\Models\Server::find(9);
app(App\Repositories\Daemon\DaemonServerRepository::class)->setServer($s)->power("restart");
echo "RESTART-SENT\n";
PHP
    docker exec -i panel php artisan tinker < "$T" >> "$LOG" 2>&1
    rm -f "$T"
    log "daily restart issued.$MODE"
    ;;

saturday)
    # Siren Saturday: an hour of escalating atmosphere. Real triggers, not
    # just text - gunshots pull hordes toward random players, the chopper
    # shadows someone, thunder sells the mood.
    N=$(players_online || echo 0)
    if [ "${N:-0}" -eq 0 ]; then log "saturday event skipped (empty)"; exit 0; fi
    log "siren saturday begins ($N players)"
    say "[EVENT] The sirens are warming up. Something moves tonight. Stay armed, Goons."
    sleep 300
    $RCON "gunshot" >/dev/null 2>&1
    say "[EVENT] Gunfire echoes across Knox County..."
    sleep 600
    $RCON "chopper" >/dev/null 2>&1
    say "[EVENT] A helicopter sweeps the county - it is drawing them OUT."
    sleep 600
    $RCON "thunder" >/dev/null 2>&1
    $RCON "gunshot" >/dev/null 2>&1
    sleep 600
    $RCON "gunshot" >/dev/null 2>&1
    say "[EVENT] More shots. The dead are on the move. Hold your ground."
    sleep 900
    say "[EVENT] Siren Saturday winds down. Count your bullets and your friends. Survivors drink free at the jukebox."
    log "siren saturday complete"
    ;;

arena)
    # Announce an arena event at the hub. Usage: goon-ops.sh arena "8 PM" "G$2000"
    WHEN="${2:-tonight}"
    FEE="${3:-G$1,000}"
    say "[ARENA] The Goon Pit opens $WHEN at the hub. Entry $FEE, winner takes the pot. Fists, then knives, then whatever you brought."
    log "arena announced: $WHEN entry $FEE"
    ;;

status)
    $RCON players
    tail -5 "$LOG"
    ;;

*)
    echo "usage: goon-ops.sh {tip|restart|saturday|status}"
    exit 1
    ;;
esac
