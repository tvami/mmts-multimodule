#!/usr/bin/env python3
"""Build an HD Full config that only RUNS a subset of the six chips.

Why
---
The bench supply limits at 3.23 A. Measured 2026-08-28:

    base (Kria + mux, module off)            0.39 A
    + 6 ROCs powered, out of reset, idle     1.08 A   (~0.115 A/chip static)
    + daq-server running, ROCs clocking      2.97 A   (~0.43  A/chip)
    fully running, expected                  ~6 A     (~0.93  A/chip)

2.97 A against a 3.23 A limit is 0.26 A of headroom, and the ROC configure step
-- the one that pushes toward 6 A -- has never completed on this module. So run
fewer chips and give the survivors room.

Power cannot be cut per chip: EN_Mx, S*_PWR_EN and RSTB are all per-SLOT. What
can be done is stop a chip running via Top.RunL/RunR, which removes the dynamic
current while leaving it powered and answering I2C. It must keep answering:
Link.find_board_for_rocs demands an EXACT six-address match, so silencing a chip
by not enabling it would make the board unidentifiable.

elinks_daq/elinks_trg are trimmed to the surviving chips' links too, because
daq-server refuses START unless every listed e-link aligns.

Chip -> ROC block -> DAQ links (idcode = sector<<5 | chip<<2 | half):

    chip 0  roc_s0_0  links 0,1        chip 3  roc_s1_1  links 6,7
    chip 1  roc_s0_1  links 2,3        chip 4  roc_s2_0  links 8,9
    chip 2  roc_s1_0  links 4,5        chip 5  roc_s2_1  links 10,11

Default keeps chips 2 and 4: they carry links 5 and 8, the only two that always
passed CRC on the LD Full.

    python3 mk_partial_hd_cfg.py                 # keep 2,4
    python3 mk_partial_hd_cfg.py --keep 2 4 0    # keep three
"""
import argparse
import pathlib
import re
import sys

CONFIGS = pathlib.Path("/Users/blackmac/Docs/1Research/MMTS/multimodule/"
                       "hexactrl-sw/hexactrl-script/configs")
BASE = CONFIGS / "initHD-trophyV3_muxC_ped.yaml"

CHIP_BLOCK = {0: "roc_s0_0", 1: "roc_s0_1", 2: "roc_s1_0",
              3: "roc_s1_1", 4: "roc_s2_0", 5: "roc_s2_1"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, nargs="+", default=[2, 4],
                    metavar="CHIP", help="chips to leave running (0-5)")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    keep = sorted(set(args.keep))
    if not keep or any(c not in CHIP_BLOCK for c in keep):
        sys.exit("chips must be in 0..5")
    keep_links = sorted(l for c in keep for l in (2 * c, 2 * c + 1))
    out = pathlib.Path(args.out) if args.out else \
        CONFIGS / ("initHD-trophyV3_muxC_run" + "".join(str(c) for c in keep) + ".yaml")

    text = BASE.read_text()

    # --- trim the e-link lists to the surviving chips -----------------------
    def trim(body):
        kept = []
        for line in body.splitlines(keepends=True):
            m = re.match(r"\s*- \{ name : 'link(\d+)'", line)
            if m and int(m.group(1)) not in keep_links:
                continue
            kept.append(line)
        return "".join(kept)

    for block in ("elinks_daq", "elinks_trg"):
        m = re.search(r"(^  %s:\n)((?:    - .*\n)+)" % block, text, re.M)
        if not m:
            sys.exit("could not find %s" % block)
        text = text[:m.start(2)] + trim(m.group(2)) + text[m.end(2):]

    # elinks_trg_phase names a single link and the shipped file points it at
    # link0, which belongs to chip 0 -- silenced in most subsets.  Repoint it at
    # the lowest surviving link so it never names a chip that is not running.
    first = keep_links[0]
    m = re.search(r"(^  elinks_trg_phase:.*\n)(    - .*\n)", text, re.M)
    if m:
        idcode = (first // 2) // 2 * 32 + (first // 2) * 4 + (first % 2)
        text = (text[:m.start(2)]
                + "    - { name : 'link%d', polarity: 1, idcode: %d }\n" % (first, idcode)
                + text[m.end(2):])

    # --- silence the chips we are not running -------------------------------
    # Edit inside each roc_s* section only: RunL/RunR appear once per chip and
    # a global replace would hit all six.
    parts = re.split(r"(?m)^(roc_s\d_\d:)$", text)
    rebuilt = [parts[0]]
    silenced = []
    for name, body in zip(parts[1::2], parts[2::2]):
        chip = next(c for c, n in CHIP_BLOCK.items() if n + ":" == name)
        if chip not in keep:
            before = body
            body = body.replace("        RunL: 1\n", "        RunL: 0\n")
            body = body.replace("        RunR: 1\n", "        RunR: 0\n")
            if body == before:
                sys.exit("no RunL/RunR found in %s" % name)
            silenced.append(chip)
        rebuilt += [name, body]
    text = "".join(rebuilt)

    out.write_text(text)
    print("wrote %s" % out.name)
    print("  running chips : %s  (%s)" % (keep, ", ".join(CHIP_BLOCK[c] for c in keep)))
    print("  silenced      : %s  (RunL/RunR = 0, still powered and on I2C)" % silenced)
    print("  e-links kept  : %s" % keep_links)
    print("  est. current  : %.2f A  (0.39 base + 6x0.115 static + %dx0.82 running)"
          % (0.39 + 6 * 0.115 + len(keep) * 0.82, len(keep)))


if __name__ == "__main__":
    main()
