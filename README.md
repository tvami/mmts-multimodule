# MMTS multimodule

Bench scripts for the CMS HGCAL Multi-Module Test System (MMTS), plus submodule
references to the CERN GitLab repos they drive.

Source of truth is the Mac copy at `~/Docs/1Research/MMTS/multimodule`; the Kria
(`daq@10.116.24.180`, Alabama bench) gets a copy of the top-level scripts.

Operating procedure lives outside this repo, in `../MMTS_ALABAMA_INSTRUCTIONS.md`
(commands) and `../MMTS_ALABAMA_RUNBOOK.md` (why). The runbook is authoritative.

## Layout

| path | what |
|---|---|
| `*.py`, `*.sh` | the bench scripts — bring-up, ROC enable, mux/power diagnostics |
| `hexactrl-sw/` | submodule — DAQ software (branch `robustness-fixes`) |
| `hexactrl-sw_backup/` | submodule — earlier DAQ tree kept for comparison (branch `ROCv3`) |
| `hgc-test-systems/` | submodule — firmware (branch `feature/multiplexer_board_v2`) |
| `hexmap/` | submodule — channel maps |
| `gui-hexmap/` | submodule — module testing GUI |
| `gui-master/` | **not tracked** — a git *worktree* of `gui-hexmap`, shares its `.git` |
| `_snapshots/` | plain-file copies of work that was not committed anywhere (see below) |

## Key scripts

| script | use |
|---|---|
| `mmts_bringup.sh <A\|B\|C> [--no-recover] [--external-power] [--board NAME]` | full slot bring-up; also restarts `daq-server` |
| `enableROCs_alabama.py` | Alabama-specific ROC enable (power management board, no `0x21` writes) |
| `findslot.py` | probes all three slots for ROCs — no bring-up, harmless, the cheapest diagnostic |
| `muxdiag.py`, `muxpower.py`, `modpower.py` | mux board / power expander diagnostics (these do **reads**, which can wedge the PL I2C master) |
| `set_daq_delays.py`, `trg_link_probe.py`, `manual_trg_scan.py` | link delay and trigger diagnostics |
| `i2cstress.py`, `i2cstress2.py` | I2C reliability stress tests |

## `_snapshots/` — why it exists

Submodules record only a commit SHA. Several things on this bench were never
committed anywhere, so a submodule-only superproject would have silently dropped
them. Snapshotted 2026-08-29:

| snapshot | what was at risk |
|---|---|
| `2026-08-29/hexactrl-script/` | 46 dirty files on a detached HEAD — patched `delay_scan.py`, `pedestal_run.py`, `zmq_controler.py`, `myinotifier.py` (the directory-scan fallback the runbook depends on), and the untracked `configs/initLD-trophyV3-3b_mux*.yaml` used by every delay scan and pedestal run |
| `2026-08-29/hexactrl-script_backup/` | same tree in `hexactrl-sw_backup`, incl. its own `initLD-trophyV3-3b_mux*.yaml` |
| `zmq_i2c_backup_20260827_130857/` | pre-change backup of `zmq_i2c` taken on the Kria |
| `hexactrl-sw_robustness-fixes.bundle` | six commits on `robustness-fixes` that exist on **no remote** — `fix fifo_latency mask and unaligned links`, `rebuild HwInterface when uhal_device changes`, `skip trg elink with no daq elink`, `use boost sleep for sub-second waits`, `bump zmq_i2c to robustness fixes`, `skip unreachable links in offset finder` |
| `zmq_i2c_robustness-fixes.bundle` | `zmq_i2c` commits on **no remote**, including `fix repr, raise, and ROC probing` (`004290d`, the pointer `hexactrl-sw` actually records) and `retry ROC type read before raising` (`e62e243`, what is checked out) |

Note `hexactrl-sw` records `zmq_i2c` at `004290d` while the working tree has
`e62e243` checked out — that mismatch is the ` M zmq_i2c` in `git status`.

Restore the bundle with:

```bash
git -C hexactrl-sw fetch ../_snapshots/hexactrl-sw_robustness-fixes.bundle robustness-fixes
```

### Outstanding

- ✅ `robustness-fixes` pushed to the `tvami` forks of both `hexactrl-sw` and
  `zmq_i2c` on 2026-08-29, so every submodule pointer now resolves. The
  `hexactrl-sw` submodule URL therefore points at the **fork**, not
  `hgcal-daq-sw`; move it back once the MR merges.
- Two MRs open 2026-08-29, and **!24 must merge first** — !55 bumps `zmq_i2c` to
  `e62e243`, which upstream cannot fetch until !24 lands:
  - zmq_i2c **!24** → `multimodule` — <https://gitlab.cern.ch/hgcal-daq-sw/zmq_i2c/-/merge_requests/24>
  - hexactrl-sw **!55** → `ROCv3-alper-dev` — <https://gitlab.cern.ch/hgcal-daq-sw/hexactrl-sw/-/merge_requests/55>
- The dirty `hexactrl-script` tree is still uncommitted — 46 files, including the
  `initLD-trophyV3-3b_mux*.yaml` configs. The snapshot is a stopgap, not version
  control; it should get a branch on a fork.
- `gui-hexmap` has ~50 files staged as deleted. Left as found — not cleaned up
  here, since it may be deliberate.

## Sync to the Kria

The Kria holds only the top-level scripts (no submodules, no `_snapshots`):

```bash
tar czf - --exclude=__pycache__ *.py *.sh | ssh daq@10.116.24.180 'tar xzf - -C ~/multimodule'
```
