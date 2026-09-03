#!/usr/bin/env bash
# churn_test.sh SLOT CFG -- the 2026-08-30 bring-up-churn experiment.
#
# Step 1 came back QUIET at 14.3 h of uptime (ACF1 +0.03, total 1.23), so
# elapsed time is not what brings the 4 kHz pickup on.  The remaining
# correlate is bring-up churn: every noisy measurement followed dozens of
# cycles, and each cycle is a full kconn_pwr off/on plus an fw-loader reload
# (--recover is mmts_bringup.sh's default).
#
# Blocks of 4 cycles, then delay-scan gate + 3 pedestals + cm_analysis, to 12.
# Cumulative count is what matters, so the blocks are not independent.
set -u
SLOT="${1:?slot}"
CFG="${2:?config}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
SERIAL=$(python3 "$ROOT/multimodule/bin/module_of.py" "$SLOT")
CUM=0

for block in 1 2 3; do
    "$ROOT/multimodule/bin/churn.sh" "$SLOT" 4 || exit 1
    CUM=$((CUM + 4))
    echo "=== after $CUM cumulative bring-ups ==="
    ssh daq@10.116.25.124 'cut -d. -f1 /proc/uptime; for h in /sys/class/hwmon/hwmon*; do
        [ "$(cat $h/name 2>/dev/null)" = ams ] && cat $h/temp1_input; done' | tr '\n' ' '
    echo

    "$ROOT/multimodule/bin/delay_scan.sh" "$SLOT" "$CFG" | tail -4
    PED_BASECFG=$ROOT/multimodule/hexactrl-sw/hexactrl-script/$CFG \
        PED_DUT=Mux${SLOT}_churn$CUM "$ROOT/multimodule/bin/ped_run.sh" "$SLOT" 3 churn$CUM 10000
    docker exec daq bash -lc \
        "python3 $ROOT/multimodule/debug/cm_analysis.py '$ROOT/Results/alabama/$SERIAL/Mux${SLOT}_churn$CUM/pedestal_run/run_*'" \
        | tail -1
done
