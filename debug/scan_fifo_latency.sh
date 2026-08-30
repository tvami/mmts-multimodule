#!/bin/bash
# Find the correct per-chip fifo_latency for pedestal runs on the Alabama bench.
#
# Background: the automatic l1aOffsetFinder does not work here -- it either
# produces an out-of-range value (fifo_latency=96 for link1, which is a 5-bit
# field -> uHAL exception -> daq-server dies) or silently falls back to the
# config defaults (fifo_latency=0, L1A_offset_or_BX=13).  With those defaults
# chip1 gives a normal ~1.2 ADC pedestal width while chip0 and chip2 give 9.7
# and 27.7, which looks like misalignment rather than real noise.
#
# DAQ links map two per chip: 0,1 -> chip0 ; 4,5 -> chip1 ; 8,9 -> chip2.
# This scans fifo_latency (applied to all links) and reports the median
# pedestal width per chip.  The correct setting should collapse all three to
# ~1 ADC.
#
# DAQ-only: no power cycles, no I2C beyond the normal per-run configure.
#
# Usage: ./scan_fifo_latency.sh "0 1 2 3 4 5 6 7 8" [L1A_offset]

set -u
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
BASECFG=$SCRIPTS/configs/initLD-trophyV3-3b_muxB.yaml
BIN=/opt/hexactrl/ROC3_dev_docker/bin

LATENCIES="${1:-0 1 2 3 4 5 6 7 8}"
OFF="${2:-13}"

printf '%-8s %-8s %-10s %-10s %-10s %s\n' \
       "fifo" "L1Aoff" "chip0" "chip1" "chip2" "run"

for fifo in $LATENCIES; do
    cfg="configs/_scan_fifo_${fifo}.yaml"
    sed -e "s/    method: 'automatic'/    method: 'manual'/" \
        -e "s/    fifo_latency: 0 #/    fifo_latency: ${fifo} #/" \
        -e "s/    L1A_offset_or_BX: 13/    L1A_offset_or_BX: ${OFF}/" \
        "$BASECFG" > "$SCRIPTS/$cfg"

    out=$(docker exec daq bash -lc "cd $SCRIPTS && \
        PYTHONPATH=\$PWD/analysis python3 pedestal_run.py -d MuxB_fifo \
        -i 10.116.24.180 -o $ROOT/Results/alabama -I -f $cfg" 2>&1)
    dir=$(echo "$out" | grep -o "$ROOT/Results/alabama/MuxB_fifo/pedestal_run/run_[0-9_]*" | head -1)
    rm -f "$SCRIPTS/$cfg"

    if [ -z "$dir" ]; then
        printf '%-8s %-8s %s\n' "$fifo" "$OFF" "RUN-FAILED"
        continue
    fi

    res=$(docker exec daq bash -lc "export PATH=$BIN:\$PATH
        unpack -i $dir/pedestal_run0.raw -o $dir/pedestal_run0.root \
               -M $dir/pedestal_run0.yaml >/dev/null 2>&1
        python3 -c \"
import uproot, numpy as np
try:
    t = uproot.open('$dir/pedestal_run0.root')['runsummary/summary']
    d = t.arrays(['chip','channeltype','adc_stdd'], library='np')
    m = d['channeltype'] == 0
    out = []
    for c in (0, 1, 2):
        s = d['adc_stdd'][m & (d['chip'] == c)]
        out.append('%.2f' % np.median(s) if len(s) else 'n/a')
    print(' '.join(out))
except Exception as e:
    print('ERR ERR ERR')
\"" 2>/dev/null | tail -1)

    printf '%-8s %-8s %-10s %-10s %-10s %s\n' \
           "$fifo" "$OFF" $res "$(basename "$dir")"
done
