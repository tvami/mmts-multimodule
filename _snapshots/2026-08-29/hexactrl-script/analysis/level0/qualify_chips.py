import os
import glob
import subprocess


def run(script, inputdir, prefix='level0'):
    cmd = f'python3 {prefix}/{script} {inputdir} {inputdir}'
    runCommand(cmd)


def runCommand(cmd):
    print(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    outs, errs = proc.communicate()
    print(outs.decode())
    if errs:
        raise RuntimeError(errs.decode())


def check_chip(inputdir, prefix='level0'):
    # clean up
    runCommand(f'rm -f {inputdir}/*/run_*/analysis_summary.yaml')

    # pedestal_scan
    dir = sorted(glob.glob(os.path.join(inputdir, 'pedestal_scan', 'run_*')), reverse=True)[0]
    run('pedestal_scan_analysis.py', dir, prefix=prefix)

    # injection_scan
    # use only the highRange injection
    dir = sorted(glob.glob(os.path.join(inputdir, 'injection_scan', 'run_*')), reverse=True)[0]
    run('injection_scan_analysis.py', dir, prefix=prefix)

    # TODO: add more analyzers

    # aggregate
    runCommand(f'python3 {prefix}/aggregate_summary.py -i {inputdir}')


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', "--inputdirs", nargs='*', default=[], help='inputdirs')
    parser.add_argument("--prefix", default='level0', help='prefix')

    args = parser.parse_args()

    for inputdir in args.inputdirs:
        check_chip(inputdir, args.prefix)
