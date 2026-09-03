#!/usr/bin/env bash
# ld5_slot.sh SLOT [NRUNS] -- bring one LD Five slot up and take it end to end.
#
#   bring-up -> 12+12 probe -> write the MEASURED map into the slot config
#            -> build a _ped arm -> gate -> pedestals -> finder line -> hexmaps
#
# Written 2026-09-02 for the first LD Five campaign, where the shipped link map
# is Chiara's single-slot guess and was wrong on the HD Tops in exactly the same
# way (she lists daq link8, the multimodule firmware gives link9).  Nothing here
# trusts a config: the probe measures, and the measurement is what gets written.
#
# Every stage is guarded.  The failures this is built against, all seen today:
#   * a bring-up that reports FAILED but whose pipeline exits 0 (`ssh ... | tail`)
#     -- so the READY line is grepped from a captured variable, never a pipeline
#   * a delay scan that produces no summary.json and lets the caller read an
#     older scan's PASS as if it were fresh -- delay_scan.sh now refuses that
#   * daq-server dying and leaving 5555 up, so the next stage hangs
set -u
SLOT="${1:?slot A|B|C}"
N="${2:-10}"
ROOT=/Users/blackmac/Docs/1Research/MMTS
CFGDIR=$ROOT/multimodule/hexactrl-sw/hexactrl-script/configs
KRIA=daq@10.116.25.124
FW=multimodule-hd-tester-trophy-v3-rxeq4

say() { printf '\n########## %s: %s\n' "$SLOT" "$*"; }

say "bring-up"
out=$(ssh "$KRIA" "pkill -f '[z]mq_server'; sleep 2; cd ~/multimodule && \
      MMTS_FW=$FW EXPECT_ROCS=3 ~/up_verified.sh $SLOT --external-power --board LD-Five" 2>&1)
echo "$out" | tail -4
# NOT `ssh ... | tail | grep`: a pipeline returns tail's status, so a failed
# bring-up exits 0 and the caller runs pedestals against a dead server.
echo "$out" | grep -q '^READY' || { say "BRINGUP FAILED -- stopping"; exit 1; }

say "12+12 probe (link map is unmeasured for this board type)"
# Take the scan directory from the scan's OWN output, not from `ls -dt`: any
# later scan (the gate, a retry) becomes the newest and a 5-link gate summary
# then looks like a 12+12 probe.  ld5_writemap.py refuses that too, belt and
# braces, but the caller should not be guessing in the first place.
# The 12-block probe config is DERIVED from the slot's one yaml and deleted
# after: a stored `_probe12` was byte-identical to the _ped outside the elink
# lists, and a second copy of the ROC settings is a second thing to forget to
# update (slot A's EdgeSel_T1 was fixed in one file and not the other).
PROBE_CFG="initLDfive-trophyV3-3b_mux${SLOT}_probe12_auto.yaml"
python3 - "$CFGDIR/initLDfive-trophyV3-3b_mux${SLOT}_ped.yaml" "$CFGDIR/$PROBE_CFG" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
ids = [0, 1, 36, 37, 72, 73, 74, 75, 76, 77, 78, 79]
def blk(kind):
    out = "  elinks_%s:\n    # AUTO-GENERATED 12-block probe, do not edit; ld5_slot.sh\n" % kind
    out += "    # writes it from the _ped file and removes it after the scan.\n"
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
echo "$probe_out" | tail -5
PROBE=$(grep -oE "$ROOT/Results/alabama/[^ ]*/delay_scan/[0-9_]+" <<<"$probe_out" | head -1)
SERIAL=$(python3 "$ROOT/multimodule/bin/module_of.py" "$SLOT")
[ -n "$PROBE" ] && [ -f "$PROBE/summary.json" ] \
    || { say "probe produced no summary.json -- stopping"; exit 2; }

say "writing the measured map into the slot config"
python3 "$ROOT/multimodule/bin/ld5_writemap.py" "$SLOT" "$PROBE/summary.json" || exit 3

say "gate"
gate=$("$ROOT/multimodule/bin/delay_scan.sh" "$SLOT" \
       "configs/initLDfive-trophyV3-3b_mux${SLOT}_ped.yaml" 2>&1 | tail -5)
echo "$gate"
grep -q "GATE: PASS" <<<"$gate" || { say "GATE FAILED -- not spending pedestals"; exit 4; }

say "$N pedestals"
PED_BASECFG=$CFGDIR/initLDfive-trophyV3-3b_mux${SLOT}_ped.yaml \
PED_DUT=Mux${SLOT}_ld5 PED_BOARD=LD-Five PED_EXTPOWER=1 \
    "$ROOT/multimodule/bin/ped_run.sh" "$SLOT" "$N" ld5 10000 2>&1 | tail -$((N + 4))

say "finder header positions (23 everywhere = right edge)"
"$ROOT/multimodule/bin/finder_positions.sh" \
    "$ROOT/Results/alabama/$SERIAL/Mux${SLOT}_ld5/pedestal_run/"run_* 2>/dev/null | tail -3

say "hexmaps"
docker run --rm --platform linux/amd64 -v "$ROOT:$ROOT" -w "$ROOT" hexactrl-client:local \
  "for d in $ROOT/Results/alabama/$SERIAL/Mux${SLOT}_ld5/pedestal_run/run_*; do
     [ -f \$d/pedestal_run0.root ] || continue
     python3 $ROOT/multimodule/debug/hexmap_robust.py \$d 2>&1 | grep -E 'live normal|adc_stdd|above'
   done" 2>&1 | tail -12

say "DONE"
