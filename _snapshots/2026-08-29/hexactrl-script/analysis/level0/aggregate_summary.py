import os
import yaml


def aggregate(inputdir):
    print(inputdir)
    out = {}
    badchns = {}
    nchips = None
    for fp, _, filenames in os.walk(inputdir):
        for fn in filenames:
            if fn != 'analysis_summary.yaml':
                continue

            *_, meas, run = fp.split('/')
            with open(os.path.join(fp, fn)) as fin:
                summary = yaml.safe_load(fin)
                out[meas] = {run: summary}
                # aggregate bad channel information per chip

                for k in summary:
                    if not k.startswith('bad_channel'):
                        continue
                    s = summary[k]

                    if nchips is None:
                        nchips = len([k for k in s.keys() if k.startswith('chip')])
                    else:
                        assert(nchips == len([k for k in s.keys() if k.startswith('chip')]))
                    for ichip in range(nchips):
                        chip_id = 'chip%d' % ichip
                        if chip_id not in badchns:
                            badchns[chip_id] = []
                        v = s[chip_id]
                        print(v)
    #                     print('... adding bad channels %s from %s/%s/%s' % (v['ch'], meas, run, k))
    #                     badchns[chip_id].extend(v['ch'])

    # for ichip in range(nchips):
    #     chip_id = 'chip%d' % ichip
    #     badchns[chip_id] = sorted(list(set(badchns[chip_id])))
    #     print('=== [chip%d] Found %d bad channels in total ===' % (ichip, len(badchns[chip_id])))
    #     print(badchns[chip_id])

    with open(os.path.join(inputdir, 'summary.yaml'), 'w') as fout:
        yaml.dump(out, fout)

    with open(os.path.join(inputdir, 'bad_channels.yaml'), 'w') as fout:
        yaml.dump(badchns, fout)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', "--inputdir", help="Input dir")
    args = parser.parse_args()

    aggregate(args.inputdir)
