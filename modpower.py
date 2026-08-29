#!/usr/bin/env python3
"""Power a module slot on or off via the power management board (TCA9535 @ 0x27).

With the bench supply wired through the power management board there is no
switch to flick: EN_Mx is the only thing that cuts module power.  This drives it
directly, so a module can be power-cycled without touching the supply and
without `kconn_pwr`, which cuts the Kria's payload rail instead.

    python3 modpower.py C off      # drop EN_M3, module C unpowered
    python3 modpower.py C on       # raise EN_M3
    python3 modpower.py off        # all three slots off
    python3 modpower.py C cycle    # off, settle, on

Constants come from enableROCs_alabama so the two cannot drift apart; importing
it is safe, its main() is guarded.

⚠️  Powering a module ON glitches the PL I2C master into a wedged state -- that
is why enableROCs_alabama runs a fw-loader reset straight afterwards.  This
script does NOT reset the master, because its usual use is `off`.  After an `on`
or a `cycle`, run a normal bring-up (`up_verified.sh SLOT ...`); do not expect
bare I2C to work in between.

⚠️  EN_Mx is a latch: it survives a firmware reload, and `--recover` /
`kconn_pwr off` clears it.  So "off" here really does stay off until something
sets it again.
"""
import sys
import time

from enableROCs_alabama import (EN_M, PWR_BOARD, PWR_BOARD_DIR_P0,
                                PWR_BOARD_DIR_VAL, PWR_BOARD_OUT_P0,
                                SUB_SPARE, SWITCH, _seq)

SETTLE = 2.0   # seconds to hold the rail down so the ROCs really lose state


def set_enable(mask, via=0x77):
    """Write the EN_M1..3 bit mask to the power management board.

    The board hangs off the Spare sub-bus of *any* switch, so `via` only picks
    the route.  Direction is rewritten every time: after a payload power cycle
    the expander comes back with its pins as inputs, and writing the output
    register alone would silently do nothing.
    """
    _seq(via, SUB_SPARE, [(PWR_BOARD, PWR_BOARD_DIR_P0, PWR_BOARD_DIR_VAL),
                          (PWR_BOARD, PWR_BOARD_OUT_P0, mask)])


def main():
    args = [a for a in sys.argv[1:]]
    slot = None
    if args and args[0].upper() in SWITCH:
        slot = args.pop(0).upper()
    action = (args[0] if args else "off").lower()
    if action not in ("on", "off", "cycle"):
        print(__doc__)
        return 2

    via = SWITCH[slot] if slot else 0x77
    on_mask = EN_M[slot] if slot else sum(EN_M.values())
    who = f"slot {slot} (EN_M{'ABC'.index(slot) + 1})" if slot else "all slots"

    if action in ("off", "cycle"):
        # 0x00 drops every EN_Mx.  Only slot C is populated, so there is nothing
        # to preserve; doing a read-modify-write instead would mean a READ, and
        # reads are what wedge this master.
        print(f"[pwr] {who} OFF")
        set_enable(0x00, via)

    if action == "cycle":
        time.sleep(SETTLE)

    if action in ("on", "cycle"):
        print(f"[pwr] {who} ON (mask 0x{on_mask:02x})")
        set_enable(on_mask, via)
        print("[pwr] master is now probably wedged -- run a bring-up next")

    return 0


if __name__ == "__main__":
    sys.exit(main())
