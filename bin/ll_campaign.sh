#!/usr/bin/env bash
# ll_campaign.sh -- LD Left campaign, 2026-09-02: probe every slot, pedestal the
# ones that pass, never let one slot's failure stop the next.  Unattended.
#
# Order B, C, A: the two clean slots first; A needed 3 bring-up tries today.
# Each slot goes through partial_slot.sh, whose exit code is the verdict:
#   0 pedestals ran   1 bring-up failed   2 no probe   3 map refused   4 gate failed
# macOS ships bash 3.2: no associative arrays (the first run died on
# `declare -A` after slot B and never reached C or A).  Plain variables.
set -u
ROOT=/Users/blackmac/Docs/1Research/MMTS
LOG=$ROOT/Results/alabama/ll_campaign_$(date -u +%Y%m%d_%H%M%S).log
FAMILY=${FAMILY:-initLD-RL-3b}; BOARD=${BOARD:-LD-Semi}
NROCS=${NROCS:-2}; LABEL=${LABEL:-ll}; N=${N:-10}
SLOTS="${*:-C A}"
summary=""
echo "campaign $FAMILY ($LABEL)  slots [$SLOTS]  probe=$([ "${SKIP_PROBE:-0}" = 1 ] && echo no || echo yes)  started $(date '+%H:%M:%S %Z')  log $LOG" | tee "$LOG"
for S in $SLOTS; do
    "$ROOT/multimodule/bin/partial_slot.sh" "$S" "$FAMILY" "$BOARD" "$NROCS" "$LABEL" "$N" 2>&1 | tee -a "$LOG"
    rc=${PIPESTATUS[0]}
    case $rc in
        0) v="PEDESTALS RAN (read the table)";;
        1) v="BRING-UP FAILED";;
        2) v="PROBE GAVE NO SUMMARY";;
        3) v="MAP REFUSED (idcode/dup guard)";;
        4) v="GATE FAILED";;
        5) v="FIRST PEDESTAL STALLED (raw kept for forensics)";;
        *) v="exit $rc";;
    esac
    printf '\n>>>>>>>>>> slot %s verdict: %s   [%s]\n' "$S" "$v" "$(date '+%H:%M:%S %Z')" | tee -a "$LOG"
    summary="$summary  slot $S : $v"$'\n'
done
{
  echo; echo "========== CAMPAIGN SUMMARY  $(date '+%H:%M:%S %Z')"; printf '%s' "$summary"
} | tee -a "$LOG"
