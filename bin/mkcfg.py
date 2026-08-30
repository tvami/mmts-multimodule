#!/usr/bin/env python3
"""Build a run-config variant by overriding arbitrary keys.

The sed-based injection in ped_run.sh only knows about the CLPS registers and
cannot target one half of one ROC -- `Inv_vref: 400` appears six times in an
LD Full config (two halves x three ROCs).  This takes explicit dotted paths.

  ./mkcfg.py BASE.yaml OUT.yaml roc_s0.sc.ReferenceVoltage.1.Inv_vref=300 ...

Integer-looking path components index into yaml integer keys (block ids), which
is what the ROC config uses for half 0 / half 1.

⚠️ A ROC register change only reaches the silicon on the FIRST successful
initialize of an i2c-server's life -- run with a fresh bring-up and read the
value back before believing any result.
"""
import sys
import yaml


def main():
    base, out, *overrides = sys.argv[1:]
    cfg = yaml.safe_load(open(base))
    for ov in overrides:
        path, val = ov.split('=', 1)
        keys = [int(k) if k.lstrip('-').isdigit() else k for k in path.split('.')]
        node = cfg
        for k in keys[:-1]:
            if k not in node:
                raise SystemExit(f'no such key: {k} (in {path})')
            node = node[k]
        try:
            val = int(val)
        except ValueError:
            pass
        old = node.get(keys[-1], '<absent>')
        node[keys[-1]] = val
        print(f'  {path}: {old} -> {val}')
    yaml.safe_dump(cfg, open(out, 'w'), default_flow_style=False)


if __name__ == '__main__':
    main()
