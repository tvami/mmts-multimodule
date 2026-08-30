"""Check every roc_s* parameter in a config against the v3b register map, so a
bad key is caught here instead of crashing the i2c-server mid-configure.
Block id 'all' means every id of that block (Translator.py:81)."""
import pickle, sys, yaml

cfg = yaml.safe_load(open(sys.argv[1]))
with open("/home/daq/multimodule/hexactrl-sw/zmq_i2c/reg_maps/"
          "HGCROC3b_I2C_params_regmap_dict.pickle", "rb") as fh:
    pm = pickle.load(fh)

bad = []
for roc, body in cfg.items():
    if not roc.startswith("roc_s"):
        continue
    for block, ids in (body.get("sc") or body).items():
        if block not in pm:
            bad.append(f"{roc}: block {block!r} unknown"); continue
        for bid, params in ids.items():
            targets = list(pm[block]) if bid == "all" else [bid]
            for t in targets:
                if t not in pm[block]:
                    bad.append(f"{roc}.{block}[{t}]: id unknown"); continue
                for name in params:
                    if name not in pm[block][t]:
                        bad.append(f"{roc}.{block}[{t}].{name}")
print("\n".join(sorted(set(bad))) if bad else "all parameter names valid for Siv3b")
