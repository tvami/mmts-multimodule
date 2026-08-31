# lib.sh -- shared setup and the puller. Sourced by every script here.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/site.sh"

KRIA="$KRIA_USER@$KRIA_IP"
HEXBIN="$HEXACTRL/bin"
SCRIPTS="$MMTS_ROOT/multimodule/hexactrl-sw/hexactrl-script"
DEBUG="$MMTS_ROOT/multimodule/debug"
RESULTS="$RESULTS_DIR"

# module_of.py and the analysis scripts read these from the environment.
export MMTS_ROOT RESULTS_DIR KRIA_IP MMTS_FW

[ -x "$HEXBIN/daq-client" ] || {
    echo "no daq-client at $HEXBIN -- set HEXACTRL in site.sh"; exit 1; }

# unpack is shelled out to by name from the run's notifier, so it must be on PATH.
[ -f "$HEXACTRL/etc/env.sh" ] && . "$HEXACTRL/etc/env.sh"
case ":$PATH:" in *":$HEXBIN:"*) ;; *) PATH="$HEXBIN:$PATH" ;; esac
export PATH

[ -n "$MMTS_VENV" ] && [ -f "$MMTS_VENV/bin/activate" ] && . "$MMTS_VENV/bin/activate"

# --- the puller ------------------------------------------------------------
# daq-client receives the event stream on 6001 and writes the .raw. Restart it
# for every RUN: one that has seen a failed START silently produces data that
# decodes to nothing. The bracket in [d]aq-client keeps pkill off our own line.
puller_alive() { pgrep -f '[d]aq-client' >/dev/null 2>&1; }

puller_restart() {
    pkill -f '[d]aq-client' 2>/dev/null
    sleep 1
    setsid "$HEXBIN/daq-client" >> "$MMTS_ROOT/daq-client.log" 2>&1 < /dev/null &
    for _ in $(seq 1 10); do
        sleep 1
        ss -ltn 2>/dev/null | grep -q ':6001 ' && return 0
    done
    echo "puller FAILED to bind 6001 -- see $MMTS_ROOT/daq-client.log"
    return 1
}

# Serial of the board in a slot, or empty. Callers fall back to the flat layout.
module_of() { python3 "$HERE/module_of.py" "$@" 2>/dev/null; }

# Output root for a slot: by-board when the registry knows it, flat when not.
outdir_for() {
    local s serial
    s="$1"; serial="$(module_of "$s")"
    if [ -n "$serial" ]; then echo "$RESULTS/$serial"; else echo "$RESULTS"; fi
}
