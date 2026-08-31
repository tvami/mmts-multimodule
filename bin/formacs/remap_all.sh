#!/usr/bin/env bash
# remap_all.sh [DUT-pattern] -- regenerate every hexmap under the results root.
#
#   ./remap_all.sh            # all runs
#   ./remap_all.sh MuxC       # one DUT directory
#
# Maps go to <results>/<serial>/<slot>/<UTC>/ so one board's history sits
# together whichever slot it was in. Run directories are never renamed.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"

pat="${1:-Mux*}"

# 🛑 DO NOT add an `rm -rf "$RESULTS"/320[TX]*` here. ped_run.sh writes the RUNS
# THEMSELVES under <results>/<serial>/, so that line deletes the data. Stale maps
# are removed per run below instead.
n=0
for d in "$RESULTS"/$pat/pedestal_run/run_* "$RESULTS"/320[TX]*/$pat/pedestal_run/run_*; do
    [ -f "$d/pedestal_run0.root" ] || continue
    rm -f "$d"/Mux*_adc_*.png "$d"/Mux*_robust_adc_*.png "$d"/Mux*_stdd*_adc_*.png
    # No -t: the board type comes from characters 5-6 of the serial, so LL/LR/LB
    # runs are not silently plotted on the LD-Full geometry.
    out=$(python3 "$DEBUG/hexmap_robust.py" "$d" 2>&1)
    mod=$(sed -n 's/^module: \([^ ]*\).*/\1/p' <<< "$out" | head -1)
    sig=$(grep -E "robust sigma|stdd/robust" <<< "$out" | awk '{printf "%s %s  ", $1, $4}')
    dut=$(basename "$(dirname "$(dirname "$d")")")
    printf '%-22s %-24s %-18s %s\n' "$dut" "$(basename "$d")" "${mod:-?}" "$sig"
    n=$((n+1))
done
echo "remapped $n runs"
