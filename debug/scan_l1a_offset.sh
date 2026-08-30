#!/bin/bash
# Find a working L1A_offset_or_BX for pedestal runs on the Alabama bench.
#
# The automatic l1aOffsetFinder does not work here: on 2026-08-25 it produced
# fifo_latency=96 for link1 (out of range for the 5-bit field -> uHAL exception
# -> daq-server died), and on the retry it simply fell back to the config's
# defaults (fifo_latency=0, L1A_offset_or_BX=13).  With those, the unpacker
# decodes 0 events out of a 10.6 MB raw file.
#
# This scans L1A_offset_or_BX with method:'manual' and reports how many events
# the unpacker actually decodes at each setting.  DAQ-only: no power cycles, no
# I2C beyond the normal per-run configure.
#
# Usage: ./scan_l1a_offset.sh "0 4 8 12 13 16 20 24 28 32"  [fifo_latency]

set -u
ROOT=/Users/blackmac/Docs/1Research/MMTS
SCRIPTS=$ROOT/multimodule/hexactrl-sw/hexactrl-script
BASECFG=$SCRIPTS/configs/initLD-trophyV3-3b_muxB.yaml
BIN=/opt/hexactrl/ROC3_dev_docker/bin

OFFSETS="${1:-0 4 8 12 13 16 20 24 28 32}"
FIFO="${2:-0}"

printf '%-10s %-14s %-12s %s\n' "L1Aoffset" "fifo_latency" "events" "run dir"

for off in $OFFSETS; do
    cfg="configs/_scan_l1a_${off}_${FIFO}.yaml"
    sed -e "s/    method: 'automatic'/    method: 'manual'/" \
        -e "s/    fifo_latency: 0 #/    fifo_latency: ${FIFO} #/" \
        -e "s/    L1A_offset_or_BX: 13/    L1A_offset_or_BX: ${off}/" \
        "$BASECFG" > "$SCRIPTS/$cfg"

    out=$(docker exec daq bash -lc "cd $SCRIPTS && \
        PYTHONPATH=\$PWD/analysis python3 pedestal_run.py -d MuxB_scan \
        -i 10.116.24.180 -o $ROOT/Results/alabama -I -f $cfg" 2>&1)
    dir=$(echo "$out" | grep -o "$ROOT/Results/alabama/MuxB_scan/pedestal_run/run_[0-9_]*" | head -1)

    if [ -z "$dir" ]; then
        printf '%-10s %-14s %-12s %s\n' "$off" "$FIFO" "RUN-FAILED" "-"
        rm -f "$SCRIPTS/$cfg"
        continue
    fi

    n=$(docker exec daq bash -lc "export PATH=$BIN:\$PATH
        unpack -i $dir/pedestal_run0.raw -o $dir/pedestal_run0.root \
               -M $dir/pedestal_run0.yaml >/dev/null 2>&1
        python3 -c \"
import uproot
try:
    print(uproot.open('$dir/pedestal_run0.root')['unpacker_data/hgcroc'].num_entries)
except Exception as e:
    print('ERR')
\"" 2>/dev/null | tail -1)

    printf '%-10s %-14s %-12s %s\n' "$off" "$FIFO" "$n" "$(basename "$dir")"
    rm -f "$SCRIPTS/$cfg"
done
