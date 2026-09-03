#!/usr/bin/env bash
# ============================================================================
# scan_slot_timing.sh -- brute-force (L1A_offset_or_BX x fifo_latency) sweep on
# one slot, reporting PER-HALF-ROC corruption.
#
#   ./scan_slot_timing.sh SLOT "OFFSETS" "FIFOS" [NEVENTS]
#
# Why per-half-ROC: HANDOVER §1/§3 -- a wide delay-scan eye and a healthy total
# entry count both looked fine for two days while every lane was broken.  The
# only metric that distinguishes a real header from the captured align pattern
# is the per-(chip,half) `corruption` fraction in runsummary/summary.  A half is
# GOOD when that fraction drops below 1.0 (ideally ~0).
#
# The goal on slot A is not a good run -- it is to find ANY lane with corruption
# < 1.0, which gives the automatic finder the reference it needs to bootstrap.
#
# MMTS_L1A_LOG2PERIOD=10 is set on every run: pedestal_run.py's default of 0 is
# ~890 kHz and ~100 % header-check failure by itself (audit item 15).
# ============================================================================
set -u

SLOT="${1:?slot A|B|C}"
OFFSETS="${2:-0 4 8 12 16 20 24 28 32 36 40}"
FIFOS="${3:-0}"
NEV="${4:-1000}"

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
# SCAN_BASECFG lets a slot use a variant base -- slot A needs the _no6 config,
# whose trigger link6 is commented out because it never aligns for randomL1A.
BASECFG=${SCAN_BASECFG:-$SCRIPTS/configs/initLD-trophyV3-3b_mux${SLOT}.yaml}
DUT=Mux${SLOT}_tscan
RESULTS=$ROOT/Results/alabama
BIN=/opt/hexactrl/ROC3_dev_docker/bin
# A healthy point finishes in ~30 s in a WARM container, but the first run in a
# freshly created one is much slower (image start, python imports, cold page
# cache) and 90 s was not enough.  That mattered because a timeout used to
# trigger fresh_puller, so one slow point made the next one cold too -- a
# self-sustaining failure loop that turned a whole sweep into RUN-FAILED rows.
# Cap generously and keep the container across timeouts.
MAXSECS=180

fresh_puller() {
    docker rm -f daq >/dev/null 2>&1
    docker run -d --name daq --platform linux/amd64 -p 6001:6001 \
        -v "$ROOT:$ROOT" -w "$SCRIPTS" hexactrl-client:local \
        '/opt/hexactrl/${SUBPATH}/bin/daq-client & wait' >/dev/null || return 1
    sleep 5
}

docker ps --format '{{.Names}}' | grep -qx daq || fresh_puller

printf '%-5s %-5s %-4s %-47s %s\n' "off" "fifo" "i2c" "per-half corruption c0h0..c2h1" "run"
printf '%s\n' "----------------------------------------------------------------------------"

for fifo in $FIFOS; do
for off in $OFFSETS; do
    cfg="configs/_tscan_${SLOT}_${off}_${fifo}.yaml"
    sed -e "s/    method: 'automatic'/    method: 'manual'/" \
        -e "s/    fifo_latency: 0 #/    fifo_latency: ${fifo} #/" \
        -e "s/    L1A_offset_or_BX: 13/    L1A_offset_or_BX: ${off}/" \
        -e "s/      NEvents: 10000/      NEvents: ${NEV}/" \
        "$BASECFG" > "$SCRIPTS/$cfg"

    # The ROC-type identify read on this bench comes back [0, 253, 104] instead
    # of [0, 125, 104] on every initialize after the first, so zmq_server replies
    # `error:` and skips rebuilding the board.  That is NOT fatal for a timing
    # scan: the ROC-side config is identical at every scan point, the ROCs keep
    # the configuration the first successful initialize gave them, and only the
    # daq-side fifo_latency/L1A_offset changes -- that leg always succeeds.
    # Measured 2026-08-27 (degrade_test.sh): a run whose i2c leg said CONFIGURED
    # and four whose leg failed gave the same six per-half numbers.  So record
    # the i2c state in the row and carry on rather than paying for a retry.
    log=$(mktemp)
    docker exec daq bash -lc "cd $SCRIPTS
        export PATH=$BIN:\$PATH
        export PYTHONPATH=\$PWD/analysis
        export MMTS_L1A_LOG2PERIOD=10
        timeout $MAXSECS python3 -u pedestal_run.py -d $DUT -i 10.116.25.124 \
            -o $RESULTS -I -f $cfg" > "$log" 2>&1
    rc=$?
    grep -q 'ROC(s) CONFIGURED' "$log" && i2c="cfg" || i2c="ERR"
    rm -f "$SCRIPTS/$cfg"

    dir=$(grep -o "$RESULTS/$DUT/pedestal_run/run_[0-9_]*" "$log" | head -1)

    # The destructive START spin: daq-server refusing to start re-runs the full
    # link alignment on every retry (audit item 7).  Kill the container, which
    # is the only way to stop the python inside it, and rebuild it.
    # daqController.start() is bounded now (20 attempts), so the old destructive
        # spin is impossible; >=6 'configured' lines is just ONE refused START.  Only
        # an unbounded spin (an unpatched client) should abort the batch.
        spin=$(grep -c 'status after start cmd : configured' "$log" 2>/dev/null | head -1)
    spin=${spin:-0}
    if [ "$spin" -ge 50 ]; then
        printf '%-5s %-5s  %s\n' "$off" "$fifo" "ABORT: START spin -- slot needs re-bring-up"
        rm -f "$log"; fresh_puller
        exit 3
    fi

    if [ -z "$dir" ] || [ ! -f "$dir/pedestal_run0.root" ]; then
        printf '%-5s %-5s %-4s %-47s %s\n' "$off" "$fifo" "$i2c" \
               "RUN-FAILED (rc=$rc)" "$(basename "${dir:-none}")"
        rm -f "$log"
        continue
    fi
    rm -f "$log"

    res=$(docker exec daq bash -lc "python3 -c \"
import uproot, numpy as np
try:
    a = uproot.open('$dir/pedestal_run0.root')['runsummary/summary'].arrays(library='np')
    m = a['channeltype'] == 0
    out = []
    for c in (0, 1, 2):
        for h in (0, 1):
            k = m & (a['chip'] == c) & (a['channel'] // 36 == h)
            out.append('%.3f' % np.median(a['corruption'][k]) if k.any() else ' n/a ')
    print(' '.join(out))
except Exception as e:
    print('READ-ERR')
\"" 2>/dev/null | tail -1)

    flag=""
    for v in $res; do
        case "$v" in READ-ERR) flag=""; break ;; esac
        awk -v x="$v" 'BEGIN{exit !(x < 0.95)}' && flag="  <== GOOD LANE"
    done
    printf '%-5s %-5s %-4s %-47s %s%s\n' "$off" "$fifo" "$i2c" "$res" "$(basename "$dir")" "$flag"
done
done
