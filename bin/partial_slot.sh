#!/usr/bin/env bash
# partial_slot.sh SLOT FAMILY BOARD NROCS LABEL [NRUNS] -- one slot end to end.
#
#   bring-up -> 12+12 probe -> write the MEASURED map into <FAMILY>_mux<S>_ped.yaml
#            -> gate -> NRUNS pedestals -> finder line -> hexmaps + per-half check
#
# Generalised from ld5_slot.sh (2026-09-02) so the LD Right/Left partials run
# through the same guarded path.  Example:
#   partial_slot.sh B initLD-RL-3b LD-Semi 2 ll 10
#
# Exit codes: 1 bring-up failed, 2 probe gave no summary, 3 map refused,
# 4 gate failed, 0 pedestals ran (their table says how well).  Every stage
# prints a "########## SLOT: stage" line so a campaign log reads at a glance.
set -u
SLOT="${1:?slot A|B|C}"; FAMILY="${2:?config family}"; BOARD="${3:?--board value}"
NROCS="${4:?expected ROC count}"; LABEL="${5:?run label}"; N="${6:-10}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
CFGDIR=$ROOT/multimodule/hexactrl-sw/hexactrl-script/configs
KRIA=daq@10.116.25.124
FW=multimodule-hd-tester-trophy-v3-rxeq4
# LD Fulls run off the power management board (EN_Mx), so they OMIT
# --external-power; every partial so far needs it.  POWER="" for a full module.
POWER="${POWER---external-power}"
PED="$CFGDIR/${FAMILY}_mux${SLOT}_ped.yaml"
[ -f "$PED" ] || { echo "no config $PED"; exit 3; }

SERIAL=$(python3 /Users/blackmac/Docs/1Research/MMTS/multimodule/bin/module_of.py "$SLOT")
[ -n "$SERIAL" ] || { echo "slot $SLOT has no module in the registry -- run register_boards.py first"; exit 3; }

say() { printf '\n########## %s: %s   [%s]\n' "$SLOT" "$*" "$(date '+%H:%M:%S %Z')"; }

say "bring-up ($BOARD, $NROCS ROCs, ${POWER:-power management board})"
out=$(ssh "$KRIA" "pkill -f '[z]mq_server'; sleep 2; cd ~/multimodule && \
      MMTS_FW=$FW EXPECT_ROCS=$NROCS ~/up_verified.sh $SLOT $POWER --board $BOARD" 2>&1)
echo "$out" | tail -4
echo "$out" | grep -q '^READY' || {
    say "BRINGUP FAILED -- last bring-up log:"
    ssh "$KRIA" 'tail -12 ~/bu_'"$SLOT"'.log' 2>&1
    exit 1; }

if [ "${SKIP_PROBE:-0}" = "1" ]; then
    say "SKIPPING the 12+12 probe (SKIP_PROBE=1): the shipped map is already known good"
else
say "12+12 probe"
PROBE_CFG="${FAMILY}_mux${SLOT}_probe12_auto.yaml"
python3 - "$PED" "$CFGDIR/$PROBE_CFG" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
ids = [0, 1, 36, 37, 72, 73, 74, 75, 76, 77, 78, 79]
def blk(kind):
    out = "  elinks_%s:\n    # AUTO-GENERATED 12-block probe; partial_slot.sh removes it after the scan.\n" % kind
    for n, i in enumerate(ids):
        out += "    - { name : 'link%d',%s polarity: 1, idcode: %d }\n" % (n, "" if n > 9 else " ", i)
    return out
s = open(src).read()
s, a = re.subn(r"  elinks_daq:\n(    #[^\n]*\n)*(    - \{[^\n]*\n)+", blk("daq"), s, count=1)
s, b = re.subn(r"  elinks_trg:\n(    #[^\n]*\n)*(    - \{[^\n]*\n)+", blk("trg"), s, count=1)
if not (a and b):
    sys.exit("could not build a probe config from %s" % src)
open(dst, "w").write(s)
PY
[ -f "$CFGDIR/$PROBE_CFG" ] || { say "could not derive a probe config -- stopping"; exit 2; }
trap 'rm -f "$CFGDIR/$PROBE_CFG"' EXIT
probe_out=$("$ROOT/multimodule/bin/delay_scan.sh" "$SLOT" "configs/$PROBE_CFG" 2>&1)
echo "$probe_out" | tail -4
PROBE=$(grep -oE "$ROOT/Results/alabama/[^ ]*/delay_scan/[0-9_]+" <<<"$probe_out" | head -1)
[ -n "$PROBE" ] && [ -f "$PROBE/summary.json" ] \
    || { say "probe produced no summary.json -- stopping"; exit 2; }

