#!/usr/bin/env python3
"""Step 1b -- read the HGCROC's own error counters.  Never read before.

The `Top` block exposes readable diagnostics that turn the fast-command
hypothesis into a direct measurement instead of an inference from downstream
corruption:

    fc_error_count   fast-command error count (8-bit, R0 178)
    err_countL/R     per-half error counts    (8-bit, R0 179/180)
    lock_count       PLL lock count           (8-bit, R0 177)
    Pll_Locked_sc    PLL locked               (R0 166 bit 5)
    statusL/R        per-half status          (4-bit, R0 176)

If the corrupt chip shows a rising fc_error_count and the clean one does not,
the fast command / clock quality is confirmed as the cause.  If it stays at 0 on
a chip whose halves fail 100 % of CRCs, the fast command is fine and the problem
is downstream of it.

usage: roc_diag.py <ip> [label]
"""
import sys
import zmq_controler as zmqctrl

REGS = ['statusL', 'statusR', 'lock_count', 'Pll_Locked_sc',
        'fc_error_count', 'err_countL', 'err_countR',
        # CLPS driver, same register (R0 165) enableROCs writes 0xFF to at
        # bring-up.  Read them back: if configure() has reset them to their
        # defaults (EN 3, ENpE 0, S 0) then every run so far has been taken with
        # pre-emphasis OFF, whatever bring-up did.
        'EN', 'ENpE', 'S', 'BIAS_I_PLL_D']

ip = sys.argv[1] if len(sys.argv) > 1 else '10.116.24.180'
label = sys.argv[2] if len(sys.argv) > 2 else ''

i2c = zmqctrl.i2cController(ip, '5555', 'configs/initLD-trophyV3-3b_muxC_ped.yaml')

node = {f'roc_s{c}': {'sc': {'Top': {0: {r: 0 for r in REGS}}}} for c in range(3)}
got = i2c.read_config(node)

print(f'--- ROC Top diagnostics {label} ---')
print(f'{"roc":<8}' + ''.join(f'{r:>15}' for r in REGS))
for c in range(3):
    # the server's reply drops the 'sc' level the request carries
    blk = got[f'roc_s{c}']
    top = blk.get('sc', blk)['Top'][0]
    print(f'roc_s{c:<3}' + ''.join(f'{top.get(r, "-"):>15}' for r in REGS))
