# MMTS setup and operation, for Module Assembly Centers

Multi-Module Test System: three hexaboards in one hexacontroller, measured one
slot at a time. From a bare AlmaLinux client and unflashed Kria to pedestals on
all three slots, with the LD Full as the example. Other board types:
[mmts_instructions_othertypes.md](mmts_instructions_othertypes.md).

**Conventions.** `$MMTS_ROOT` is the client working directory, `$KRIA_IP` the
hexacontroller address, `$SLOT` is `A`, `B` or `C`, and `$MM` is
`$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule`. Set them in 0.5. Each
code block says where to type it: the lab computer (the AlmaLinux client) or the
Kria.

---

## Contents

- [0. From a bare AlmaLinux client to a working bench](#0-from-a-bare-almalinux-client-to-a-working-bench)
- [1. Powering up](#1-powering-up)
- [2. Running a board](#2-running-a-board)
- [3. LD Full (LF)](#3-ld-full-lf)
- [4 to 10. The other board types](mmts_instructions_othertypes.md)
- [Route B: set up a Kria by hand](#route-b-set-up-a-kria-by-hand)
- [11. Reference](#11-reference)
- [12. Common mistakes](#12-common-mistakes)

Read 0 once per new client or Kria, then 1 (power-up), 2 (routine measurement)
and 3 (LD Full). Sections 4 to 10 are in
[mmts_instructions_othertypes.md](mmts_instructions_othertypes.md). 11 is
reference; 12 is for failures.

---

# 0. From a bare AlmaLinux client to a working bench

## 0.1 What runs where

| | client (AlmaLinux 9, x86_64) | Kria (hexacontroller, aarch64) |
|---|---|---|
| `hexactrl-script/multimodule/`, the bench scripts | yes | its `kria/` subset only |
| `hexactrl-sw` client side: `daq-client`, `unpack` | yes | no |
| `delay_scan.py`, `pedestal_run.py`, analysis, hexmaps | yes | no |
| bring-up, ROC enable, mux and power I2C | no | yes |
| `zmq_server.py` (the i2c-server, port 5555) | no | yes |
| `daq-server` (port 6000) | no | yes |
| firmware bitstream and uHAL address tables | no | yes |

The client needs GitLab only at install time; the Kria never needs internet.

## 0.2 Client prerequisites

**(on the lab computer)**

```bash
sudo dnf install -y git python3 python3-pip
```

Also: about 20 GB free disk, and a CERN account with an ssh key at
`gitlab.cern.ch`.

## 0.3 Passwordless access to the Kria

**Key based login.**

**(on the lab computer)**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_kria -C "mmts-client"
ssh-copy-id -i ~/.ssh/id_ed25519_kria.pub daq@<kria-ip>
```

**Connection multiplexing.** List the raw address as well as the alias; the
scripts call `ssh daq@<kria-ip>` directly.

**(on the lab computer, the file `~/.ssh/config`)**

```
Host kria <kria-ip>
    HostName        <kria-ip>
    User            daq
    IdentityFile    ~/.ssh/id_ed25519_kria
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m
    ServerAliveInterval 30
```

Verify: `ssh kria true`, then `ls ~/.ssh/cm-*`.

**Passwordless `sudo` for `kconn_pwr` and `fw-loader`.** Without it bring-up
hangs or fails silently. Type this on the Kria:

**(on the lab computer, this is what logs you into the Kria)**

```bash
ssh kria
```

Confirm the binary paths:

**(on the Kria)**

```bash
command -v fw-loader kconn_pwr
```

Write the rule, substituting those paths if they differ:

**(on the Kria)**

```bash
echo "daq ALL=(root) NOPASSWD: /usr/bin/fw-loader, /usr/bin/kconn_pwr" \
  | sudo tee /etc/sudoers.d/hgc-bench
sudo chmod 440 /etc/sudoers.d/hgc-bench
sudo -n fw-loader list
```

The last line must print without a password prompt (a prompt means wrong paths
or mode not 440). Then `exit`.

## 0.4 Clone the repositories

**Step 1, `hexactrl-sw`**, branch `ROCv3-alper-dev` (not `ROCv3`). Its
`hexactrl-script` submodule holds the bench scripts and run configs.

**(on the lab computer)**

```bash
export MMTS_ROOT=$HOME/mmts
mkdir -p "$MMTS_ROOT" && cd "$MMTS_ROOT"
git clone -b ROCv3-alper-dev --recurse-submodules \
  ssh://git@gitlab.cern.ch:7999/hgcal-daq-sw/hexactrl-sw.git hexactrl-sw
```

**`--recurse-submodules` is required.** Without it the 0.6a build dies with
`does not contain a CMakeLists.txt file` at `add_subdirectory(analysis)`, and
B8 copies an empty `zmq_i2c`. Fix: `git submodule update --init --recursive` in
`hexactrl-sw`.

**Step 2, `gui-hexmap`** (repository `hgcal-module-testing-gui`; directory name
recorded as `GUI_HEXMAP` in 0.5).

**(on the lab computer)**

```bash
git clone -b master \
  ssh://git@gitlab.cern.ch:7999/acrobert/hgcal-module-testing-gui.git gui-hexmap
```

Without GitLab ssh, use `https://gitlab.cern.ch/` instead of
`ssh://git@gitlab.cern.ch:7999/` (prompts for username and personal access
token).

**(on the lab computer)**

```bash
git -C hexactrl-sw rev-parse --abbrev-ref HEAD
git -C gui-hexmap  rev-parse --abbrev-ref HEAD
ls hexactrl-sw/hexactrl-script/multimodule/puller.sh
ls hexactrl-sw/zmq_i2c/Link.py hexactrl-sw/hexactrl-script/analysis/CMakeLists.txt
```

Expect `ROCv3-alper-dev`, `master`, and no `No such file or directory`.
Submodules show a detached `HEAD`; that is correct.

Resulting layout (`RESULTS_DIR` in 0.5 moves `Results`):

**(the resulting layout on the lab computer, not commands)**

```
$MMTS_ROOT/
├── hexactrl-sw/                  step 1, branch ROCv3-alper-dev
│   ├── hexactrl-script/          submodule: the scripts, configs and analysis
│   │   ├── analysis/             submodule: the pedestal and scan analyses
│   │   ├── configs/              the run configs, one per board type and slot
│   │   ├── multimodule/          THE BENCH SCRIPTS: this is $MM
│   │   │   └── kria/             the subset copied to the Kria in B8
│   │   ├── delay_scan.py
│   │   └── pedestal_run.py
│   └── zmq_i2c/                  submodule: the i2c-server, copied to the Kria
├── gui-hexmap/                   step 2, channel maps and geometries
└── Results/                      created on the first run
```

Clone `hgc-test-systems` (firmware) only to rebuild a bitstream. Do not use the
deprecated `gitlab.cern.ch/hgcal-daq-sw/hexmap`: it has no LD-Full-V3 map, so
plots show wrong channel positions.

## 0.5 Site settings

Append to `~/.bashrc`. **Change `KRIA_IP`** to the address you `ssh` to; keep
the rest unless you moved something.

**(on the lab computer, appended to `~/.bashrc`)**

```bash
export KRIA_IP=10.0.0.1
export MMTS_ROOT=$HOME/mmts
export MM=$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule
export SCRIPTS=$MMTS_ROOT/hexactrl-sw/hexactrl-script
export KRIA_USER=daq
export HEXACTRL=/opt/hexactrl/ROCv3-alper-dev
export MMTS_VENV=$MMTS_ROOT/venv
export MMTS_FW=multimodule-hd-tester-trophy-v3
export RESULTS_DIR=$MMTS_ROOT/Results
export GUI_HEXMAP=$MMTS_ROOT/gui-hexmap
export PATH=$HEXACTRL/bin:$PATH
```

Plain `export NAME=value` only: no quotes, `${...}` or `${NAME:-default}`.

Then `source ~/.bashrc` and check:

**(on the lab computer)**

```bash
echo "MMTS_ROOT=$MMTS_ROOT SCRIPTS=$SCRIPTS KRIA_IP=$KRIA_IP"
ls "$SCRIPTS/delay_scan.py" "$MM/puller.sh"
timeout 5 bash -c "cat < /dev/tcp/$KRIA_IP/5555" 2>/dev/null; rc=$?
case $rc in
  0|1) echo "KRIA_IP PASS: $KRIA_IP answered" ;;
  124) echo "KRIA_IP FAIL: nothing answered at $KRIA_IP (timed out)" ;;
  *)   echo "KRIA_IP unexpected rc=$rc" ;;
esac
```

Expect `KRIA_IP PASS`. Before a bring-up, `Connection refused` is healthy;
`rc=124` means a wrong `KRIA_IP` or a firewall.

| variable | what it is |
|---|---|
| `MMTS_ROOT` | the directory from 0.4, the parent of `hexactrl-sw` |
| `MM` | the bench scripts, `hexactrl-script/multimodule` |
| `SCRIPTS` | `hexactrl-script` itself, where `delay_scan.py` lives |
| `KRIA_IP`, `KRIA_USER` | your hexacontroller; user `daq` by default |
| `HEXACTRL` | the install prefix from 0.6a |
| `MMTS_VENV` | the virtualenv from 0.6b, or empty for system-wide |
| `MMTS_FW` | the firmware design, see B5 |
| `RESULTS_DIR` | the output root |
| `GUI_HEXMAP` | the `gui-hexmap` clone from 0.4 |

`MMTS_ROOT` and `KRIA_IP` are required; the rest default to the block above.
Override for one run on the command line, e.g. `MMTS_FW=...
"$MM/delay_scan.sh" B`.

Symptoms of a bad variable:

- Wrong `KRIA_IP`: `delay_scan.py` hangs at `Initializing i2c sockets`, while
  `ssh kria` still works.
- Unset `SCRIPTS`: `cd "$SCRIPTS"` silently stays put, and the error names a
  directory you never chose (hand-typed commands of 2 to 10 only).

## 0.6 Install the client stack

### a. hexactrl-sw

There is no RPM for `ROCv3-alper-dev`; build from source into
`/opt/hexactrl/ROCv3-alper-dev`.

**(on the lab computer)**

```bash
sudo dnf install -y cmake make gcc-c++ boost-devel
sudo dnf install -y epel-release
sudo dnf config-manager --set-enabled crb
sudo dnf install -y root yaml-cpp-devel cppzmq-devel zeromq-devel
cmake --version && root-config --version
ls /usr/include/yaml-cpp/yaml.h /usr/include/zmq.hpp
```

ROOT (about 1 GB) may come from CVMFS or a module instead; cmake finds it via
`$ROOTSYS`. There is no `root-devel`. Without `crb` the install dies with
`nothing provides liburing-devel`. Without yaml-cpp, `make` fails with `fatal
error: yaml-cpp/yaml.h`. If EPEL lacks `cppzmq-devel`, use the CERN repo's
`cppzmq-devel-latest`.

**(on the lab computer)**

```bash
cd "$MMTS_ROOT/hexactrl-sw" && mkdir -p build && cd build
cmake -DBUILD_CLIENT=ON -DBRANCH_NAME=ROCv3-alper-dev \
      -DCMAKE_INSTALL_PREFIX=/opt/hexactrl/ROCv3-alper-dev ../
make -j"$(nproc)" && sudo make install
```

Keep all three flags: without `BUILD_CLIENT` there is no `daq-client` or
`unpack`; without `BRANCH_NAME` a snapshot with no `.git` installs into
`/opt/hexactrl/` itself.

**Deactivate conda before configuring.** The configure output must show the
system Python:

**(configure output, not a command)**

```
-- Found PythonInterp: /usr/bin/python3 (found suitable version "3.9...")
```

If it shows `miniforge3` or `anaconda3`: `conda deactivate`, delete the build
directory, configure again.

Build on the x86_64 client; the Kria gets its own aarch64 build in B2. Do not
substitute the public `ROCv3` RPM (it installs under `/opt/hexactrl/ROCv3/` and
predates the MR !55 fixes of B2).

Confirm `daq-client`, `hitproducer` and `unpack` landed:

**(on the lab computer)**

```bash
ls /opt/hexactrl/ROCv3-alper-dev/bin
```

Keep `export PATH=$HEXACTRL/bin:$PATH` from 0.5. Without it a run produces no
`.root` and `pedestal_run0.log` says `unpack: command not found`. The client
has no `etc/env.sh`; that is expected.

### b. Python dependencies

**(on the lab computer)**

```bash
python3 -m venv --system-site-packages "$MMTS_ROOT/venv"
source "$MMTS_ROOT/venv/bin/activate"
pip install --no-cache-dir \
    "numpy<2" pyzmq pyyaml pandas matplotlib scipy seaborn \
    uproot uproot3 awkward awkward-pandas more_itertools \
    nested_dict nested_lookup pyinotify tables
```

**Build the venv with the system `python3`, conda deactivated.** On Python 3.12
`uproot3` fails with `'FileFinder' object has no attribute 'find_module'`.
`which python3` must be `$MMTS_ROOT/venv/bin/python3` and `lib` must show
`python3.9`. The last three lines fix a wrong version:

**(on the lab computer)**

```bash
which python3
ls "$MMTS_ROOT/venv/lib"
conda deactivate
rm -rf "$MMTS_ROOT/venv"
/usr/bin/python3 -m venv --system-site-packages "$MMTS_ROOT/venv"
```

Then re-run the `pip install` above.

### c. The scripts

`$MM/README.md` lists every file.

**(on the lab computer)**

```bash
cd "$MM"
chmod +x *.sh *.py kria/*
./puller.sh
```

Expect `puller up on 6001`.

| script | what |
|---|---|
| `run_slot.sh` | one slot end to end: bring-up, gate, N pedestals, finder line, hexmaps, per-half check. The routine command |
| `register_boards.py` | records serial per slot; run before the first bring-up after every board change |
| `bench_up.sh` | cold start: bitstream, payload power, ROC enable |
| `delay_scan.sh` | delay scan plus the PASS/FAIL gate |
| `ped_run.sh` | N pedestal runs scored by CRC |
| `slot_measure.sh` | bring up, gate, N pedestals, common-mode decomposition |
| `cm_analysis.py` | common-mode decomposition: total, CM, residual, autocorrelation |
| `hexmap_robust.py`, `remap_all.sh` | hexmaps for one run, or everything under the results root |
| `puller.sh`, `gate.py`, `module_of.py`, `finder_positions.sh` | shared pieces |

The scripts restart the puller per run and put the hexactrl `bin` on `PATH`.
Sections 2 to 10 also give the underlying commands. In `up_verified.sh` output,
a silent minute is a try in progress; section 2 says which log to `tail -f`.

## 0.7 Copy the code to the Kria

Moved to B8. Route A already includes it; B8 is for a hand-built Kria or an
image older than the client.

## 0.8 One-time Kria setup

**Route A** (below) flashes a prepared SD image; use it by default. **Route B**
(B1 to B8, end of this document) builds the same by hand, for a Kria that cannot
be flashed or to repair one that fails 0.9. Both end at 0.9.

### Route A: flash the prepared image

Public CERNBox link, no sign-in needed.

| | |
|---|---|
| file | `kria-mmts-20261013.img.gz` |
| download | 7,370,545,571 bytes (7.4 GB) |
| written to the card | 15,934,160,896 bytes (15.9 GB) |
| sha256 of the download | `6849d162dc1a01814b01e3d08e693118b9e98725adeb0c1d76a7766914df254a` |
| public link, browser | `https://cernbox.cern.ch/s/gA7anszJiATLSSR` (the `forMACs` folder) |
| public link, file only | `https://cernbox.cern.ch/remote.php/dav/public-files/gA7anszJiATLSSR/kria-mmts-20261013.img.gz` |
| EOS path | `/eos/user/t/tvami/forMACs/kria-mmts-20261013.img.gz`, by `xrdcp` from `root://eosuser.cern.ch/` |
| fallback | the 09-08 image `kria11-ucsb-20260908.img.gz` (5.1 GB, sha256 `1a5dc548…`, writes 10.7 GB), public link `https://cernbox.cern.ch/s/vCNbETZNHUdHyCS/download`, no sign-in |

Use a **32 GB** card; 16 GB is a few MB too small. The image has no ssh host
keys, so the first ssh shows a new host key.

#### A1. Fetch and check it

**(on the lab computer, Linux or macOS)**

```bash
cd "$MMTS_ROOT"
L=https://cernbox.cern.ch/remote.php/dav/public-files/gA7anszJiATLSSR
curl -L -o kria-mmts-20261013.img.gz        $L/kria-mmts-20261013.img.gz
curl -L -o kria-mmts-20261013.img.gz.sha256 $L/kria-mmts-20261013.img.gz.sha256
ls -l kria-mmts-20261013.img.gz
```

In a browser, click the file; `.../s/gA7anszJiATLSSR/download` gives a tar of
the whole folder.

Or by xrootd, with a CERN Kerberos ticket (`kinit user@CERN.CH`) or CMS VOMS
proxy:

**(on the lab computer, or any machine with xrootd)**

```bash
xrdcp root://eosuser.cern.ch//eos/user/t/tvami/forMACs/kria-mmts-20261013.img.gz .
xrdcp root://eosuser.cern.ch//eos/user/t/tvami/forMACs/kria-mmts-20261013.img.gz.sha256 .
```

`[3010] Unable to open file ... Operation not permitted` means you lack folder
access; ask for it to be shared with your CERN username, or use `curl`.

**Check the checksum before writing.** A truncated image writes fine and then
fails to boot.

**(on the lab computer, Linux)**

```bash
sha256sum kria-mmts-20261013.img.gz
```

**(on the lab computer, macOS)**

```bash
shasum -a 256 kria-mmts-20261013.img.gz
```

It must match the table; otherwise download again.

#### A2. Identify the card, and check it twice

**`dd` overwrites whatever device you name, including your system disk.**
Match the size to the card you inserted.

**(on the lab computer, Linux)**

```bash
lsblk -d -o NAME,SIZE,MODEL,TRAN
```

Usually `sdb` (USB reader) or `mmcblk0` (built-in).

**(on the lab computer, macOS)**

```bash
diskutil list external physical
```

A `/dev/diskN`; write to `/dev/rdiskN` (several times faster).

#### A3. Write it to the card

Substitute the device you confirmed.

**(on the lab computer, Linux)**

```bash
sudo umount /dev/sdX* 2>/dev/null
gunzip -c kria-mmts-20261013.img.gz \
  | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

**(on the lab computer, macOS)**

```bash
diskutil unmountDisk /dev/diskN
gunzip -c kria-mmts-20261013.img.gz | sudo dd of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Do not mix the two forms:

| | Linux | macOS |
|---|---|---|
| list the disks | `lsblk` | `diskutil list` |
| unmount | `umount /dev/sdX*`, per partition | `diskutil unmountDisk /dev/diskN`, whole device |
| device to write | `/dev/sdX` or `/dev/mmcblk0` | `/dev/rdiskN`, the raw node |
| block size | `bs=4M`, uppercase | `bs=4m`, lowercase |
| progress | `status=progress` | Ctrl+T (no `status=progress`) |

Expect 5 to 15 minutes.

#### A4. Boot it

Move the card to the Kria and power it on. It takes a DHCP address, which
becomes `KRIA_IP` in 0.5. To find it, scan your subnet (from `ip -4 addr`, in
place of `10.116.24.0/23`) with the Kria off and on:

**(on the lab computer)**

```bash
sudo nmap -sn 10.116.24.0/23 -oG - | awk '/Up/{print $2}' | sort > before.txt
# power the Kria on, wait 2 minutes
sudo nmap -sn 10.116.24.0/23 -oG - | awk '/Up/{print $2}' | sort > after.txt
comm -13 before.txt after.txt
```

The new address is the Kria. If there is more than one, ask your network admin
for the lease and a fixed address.

## 0.9 Check the installation

**(on the lab computer, checking the Kria)**

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria 'ls -l /dev/i2c-2 /dev/uio0; gpiofind Multiplex_A'
ssh kria 'grep -c "id=\"TOP_[ABC]\"" /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml'
ssh kria 'cd ~/multimodule && python3 findslot.py'
```

The `grep` must print `3`; otherwise do B4 (a firmware install may have restored
the stock file). Missed, it shows later as a gate saying `no summary.json` and
`daq-server` logging `Device ID , "TOP_A", does not exist in connection map`.

**(on the lab computer, checking the lab computer)**

```bash
source "$MMTS_VENV/bin/activate"
command -v daq-client unpack
python3 -c "import uproot, uproot3, numpy, zmq; print(uproot.__version__)"
"$MM/puller.sh"
```

**Do not run this block on the Kria** (`uname -m`: `x86_64` is the lab
computer, `aarch64` the Kria).

**`no ROCs` on all three slots is expected here**, with 0 A on the meter: no
module is powered yet, and `findslot.py` only probes LD-Full addresses
`0x08 0x18 0x28` on `S1_I2C`. It proves the I2C master, the switches at `0x71`,
`0x73`, `0x77` and the mux GPIO writes work.

### What to do when `findslot.py` fails instead

This is a fault, not `no ROCs`:

**(expected output of a failure, not a command)**

```
slot A: mux GPIO write failed ([Errno 5] Input/output error)
slot B (switch 0x73): no ROCs [bus wedged during probe]
slot C: mux GPIO write failed ([Errno 5] Input/output error)
```

Power the bench up per section 1 (1.2 powers it), then run `findslot.py` once
more. If it still fails after a clean cold start, see 12.3 and 12.4. Do not
re-run it repeatedly and **do not use `i2cdetect -y 2`**: reads wedge this
master.

---

# 1. Powering up

Take `--board`, `EXPECT_ROCS` and the power-board setting from your board's
row in 2.1. Use `any` on a board type you have not run before.

| board | `--board` | `EXPECT_ROCS` | power distribution board |
|---|---|---|---|
| LD Full | `LD-Full` | 3 | fitted |
| HD Full | `HD-Full` | 6 | fitted |
| LD Five | `LD-Five` | 3 | none |
| LD Left, Right, Bottom, Top | `LD-Semi` | 2 | none |
| HD Top, Bottom, Semi | `HD-Top`, `HD-Bottom`, `HD-Semi` | 3, 4, 2 | none |
| unknown | `any` | read it off the probe | check the board |

The examples use an LD Full. Without a power board, pass `--external-power` to
`enableROCs.py` and `up_verified.sh`; with one, pass `--power-board` to
`bench_up.sh`. **Getting this wrong gives `no ROCs`.**

## 1.0 Size the supply BEFORE you trust any measurement

| board | measured draw at 1.72 V |
|---|---|
| any slot, rail on, ROCs idle | 0.4 to 0.5 A |
| LD Full, three chips | ~1.2 A enabled, 1.9 to 2.0 A configured and running |
| LD partials, two chips | ~1.2 A |
| HD Top, three chips | ~2.1 to 2.2 A |
| HD Full, six chips | 4.43 A |

An HD Full needs more than one ~3.2 A channel. On a SIGLENT SPD3303X-E press
`Para`, put both leads on CH1 only (`Para Out`), and set the voltage on CH1
with current at the per-channel maximum (6.4 A gives `current setting
overrange`). **Never wire `+CH1 / −CH2`** (in `Ser` mode that doubles the
voltage).

You are clipping if the mode reads `CC` and the output is below the setpoint.
Clipping looks like broken hardware: dead e-links, a different ROC count each
bring-up, a module that stops after ~30 minutes. The meter reads 0 A briefly
during every bring-up; that is normal.

## 1.1 The order, always

**(the order of operations, not commands)**

```
bring-up  →  i2c-server  →  daq-server  →  puller  →  DELAY SCAN  →  pedestal
```

Always take a delay scan before a pedestal. Only the first slot `daq-server`
scans after starting carries trigger (the others read 0 of 12 on trigger); to
move it, restart `daq-server` and scan that slot first.

After any failed or interrupted run, restart `daq-server` and the puller.

## 1.2 Powering the bench without a bring-up

Skip this before a bring-up (`mmts_bringup.sh` and `up_verified.sh` do it via
`--recover`). Use it after a mains cycle when driving `enableROCs.py` by hand
or after a `findslot.py` `[Errno 5]` at 0.9.

**(on the lab computer)**

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria 'sudo kconn_pwr on'
```

Otherwise pass `--recover` to `enableROCs.py`; without power every probe
returns `no ROCs`.

## 1.3 The bring-up wrappers

Use `mmts_bringup.sh` for a first bring-up or when anything is wrong;
`up_verified.sh` for routine runs on a working slot.

| | `mmts_bringup.sh SLOT` | `up_verified.sh SLOT` |
|---|---|---|
| attempts | one | up to 8 bring-ups, then up to 3 i2c-server starts |
| output | on your screen | to `~/bu_<slot>.log`; one line per try start and end |
| to watch a try | on screen | `ssh kria 'tail -f ~/bu_<slot>.log'` in a second terminal |
| kills a stale i2c-server first | no, the block below does | yes |
| starts the i2c-server on 5555 | no, run `start_i2c.sh` | yes |
| restarts `daq-server` on 6000 | yes | yes, through `mmts_bringup.sh` |
| verifies the result | no | ROC count, no `FAILED`, board identified, 5555 and 6000 listening |
| use it | commissioning, diagnosis, anything unexplained | a slot you have brought up before |

**(on the Kria)**

```bash
pkill -f '[z]mq_server'
cd ~/multimodule && ./mmts_bringup.sh A --board LD-Full
```

Continue only if it ends in the ROC list (`3 ROC(s) enabled [...]`, per 1.4).
`bring-up failed` or a traceback: go to 12.3 and 12.4.

**(on the Kria, only after the bring-up printed its ROC list)**

```bash
~/start_i2c.sh A
```

**Do not skip this**, or the next scan hangs at `Initializing i2c sockets`.
Pass: after ~25 s it prints `Identify a board with HGCROC Siv3b`, and
`ss -ltn | grep -E '5555|6000'` shows both ports. Plain `Siv3`: redo the
bring-up (1.4). After a failed bring-up, run `pkill -f '[z]mq_server'` instead
(12.1).

### When the bring-up fails instead

| message | from | means |
|---|---|---|
| `!! bring-up failed -- re-run once.` | `mmts_bringup.sh` | one attempt failed |
| `FAILED to bring slot A up cleanly -- read ~/bu_A.log and ~/zmq_srvA.log` | `up_verified.sh` | all eight bring-ups failed (~ten minutes) |

Read the per-try lines: `bringup try 3: 0/3 ROCs ...` is the bring-up;
`i2c try 1: 4 errors, 5555=0 ...` is the i2c-server (12.2, 12.3). Then read
`~/bu_A.log` and `~/zmq_srvA.log`.

Re-run once, back to back rather than one per boot (12.4). **If the retries
reach `5/5`, or reach it sooner than last time, stop:** `sudo shutdown -h
now`, press the power button, wait for `ssh kria`, and restart at the
bring-up block of 1.3. Nothing else needs redoing unless you installed
firmware (B4).

Identical zero-ROC tries in `up_verified.sh` are a real fault, not the
lottery: interrupt it, read `~/bu_<slot>.log`, and switch to
`mmts_bringup.sh`.

Routine form (LD Full; your type's section has the line per slot):

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --board LD-Full"
```

Set `EXPECT_ROCS` to your board's count (default 3), or a partial enable is
reported `READY`.

### `--module N`: `EN_Mx` is cabling, not the slot index

With a power board, `--module` defaults to the slot (`A`→1, `B`→2, `C`→3).
If the lead is on another output you get `no ROCs` at near-zero current.
Then sweep, keeping your own `--board` and `EXPECT_ROCS`:

**(on the lab computer, only after a bring-up gave `no ROCs` at near-zero
current; run one line at a time and stop at the one that draws current)**

```bash
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 1"
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 2"
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 3"
```

If none draws current, see the low-current row of 12.3. Other scripts take
the flag as `PED_MODULE` (`ped_run.sh`) and `SM_MODULE` (`slot_measure.sh`).

Cold start from the client, for commissioning only (LD Full; each type's
section has its own line):

**(on the lab computer, when driving a cold start by hand, not in a normal run)**

```bash
"$MM/bench_up.sh" A --board LD-Full --expect 3 --power-board
```

## 1.4 What good looks like, and when to just re-run

Pass: the bring-up prints the full ROC list, readbacks of `0x0`, and
`daq-server ... ok` on 6000.

**(expected output, not a command)**

```
3 ROC(s) enabled ['0x8', '0x18', '0x28']
```

The i2c-server must print `Identify a board with HGCROC Siv3b` (plain `Siv3`
leads to `KeyError: 'dac_hyst_toa'`; redo both). **Check that the `[I2C]
Board identification` line names your board.** A partial enable can match
another board type (collisions from 11.2 below):

**(expected output of a failure, not a command)**

```
[I2C] Board identification: V3 HD Semi-left or HD Semi-right HB
Identify a board with HGCROC Siv3b
--- listening ---
```

| you have | missing | identifies as |
|---|---|---|
| LD Full | `0x28` | HD Semi |
| LD Five | `0x68` | LD Semi |
| HD Bottom | `0x68` | HD Top |
| HD Full | `0x48 0x58 0x68` | LD Full |
| HD Full | `0x28 0x48 0x58 0x68` | HD Semi |
| HD Full | `0x08 0x18 0x28` | LD Five |

Fix: re-run the bring-up until the full ROC list appears. The same address
missing every time is the silent chip of 12.3.

| step | takes | normal meanwhile |
|---|---|---|
| bring-up | 60 to 90 s | stops at `Turning on payload power`; 6000 not listening |
| i2c-server | 15 to 30 s | `IOError in mux_setup group (attempt n/5) ... Retrying.`; 5555 not yet bound |
| a scan or pedestal starting | tens of seconds | sits at `Initializing i2c sockets` |

Fewer ROCs than expected: run it again (two to four attempts is routine).
Repeated identical `0/N` is a fault: use `mmts_bringup.sh` (1.3).

---

# 2. Running a board

Look up the board type, register the serial, run one command per slot.
2.4 to 2.7 are its stages, for a slot already verified in 1.3.

## 2.1 Which board do you have

Serial characters 5 and 6 give the geometry. Character 7 (ROC revision) is
not needed here; see 11.1.

**(example serials, not commands)**

```
320X LR 4 D QE 00020    ->  LD Right, ROC v3D
320X LF 4 C QH 00443    ->  LD Full,  ROC v3C
320X LL 4 D QE 00016    ->  LD Left,  ROC v3D
320X HF 4 D PM 02021    ->  HD Full,  ROC v3D
```

Type codes follow the GUI repository: `LF LR LL L5 LT LB` and `HF HB HL HT HR`.

| type | section | `--board` | ROCs | power distribution board | run config family | delay scan gate |
|---|---|---|---|---|---|---|
| LD Full (LF) | 3 | `LD-Full` | 3 | **fitted** | `initLD-Full-3b` | 18 of 18 |
| LD Five (L5) | [4](mmts_instructions_othertypes.md#4-ld-five-l5) | `LD-Five` | 3 | none | `initLD-Five-3b` | 7 of 7 |
| LD Left, LD Right (LL, LR) | [5](mmts_instructions_othertypes.md#5-ld-left-and-ld-right-ll-lr) | `LD-Semi` | 2 | none | `initLD-Left-3b` | 5 of 5 |
| LD Bottom, LD Top (LB, LT) | [6](mmts_instructions_othertypes.md#6-ld-bottom-and-ld-top-lb-lt) | `LD-Semi` | 2 | none | `initLD-Bottom-3b` | A 6, B 6, C 5 |
| HD Full (HF) | [7](mmts_instructions_othertypes.md#7-hd-full-hf) | `HD-Full` | 6 | **fitted** | `initHD-Full-trophyV3` | 24 of 24 |
| HD Top (HT) | [8](mmts_instructions_othertypes.md#8-hd-top-ht) | `HD-Top` | 3 | none | `initHD-Top-trophyV3` | A 9, B 7, C 6 |
| HD Bottom (HB) | [9](mmts_instructions_othertypes.md#9-hd-bottom-hb) | `HD-Bottom` | 4 | not yet seen; start as none | `initHD-Bottom-trophyV3` | not measured |
| HD Semi (HL, HR) | [10](mmts_instructions_othertypes.md#10-hd-semi-hl-hr) | `HD-Semi` | 2 | not yet seen; start as none | `initHD-Semi-trophyV3` | not measured |

Run configs are `configs/<family>_mux{A,B,C}_ped.yaml`, one per slot; never
copy one across slots (trigger sets in 11.3, ROC addresses in 11.2). On a new
type, probe with `--board any` first.

The power distribution board column sets the power flag (spellings at the end
of 2.3). **Wrong flag on a fitted board: `no ROCs`.**

## 2.2 Register the board

Output is grouped by board, not slot:

**(the output layout on the lab computer, not a command)**

```
Results/<serial>/Mux<slot>/{delay_scan,pedestal_run}/<UTC timestamp>/
```

Serials live in `Results/module_ids.json` (UTC `{slot, from, to, module}`
windows). Run `register_boards.py` **before** the first bring-up and after
every swap, or results file under the previous serial. It also creates the
registry on a new bench:

**(on the lab computer)**

```bash
"$MM/register_boards.py" A=320XLF4DQR00332 B=320XLF4DME01621 C=320XLF4DME01744
"$MM/module_of.py" B
```

`module_of.py` prints slot B's serial. Omitted slots are recorded empty;
`--at YYYY-mm-ddTHH:MM:SSZ` backdates a swap. Plotter output `module: UNKNOWN`
means no registry entry: fix the registry, not `-m`.

## 2.3 Run it

Runs bring-up, gate, N pedestals, finder line, hexmaps and per-half check,
stopping on any failure. LD Full on slot A (other types: top of their section):

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Full-3b LD-Full 3 ldfull 5
```

Arguments: slot, config family, `--board`, ROC count (2.1), output label,
number of runs.

* `POWER=` (empty): power distribution board fitted (LD Full, HD Full).
  Omitted, it defaults to `--external-power` for partials.
* `SKIP_PROBE=1`: use the shipped link map; omit only where links are not
  measured, per 11.3.

It needs a registered serial (2.2) and always does its own bring-up: **use it
only on a fresh slot**. On a slot verified in 1.3, hand-drive from 2.5, per
2.4.

**(expected output, not a command)**

```
########## A: bring-up (LD-Full, 3 ROCs, power management board)   [18:09:30 CDT]
bringup try 1 of 8: running (60 to 90 s) ...
bringup try 1: 0/3 ROCs
bringup try 2 of 8: running (60 to 90 s) ...
  i2c-server start 1 of 3: running (about 25 s) ...
READY  bringup=2 i2c=1  [I2C] Board identification: V3 LD Full HB

########## A: SKIPPING the 12+12 probe (SKIP_PROBE=1): the shipped map is already known good   [18:11:00 CDT]

########## A: gate   [18:11:00 CDT]
# slot A  board <serial>  config configs/initLD-Full-3b_muxA_ped.yaml
puller up on 6001
scanning, 20 to 40 s (log: Results/<serial>/MuxA/delay_scan.log)
Results/<serial>/MuxA/delay_scan/<UTC timestamp>
  daq: 6/6  link0=.. link1=.. link4=.. link5=.. link8=.. link9=..
  trg: 12/12  link0=.. ... link11=..
GATE: PASS -- safe to run pedestals

########## A: pedestal 1 of 5 (smoke test, ~30 s)   [18:11:40 CDT]
run   entries   CRC pass c0h0.. (3 chips x 2 halves)   adc_mean ...   badBX   dir
1     2347488   1.000 1.000 1.000 1.000 1.000 1.000    101 89 99 114 93 92   0.000   run_...
########## A: pedestals 2..5 (~30 s each)   [18:12:20 CDT]
########## A: finder header positions (23 everywhere = right edge)
########## A: hexmaps + per-half check (every half adc_stdd > 0, else FROZEN)
########## A: DONE
```

| stage | takes | the line that ends it |
|---|---|---|
| bring-up | 60 to 90 s per try, up to 8 tries (up to ten minutes) | `READY`, or `BRINGUP FAILED` with the tail of `~/bu_A.log` |
| gate | 20 to 40 s | the `GATE:` line |
| each pedestal | ~30 s | its row in the CRC table |
| hexmaps | ~10 s per run | `DONE` |

To follow a bring-up try:

**(on the lab computer, in a second terminal)**

```bash
ssh kria 'tail -f ~/bu_A.log'
```

Meter: 0 A, then ~1.2 A after `Turning on payload power`, 1.9 to 2.0 A while
chips configure. Near 0 A past `Turning on payload power` gives `0/3 ROCs`, per
12.3.

Per-script spellings (only `run_slot.sh` and `up_verified.sh` are routine):

| script | `--board` | ROCs | no power distribution board | `EN_Mx` bit |
|---|---|---|---|---|
| `run_slot.sh` | argument 3 | argument 4 | default; `POWER=` (empty) when fitted | |
| `up_verified.sh`, `mmts_bringup.sh` | `--board` | `EXPECT_ROCS=` | `--external-power` | `--module N` |
| `ped_run.sh` | `PED_BOARD=` | | `PED_EXTPOWER=1` | `PED_MODULE=N` |
| `slot_measure.sh` | `SM_BOARD=` | `SM_EXPECT=` | `SM_EXTPOWER=1` | `SM_MODULE=N` |
| `bench_up.sh` | `--board` | `--expect` | default; `--power-board` when fitted | `--module N` |

---

**The steps one at a time.** 2.4 to 2.7 are `run_slot.sh` by hand. Preamble
for every client shell:

**(on the lab computer)**

```bash
source "$MMTS_VENV/bin/activate"
SLOT=A
OUT=$RESULTS_DIR/$(python3 "$MM/module_of.py" "$SLOT")
echo "SCRIPTS=$SCRIPTS KRIA_IP=$KRIA_IP OUT=$OUT"
```

The rest comes from `~/.bashrc` at 0.5. **Check the `echo` for empty
values**: they fail silently (`-i ""` hangs, `-o ""` loses the run). An
unregistered board gives an empty `OUT` suffix; use `$RESULTS_DIR`.

## 2.4 Bring up the slot

Skip this on a slot verified in 1.3 (full ROC list, `[I2C] Board
identification` naming your type): go to 2.5. Do not use `run_slot.sh` there
either; it redoes the bring-up (costly on the bus of 12.4).

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=<N> \
  ~/up_verified.sh <SLOT> --board <BOARD>"
```

`up_verified.sh` kills any leftover i2c-server first (12.1). With a
hand-typed `mmts_bringup.sh`, kill it yourself, or a chip may report `stopped
responding mid-config`.

Add `--external-power` without a power distribution board, and `--module N`
if `EN_Mx` differs from the slot index, per 1.3.

**(expected output, not a command)**

```
bringup try 1 of 8: running (60 to 90 s) ...
bringup try 1: 0/3 ROCs
bringup try 2 of 8: running (60 to 90 s) ...
  i2c-server start 1 of 3: running (about 25 s) ...
READY  bringup=2 i2c=1  [I2C] Board identification: V3 LD Full HB
```

Pass: `READY`, which means the ROC count matched `EXPECT_ROCS`, the board
identified (check it names your type), and 5555 and 6000 listen. Each try is a
silent minute; eight take ten minutes. To follow one:

**(on the lab computer, in a second terminal)**

```bash
ssh kria 'tail -f ~/bu_<SLOT>.log'
```

On `FAILED to bring slot <SLOT> up cleanly`, read `~/bu_<SLOT>.log`. A
different chip missing each time: rerun, per 1.4. Eight identical `0/N` tries:
a fault, per 1.3; 0.05 to 0.1 A in CV past `Turning on payload power` (instead
of the idle draw of 1.0) is an unpowered module.

## 2.5 Delay scan and the gate

Always before a pedestal, never after.

**(on the lab computer)**

```bash
"$MM/delay_scan.sh" <SLOT> configs/<FAMILY>_mux<SLOT>_ped.yaml
```

`<FAMILY>` is from 2.1. LD Full on slot A, with the 2.6 pedestal:

**(on the lab computer)**

```bash
"$MM/delay_scan.sh" A configs/initLD-Full-3b_muxA_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

Takes 20 to 40 s; log in `Mux<SLOT>/delay_scan.log`. Long form, showing the
client log live:

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
python3 delay_scan.py -d Mux<SLOT> -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/<FAMILY>_mux<SLOT>_ped.yaml
python3 "$MM/gate.py" "$OUT/Mux<SLOT>"
```

**(expected output, not a command)**

```
Results/<serial>/MuxA/delay_scan/<timestamp>
  daq: 3/3  link0=57 link1=61 link4=58
  trg: 6/6  link0=44 link1=51 link2=49 link3=47 link5=52 link6=45
GATE: PASS -- safe to run pedestals
```

A healthy long-form log ends `status after start cmd : running`; a single
`b'error'` on initialize or configure is a client retry; `daq-server`'s log
shows whether it mattered.

**The gate must PASS before a pedestal.** On failure, re-run bring-up and scan
again; this usually fixes it.

Trigger 0 everywhere with DAQ fine: restart `daq-server` and scan this slot
first, per 1.1.

`no summary.json -- the scan did not produce output` or `STALE: newest
summary is ... written N s before this scan started` means `daq-server`
delivered nothing; the log tails follow:

**(expected output of a failure, not a command)**

```
no summary.json -- the scan did not produce output
  last lines of the scan's log, .../MuxA/delay_scan.log:
    INFO : ... (daqController) : returned status (from configure) = error
  last lines of ~/daq-server.log on the Kria:
    ERROR - Device ID , "TOP_A", does not exist in connection map
    impossible to process configure when state is Error
```

`Device ID , "TOP_<SLOT>", does not exist in connection map`: redo B4.
`Permission denied` on a uio device: B7. Then re-run bring-up. A 180 s timeout
with both logs empty: `KRIA_IP` or the firewall, per 0.5 and B6.

A full-marks scan is not enough on its own; also check the offset finder's
header positions after a real run.

## 2.6 Pedestal

Restart the puller first.

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
PYTHONPATH=$PWD/analysis \
  python3 pedestal_run.py -d Mux<SLOT> -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/<FAMILY>_mux<SLOT>_ped.yaml
```

`-I` is **required**, or `daq-server` stays in `created`.

Or N runs scored by CRC in one table:

**(on the lab computer)**

```bash
PED_BOARD=<BOARD> "$MM/ped_run.sh" <SLOT> 5 <label> 10000
```

LD Full on slot A, 5 runs of 10000 events:

**(on the lab computer)**

```bash
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

Partials add `PED_EXTPOWER=1`. `ped_run.sh` does **no bring-up and no gate**,
so do 2.4 and 2.5 first (`PED_BRINGUP=1` adds a bring-up per run, enabling
`PED_BOARD`, `PED_EXTPOWER=1` and `PED_MODULE=N`).

Expect one row about every 30 s; minutes per run means marginal links.
`RUN-FAILED (rc=124)` with an empty run directory is the 240 s timeout at
initialize, per 12.3.

Keep `method: 'automatic'` for `fifo_latency`. Pin `fifo_latency` and
`L1A_offset_or_BX` by hand only on a slot with no good lane.

## 2.7 Hexmaps and common mode

Unpacking runs automatically if the install's `bin` is on `PATH`. Pass: a
`.root`, nine PNGs, no `crash_report.log`.

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" <run-dir> -l <label> --clip 5
python3 "$MM/cm_analysis.py" "$OUT/Mux<SLOT>/pedestal_run/run_*"
```

For the 2.6 LD Full slot A runs:

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" "$OUT"/MuxA/pedestal_run/run_* -l ldfull --clip 5
python3 "$MM/cm_analysis.py" "$OUT/MuxA/pedestal_run/run_*"
```

Geometry comes from the serial, so these lines are the same for every board.
**Do not pass `-t`**: it plots a partial on the full geometry.

Check the printed `module:` and mapping lines; a wrong map (for example
`_BAD.csv`) silently relocates almost every channel.

Report `adc_stdd` and `adc_iqr/1.349`. Compare boards on `adc_stdd`: the robust
one only takes the values 0, 0.74, 1.48, 2.22. Trust the robust one when the run
has packet corruption, which inflates `adc_stdd`. `adc_mean` is not reproducible
run to run.

---

# 3. LD Full (LF)

| | |
|---|---|
| `--board` | `LD-Full` |
| ROCs | 3, at `0x08 0x18 0x28` |
| power distribution board | **fitted**, so no `--external-power` |
| DAQ links | 6, links `0 1 4 5 8 9` on every slot |
| trigger links | 12, all of them, on every slot |
| halves in the pedestal output | six |
| delay scan gate | 18 of 18 |
| run configs | `configs/initLD-Full-3b_mux{A,B,C}_ped.yaml` |
| `in_inv_cmd_rx` | 1, on v3D boards too; the shipped configs carry it |
| `EdgeSel_T1` | per slot, in the shipped configs: A 0, B 1, C 0 |
| draw at 1.72 V | ~1.2 A enabled and idle, 1.9 to 2.0 A with three chips configured |

Expected: CRC 1.000 on all six halves, `badBX` 0.000, header positions 23
everywhere.

**`in_inv_cmd_rx` stays 1 on an LD Full, whatever character 7 says** (11.1).
Set to 0, trigger reads 0 of 12 with healthy DAQ. Check the applied value in
the run's `initial_full_config.yaml`; never edit a config mid-scan.

`EdgeSel_T1` is per slot; a wrong edge gives a zero-byte run. Check `header
positions` in `daq-server.log` (all 23 is right).

One command per slot, on a fresh slot only; on a slot verified in 1.3, type
just the last two lines of 3.1, per 2.4:

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Full-3b LD-Full 3 ldfull 5
```

2.3 shows its output.

## 3.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --board LD-Full"
"$MM/delay_scan.sh" A configs/initLD-Full-3b_muxA_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

## 3.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --board LD-Full"
"$MM/delay_scan.sh" B configs/initLD-Full-3b_muxB_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" B 5 ldfull 10000
```

## 3.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --board LD-Full"
"$MM/delay_scan.sh" C configs/initLD-Full-3b_muxC_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" C 5 ldfull 10000
```

Keep `L1A_offset_or_BX: 13` in the slot C config, per 11.6.

---

# Route B: set up a Kria by hand

B1 to B8 build what the Route A image contains. Run them in order on a stock
hexacontroller image, or singly on a Route A Kria that failed the matching
check in 0.9.

## B1. Base image

Flash the standard HGCAL hexacontroller image. Confirm:

**(on the lab computer)**

```bash
ssh kria 'command -v fw-loader kconn_pwr; id daq'
```

## B2. hexactrl-sw under `/opt`

Build the server side on the Kria. Leave `-DBUILD_CLIENT` off; pass
`BRANCH_NAME` (the copy has no `.git`).

**(on the lab computer)**

```bash
cd "$MMTS_ROOT"
tar czf - --exclude=.git --exclude=build hexactrl-sw | ssh kria 'tar xzf - -C ~'
```

**(on the Kria)**

```bash
cd ~/hexactrl-sw && mkdir -p build && cd build
cmake -DBRANCH_NAME=ROCv3-alper-dev \
      -DCMAKE_INSTALL_PREFIX=/opt/hexactrl/ROCv3-alper-dev ../
make -j"$(nproc)" && sudo make install
ls /opt/hexactrl/ROCv3-alper-dev/{bin/daq-server,lib/libhexactrl.so,etc/env.sh}
```

Run `sudo make install` from a login shell (outside the passwordless rule of
0.3). **Build the same commit on the Kria and the client.**

Shells that run `daq-server` or the link diagnostics need the environment
(bring-up and `zmq_server` do not):

**(on the Kria)**

```bash
source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
```

## B3. Firmware

Add the firmware repo (the stock `CERN-REPO-hgcwebsw.repo` has none, and
`dnf` says `No match for argument`). The Kria needs internet.

**(on the Kria)**

```bash
sudo tee /etc/yum.repos.d/hgc-online-sw.repo <<'EOF'
[hgc-online-sw]
name=HGCAL online software and firmware
baseurl=https://hgc-online-sw.web.cern.ch/hgc-online-sw/repository/
enabled=1
gpgcheck=0
EOF
```

Install by the full `name-version-release`, release
`2026_09_01_16_56_41.49751f37` or newer (`update` over an older build,
`install` on a Kria with none; list with `sudo dnf list --available
multimodule-hd-tester-trophy-v3`):

**(on the Kria)**

```bash
sudo dnf update multimodule-hd-tester-trophy-v3-feature_multiplexer_board_v2-2026_09_01_16_56_41.49751f37
rpm -q multimodule-hd-tester-trophy-v3
```

**Never use the bare package name or an unqualified `dnf update`**: rpm then
picks `test_merge_everything`, a 2025 build with no equalization. Run
`sudo dnf` from a login shell.

The RPM overwrites `uHAL_xml/connections.xml`: redo B4 after every install,
or every slot fails. Then load it:

**(on the lab computer)**

```bash
ssh kria 'sudo fw-loader list'
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
```

Without a loaded bitstream (fresh boot), bring-up dies at `[pwr]` with
`[Errno 2] ... '/dev/i2c-2'`.

## B4. `connections.xml` needs `TOP_A`, `TOP_B`, `TOP_C`

A fresh install defines only `TOP`; `daq-server` needs a table and an entry
per slot. Make the tables:

**(on the Kria)**

```bash
cd /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml
for S in A B C; do
  OTHERS=$(echo ABC | tr -d "$S")
  sed -E "/id=\"(bram_trg|link_capture_trg)_[${OTHERS}]\"/d" fw_block_addresses.xml \
    | sed -E "s/id=\"(bram_trg|link_capture_trg)_${S}\"/id=\"\1\"/" \
    | sudo tee fw_block_addresses_${S}.xml > /dev/null
done
grep -c 'id="bram_trg"' fw_block_addresses_[ABC].xml
```

Expect 1 per file. Then rewrite `connections.xml` (keeps a `.orig` the first
time):

**(on the Kria)**

```bash
cd /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml
X=/opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml
[ -f connections.xml.orig ] || sudo cp connections.xml connections.xml.orig
{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo
  echo '<connections>'
  echo "   <connection id=\"TOP\" uri=\"uioaxi-1.0://$X/fw_block_addresses.xml\" address_table=\"file://$X/fw_block_addresses.xml\"/>"
  for S in A B C; do
    echo "   <connection id=\"TOP_$S\" uri=\"uioaxi-1.0://$X/fw_block_addresses_$S.xml\" address_table=\"file://$X/fw_block_addresses_$S.xml\"/>"
  done
  echo '</connections>'
} | sudo tee connections.xml > /dev/null
grep -c 'id="TOP_[ABC]"' connections.xml
```

Expect 3. Re-run this block after every firmware install (B3).

## B5. The equalized bitstream

Use firmware release `2026_09_01_16_56_41.49751f37` or later (the RPM of B3), with `MMTS_FW=multimodule-hd-tester-trophy-v3`.

## B6. Open the three ports

A stock AlmaLinux firewall on either machine blocks these. The symptom is a
hang, not a connection error.

| port | listens on | carries |
|---|---|---|
| 5555 | the Kria | the i2c-server, ROC configuration |
| 6000 | the Kria | `daq-server`, run control |
| 8888 | the Kria | the event stream; the puller connects out to it |
| 6001 | the lab computer | puller control, from `delay_scan.py` on the same machine |

**(on the Kria)**

```bash
sudo firewall-cmd --permanent --add-port=5555/tcp --add-port=6000/tcp --add-port=8888/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

Expect `5555/tcp 6000/tcp 8888/tcp`.

**(on the lab computer)**

```bash
sudo firewall-cmd --permanent --add-port=6001/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

Expect `6001/tcp`. If it is empty, bring-up is clean but the scan receives
nothing for 180 s and the gate says `no summary.json`.

Test from the client:

**(on the lab computer)**

```bash
for p in 5555 6000; do
  timeout 5 bash -c "cat < /dev/tcp/$KRIA_IP/$p" 2>/dev/null; rc=$?
  case $rc in
    0|1) echo "port $p PASS: reachable" ;;
    124) echo "port $p FAIL: blocked (timed out)" ;;
    *)   echo "port $p unexpected rc=$rc" ;;
  esac
done
```

A refusal is a pass; only a timeout is a fault.

After a bring-up, test 8888 with `exec` (`cat` times out against a live
server):

**(on the lab computer)**

```bash
timeout 5 bash -c "exec 3<>/dev/tcp/$KRIA_IP/8888"; echo "8888 rc=$?"
```

`rc=0` pass, `rc=1` refused, `rc=124` blocked. With `iptables` or `nft`, open
the same ports there.

### One puller at a time

**Run only one `daq-client` per Kria.** A second `daq-client` pulling from the
same Kria, from any computer, silently takes half its data. Several Krias are
fine, each with its own `daq-client`. Symptom: clean bring-up, `no summary.json`, a
run directory with only `initial_full_config.yaml`, and in
`$MMTS_ROOT/daq-client.log`:

**(expected output of a failure, not a command)**

```
Error : serialization::archive ... not in dataTypeMap
```

During a scan, check the peers on 8888:

**(on the lab computer, during a scan)**

```bash
ssh kria 'ss -tn | grep 8888'
```

Expect one peer, your client. Stop any other on its machine:

**(on the other machine)**

```bash
pkill -f '[d]aq-client'
```

If `pgrep -af daq-client` finds nothing there, look for a Docker container
(`lsof -nP -iTCP | grep 8888`, `docker ps`). When taking over a bench, stop
the previous machine's puller first.

**(on the lab computer, the full picture in one line)**

```bash
pgrep -af '[d]aq-client'; ssh kria 'pgrep -af "[d]aq-server|[z]mq_server"; ss -tn | grep 8888'
```

Expect one `daq-client` here; one `daq-server`, one `zmq_server` and one 8888
peer on the Kria. Otherwise see 12.1.

## B7. Device permissions

Without these rules `gpiofind` aborts, and `daq-server` logs
`Permission denied` and rejects every configure.

**(on the Kria)**

```bash
echo 'SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpiochip-all.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=gpio
echo 'SUBSYSTEM=="uio", KERNEL=="uio*", GROUP="daq", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-uio-daq.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=uio
```

Confirm `daq` is in `i2c` and `gpio`; log out and in after any `usermod`.

## B8. Copy the code to the Kria

No git on the Kria. The i2c-server runs from `~/multimodule/hexactrl-sw`,
**not** from `/opt`.

**(on the lab computer)**

```bash
cd "$MM/kria"
ssh kria 'mkdir -p ~/multimodule/hexactrl-sw'
tar cf - enableROCs.py mmts_bringup.sh findslot.py set_daq_delays.py sgl_ladder.py \
  up_verified.sh start_i2c.sh start_daq.sh set_pwr_en.py \
  | ssh kria 'tar xf - -C ~/multimodule'
ssh kria 'cd ~ && for f in up_verified.sh start_i2c.sh start_daq.sh set_pwr_en.py; do ln -sfn multimodule/$f $f; done'
cd "$MMTS_ROOT/hexactrl-sw"
tar czf - --exclude=__pycache__ zmq_i2c | ssh kria 'tar xzf - -C ~/multimodule/hexactrl-sw'
ssh kria 'chmod +x ~/multimodule/*.sh ~/multimodule/*.py'
```

| file | what |
|---|---|
| `up_verified.sh SLOT [--external-power] [--board NAME] [--module N]` | kills the previous slot's i2c-server; runs `mmts_bringup.sh` up to `BRINGUP_TRIES` times (default 8) and the i2c-server up to 3; prints `READY` only when the ROC count matches `EXPECT_ROCS`, no `FAILED`, the board identified, and 5555 and 6000 listen. `KEEP_PAYLOAD=1` reloads the bitstream per try instead of cycling payload power |
| `start_i2c.sh SLOT` | restart the i2c-server on a slot, detached, and print its identify line; no firmware reload |
| `start_daq.sh` | (re)start `daq-server` after the i2c-server is up, releasing the trigger claim |
| `set_pwr_en.py SLOT on\|off ...` | drive one slot's payload rail without a bring-up |
| `sgl_ladder.py [N] [--label TEXT]` | per-slot I2C write statistics (fake-ACK check, switch writes, Sgl selects); first test after a power button |

Re-run the `tar` after any script change. Edit only `$MM/kria/`, never the
Kria copies.

---

# 11. Reference

Use this when a value looks wrong, a board type is new, or the automatic
analysis did not run.

## 11.1 ROC revision and `in_inv_cmd_rx`

Character 7 of the serial is the ROC revision, `C` or `D`.

**Do not change `Top.in_inv_cmd_rx` from the shipped config.** A wrong value
leaves every trigger link at `ngood=0` with DAQ fine. The LD Full needs 1
even on v3D.

| type | serial character 7 | `in_inv_cmd_rx` |
|---|---|---|
| LD Full | D | **1** |
| LD Left, Right, Bottom, Five | D | 0 |
| HD Full | D | 0 |
| HD Top | D | 0 |

Measured both ways on a v3D HD Full, each with its own bring-up:

| `in_inv_cmd_rx` | DAQ | trigger |
|---|---|---|
| **0** | 12/12 | 8/12 |
| 1 | 12/12 | **0/12** |

To test another value, do a fresh bring-up, not a rescan: ROC registers apply
only on an i2c-server's first initialize.

## 11.2 ROC addresses per board

A board with any ROC silent fails with `Exception: ROC addresses [...] do not match a known board`.
A bad bring-up gives the same message, so read the printed address list
first.

| board | ROC addresses |
|---|---|
| V3 LD Full HB | `0x08 0x18 0x28` |
| V3 LD Five HB | `0x48 0x58 0x68` |
| V3 LD Semi or Half HB | `0x48 0x58` |
| V3 HD Semi-left, Semi-right | `0x08 0x18` |
| V3 HD Bottom | `0x18 0x58 0x28 0x68` |
| V3 HD Top | `0x18 0x58 0x28` |
| **V3 HD Full HB** | **`0x08 0x18 0x28 0x48 0x58 0x68`** |

The probe does not cover `0x00/0x20/0x40/0x60`, so ROCv2 LD and NSH boards
are not found.

## 11.3 Measured link sets and the probe

The trigger set depends on the slot; never copy a trigger map across slots.
The gate counts the links each slot's shipped `_ped.yaml` lists.

| board type | DAQ, every slot | trigger live, A | B | C | in the shipped config |
|---|---|---|---|---|---|
| LD Full | `0 1 4 5 8 9` | all 12 | all 12 | all 12 | all 12 |
| LD Five | `0 1 4 5 9` | 10 of 12 | | | A `0 4`, B `1 4`, C `1 6` |
| LD Left, Right | `0 1 4` | `0 1 2 3 5 6` | `0 1 2 3 5 6` | `0 1 2 4 5 11` | A `5 6`, B `0 3`, C `1 4` |
| LD Bottom | `0 1 4` | `1 2 6` | `1 2 5` | `1 5` | the same |
| HD Full | all 12 | all 12 | all 12 | all 12 | all 12 |
| HD Top | `0 1 4 5 9` | `0 1 5 9` | `0 1` | `0` | the same |
| HD Bottom, HD Semi | not measured | | | | a template |

For a type or slot not listed, run `run_slot.sh` without `SKIP_PROBE=1`.

**(on the lab computer)**

```bash
"$MM/run_slot.sh" B initLD-Left-3b LD-Semi 2 probe 3
```

It writes the live set into the config and re-does the bring-up. Always
re-bring-up after a probe; a pedestal in the same bring-up stalls at 64
events.

## 11.4 Trophies

Trophies are shared across geometries (LB with LR and LT). A trophy type code
that differs from the module's does not mean a wrong trophy.

## 11.5 Offline unpack, when the automatic path fails

**(on the lab computer)**

```bash
D=$OUT/Mux<SLOT>/pedestal_run/run_<timestamp>
unpack -i $D/pedestal_run0.raw -o $D/pedestal_run0.root -M $D/pedestal_run0.yaml
cd "$SCRIPTS" && python3 -c "
import sys; sys.path.insert(0,'analysis')
import level0.pedestal_run_analysis as A
a = A.pedestal_run_analyzer(odir='$D'); a.add('$D/pedestal_run0.root')
a.mergeData(); a.makePlots()"
```

A good LD Full run: `.root` about 5 MB, `unpacker_data/hgcroc` 2 347 488
entries, `runsummary/summary` 234 rows, nine PNGs. Partials give fewer, in
proportion to their chips and channels.

## 11.6 Slot quirks, and what a good result looks like

- **Only one slot carries trigger**: the first one `daq-server` scanned since
  it started. Restart `daq-server` and scan your slot first. See 1.1.
- Slot C: never select sub-bus 7; it hangs the bus.
- Slot C: the trigger set differs from A and B (see 11.3). Another slot's
  config on C gives a FAIL.
- Slot C: keep `L1A_offset_or_BX: 13` with `method: 'automatic'`, even though
  the finder writes 14.

Pass yardstick: ten pedestals on a healthy LD Full slot give 60 of 60
half-ROCs below corruption 1.0, robust σ 0.741 ADC, a full gate first try,
30 s per run.

---

# 12. Common mistakes

## 12.1 Never do these

| never | why, and what it costs |
|---|---|
| Run the ZL30274 clock step (`i2cset -y 0 0x70 1` plus `zl30274_configurator.py`) | Wrecks the PL I2C master; needs a mains power cycle. Ignore docs that say to run it |
| `i2cdetect -y 2`, or any `--readback` | Reads wedge the I2C master |
| Hammer a non-responding ROC | Same wedge, faster |
| Re-run bring-up while `zmq_server` is running | Six dead DAQ links, twelve good trigger links. Run `pkill -f '[z]mq_server'` first (`up_verified.sh` does it for you) |
| `systemctl start zmq-server@X` or `daq-server.service` | Runs the RPM copies without the bench fixes. Start both by hand |
| Go straight to a pedestal | See 1.1. An unaligned slot times out at 240 s per run and can take down `daq-server` and the puller |
| Reuse a `daq-client` between runs | After a failed START its data decodes to nothing. Restart it per run |
| Drop `-I` | `daq-server` never leaves `created` and the client spins forever |

## 12.2 The traps that look like results

1. **`no ROCs` on every slot after a hardware change.** Check the loopback,
   the cables you just unplugged (including the power management board to mux
   board data cable), and module seating.
2. **Healthy entry counts with every lane broken.** Check per-half corruption
   too; neither means anything alone.
3. **`corruption == 0` on a dead half.** `adc_mean = adc_stdd = adc_iqr = 0`
   on every channel means zeros. A real half sits near `adc_mean ≈ 94`.
4. **Low corruption on a low yield run.** 216 of 10 000 events decoded looks
   perfect. Check the row count against the board's chips and channels.
5. **A stale identify line.** If the ROC type read returns `[0, 253, 104]`
   instead of `[0, 125, 104]`, every `initialize` returns `error:` while 5555
   stays up. `Identify a board with HGCROC` must be the last identify line in
   the log. Fix with a fresh bring-up; restarting `zmq_server` is not enough.
6. **Config applies only on the first `initialize`.** Always read the
   register back.

## 12.3 Symptom to action

| symptom | do |
|---|---|
| Everything returns `[Errno 5]`, switches do not ACK | Run bring-up in the recover form, possibly twice |
| `findslot.py` prints `mux GPIO write failed ([Errno 5] ...)` or `bus wedged during probe` | Cold start in the order of 1.2 and probe again. If it persists, see 12.4 |
| `KeyError: 'dac_hyst_toa'` | Redo bring-up plus i2c-server |
| Client hangs at `ROC(s) CONFIGURED` | Restart `daq-server` |
| A scan sits at `Initializing i2c sockets` and never proceeds | Run `~/start_i2c.sh SLOT`. Section 1.3 |
| Same hang, but `ss` on the Kria shows 5555 **and** 6000 listening and the identify line is good | `echo "KRIA_IP=$KRIA_IP"`; `192.0.2.7` is the placeholder of 0.5. If correct, fix the firewall per B6 |
| `status after start cmd : configured`, repeating | **Interrupt at once.** Find the unaligned link in `~/daq-server.log`, then re-run bring-up |
| `status after start cmd : created`, repeating | Add `-I` |
| 6 DAQ links dead, 12 trigger fine | Check `gpiofind Multiplex_A` and `ps aux \| grep "[g]pioset"`: the chip numbers must match |
| 0 of 12 trigger, DAQ fine | Restart `daq-server` and scan this slot first |
| All 12 trigger links `ngood=0`, DAQ perfect | Fix `in_inv_cmd_rx`: v3C is 1, v3D is 0, LD Full always 1 (11.1) |
| `.raw` unpacks to 0 entries | Restart `daq-client` |
| `unpack: command not found` in `pedestal_run0.log` | Put the install's `bin` on `PATH`. Section 0.6a |
| `python3: can't open file '.../delay_scan.py'`, naming a directory you did not choose | Set `SCRIPTS`; check with `echo "SCRIPTS=$SCRIPTS"`. Section 0.5 |
| `register_boards.py` gives `FileNotFoundError` or `JSONDecodeError: Expecting value` on `module_ids.json` | `git pull --ff-only` and `git submodule update --init --recursive` in `hexactrl-sw`, section 0.4 |
| `ModuleNotFoundError: No module named 'zmq'` | `which python3` must be `$MMTS_ROOT/venv/bin/python3`; if it is, re-run the `pip install` of 0.6b |
| Environment variables you just set are gone again | Put the three exports in `~/.bashrc`, per 0.5 |
| `source .../ROCv3-alper-dev/etc/env.sh` gives `No such file or directory` on the client | Expected on the client. Set `PATH` instead. Section 0.6a |
| cmake says `/hexactrl-script/analysis does not contain a CMakeLists.txt`, then `make` says `No targets specified` | `git submodule update --init --recursive` in `hexactrl-sw`. Section 0.4 |
| cmake reports `Found PythonInterp: .../miniforge3/bin/python3` | `conda deactivate`, delete the build directory, configure again. Section 0.6a |
| `make` fails on `yaml-cpp/yaml.h` or `zmq.hpp: No such file or directory` | Install `yaml-cpp-devel` and `cppzmq-devel`. Section 0.6a |
| `$MM/puller.sh: No such file or directory`, and no `multimodule/` at all | `git pull --ff-only` then `git submodule update --init --recursive` in `hexactrl-sw`. Section 0.4 |
| `dnf` answers `No matching Packages to list` for the firmware, and `dnf repolist` shows `HCGAL-DAQ-SW` alone | Write the `hgc-online-sw` repo file. Section B3 |
| `ZMQError: Address already in use` on 5555 | `ssh kria 'pkill -f "[z]mq_ser""ver.py"'` |
| `daq-client` cannot bind 6001 | `pkill -f '[d]aq-client'` |
| The gate says `no summary.json`, the run directory holds only `initial_full_config.yaml`, and `~/daq-server.log` ends in a healthy `STOP` | Stop the second puller: during a scan `ssh kria 'ss -tn \| grep 8888'` must show only your client. Section B6, "One puller at a time" |
| `Error : serialization::archive ... not in dataTypeMap` in `$MMTS_ROOT/daq-client.log`, followed by pages of misparsed `link_capture_daq.link0` | Same second puller as the row above; do not rebuild anything |
| A port test gives `rc=124` on a port that `ss` shows listening | Test with `timeout 5 bash -c "exec 3<>/dev/tcp/HOST/PORT"`, not `cat < /dev/tcp/...`. Section B6 |
| The scan reaches `status after start cmd : running` and then nothing for minutes, and the gate says `no summary.json` | Open 6001 on the lab computer (`sudo firewall-cmd --list-ports` is empty). Section B6 |
| Orphaned holders after a killed server | `pkill -f 'gpioset -m signal -b'` |
| `daq-client` exits with `std::length_error` or signal 6 | Restart `daq-server`, re-run bring-up, restart the puller |
| `elink link_capture_daq.linkN is not aligned` | Re-run bring-up; `--realign` does not fix it |
| `gpiofind: Permission denied` | Add the gpiochip udev rule. Section B7 |
| `daq-server` logs `Permission denied` then `impossible to process configure when state is Error` | Add the uio udev rule (B7), then restart `daq-server` |
| `fw-loader load: error: the following arguments are required: firmware` | Name the design: `multimodule-hd-tester-trophy-v3`. Section 0.5 |
| `sed: -e expression #1, char 49: extra characters after command`, and the echoed line shows `done` where you typed `!d` | Use the loop as written in B4 |
| Bring-up dies at `[pwr]` with `[Errno 2] ... '/dev/i2c-2'` | `fw-loader load` first |
| Repeated `[Errno 13] Permission denied: '/dev/i2c-2'` after many reloads | Reboot the Kria |
| `ROC addresses [...] do not match a known board` | Read the printed address list; usually a bad bring-up |
| Bring-up prints `board X needs all N of [...]; ['0x58'] never answered` | Reseat. If the same address is missing in every slot, the board is faulty |
| `retry 5/5` at the `[pwr] power management board 0x27` line, first bring-up after a power cycle | Use `--external-power`; one `--recover --external-power` bring-up clears the wedge |
| Supply reads 0.4 to 0.5 A on a channel with nothing brought up | Normal. Configured: about 1.9 A for three LD chips, 2.2 A for three HD chips |
| Bring-up repeats `0/N ROCs` and the supply sits in **CV at 0.05 to 0.1 A**, well under the 0.4 A quiescent | Interrupt `up_verified.sh`. Check the supply is on at 1.72 V and the power distribution board to mux board data cable is in. Sweep `--module 1/2/3` and keep the one that jumps the meter to ~1.2 A; if none does, check the module's flex and seating |
| `daq-server.log` says `Device ID , "TOP_A", does not exist in connection map` then `impossible to process configure when state is Error` | Replace the stock `connections.xml` per B4, again after every firmware install |
| The gate prints `no summary.json -- the scan did not produce output` or `STALE: newest summary is ...` | Act on the log tails `delay_scan.sh` prints below it: connection map (row above), uio rule (B7), or, for empty logs, `KRIA_IP` or the firewall. Section 2.5 |
| `bringup try N of 8: running ...` and then a silent minute | Normal (60 to 90 s per try). Watch with `ssh kria 'tail -f ~/bu_<slot>.log'`. Section 2.4 |
| Bring-up enables 2 of N with a different chip missing each time, or `0/N` once and then `READY bringup=2` | Re-run back to back |
| Gate FAIL on a `READY` bring-up, one DAQ or trigger link reading 0 | Re-run the bring-up. Do not make a config that drops the link |
| A zero-byte run behind a clean gate | Diff the run directory's `initial_full_config.yaml` against the shipped `EdgeSel_T1` for the slot. `header positions` in `daq-server.log` must be 23 on every link |
| Bring-up `3/3` but the i2c-server dies on `could not identify ROC type from readBack [0, 253, 104]` or `OSError: [Errno 5]` on a read, or the client hangs at initialize with an empty run directory and `RUN-FAILED (rc=124)` | Power-cycle the Kria, bring up back to back and run at once with no idle gap, or use another slot. Do not recreate the puller |
| `mmts_bringup.sh` on a bench-fed module dies at `[roc]` with a chip that `stopped responding mid-config`, right after a clean run on another slot | Run `pkill -f '[z]mq_server'` first, per 1.3 |

## 12.4 When only the power button will do

- **Retries climb from 1/5 to 5/5 across successive runs, ROCs dropping mid
  config.** Count retries in `~/bu_<slot>.log` and stop once they are
  exhausted. Run `sudo shutdown -h now`, cycle the power button, then run the
  bring-ups back to back. Confirm the bus on a known-good slot before blaming
  the module.
- **It gets worse every run and `0x71` or `0x73` stops ACKing entirely.** Halt
  and mains cycle.

**Start a kernel recorder before chasing one of these**; the stock image
keeps no journal across reboots.

**(on the Kria)**

```bash
setsid bash -c 'dmesg -w >> ~/kernel.log' < /dev/null > /dev/null 2>&1 &
pgrep -af 'dmesg -w'
```

Ignore the immediate `Done`; `pgrep` must list it. Restart it after every
power cycle; read with `tail -50 ~/kernel.log`.

The Kria clock boots at `2025-12-04`, so its log times do not match the
client's until the clock is set.

## 12.5 A few smaller ones

- Over ssh, use `pkill -f "[z]mq_server.py"`; plain `pkill -f
  "zmq_server.py"` kills your own ssh command. Same for `daq-server` and
  `daq-client`.
- After calling `daqController.start()` by hand, call `stop()`, or every
  later run fails at START.
- The Kria, run directory names and `module_ids.json` use UTC.
- Use `MMTS_L1A_LOG2PERIOD=10`.
- **Never add an `rm -rf` of the results root to `remap_all.sh`**:
  `rm -rf Results/320[TX]*` deletes the data.

---