say "writing the measured map into ${PED##*/}"
python3 "$ROOT/multimodule/bin/ld5_writemap.py" "$SLOT" "$PROBE/summary.json" "$FAMILY" || exit 3

# 🔑 A SECOND bring-up, because the 12+12 probe poisons the one it ran in.
# Measured on slot C 2026-09-02 19:22Z vs 19:25Z: identical applied config
# (same RunL, same idcodes), no probe = 10000 events, probe first = stall at 64.
# The probe arms all 12 capture blocks and LinkAligner only ever WRITES
# invert=1, never clears it, so the 9 dead blocks stay latched.  Every clean
# 10-pedestal set today came from a bring-up with no probe in it.
say "SECOND bring-up (the probe poisons its own bring-up)"
out=$(ssh "$KRIA" "pkill -f '[z]mq_server'; sleep 2; cd ~/multimodule && \
      MMTS_FW=$FW EXPECT_ROCS=$NROCS ~/up_verified.sh $SLOT $POWER --board $BOARD" 2>&1)
echo "$out" | tail -3
echo "$out" | grep -q '^READY' || { say "SECOND BRINGUP FAILED -- stopping"; exit 1; }
fi

say "gate"
gate=$("$ROOT/multimodule/bin/delay_scan.sh" "$SLOT" "configs/${FAMILY}_mux${SLOT}_ped.yaml" 2>&1 | tail -5)
echo "$gate"
grep -q "GATE: PASS" <<<"$gate" || { say "GATE FAILED -- not spending pedestals"; exit 4; }

DUT="Mux${SLOT}_${LABEL}"
# Smoke test first: ONE pedestal.  A stalled run costs a 240 s timeout and
# wedges daq-server, so ten in a row is 40 min of the same answer (slot B on
# the LD Left, 2026-09-02).  One stall = verdict 5, raw kept, next slot.
say "pedestal 1 of $N (smoke test)"
smoke=$(PED_BASECFG=$PED PED_DUT=$DUT PED_BOARD=$BOARD PED_EXTPOWER="${POWER:+1}" PED_TRIES=1 \
        "$ROOT/multimodule/bin/ped_run.sh" "$SLOT" 1 "$LABEL" 10000 2>&1 | tail -5)
echo "$smoke"
grep -qE '^1 +[0-9]{5,}' <<<"$smoke" || {
    say "FIRST PEDESTAL STALLED -- not spending $((N - 1)) more; raw kept under $DUT"
    exit 5; }

say "pedestals 2..$N"
PED_BASECFG=$PED PED_DUT=$DUT PED_BOARD=$BOARD PED_EXTPOWER="${POWER:+1}" \
    "$ROOT/multimodule/bin/ped_run.sh" "$SLOT" "$((N - 1))" "$LABEL" 10000 2>&1 | tail -$((N + 3))

say "finder header positions (23 everywhere = right edge)"
"$ROOT/multimodule/bin/finder_positions.sh" \
    "$ROOT/Results/alabama/$SERIAL/$DUT/pedestal_run/"run_* 2>/dev/null | tail -3

say "hexmaps + per-half check (every half adc_stdd > 0, else FROZEN)"
docker run --rm --platform linux/amd64 -v "$ROOT:$ROOT" -w "$ROOT" hexactrl-client:local "
for d in $ROOT/Results/alabama/$SERIAL/$DUT/pedestal_run/run_*; do
  [ -f \$d/pedestal_run0.root ] || continue
  echo \"=== \$(basename \$d)\"
  python3 $ROOT/multimodule/debug/hexmap_robust.py \$d 2>&1 | grep -E 'adc_stdd|above'
done
python3 -c \"
import uproot,numpy as np,glob,os
for d in sorted(glob.glob('$ROOT/Results/alabama/$SERIAL/$DUT/pedestal_run/run_*')):
    if not os.path.exists(d+'/pedestal_run0.root'): continue
    t=uproot.open(d+'/pedestal_run0.root')['unpacker_data/hgcroc']
    a=t.arrays(['chip','half','adc'],library='np'); k=a['chip']*10+a['half']
    print(os.path.basename(d),' '.join('c%dh%d %.1f/%.2f%s'%(kk//10,kk%10,a['adc'][k==kk].mean(),a['adc'][k==kk].std(),' FROZEN' if a['adc'][k==kk].std()==0 else '') for kk in sorted(set(k.tolist()))))
\"" 2>&1 | tail -$((2 * N + 4))

say "DONE"
