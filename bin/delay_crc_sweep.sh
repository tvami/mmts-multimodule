#!/usr/bin/env bash
# STEP 1 of PLAN_2026-08-29: a delay scan scored by CRC on REAL PAYLOAD.
#
# The stock delayScan transmits only 0xACCCCCCC -- transition-rich, and it never
# contains the isolated '1' in a run of zeros that this bench actually drops.  So
# every existing delay number is measured against a pattern that cannot show the
# defect.  This sweeps the IDELAY taps and scores CRC pass on real pedestal data.
#
# Delays are written DURING the acquisition (see delay_midrun.sh): daq-server
# re-runs alignment inside `start`, so anything written earlier is overwritten.
# Scoring therefore ignores the first 20 % of each run, which precedes the write.
#
#   ./delay_crc_sweep.sh SLOT NPOINTS
set -u
SLOT="${1:-C}"; N="${2:-16}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
for i in $(seq 0 $((N-1))); do
    tap=$(( i * 511 / (N-1) ))
    d=""
    for L in 0 1 4 5 8 9; do d="$d $L:$tap"; done
    out=$(./bin/delay_midrun.sh "$SLOT" "$d" 16 "sweep" 2>&1)
    dir=$(echo "$out" | grep -o "$ROOT/Results/alabama/.*run_[0-9_]*" | head -1)
    held=$(echo "$out" | grep -cE "^link[0-9]+ +1 +$tap ")
    if [ -z "$dir" ]; then printf 'tap %3d  RUN-FAILED\n' "$tap"; continue; fi
    # The puller's inotify unpack does not always fire on these runs; unpack by
    # hand rather than silently losing the point.
    if [ ! -f "$dir/pedestal_run0.root" ]; then
        docker exec daq bash -lc "export PATH=/opt/hexactrl/ROC3_dev_docker/bin:\$PATH
            unpack -i $dir/pedestal_run0.raw -o $dir/pedestal_run0.root \
                   -M $dir/pedestal_run0.yaml" >/dev/null 2>&1
    fi
    [ -f "$dir/pedestal_run0.root" ] || { printf 'tap %3d  NO-ROOT\n' "$tap"; continue; }
    docker exec daq bash -lc "python3 -c \"
import uproot, numpy as np
t=uproot.open('$dir/pedestal_run0.root')['unpacker_data/hgcroc']
a=t.arrays(['chip','half','corruption'],library='np')
chip,half,code=a['chip'],a['half'],a['corruption'].astype('int64')
r=[]
for c in (0,1,2):
    for h in (0,1):
        m=np.where((chip==c)&(half==h))[0]
        if not len(m): r.append('  -  '); continue
        v=code[m][len(m)//5:]          # drop the pre-write fifth
        r.append('%.3f'%(((v&2)==0).mean()))
print('tap %3d  held %d/6  ' % ($tap,$held) + ' '.join(r))
\"" 2>/dev/null
done
