#!/usr/bin/env bash
# Regenerate every hexmap under Results/alabama with the hexaboard serial in the
# title and file names, and build a per-board view of the runs.
#
#   ./bin/remap_all.sh            # all runs
#   ./bin/remap_all.sh MuxC_rxeq4 # one DUT directory
#
# The serial for each run comes from Results/alabama/module_ids.json (slot from
# the Mux<S>_ directory, time from the run name, UTC).  Maps are written to
# Results/alabama/<serial>/<slot>/<YYYYMMDD_HHMMSS>/, so one board's whole
# history sits together whichever slot it was in.  Run directories are never
# renamed: RESULTS_*.md cites them.  Runs with no registry entry keep their maps
# beside the data.
set -u
ROOT=/Users/blackmac/Docs/1Research/MMTS
RES=$ROOT/Results/alabama
pat="${1:-Mux*}"

# 🛑 DO NOT reinstate the `rm -rf "$RES"/320[TX]*` that used to be here.  It was
# safe only while raw data lived in Results/alabama/Mux<slot>/ and the serial
# trees held generated maps.  ped_run.sh now writes the RUNS THEMSELVES to
# Results/alabama/<serial>/Mux<slot>/pedestal_run/, so that line deletes the
# data.  Stale maps are removed per run below instead.
n=0
for d in "$RES"/$pat/pedestal_run/run_* "$RES"/320[TX]*/$pat/pedestal_run/run_*; do
    [ -f "$d/pedestal_run0.root" ] || continue
    rm -f "$d"/Mux*_adc_*.png "$d"/Mux*_robust_adc_*.png "$d"/Mux*_stdd*_adc_*.png
    # no -t: the board type comes from characters 5-6 of the serial, so LL/LR/LB
    # runs are not silently plotted on the LD-Full geometry
    out=$(docker exec daq bash -lc "python3 $ROOT/multimodule/debug/hexmap_robust.py $d" 2>&1)
    mod=$(sed -n 's/^module: \([^ ]*\).*/\1/p' <<< "$out" | head -1)
    sig=$(grep -E "robust sigma|stdd/robust" <<< "$out" | awk '{printf "%s %s  ", $1, $4}')
    dut=$(basename "$(dirname "$(dirname "$d")")")
    printf '%-22s %-24s %-18s %s\n' "$dut" "$(basename "$d")" "${mod:-?}" "$sig"
    n=$((n+1))
done
echo "remapped $n runs"
ls -d "$RES"/320T* 2>/dev/null
