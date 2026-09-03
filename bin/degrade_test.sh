#!/usr/bin/env bash
# ============================================================================
# degrade_test.sh SLOT N [OFFSET] [NEVENTS]
#
# Run N pedestals back-to-back after ONE bring-up, reporting for each run both
#   * whether the i2c leg reported ROC(s) CONFIGURED, and
#   * the per-half-ROC corruption.
#
# No retries, no re-bring-up: the point is to see whether the slot degrades with
# use.  Observed on slot A 2026-08-27: the first run after a bring-up gives a
# half with corruption 0.43, every later run gives 1.0 on all six halves and the
# ROC-type identify read returns [0, 253, 104] instead of [0, 125, 104].
# ============================================================================
set -u

SLOT="${1:?slot}"
N="${2:-4}"
OFF="${3:-13}"
NEV="${4:-1000}"

ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
RESULTS=$ROOT/Results/alabama
DUT=Mux${SLOT}_degrade
BIN=/opt/hexactrl/ROC3_dev_docker/bin

cfg="configs/_degrade_${SLOT}.yaml"
sed -e "s/    method: 'automatic'/    method: 'manual'/" \
    -e "s/    L1A_offset_or_BX: 13/    L1A_offset_or_BX: ${OFF}/" \
    -e "s/      NEvents: 10000/      NEvents: ${NEV}/" \
    "$SCRIPTS/configs/initLD-trophyV3-3b_mux${SLOT}.yaml" > "$SCRIPTS/$cfg"

printf '%-4s %-10s  %-47s %s\n' "run" "i2c" "per-half corruption c0h0..c2h1" "dir"
printf '%s\n' "---------------------------------------------------------------------------"

for i in $(seq 1 "$N"); do
    log=$(mktemp)
    docker exec daq bash -lc "cd $SCRIPTS
        export PATH=$BIN:\$PATH
        export PYTHONPATH=\$PWD/analysis
        export MMTS_L1A_LOG2PERIOD=10
        timeout 200 python3 -u pedestal_run.py -d $DUT -i 10.116.25.124 \
            -o $RESULTS -I -f $cfg" > "$log" 2>&1

    if grep -q 'ROC(s) CONFIGURED' "$log"; then i2c="CONFIGURED"; else i2c="**FAILED**"; fi
    dir=$(grep -o "$RESULTS/$DUT/pedestal_run/run_[0-9_]*" "$log" | head -1)
    rm -f "$log"

    if [ -z "$dir" ] || [ ! -f "$dir/pedestal_run0.root" ]; then
        printf '%-4s %-10s  %s\n' "$i" "$i2c" "no .root produced"
        continue
    fi

    res=$(docker exec daq bash -lc "python3 -c \"
import uproot, numpy as np
a = uproot.open('$dir/pedestal_run0.root')['runsummary/summary'].arrays(library='np')
m = a['channeltype'] == 0
print(' '.join('%.3f' % np.median(a['corruption'][m & (a['chip']==c) & (a['channel']//36==h)])
               for c in (0,1,2) for h in (0,1)))
\"" 2>/dev/null | tail -1)
    printf '%-4s %-10s  %-47s %s\n' "$i" "$i2c" "$res" "$(basename "$dir")"
done

rm -f "$SCRIPTS/$cfg"
