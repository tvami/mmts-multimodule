#!/usr/bin/env python3
"""ld5_writemap.py SLOT SUMMARY_JSON -- write a MEASURED link map into the LD Five configs.

Reads a 12+12 probe's summary.json, takes every block with ngood > 0 as live, and
rewrites one file:

  initLDfive-trophyV3-3b_mux<S>_ped.yaml   the ONE config per slot, rewritten
                                           in place: measured DAQ + 2 strongest trg

Why the pedestal arm carries only two trigger links: daq-server refuses START on
ANY listed e-link that is not aligned at run time, and a link can pass a delay
scan and still fail there (HD Top slot A's link8 did, at ngood 110-132).  Each
such refusal costs a 240 s timeout.  An EMPTY elinks_trg hangs forever, so two is
the safe floor.

DAQ polarity is left at 1 always.  LinkAligner only ever WRITES invert=1 and never
clears it, so a polarity mistake on a DAQ link survives until the bitstream is
reloaded and then looks like a hardware fault.
"""
import json
import re
import sys

CFGDIR = "/Users/blackmac/Docs/1Research/MMTS/multimodule/hexactrl-sw/hexactrl-script/configs"

slot, summary_path = sys.argv[1], sys.argv[2]
# Optional 3rd arg: config family.  The LD Five is the default; the LD
# Right/Left partials use `initLD-RL-3b` (2 ROCs, same block->idcode table,
# the dup check refuses a map that would give two halves one identity).
FAMILY = sys.argv[3] if len(sys.argv) > 3 else "initLDfive-trophyV3-3b"
s = json.load(open(summary_path))


def live(kind):
    """[(block index, ngood)] for blocks of this kind that carry a stream."""
    out = []
    for k, v in s.items():
        if kind not in k:
            continue
        n = int(re.search(r"link(\d+)$", k.split(".")[-1]).group(1))
        if v["ngood"] > 0:
            out.append((n, v["ngood"]))
    return sorted(out)


nblocks = sum(1 for k in s if "daq" in k) + sum(1 for k in s if "trg" in k)
if nblocks < 24:
    sys.exit("%s lists only %d blocks -- that is a GATE scan, not a 12+12 probe; "
             "refusing to derive a link map from it" % (summary_path, nblocks))

daq, trg = live("daq"), live("trg")
if not daq:
    sys.exit("no live DAQ links in %s -- refusing to write a map" % summary_path)
print("  measured daq %s" % [n for n, _ in daq])
print("  measured trg %s" % [n for n, _ in trg])

# DAQ idcodes are TOPOLOGY labels, (sector<<5)|(chip<<2)|half, not block numbers.
# The probe config's positional codes gave link9 -> 77 (= chip 3 on a 3-ROC
# board): the unpacker reported a chip 3 and the run halted at 64 events on
# both B and C (2026-09-02).  Assign Chiara's codes to the live blocks in order,
# exactly as the working HD Top ped file does (0,1,4,5,40 on the same links).
# Keyed by BLOCK number, never by position in the live list: slot A measured
# {0,1,4,9} (link5 dead) on 2026-09-02 and a positional table then handed link9
# idcode 37, i.e. chip1 half1, which is link5's identity.  Chiara's blocks are
# {0,1,4,5,8}; this firmware moves her 8 to 9 (same shift as the HD Tops).
LD_DAQ_IDCODES = {0: 0, 1: 1, 4: 36, 5: 37, 8: 72, 9: 72}

# Trigger idcodes are the plain block enumeration.  They are NOT read out in
# randomL1A (the working HD Top runs carry 0 triggerhgcroc entries), so they do
# not have to be topology-correct the way the DAQ ones do.  Embedded here so a
# slot needs exactly one yaml on disk; this used to be parsed out of a
# `_probe12` file that was byte-identical to the _ped outside the elink lists.
LD_TRG_IDCODES = {n: v for n, v in enumerate(
    [0, 1, 36, 37, 72, 73, 74, 75, 76, 77, 78, 79])}

missing = [n for n, _ in daq if n not in LD_DAQ_IDCODES]
if missing:
    sys.exit("live DAQ block(s) %s have no topology idcode; refusing to guess "
             "(a wrong idcode halts the run after a perfect finder line)" % missing)
