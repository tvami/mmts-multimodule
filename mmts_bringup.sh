#!/bin/bash
# MMTS Alabama bench (kria4) -- bring-up.  Authoritative procedure lives in
# MMTS_ALABAMA_RUNBOOK.md on the Mac; this script is the executable summary.
#
#   ./mmts_bringup.sh [A|B|C] [--no-recover] [--external-power] [--keep-daq-server]
#                     [--board NAME]
#
#   --board NAME : ROC address set to probe (see ROC_ADDR_SETS in
#                enableROCs_alabama.py).  Default LD-Full = 0x08/0x18/0x28.
#                Partials sit at other bases -- the LD Bottom boards in slots B
#                and C are LD-Semi = 0x48/0x58.  'any' probes all six V3 bases.
#
#   --external-power : the power management board is not in the loop (e.g. the
#                supply is wired straight to a slot).  Skips the 0x27 EN_Mx step
#                and the fw-loader reset that clears the wedge it causes.  It
#                does NOT mean "leave the module unpowered".
#                (--no-power is accepted as the old, misleading name.)
#
#   --keep-daq-server : do NOT restart daq-server.  By default it IS restarted,
#                because it holds the trigger claim for the slot it scanned first
#                and only a restart releases it.
#
# Order matters: bring-up -> i2c-server -> puller -> scan.  Bring-up reloads the
# PL bitstream, which renumbers the gpiochips; a server started before that keeps
# gpioset holders on a chip that no longer exists, so its Multiplex hold is never
# asserted (symptom: 6 dead DAQ links, 12 healthy trigger links, server looks fine).
#
# ============================ DO NOT ============================
# * DO NOT run the ZL30274 clock step from Multiplexer Documentation.docx.pdf:
#       i2cset -y 0 0x70 1 ; python3 zl30274_configurator.py multiplexer_board_40.0000.mfg
#   It moves the clock out from under the PL I2C master.  Tried 2026-08-24: the
#   server failed 25x at the first switch write, then bring-up got 0 ROCs, then
#   bring-up crashed with 0x73 not ACKing.  --recover makes it WORSE each run.
#   Recovery is `sudo shutdown -h now` + the Kria's power button (NOT kconn_pwr --
#   the chip is on the PS I2C rail).
#
# * DO NOT use `systemctl start zmq-server@B`.  That unit runs
#   /opt/hexactrl/ROCv3-alper-dev/i2c/zmq_server.py -- the RPM copy, which has
#   NONE of our fixes (group-retry mux_setup, single-slot mux_setup, the 0x21
#   _reg_out direction fix, MUX_SUBBUSES=[1,3]).  Always run it from
#   ~/multimodule/hexactrl-sw/zmq_i2c/ as printed at the end of this script.
#
# * DO NOT run `i2cdetect -y 2` or `--readback`.  Reads wedge this master.
# ================================================================
set -u

SLOT="${1:-B}"
RECOVER="--recover"
NOPOWER=""
KEEPDAQ=""
BOARD=""
MODULE=""
prev=""
for a in "$@"; do
    [ "$a" = "--keep-daq-server" ] && KEEPDAQ="1"
    [ "$a" = "--no-recover" ] && RECOVER=""
    case "$a" in --no-power|--external-power) NOPOWER="--external-power" ;; esac
    [ "$prev" = "--board" ] && BOARD="--board $a"
    case "$a" in --board=*) BOARD="--board ${a#--board=}" ;; esac
    # EN_Mx bit on the power distribution board.  NOT the slot index: it is
    # which power-board output the module lead is plugged into.
    [ "$prev" = "--module" ] && MODULE="--module $a"
    case "$a" in --module=*) MODULE="--module ${a#--module=}" ;; esac
    prev="$a"
done
case "$SLOT" in A|B|C) ;; *) echo "usage: $0 [A|B|C] [--no-recover] [--external-power] [--keep-daq-server] [--board NAME]"; exit 2 ;; esac

cd ~/multimodule || exit 1

# Stale gpioset holders outlive a killed server and fight the next one for the
# same Multiplex lines.
echo "[1/3] clearing gpioset holders"
pkill -f 'gpioset -m signal -b' 2>/dev/null
sleep 1

# --recover = kconn_pwr off -> fw-loader load -> kconn_pwr on, then the full
# power/enable sequence.  Needed at session start and on every slot change.
# Roughly half of all bring-ups wedge partway: a clean re-run is the fix.
echo "[2/3] bring-up: slot $SLOT $RECOVER $NOPOWER $BOARD $MODULE"
python3 enableROCs_alabama.py "$SLOT" $RECOVER $NOPOWER $BOARD $MODULE || {
    echo "!! bring-up failed -- re-run once.  Worse each run => see the header."
    exit 1
}

# daq-server serves TOP_A/TOP_B/TOP_C from one process and survives firmware
# reloads -- BUT it holds the TRIGGER CLAIM for whichever slot it scanned first,
# and only a restart releases it.  Skip the restart on a slot change and the new
# slot reads 6/18: six good DAQ links and twelve dead trigger links, with nothing
# in the output saying why.  Since bring-up is mandatory on a slot change anyway,
# restart it here so the claim is always released -- correct by construction.
# Re-running bring-up on the SAME slot is harmless: that slot simply re-claims on
# its next scan.  Use --keep-daq-server to leave a running one alone.
if [ -n "$KEEPDAQ" ] && ss -ltn 2>/dev/null | grep -q ':6000 '; then
    echo "[3/3] daq-server left running (--keep-daq-server) -- STILL HOLDS the trigger claim"
else
    if ss -ltn 2>/dev/null | grep -q ':6000 '; then
        echo "[3/3] restarting daq-server (releases the trigger claim)"
        pkill -f '[d]aq-server' 2>/dev/null
        sleep 1
    else
        echo "[3/3] starting daq-server"
    fi
    # env.sh does `export LD_LIBRARY_PATH=...:$LD_LIBRARY_PATH`, which is unbound
    # in a login shell after a reboot -- `set -u` would abort the whole script.
    set +u
    source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
    set -u
    setsid /opt/hexactrl/ROCv3-alper-dev/bin/daq-server \
        -f /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml -p 6000 \
        > ~/daq-server.log 2>&1 < /dev/null &
    sleep 3
    ss -ltn | grep -q ':6000 ' || echo "     WARNING: not listening, see ~/daq-server.log"
fi

echo
echo "next:  cd ~/multimodule/hexactrl-sw/zmq_i2c && python3 zmq_server.py --mux --slot $SLOT"
