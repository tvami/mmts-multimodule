#!/usr/bin/env bash
# finder_positions.sh RUN_DIR... -- print the offset finder's per-link header
# positions for each pedestal run.  This one line is the fast-command diagnostic:
# every link at the same position (23 on this bench) is healthy; a link MISSING
# from the line or far from the others has latched its BCR at a random orbit
# offset (the wrong EdgeSel_T1 for its slot) and its capture will read idles.
for R in "$@"; do
    printf "%-60s %s\n" "$(basename "$(dirname "$(dirname "$R")")")/$(basename "$R")" \
        "$(grep -h 'header positions' "$R/daq-server.log" 2>/dev/null | tail -1 | sed 's/.*positions//')"
done
