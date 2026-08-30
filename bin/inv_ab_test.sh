#!/usr/bin/env bash
# inv_ab_test.sh -- A/B the ROC `in_inv_cmd_rx` bit, scored by SUPPLY CURRENT.
#
# in_inv_cmd_rx selects the polarity of the ROC's incoming fast-command/clock
# stream.  Get it wrong and the ROC's PLL never locks: I2C still works (separate
# low-speed path), every e-link is dead, and the chip draws only its static
# current.  On the 2026-08-28 HD Full all three of those are true at once, and
# the module draws ~1.08 A against an expected ~6 A.
#
# Link alignment turned out to be a poor readout -- everything is dead either
# way.  Current is unambiguous, so this script just gets each variant configured
# and then STOPS for the current to be read off the supply by hand.
#
# Each variant needs its OWN fresh bring-up: a ROC config only reaches the
# silicon on the FIRST successful initialize of an i2c-server's life.
set -u

VARIANT="${1:?usage: inv_ab_test.sh 0|1}"
case "$VARIANT" in
    0) CFG=configs/initHD-trophyV3_muxC_ped.yaml ;;
    1) CFG=configs/initHD-trophyV3_muxC_ped_inv1.yaml ;;
    *) echo "variant must be 0 or 1"; exit 2 ;;
esac

ROOT=/Users/blackmac/Docs/1Research/MMTS
KRIA=daq@10.116.24.180
NROC=$(grep -c '^roc_s[0-9_]*:' "$ROOT/multimodule/hexactrl-sw/hexactrl-script/$CFG")

echo "### in_inv_cmd_rx = $VARIANT   ($CFG)"

# Verify the bit really is what we think before spending a bring-up on it.
got=$(grep -c "in_inv_cmd_rx: $VARIANT" "$ROOT/multimodule/hexactrl-sw/hexactrl-script/$CFG")
[ "$got" = "$NROC" ] || { echo "ABORT: config has $got/$NROC blocks at in_inv_cmd_rx=$VARIANT"; exit 3; }

echo "--- fresh bring-up (needed: config applies only on a server's first initialize)"
ssh "$KRIA" "EXPECT_ROCS=$NROC timeout 900 ~/up_verified.sh C --board HD-Full" \
    | tail -2 | grep -q '^READY' || { echo "BRING-UP FAILED"; exit 1; }
echo "    READY -- read the supply current NOW (powered, pre-configure)"

"$ROOT/multimodule/bin/align_probe.sh" "$CFG" 2>&1 | grep -vE '^\s*$'

echo
echo "### in_inv_cmd_rx=$VARIANT configured -- READ THE SUPPLY CURRENT NOW"