did = {n: LD_DAQ_IDCODES[n] for n, _ in daq}
dup = sorted({v for v in did.values() if list(did.values()).count(v) > 1})
if dup:
    sys.exit("blocks %s share idcode(s) %s -- two halves cannot carry one identity"
             % (sorted(did), dup))
tid = LD_TRG_IDCODES


def block(kind, items, ids, note):
    out = "  elinks_%s:\n" % kind
    for line in note:
        out += "    # %s\n" % line
    for n, ng in items:
        out += "    - { name : 'link%d',%s polarity: 1, idcode: %d }   # ngood %d\n" % (
            n, "" if n > 9 else " ", ids[n], ng)
    return out


def rewrite(path, src, daq_block, trg_block, header):
    """Replace both elink lists in `src` and write it to `path`.

    Counts substitutions rather than comparing before/after: re-writing a block
    with content identical to what is already there is a legitimate no-op (it
    happens whenever the _ped arm keeps the default's DAQ list), and an
    inequality check calls that a failure.
    """
    out, ndaq = re.subn(r"  elinks_daq:\n(    #[^\n]*\n)*(    - \{[^\n]*\n)+",
                        daq_block, src, count=1)
    out, ntrg = re.subn(r"  elinks_trg:\n(    #[^\n]*\n)*(    - \{[^\n]*\n)+",
                        trg_block, out, count=1)
    if not (ndaq and ntrg):
        sys.exit("could not locate elinks_daq/elinks_trg in %s (daq=%d trg=%d)"
                 % (path, ndaq, ntrg))
    if not out.startswith("#"):
        out = header + out
    open(path, "w").write(out)
    return out


run = summary_path.rstrip("/").split("/")[-2]
dnote = ["MEASURED slot %s, probe run %s -- live DAQ blocks %s." % (slot, run, [n for n, _ in daq]),
         "Chiara's shipped file guesses {0,1,4,5,8}; the multimodule firmware's",
         "capture-block numbering gives link9, exactly as on the HD Tops.",
         "idcodes are topology (sector<<5|chip<<2|half), Chiara's, in block order.",
         "DAQ polarity stays 1: the invert is sticky until a bitstream reload."]
# ONE yaml per slot: the _ped file is the only LD Five config on disk, and it is
# rewritten in place from its own contents.  The `_probe12` and all-links slot
# defaults are gone (2026-09-02); ld5_slot.sh derives a throwaway 12-block probe
# config from this file when it needs one.
strong = sorted(trg, key=lambda x: -x[1])[:2]
pnote = ["PEDESTAL arm: only the %d strongest trigger links, of %d alive." % (len(strong), len(trg)),
         "daq-server refuses START on any listed unaligned e-link and a link can",
         "pass a delay scan yet fail at run time (HD Top slot A link8), costing a",
         "240 s timeout each.  An empty elinks_trg hangs, so this is the floor.",
         "Full measured trigger set at probe time: %s." % [n for n, _ in trg]]
ppath = "%s/%s_mux%s_ped.yaml" % (CFGDIR, FAMILY, slot)
ped = rewrite(ppath, open(ppath).read(),
              block("daq", daq, did, dnote), block("trg", sorted(strong), tid, pnote),
              "# LD FIVE, slot %s, PEDESTAL config -- MEASURED map, probe run %s.\n"
              "# First LD Fives on this bench (2026-09-02).\n" % (slot, run))
# trg_phase must name a link that is actually in elinks_trg: the shipped files
# carry link0 there whatever the trigger list says, and the HD Top configs that
# ran clean all had the same link in both.
n0, _ = sorted(strong)[0]
ped, nph = re.subn(r"  elinks_trg_phase:[^\n]*\n(    - \{[^\n]*\n)+",
                   "  elinks_trg_phase: ##only needed when using external L1A source\n"
                   "    - { name : 'link%d', polarity: 1, idcode: %d }\n" % (n0, tid[n0]),
                   ped, count=1)
if nph:
    open(ppath, "w").write(ped)

print("  wrote %s (trg %s)" % (ppath.split("/")[-1], [n for n, _ in sorted(strong)]))
