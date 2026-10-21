# MMTS setup and operation, for Module Assembly Centers

Multi-Module Test System: three hexaboards in one hexacontroller, measured one
slot at a time. This document takes you from a bare AlmaLinux client and an
unflashed Kria to pedestals on all three slots.

**Conventions.** `$MMTS_ROOT` is the working directory on the client,
`$KRIA_IP` the hexacontroller's address, `$SLOT` is `A`, `B` or `C`, and `$MM`
is `$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule`. Set them once in 0.5.

Every code block says where it is typed: **the lab computer**, the AlmaLinux
client, or **the Kria**. A lab computer block may act on the Kria through `ssh`;
only a few steps must be typed on the Kria itself.

---

## Contents

- [0. From a bare AlmaLinux client to a working bench](#0-from-a-bare-almalinux-client-to-a-working-bench)
- [1. Powering up](#1-powering-up)
- [2. Running a board](#2-running-a-board)
- [3. LD Full (LF)](#3-ld-full-lf)
- [4. LD Five (L5)](#4-ld-five-l5)
- [5. LD Left and LD Right (LL, LR)](#5-ld-left-and-ld-right-ll-lr)
- [6. LD Bottom and LD Top (LB, LT)](#6-ld-bottom-and-ld-top-lb-lt)
- [7. HD Full (HF)](#7-hd-full-hf)
- [8. HD Top (HT)](#8-hd-top-ht)
- [9. HD Bottom (HB)](#9-hd-bottom-hb)
- [10. HD Semi (HL, HR)](#10-hd-semi-hl-hr)
- [Route B: set up a Kria by hand](#route-b-set-up-a-kria-by-hand)
- [11. Reference](#11-reference)
- [12. Common mistakes](#12-common-mistakes)

Read 0 once per new client or Kria. Then 1 for power-up and bring-up, 2 for the
routine measurement, and your board type's section, 3 to 10. Section 11 is the
reference behind the numbers; 12 is where to go when something fails.

---

# 0. From a bare AlmaLinux client to a working bench

## 0.1 What runs where

| | client (AlmaLinux 9, x86_64) | Kria (hexacontroller, aarch64) |
|---|---|---|
| `hexactrl-script/multimodule/`, the bench scripts | ✅ | its `kria/` subset only |
| `hexactrl-sw` client side: `daq-client`, `unpack` | ✅ | ✗ |
| `delay_scan.py`, `pedestal_run.py`, analysis, hexmaps | ✅ | ✗ |
| bring-up, ROC enable, mux and power I2C | ✗ | ✅ |
| `zmq_server.py` (the i2c-server, port 5555) | ✗ | ✅ |
| `daq-server` (port 6000) | ✗ | ✅ |
| firmware bitstream and uHAL address tables | ✗ | ✅ |

The client drives everything over ssh and ZeroMQ. It needs GitLab only at
install time; the Kria never needs internet at run time.

## 0.2 Client prerequisites

**(on the lab computer)**

```bash
sudo dnf install -y git python3 python3-pip
```

Also about 20 GB of free disk for results, and a CERN account with an ssh key
registered at `gitlab.cern.ch`.

## 0.3 Passwordless access to the Kria

The wrappers make many short ssh calls per run, so do both of these first.

**Key based login.**

**(on the lab computer)**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_kria -C "mmts-client"
ssh-copy-id -i ~/.ssh/id_ed25519_kria.pub daq@<kria-ip>
```

**Connection multiplexing.** Add to `~/.ssh/config`. List the raw address as
well as the alias, because the scripts call `ssh daq@<kria-ip>` directly.

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

Verify with `ssh kria true` and then `ls ~/.ssh/cm-*`.

**Passwordless `sudo` for the two power commands.** Bring-up runs `sudo
kconn_pwr` and `sudo fw-loader` over a non-interactive ssh channel with no
terminal to prompt on; without this it hangs or fails silently. This step is
typed on the Kria, since the first `sudo` needs a terminal:

**(on the lab computer, this is what logs you into the Kria)**

```bash
ssh kria
```

Confirm the binary paths first, since the rule matches exact paths:

**(on the Kria)**

```bash
command -v fw-loader kconn_pwr
```

Then write the rule, substituting those paths if they differ.
`/etc/sudoers.d/hgc-bench` does not exist on a fresh Kria:

**(on the Kria)**

```bash
echo "daq ALL=(root) NOPASSWD: /usr/bin/fw-loader, /usr/bin/kconn_pwr" \
  | sudo tee /etc/sudoers.d/hgc-bench
sudo chmod 440 /etc/sudoers.d/hgc-bench
sudo -n fw-loader list
```

The last line must print without prompting. A password prompt means wrong paths
in the rule or a file not at mode 440. `exit` when it passes.

## 0.4 Clone the repositories

Two clones, both on CERN GitLab. The bench scripts, run configs and Kria-side
helpers all live inside `hexactrl-script`.

**Step 1, `hexactrl-sw`.** Branch `ROCv3-alper-dev`, not `ROCv3`. It is the DAQ
software, the `zmq_i2c` server, and, through its `hexactrl-script` submodule,
the bench scripts and run configs. Everything is on the upstream branch.

**(on the lab computer)**

```bash
export MMTS_ROOT=$HOME/mmts
mkdir -p "$MMTS_ROOT" && cd "$MMTS_ROOT"
git clone -b ROCv3-alper-dev --recurse-submodules \
  ssh://git@gitlab.cern.ch:7999/hgcal-daq-sw/hexactrl-sw.git hexactrl-sw
```

⚠️ **`--recurse-submodules` is not optional.** Three submodules on two levels:
`hexactrl-script` and `zmq_i2c` under `hexactrl-sw`, and `analysis` under
`hexactrl-script`. A plain clone leaves all three empty, and the failures come
later without naming a submodule: the 0.6a build dies at
`add_subdirectory(analysis)` with `does not contain a CMakeLists.txt file`, and
the B8 tar copies an empty `zmq_i2c` to the Kria. On an existing clone,
`git submodule update --init --recursive` from `hexactrl-sw` fixes it.

**Step 2, `gui-hexmap`.** The repository is `hgcal-module-testing-gui`; the
directory name is yours, recorded as `GUI_HEXMAP` in 0.5.

**(on the lab computer)**

```bash
git clone -b master \
  ssh://git@gitlab.cern.ch:7999/acrobert/hgcal-module-testing-gui.git gui-hexmap
```

Without GitLab ssh, replace `ssh://git@gitlab.cern.ch:7999/` with
`https://gitlab.cern.ch/` in each URL; it prompts for username and a personal
access token.

Check the branches and the submodules:

**(on the lab computer)**

```bash
git -C hexactrl-sw rev-parse --abbrev-ref HEAD
git -C gui-hexmap  rev-parse --abbrev-ref HEAD
ls hexactrl-sw/hexactrl-script/multimodule/puller.sh
ls hexactrl-sw/zmq_i2c/Link.py hexactrl-sw/hexactrl-script/analysis/CMakeLists.txt
```

The first two print `ROCv3-alper-dev` and `master`. `No such file or directory`
on the last two means the recursive update did not run. Submodules are pinned
by commit, so their own `rev-parse` prints `HEAD`; detached is correct.

Resulting layout. `RESULTS_DIR` in 0.5 moves `Results`:

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

`hgc-test-systems`, the firmware, is needed only to rebuild a bitstream. Clone
it then, not now.

⛔ Do not clone `gitlab.cern.ch/hgcal-daq-sw/hexmap`. It is deprecated, its
`master` has no LD-Full-V3 channel map, and plots come out with the right
outline and wrong channel positions. `gui-hexmap` is the only correct source.

## 0.5 Site settings

Set these once in `~/.bashrc`. **`KRIA_IP` is the one line you must change**:
your hexacontroller's address exactly as you would type it into `ssh`, with no
quotes, braces or `${...}`. The rest can be pasted as they are unless you moved
something.

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

Plain `export NAME=value` only: no quotes around the address, no
`${NAME:-default}` fallbacks.

Then `source ~/.bashrc` and check that it took:

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

🔑 **The `case` is there because the raw check reads backwards.** Nothing
listens on 5555 until a bring-up, so the healthy answer is `Connection refused`:
the packet reached the Kria and got an RST. The failure is a five second
silence, `rc=124`, which is a wrong `KRIA_IP` or a firewall.

| variable | what it is |
|---|---|
| `MMTS_ROOT` | the directory from 0.4, the parent of `hexactrl-sw` |
| `MM` | the bench scripts, `hexactrl-script/multimodule` |
| `SCRIPTS` | `hexactrl-script` itself, where `delay_scan.py` lives |
| `KRIA_IP`, `KRIA_USER` | **your hexacontroller**, user `daq` by default |
| `HEXACTRL` | the install prefix from 0.6a |
| `MMTS_VENV` | the virtualenv from 0.6b, or empty for system-wide |
| `MMTS_FW` | the firmware design, see B5 |
| `RESULTS_DIR` | the output root |
| `GUI_HEXMAP` | the `gui-hexmap` clone from 0.4 |

The scripts read these through `$MM/lib.sh`. `MMTS_ROOT` and `KRIA_IP` are
required, and a script stops naming a missing one; the rest default to the
block above. Override any of them for one run on the command line, e.g.
`MMTS_FW=... "$MM/delay_scan.sh" B`.

Two fail in ways that do not look like a wrong variable:

🛑 **A wrong `KRIA_IP` hangs rather than errors.** `delay_scan.py` waits forever
at `Initializing i2c sockets`, while **`ssh kria` keeps working** because it
resolves through `~/.ssh/config`, not `KRIA_IP`. The scripts check that the
variable is set, not that it is right; the `/dev/tcp` line above does.

🔑 **`SCRIPTS` unset fails silently.** `cd ""` is a no-op, so `cd "$SCRIPTS"`
leaves you where you were and the error names a directory you never chose.
Only the hand-typed commands of sections 2 to 10 use it.

## 0.6 Install the client stack

### a. hexactrl-sw

Build the client side of the `ROCv3-alper-dev` clone and install it under
`/opt/hexactrl/ROCv3-alper-dev`.

**There is no RPM.** The `deploy-eos` CI job runs only for `ROCv3`, so the
public repository at `hgc-online-sw.web.cern.ch` carries nothing from this
branch. Build from source on both the client and the Kria.

The client build needs **Boost, ROOT, yaml-cpp and cppzmq**. uHAL belongs to
the server build of B2. ROOT alone is about a gigabyte:

**(on the lab computer)**

```bash
sudo dnf install -y cmake make gcc-c++ boost-devel
sudo dnf install -y epel-release
sudo dnf config-manager --set-enabled crb
sudo dnf install -y root yaml-cpp-devel cppzmq-devel zeromq-devel
cmake --version && root-config --version
ls /usr/include/yaml-cpp/yaml.h /usr/include/zmq.hpp
```

`root` comes from EPEL on AlmaLinux 9. If your site provides ROOT through CVMFS
or a module, source that instead; cmake finds it via `$ROOTSYS`.

⚠️ **Three traps in that block.** There is **no `root-devel`**: the headers ship
in `root-core` and the `root` metapackage pulls what you need. **`crb` must be
enabled first**, because `root-io` needs `liburing-devel` from CRB; without it
the install dies with `nothing provides liburing-devel`. And **cmake never
checks for yaml-cpp or cppzmq**, so leaving them out configures cleanly and
fails minutes later in `make` with `fatal error: yaml-cpp/yaml.h`. If EPEL has
no `cppzmq-devel` on your release, the CERN repo's `cppzmq-devel-latest` is the
same header-only binding.

**(on the lab computer)**

```bash
cd "$MMTS_ROOT/hexactrl-sw" && mkdir -p build && cd build
cmake -DBUILD_CLIENT=ON -DBRANCH_NAME=ROCv3-alper-dev \
      -DCMAKE_INSTALL_PREFIX=/opt/hexactrl/ROCv3-alper-dev ../
make -j"$(nproc)" && sudo make install
```

⚠️ **All three flags matter, and the failures are quiet.** `BUILD_CLIENT`
defaults to OFF and builds the server side instead, with no `daq-client` and
no `unpack`. The install path is `/opt/hexactrl/${BRANCH_NAME}`, read from
`git` when not passed; from a snapshot with no `.git` it comes back empty and
everything lands in `/opt/hexactrl/` itself. `make install` writes under
`/opt` and needs `sudo`.

🔑 **Deactivate conda before configuring.** cmake takes the first `python3` on
`PATH`, so a `(base)` prompt builds against miniforge's 3.12, which cannot
import `uproot3` (0.6b). Read the configure output:

**(configure output, not a command)**

```
-- Found PythonInterp: /usr/bin/python3 (found suitable version "3.9...")
```

Anything under `miniforge3` or `anaconda3` means `conda deactivate`, **delete
the build directory**, and configure again: the interpreter is cached.

Build on the x86_64 client that will run it. The Kria gets its own aarch64
build in B2.

⛔ The public `ROCv3` RPM is not a substitute. It lands under
`/opt/hexactrl/ROCv3/`, changing every path here, and predates the MR !55 fixes
of B2.

Confirm `daq-client`, `hitproducer` and `unpack` landed:

**(on the lab computer)**

```bash
ls /opt/hexactrl/ROCv3-alper-dev/bin
```

Every shell that runs a client command needs that `bin` on `PATH`, which the
0.5 block does with `export PATH=$HEXACTRL/bin:$PATH`.

🔑 That `PATH` is the fix for the most common analysis failure: the notifier
shells out to a bare `unpack`, and without it a run produces no `.root` and
`pedestal_run0.log` says `unpack: command not found`.

⚠️ **There is no `etc/env.sh` on the client.** `CMakeLists.txt` installs it
only for the server build, and it holds cactus and uHAL paths the client does
not need. The client build installs `bin` and nothing else. `multimodule/lib.sh`
sources it only if it exists and prepends `$HEXACTRL/bin` regardless, so the
export matters for the hand-driven commands of 2 to 10, not for `run_slot.sh`.

### b. Python dependencies

A virtual environment that can still see the system Python modules:

**(on the lab computer)**

```bash
python3 -m venv --system-site-packages "$MMTS_ROOT/venv"
source "$MMTS_ROOT/venv/bin/activate"
pip install --no-cache-dir \
    "numpy<2" pyzmq pyyaml pandas matplotlib scipy seaborn \
    uproot uproot3 awkward awkward-pandas more_itertools \
    nested_dict nested_lookup pyinotify tables
```

`numpy<2` and `uproot3` are pinned: the pedestal analysis and
`hexmap_robust.py` read trees through uproot3. ROOT and pylandau are not needed
here.

🔑 **Build the venv with the system `python3`, conda deactivated.** `uproot3`
does not work on Python 3.12 (`'FileFinder' object has no attribute
'find_module'`), and a conda `base` shadows `/usr/bin/python3`, so `python3 -m
venv` silently builds a 3.12 venv and defeats `--system-site-packages`. With
the venv active, `which python3` must be `$MMTS_ROOT/venv/bin/python3` and the
`lib` listing must show `python3.9`. The last three lines are only for a wrong
version:

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

`$MM/README.md` lists every file; these are the ones you type.

**(on the lab computer)**

```bash
cd "$MM"
chmod +x *.sh *.py kria/*
./puller.sh
```

The last line prints `puller up on 6001`.

| script | what |
|---|---|
| `run_slot.sh` | **one slot end to end**: bring-up, gate, N pedestals, finder line, hexmaps, per-half check. This is the command a routine measurement uses |
| `register_boards.py` | record which serial is in which slot. Run it before the first bring-up after every board change |
| `bench_up.sh` | cold start: bitstream, payload power, ROC enable |
| `delay_scan.sh` | delay scan plus the PASS/FAIL gate |
| `ped_run.sh` | N pedestal runs scored by CRC |
| `slot_measure.sh` | bring up, gate, N pedestals, common-mode decomposition |
| `cm_analysis.py` | common-mode decomposition of a pedestal run: total, CM, residual, autocorrelation |
| `hexmap_robust.py`, `remap_all.sh` | hexmaps for one run, or for everything under the results root |
| `puller.sh`, `gate.py`, `module_of.py`, `finder_positions.sh` | the pieces the others share |

Two things they do for you:

- **The puller is restarted per run.** A `daq-client` that saw a failed START
  silently produces data that decodes to nothing.
- **`PATH` picks up the hexactrl `bin`**, so the notifier's bare `unpack` works.

Sections 2 to 10 also give the underlying commands, for driving it by hand.

**What you see.** `run_slot.sh` prints a banner per stage, then that stage's
output live. `up_verified.sh` prints one line when a try starts and one when it
ends, so a silent minute is a try in progress. `delay_scan.sh` names the log it
keeps and prints the gate. Section 2 gives timings and which log to `tail -f`.

## 0.7 Copy the code to the Kria

Moved to **B8**, the last step of Route B at the end of this document. The
Route A image already carries the Kria-side scripts and the i2c-server; B8 is
for a hand-built Kria, or a flashed image that has fallen behind the client.

## 0.8 One-time Kria setup

**Route A**, below, writes a prepared image onto the SD card. Take it unless
you have a reason not to.

**Route B** builds the same result by hand, one piece at a time. It is at the
end of this document because most benches never need it: take it on a Kria
that cannot be flashed, or one step at a time to repair a Route A Kria that
fails a check in 0.9. Its steps are B1 to B8.

Both routes end at 0.9. Run those checks either way.

### Route A: flash the prepared image

A gzipped snapshot of a working bench Kria's SD card, on CERNBox. The public
link needs no sign-in and no CERN account. The same file works from Linux and
macOS.

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

The card must be **32 GB**. A nominal 16 GB card is a few MB short of the
15.9 GB the image writes.

The 10-13 image adds the `~/multimodule` wrappers of B8, the hardened i2c-server,
the firmware variants, chrony, and has no ssh host keys: the first ssh to a
freshly flashed Kria shows a new host key.

#### A1. Fetch and check it

Download it with `curl`, no sign-in needed:

**(on the lab computer, Linux or macOS)**

```bash
cd "$MMTS_ROOT"
L=https://cernbox.cern.ch/remote.php/dav/public-files/gA7anszJiATLSSR
curl -L -o kria-mmts-20261013.img.gz        $L/kria-mmts-20261013.img.gz
curl -L -o kria-mmts-20261013.img.gz.sha256 $L/kria-mmts-20261013.img.gz.sha256
ls -l kria-mmts-20261013.img.gz
```

Or open `https://cernbox.cern.ch/s/gA7anszJiATLSSR` in a browser and click the
file. Do not use `.../s/gA7anszJiATLSSR/download`: that gives a tar of the
whole folder, both images included.

**By xrootd**, from a machine with `xrdcp` and a CERN Kerberos ticket
(`kinit user@CERN.CH`) or a CMS VOMS proxy:

**(on the lab computer, or any machine with xrootd)**

```bash
xrdcp root://eosuser.cern.ch//eos/user/t/tvami/forMACs/kria-mmts-20261013.img.gz .
xrdcp root://eosuser.cern.ch//eos/user/t/tvami/forMACs/kria-mmts-20261013.img.gz.sha256 .
```

⚠️ **xrootd needs read access to the folder, which the public link does not
give.** Without it `xrdcp` fails with `[3010] Unable to open file ...
Operation not permitted`. Ask for the folder to be shared with your CERN
username, or use `curl` above.

⚠️ **Check the checksum before you write a card.** A truncated download writes
without complaint and the Kria then fails to boot, or boots a corrupted root.
A short or mismatched download is your network dropping the transfer; the fix
is to download again.

**(on the lab computer, Linux)**

```bash
sha256sum kria-mmts-20261013.img.gz
```

**(on the lab computer, macOS)**

```bash
shasum -a 256 kria-mmts-20261013.img.gz
```

It must print the sha256 in the table. Otherwise download again; do not
continue.

#### A2. Identify the card, and check it twice

🛑 **`dd` writes to whatever device you name, with no confirmation and no undo.
Naming your system disk destroys the lab computer.** Confirm the size matches
the card you just inserted.

**(on the lab computer, Linux)**

```bash
lsblk -d -o NAME,SIZE,MODEL,TRAN
```

The card is the removable device whose size matches, usually `sdb` in a USB
reader or `mmcblk0` in a built-in one.

**(on the lab computer, macOS)**

```bash
diskutil list external physical
```

The card is a `/dev/diskN` whose size matches. When writing, **use
`/dev/rdiskN`**, the raw node: it bypasses the buffer cache and is several
times faster. Linux has no equivalent; `/dev/sdX` is already the right node.

#### A3. Write it to the card

Both forms **stream the decompression straight into `dd`**, so the 15.9 GB
image never touches disk. Substitute the device you just confirmed.

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

⚠️ **The two platforms differ in four places, and three fail quietly.**

| | Linux | macOS |
|---|---|---|
| list the disks | `lsblk` | `diskutil list` |
| unmount | `umount /dev/sdX*`, one call per partition | `diskutil unmountDisk /dev/diskN`, whole device |
| device to write | `/dev/sdX` or `/dev/mmcblk0` | `/dev/rdiskN`, the raw node |
| block size | `bs=4M`, uppercase | `bs=4m`, lowercase |
| progress | `status=progress` | **Ctrl+T**, there is no `status=progress` |

macOS `dd` accepts only `none` and `noxfer` for `status=`, so `progress` is an
error there. Press Ctrl+T for a progress line. Expect five to fifteen minutes.

#### A4. Boot it

Move the card to the Kria, power it on, and find it on the network. The image
takes its address by DHCP: read it from your DHCP server, the Kria's console,
or by watching for a new host on the bench subnet. That address is `KRIA_IP`
in 0.5.

To watch for the new host, scan with the Kria off and again with it on. `ip -4
addr` gives your own subnet; use it in place of `10.116.24.0/23`:

**(on the lab computer)**

```bash
sudo nmap -sn 10.116.24.0/23 -oG - | awk '/Up/{print $2}' | sort > before.txt
# power the Kria on, wait 2 minutes
sudo nmap -sn 10.116.24.0/23 -oG - | awk '/Up/{print $2}' | sort > after.txt
comm -13 before.txt after.txt
```

The new address is the Kria; the first `ssh` to it shows a new host key, since
the image ships without one. More than one new address means ask your network
admin for the lease, and for a fixed address.

## 0.9 Check the installation

All typed on the lab computer. The first block checks the Kria over `ssh`, the
second the client stack.

**(on the lab computer, checking the Kria)**

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria 'ls -l /dev/i2c-2 /dev/uio0; gpiofind Multiplex_A'
ssh kria 'grep -c "id=\"TOP_[ABC]\"" /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml'
ssh kria 'cd ~/multimodule && python3 findslot.py'
```

The `grep` must print `3`. Anything else means B4 is not done, or a firmware
install put the stock file back. The failure comes much later and looks like
something else: a clean bring-up, a scan that runs, and a gate saying `no
summary.json` because `daq-server` logged `Device ID , "TOP_A", does not exist
in connection map`.

**(on the lab computer, checking the lab computer)**

```bash
source "$MMTS_VENV/bin/activate"
command -v daq-client unpack
python3 -c "import uproot, uproot3, numpy, zmq; print(uproot.__version__)"
"$MM/puller.sh"
```

⚠️ **Do not run the second block on the Kria.** It has no `daq-client`, venv,
uproot or ROOT, and is not supposed to. `hostname; uname -m` settles which
machine you are on: `x86_64` is the lab computer, `aarch64` the Kria.

`findslot.py` probes all three slots for ROCs without a bring-up. It is
harmless and the cheapest diagnostic on the bench.

🔑 **`no ROCs` on all three slots is the expected result here.** Nothing has
powered a module yet: `findslot.py` writes the mux board's `S*_PWR_EN` but
does not run `kconn_pwr on` and never touches `EN_Mx` on the power board at
`0x27`. It also probes only the LD-Full addresses `0x08 0x18 0x28` on sub-bus
`S1_I2C`, so a partial at `0x48 0x58` or an HD Full's second sub-bus reads `no
ROCs` even when powered. What it proves: the PL I2C master is alive, all three
switches ACKed at `0x71`, `0x73` and `0x77`, and the mux GPIO writes went
through. Expect **0 A on the meter** until a bring-up.

### What to do when `findslot.py` fails instead

🛑 **`mux GPIO write failed ([Errno 5] Input/output error)` or `bus wedged
during probe` is a fault, not `no ROCs`.** The write never completed, so the
PL I2C master is what answered:

**(expected output of a failure, not a command)**

```
slot A: mux GPIO write failed ([Errno 5] Input/output error)
slot B (switch 0x73): no ROCs [bus wedged during probe]
slot C: mux GPIO write failed ([Errno 5] Input/output error)
```

**Do not try to fix it from here. Go to section 1 and power the bench up in
the documented order**, then run `findslot.py` once more. The usual cause is
that nothing has powered the bench yet; 1.2 is the step that does. If it still
fails after a clean cold start, 12.3 and 12.4 cover the wedge.

Do not re-run `findslot.py` repeatedly, and do not reach for `i2cdetect -y 2`.
Reads wedge this master, so that check causes the fault it looks for.

---

# 1. Powering up

🔑 **Read your board's row in 2.1 first.** Every bring-up command takes three
values from the board type: `--board`, `EXPECT_ROCS`, and whether the module
has a power distribution board, which decides `--external-power`.
`--external-power` on a board that has one skips the `0x27` `EN_Mx` write that
powers the module, so it stays dead and reads `no ROCs`.

The short version. `any` probes every V3 address and enables what answers; use
it on a board type you have not run before:

| board | `--board` | `EXPECT_ROCS` | power distribution board |
|---|---|---|---|
| LD Full | `LD-Full` | 3 | fitted |
| HD Full | `HD-Full` | 6 | fitted |
| LD Five | `LD-Five` | 3 | none |
| LD Left, Right, Bottom, Top | `LD-Semi` | 2 | none |
| HD Top, Bottom, Semi | `HD-Top`, `HD-Bottom`, `HD-Semi` | 3, 4, 2 | none |
| unknown | `any` | read it off the probe | check the board |

The examples use an LD Full, three ROCs with a power distribution board.

⚠️ **The two wrappers default the opposite way.** `enableROCs.py` and
`up_verified.sh` assume the power board is there and take `--external-power`
to say it is not. `bench_up.sh` assumes it is not and takes `--power-board`.
Both mistakes give the same dead module reading `no ROCs`.

## 1.0 Size the supply BEFORE you trust any measurement

🔑 **A module at its supply's current limit produces data that looks like
broken hardware.** On an HD Full at the limit the rail sags from 1.72 V to
**1.35 V** and **all 24 e-links die**. With headroom the same module gives
12/12 DAQ links and CRC 1.000.

| board | measured draw at 1.72 V |
|---|---|
| any slot, rail on, ROCs idle | 0.4 to 0.5 A |
| LD Full, three chips | ~1.2 A enabled, **1.9 to 2.0 A** configured and running |
| LD partials, two chips | ~1.2 A |
| HD Top, three chips | ~2.1 to 2.2 A |
| **HD Full, six chips** | **4.43 A** |

The meter reads 0 A briefly during every bring-up, while `--recover` cycles
payload power. Read it after `Turning on payload power`, and again while a
run has the chips configured.

⚠️ **Many bench supplies are ~3.2 A per channel and cannot run an HD Full on
one channel.** On a SIGLENT SPD3303X-E that is a **hardware maximum**. Press
**`Para`** to link CH1 and CH2 into one 0-6.4 A channel:

* both leads on **CH1 only** (`Para Out`); CH2's terminals stay empty;
* set the voltage on CH1 and leave the current at its per-channel maximum;
  asking for 6.4 A gives `current setting overrange`;
* 🛑 **never wire `+CH1 / −CH2`**. That is the *series* pattern and in `Ser`
  mode puts **double** the set voltage on the board.

**How to tell you are clipping:** the mode reads **`CC`** and the **output
voltage is below the setpoint**. Both halves matter, since in parallel mode
the slave channel always reads `CC`.

**What clipping imitates**, each of which reads as a hardware fault: the meter
wandering with nothing running; consecutive bring-ups finding a **different
number of ROCs** (4 of 6, then 6 of 6), because ROCs enable sequentially and
the last one fails as the rail sags; a module that works and then stops after
~30 minutes.

🔑 Silencing chips **cannot rescue bring-up**: `Link.find_board_for_rocs`
requires an exact address-set match, so every ROC must enable before any
config can quiet them. Size the supply for the spike.

## 1.1 The order, always

**(the order of operations, not commands)**

```
bring-up  →  i2c-server  →  daq-server  →  puller  →  DELAY SCAN  →  pedestal
```

🔑 **Always take a delay scan before a pedestal.** The scan takes seconds and
is harmless when it fails. A pedestal on an unaligned slot makes `daq-server`
refuse START, and the client's retry loop hammers it thousands of times and
can take the server and the puller down.

🔑 **Exactly one slot carries trigger at a time: the first slot `daq-server`
scanned since it last started.** The other two read 0 of 12 on trigger with
DAQ perfect. To move it, restart `daq-server` and scan that slot first. No
mains cycle needed. `mmts_bringup.sh` restarts `daq-server` for you;
`--keep-daq-server` overrides.

**After any failed or interrupted run, restart `daq-server` and the puller.**
Both hold state from the dead run.

## 1.2 Powering the bench without a bring-up

🔑 **Skip this if your next command is a bring-up.** `mmts_bringup.sh` and
`up_verified.sh` default to `--recover`, which does these two things plus a
`kconn_pwr off` first. This is for powering the bench when you are **not**
about to run one: a `findslot.py` that failed with `[Errno 5]` at 0.9, or
driving `enableROCs.py` yourself.

**(on the lab computer)**

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria 'sudo kconn_pwr on'
```

⚠️ `enableROCs.py` has no `--no-recover` flag: plain is the default and does
not cycle power; `--recover` opts in. After a mains cycle use the recover form
or the two commands above, otherwise every probe returns `no ROCs` against an
unpowered bus with all writes still ACKing. The wrappers are the other way
round: `mmts_bringup.sh` defaults to `--recover` and takes `--no-recover`, and
`up_verified.sh` passes flags through, so a wrapper bring-up has cycled
payload power on every attempt.

## 1.3 The bring-up wrappers

**`mmts_bringup.sh` for a first bring-up or when anything is wrong;
`up_verified.sh` for routine measurement on a bench that already works.**

| | `mmts_bringup.sh SLOT` | `up_verified.sh SLOT` |
|---|---|---|
| attempts | one | up to 8 bring-ups, then up to 3 i2c-server starts |
| output | on your screen | to `~/bu_<slot>.log`; one line when a try starts and one when it ends |
| to watch a try | it is already in front of you | `ssh kria 'tail -f ~/bu_<slot>.log'` in a second terminal |
| kills a stale i2c-server first | **no**, do it yourself, as the block below does | yes |
| starts the i2c-server on 5555 | **no, run `start_i2c.sh` yourself** | yes |
| restarts `daq-server` on 6000 | yes | yes, through `mmts_bringup.sh` |
| verifies the result | no | ROC count, no `FAILED`, board identified, 5555 and 6000 listening |
| use it | commissioning, diagnosis, anything unexplained | a slot you have brought up before |

🔑 **Start a new board, a new bench, or any investigation with
`mmts_bringup.sh`.** It runs once and puts the real error in front of you,
and its `--recover` default means it is a complete bring-up:

**(on the Kria)**

```bash
pkill -f '[z]mq_server'
cd ~/multimodule && ./mmts_bringup.sh A --board LD-Full
```

🛑 **Read the result before typing anything else.** Go on only when it ended
in its ROC list, `3 ROC(s) enabled [...]` for an LD Full, per 1.4. `bring-up
failed` or a traceback means 12.3 and 12.4, not the next block.

**(on the Kria, only after the bring-up printed its ROC list)**

```bash
~/start_i2c.sh A
```

⚠️ **This block is not optional, and nothing reminds you of it.**
`mmts_bringup.sh` restarts `daq-server` on 6000 but does **not** start the
i2c-server on 5555. Skip it and the next scan sits at `Initializing i2c
sockets`. `ss -ltn | grep -E '5555|6000'` must show both.

`start_i2c.sh` takes about 25 s and ends with the identify line: **`Identify a
board with HGCROC Siv3b`** is right; plain `Siv3` means redo the bring-up, per
1.4.

🔑 **Running it on a failed bring-up costs you the next attempt.** It binds
5555 regardless, so `--- listening ---` under a traceback reads as partial
success, and the re-run is then a bring-up under a live server, which is 12.1.
`pkill -f '[z]mq_server'` before re-running.

### When the bring-up fails instead

| message | from | means |
|---|---|---|
| `!! bring-up failed -- re-run once.` | `mmts_bringup.sh` | one attempt failed |
| `FAILED to bring slot A up cleanly -- read ~/bu_A.log and ~/zmq_srvA.log` | `up_verified.sh` | **eight** bring-ups failed, each with up to three i2c-server starts, so roughly ten minutes and eight payload power cycles are already gone |

🔑 **`up_verified.sh` failing after a hand-run `mmts_bringup.sh` that looked
fine is not a contradiction.** It counts a try as good only when the ROC count
reaches `EXPECT_ROCS`, `FAILED` appears nowhere, the i2c-server logged `Board
identification`, and 5555 and 6000 both listen.

**Read its per-try lines first**, since the two halves have different causes:
`bringup try 3: 0/3 ROCs ...` is the bring-up and the rest of this subsection
applies; `i2c try 1: 4 errors, 5555=0 ...` is the i2c-server, the stale
identify trap of 12.2 or the dead-reads row of 12.3. Then read `~/bu_A.log`
and `~/zmq_srvA.log`. Both are truncated on each launch.

🔑 **Re-run the bring-up block once, and decide on the retry counts rather
than the ROC count.** A partial enable with a different chip missing each time
is the lottery of 1.4 and wants another go. `[Errno 5]` on the `[mux]` writes
to `0x71`, `0x73` and `0x77` does not: those never leave the mux board, so the
PL I2C master is failing. **If the retries reach `5/5`, or reach it earlier
than last time, stop.** `--recover` cannot clear that state and every further
attempt degrades it. Halt with `sudo shutdown -h now`, press the power button,
wait for `ssh kria`, and **restart at the bring-up block of 1.3.** Everything
else is on disk and survives: the udev rules of B7, `connections.xml` and the
per-slot tables of B4, the firewall of B6, the sudoers rule of 0.3, the
firmware RPM, and the Kria-side scripts of B8. The cold-start lines of 1.2 are
not needed either, since `--recover` does them. Only a firmware install sends
you back to B4.

Run the bring-ups **back to back** rather than one per boot: a slot that
failed on five separate fresh boots came up 4 of 10 in a row, with the error
count falling each attempt. 12.4 is the long form.

⚠️ **`up_verified.sh` retries what should not be retried.** Its eight attempts
are calibrated for the lottery, where each failure is a *partial* enable.
Against a real fault, an unpowered module, a wrong `--module` bit, an open
power path, they are eight identical failures that give the master eight more
chances to wedge while the actual error sits unread in `~/bu_<slot>.log`. **A
run of identical zero-ROC tries is a fault: interrupt it, read that log, and
go back to `mmts_bringup.sh`.**

Once the slot is known good, use `up_verified.sh`, which also starts the
i2c-server and checks what a log line will lie about. LD Full form; your type's
section has the line per slot:

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --board LD-Full"
```

⚠️ `EXPECT_ROCS` defaults to 3. Set it to your board's count. With the default
a partial enable such as `4 ROC(s) enabled ... 1 FAILED ['0x28']` on a six-ROC
board is reported as `READY`, and the pedestal then times out four times over.

### 🔑 `--module N`: `EN_Mx` is cabling, not the slot index

With a power distribution board fitted, the bring-up drives `EN_Mx` to switch
the module on. The default is the slot's index (`A`→1, `B`→2, `C`→3), which is
**an assumption about which output the power lead is plugged into**.

Wrong, it gives `no ROCs` with **next to nothing on the meter**, which looks
like a dead module, a bad trophy or a seating fault. Leave `--module` off until
it fails that way, then sweep the three values one at a time, keeping `--board`
and `EXPECT_ROCS` at your own board's, and watch the meter:

**(on the lab computer, only after a bring-up gave `no ROCs` at near-zero
current; run one line at a time and stop at the one that draws current)**

```bash
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 1"
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 2"
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 3"
```

⛔ **Do not change `--board` while sweeping.** `--board HD-Full` on an LD Full
demands six addresses on a three-chip board and can never succeed.

🔑 **Diagnostic rule.** `no ROCs` with the **mux-board GPIO writes succeeding**
means master, switch and expander are fine. **Sweep `--module 1/2/3` and watch
the meter before suspecting the module.** Any draw at all identifies the bit.
If all three read the same near-zero current, the power path is the problem:
see the low-current row of 12.3.

The flag is forwarded by `bench_up.sh` and `mmts_bringup.sh` directly, by
`ped_run.sh` as `PED_MODULE`, and by `slot_measure.sh` as `SM_MODULE`.

`bench_up.sh` does the cold start from the client, in the only order that
works. It is a commissioning tool, not part of a routine measurement. LD Full
form; each type's section has its own line:

**(on the lab computer, when driving a cold start by hand, not in a normal run)**

```bash
"$MM/bench_up.sh" A --board LD-Full --expect 3 --power-board
```

⚠️ **`bench_up.sh` spells the power board the other way round:** opt *in* with
`--power-board` here, opt *out* with `--external-power` in `up_verified.sh`.
Leaving `--power-board` off an LD Full gives the same dead module.

## 1.4 What good looks like, and when to just re-run

A good bring-up prints the ROC list, readbacks of `0x0`, and `daq-server ...
ok` on 6000:

**(expected output, not a command)**

```
3 ROC(s) enabled ['0x8', '0x18', '0x28']
```

A good i2c-server prints **`Identify a board with HGCROC Siv3b`**. Plain
`Siv3` means redo bring-up plus i2c-server, otherwise the next configure dies
with `KeyError: 'dac_hyst_toa'`.

🛑 **Read the `[I2C] Board identification` line above it too, and stop if it
names a board type you do not have.** `Link.py` matches the exact address set,
so a partial enable whose subset is *another* board's whole set identifies as
that board, prints a clean `Siv3b` line, binds 5555, and applies the wrong
link map. Seen on an LD Full whose `0x28` never came up:

**(expected output of a failure, not a command)**

```
[I2C] Board identification: V3 HD Semi-left or HD Semi-right HB
Identify a board with HGCROC Siv3b
--- listening ---
```

The subsets that collide, from 11.2. An HD Full contains five other types:

| you have | missing | identifies as |
|---|---|---|
| LD Full | `0x28` | HD Semi |
| LD Five | `0x68` | LD Semi |
| HD Bottom | `0x68` | HD Top |
| HD Full | `0x48 0x58 0x68` | LD Full |
| HD Full | `0x28 0x48 0x58 0x68` | HD Semi |
| HD Full | `0x08 0x18 0x28` | LD Five |

The cure is the bring-up: re-run it and require the full ROC list.
`up_verified.sh` catches this by rejecting any log containing `FAILED`; a
hand-driven `mmts_bringup.sh` does not, which is why 1.3 makes you read the
ROC list first. The same address missing every time is 12.3's silent chip:
reseat, and suspect the board if it is missing in every slot.

⏳ **Give each step time.** Both look broken partway through.

| step | takes | what it looks like mid-flight, which is not failure |
|---|---|---|
| bring-up | 60 to 90 s | log stops at `Turning on payload power`, and `daq-server` is down with 6000 not listening, because it is killed before being restarted |
| i2c-server | 15 to 30 s | `IOError in mux_setup group (attempt n/5) ... Retrying.` Retries are normal and usually succeed. 5555 is not yet bound |
| a scan or pedestal starting | tens of seconds | it sits at `Initializing i2c sockets` while the ROCs are configured over ZeroMQ. A pause here is the normal case, not a hang |

Conclude nothing until the bring-up log ends in `next:` or `bring-up failed`,
**and** the server log contains `Identify a board with HGCROC Siv3b` or a
traceback. Both logs are truncated on each launch; check the mtime if in doubt.

**Fewer ROCs than expected means run it again.** Two to four attempts is
routine on a healthy bench, and a few `transient I2C error ... retry n/5`
lines are normal. ⚠️ That applies to a *partial* enable with a different chip
missing each time. Repeated `0/N`, the same every attempt, is not the lottery:
switch to `mmts_bringup.sh` and read the error, per 1.3.

---

# 2. Running a board

The routine path: work out which board type you have and read its parameters
off one table, register the serial so the output files under it, and run one
command per slot. 2.4 to 2.7 are that command's stages one at a time, for when
you already hold a verified slot from 1.3 or want to see one step on its own.

## 2.1 Which board do you have

Characters 5 and 6 of the serial are the geometry, which decides everything
below. Character 7 is the ROC revision, which you do not need here; 11.1 says
why.

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
| LD Five (L5) | 4 | `LD-Five` | 3 | none | `initLD-Five-3b` | 7 of 7 |
| LD Left, LD Right (LL, LR) | 5 | `LD-Semi` | 2 | none | `initLD-Left-3b` | 5 of 5 |
| LD Bottom, LD Top (LB, LT) | 6 | `LD-Semi` | 2 | none | `initLD-Bottom-3b` | A 6, B 6, C 5 |
| HD Full (HF) | 7 | `HD-Full` | 6 | **fitted** | `initHD-Full-trophyV3` | 24 of 24 |
| HD Top (HT) | 8 | `HD-Top` | 3 | none | `initHD-Top-trophyV3` | A 9, B 7, C 6 |
| HD Bottom (HB) | 9 | `HD-Bottom` | 4 | not yet seen; start as none | `initHD-Bottom-trophyV3` | not measured |
| HD Semi (HL, HR) | 10 | `HD-Semi` | 2 | not yet seen; start as none | `initHD-Semi-trophyV3` | not measured |

Run configs are `configs/<family>_mux{A,B,C}_ped.yaml`, one per slot. The
trigger set is per slot as well as per type, so never copy one across slots;
11.3 has the measured sets and 11.2 the ROC addresses. On a type you have not
run before, probe with `--board any` and read the printed address list first.

🔑 **The power distribution board column costs the most when misread.** It
decides the power flag on every command, and the scripts spell that flag three
ways; the table at the end of 2.3 lists them. A module with the board fitted
and the flag wrong is never powered, and reads `no ROCs`.

## 2.2 Register the board

Output is grouped by board, so one module's history sits together whichever
slot it was in:

**(the output layout on the lab computer, not a command)**

```
Results/<serial>/Mux<slot>/{delay_scan,pedestal_run}/<UTC timestamp>/
```

The serial comes from `Results/module_ids.json`, a list of `{slot, from, to,
module}` windows in UTC. Run `register_boards.py` the moment the boards are in
and **before** the first bring-up, since a stale entry files a whole campaign
under the previous serial. Re-run it after every swap; on a new bench it
creates the results directory and the registry:

**(on the lab computer)**

```bash
"$MM/register_boards.py" A=320XLF4DQR00332 B=320XLF4DME01621 C=320XLF4DME01744
"$MM/module_of.py" B
```

The last line prints the serial recorded for slot B. A slot left out is
recorded as empty; `--at YYYY-mm-ddTHH:MM:SSZ` backdates a swap. A board with
no window falls back to the flat layout and the plotter prints `module:
UNKNOWN`. Fix the registry rather than passing `-m` on every command.

## 2.3 Run it

One command per slot: bring-up, gate, N pedestals, finder line, hexmaps and a
per-half check, each stage stopping the sequence on failure. LD Full on slot A;
your type's line is at the top of its section:

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Full-3b LD-Full 3 ldfull 5
```

The arguments are the slot, the config family, `--board` name and ROC count
from 2.1, a label that only names the output, and the number of runs. Two
switches go in front:

* **`POWER=`**, empty, says the module has a power distribution board, so the
  `0x27` `EN_Mx` write runs. The default is `--external-power`, right for
  every partial; an LD Full or HD Full is dead without `POWER=`.
* **`SKIP_PROBE=1`** uses the shipped link map. Leave it off only on a type or
  slot whose links are not measured, per 11.3; the probe costs a second
  bring-up.

It refuses to start without a serial in the registry, so 2.2 comes first. It
always begins with its own bring-up, so **use it from a slot you have not
brought up yet**; on a verified slot from 1.3, hand-drive from 2.5, per 2.4.

**What you see.** A `##########` banner per stage, then that stage's output:

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
| bring-up | 60 to 90 s per try, up to 8 tries, so up to ten minutes | `READY`, or `BRINGUP FAILED` with the tail of `~/bu_A.log` |
| gate | 20 to 40 s | the `GATE:` line |
| each pedestal | ~30 s | its row in the CRC table |
| hexmaps | ~10 s per run | `DONE` |

To see inside a bring-up try while it runs:

**(on the lab computer, in a second terminal)**

```bash
ssh kria 'tail -f ~/bu_A.log'
```

The meter tells the same story: 0 A at `Turning off payload power`, about
1.2 A once `Turning on payload power` has passed and `EN_Mx` is written, and
1.9 to 2.0 A while the chips are configured. A bring-up that stays near 0 A
past `Turning on payload power` ends in `0/3 ROCs`, per 12.3.

The same values, as each script spells them. Only `run_slot.sh` and
`up_verified.sh` are on the routine path:

| script | `--board` | ROCs | no power distribution board | `EN_Mx` bit |
|---|---|---|---|---|
| `run_slot.sh` | argument 3 | argument 4 | the default; **`POWER=`**, empty, when fitted | |
| `up_verified.sh`, `mmts_bringup.sh` | `--board` | `EXPECT_ROCS=` | `--external-power` | `--module N` |
| `ped_run.sh` | `PED_BOARD=` | | `PED_EXTPOWER=1` | `PED_MODULE=N` |
| `slot_measure.sh` | `SM_BOARD=` | `SM_EXPECT=` | `SM_EXTPOWER=1` | `SM_MODULE=N` |
| `bench_up.sh` | `--board` | `--expect` | the default; **`--power-board`** when fitted | `--module N` |

---

**The steps one at a time.** 2.4 to 2.7 are what `run_slot.sh` does, as
hand-typed commands, for when you already hold a verified slot from 1.3 or
want to watch one stage. The type sections give the three-line form per slot.
They assume this preamble in every client shell:

**(on the lab computer)**

```bash
source "$MMTS_VENV/bin/activate"
SLOT=A
OUT=$RESULTS_DIR/$(python3 "$MM/module_of.py" "$SLOT")
echo "SCRIPTS=$SCRIPTS KRIA_IP=$KRIA_IP OUT=$OUT"
```

Everything else comes from `~/.bashrc` at 0.5. The `echo` matters: all three
are expanded locally and an empty one does not stop anything. `cd ""` leaves
you where you were, `-i ""` hangs, and `-o ""` writes the run somewhere you
will not find it. If the board is not in the registry `module_of.py` prints
nothing; use `$RESULTS_DIR` directly.

## 2.4 Bring up the slot

🔑 **Skip this if you already have a verified slot** from 1.3, with the full
ROC list and an `[I2C] Board identification` line naming your board type. Go
to 2.5, or the **last two lines** of your type's slot block.

⚠️ **In that case do not use `run_slot.sh` either.** It always starts with its
own `up_verified.sh` and has no flag to skip it. On a bench that brings up
first time that costs a minute; on the bus of 12.4, where you spent several
attempts and a power cycle earning that state, it throws it away and re-rolls
the lottery.

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=<N> \
  ~/up_verified.sh <SLOT> --board <BOARD>"
```

`up_verified.sh` first kills any i2c-server from the previous slot. A bring-up
under a live server reloads the bitstream out from under it and orphans its
Multiplex hold, per 12.1, and on the HD Tops produced a chip that `stopped
responding mid-config`. Only a hand-typed `mmts_bringup.sh` leaves that kill
to you.

Add `--external-power` for a board without a power distribution board, and
`--module N` if `EN_Mx` does not match the slot index, per 1.3.

**What it prints:**

**(expected output, not a command)**

```
bringup try 1 of 8: running (60 to 90 s) ...
bringup try 1: 0/3 ROCs
bringup try 2 of 8: running (60 to 90 s) ...
  i2c-server start 1 of 3: running (about 25 s) ...
READY  bringup=2 i2c=1  [I2C] Board identification: V3 LD Full HB
```

A silent minute after a `running` line is that try in progress; eight tries is
ten minutes. `READY` means the ROC count matched `EXPECT_ROCS`, nothing said
`FAILED`, the board identified, and 5555 and 6000 listen. The identification
must name your board type. To see inside a try:

**(on the lab computer, in a second terminal)**

```bash
ssh kria 'tail -f ~/bu_<SLOT>.log'
```

The meter: 0 A at `Turning off payload power`, the idle draw of 1.0 once
`Turning on payload power` has passed, the configured draw during a run.

`FAILED to bring slot <SLOT> up cleanly` means read `~/bu_<SLOT>.log` first. A
different chip missing each time is the lottery: run again, back to back, per
1.4. Eight identical `0/N` tries are a fault, per 1.3, and the meter says
which: 0.05 to 0.1 A in CV past `Turning on payload power` is an unpowered
module, not a bad bus.

## 2.5 Delay scan and the gate

Always before a pedestal, never after.

**(on the lab computer)**

```bash
"$MM/delay_scan.sh" <SLOT> configs/<FAMILY>_mux<SLOT>_ped.yaml
```

`<FAMILY>` is the config family from 2.1. For an LD Full on slot A, with the
pedestal of 2.6 after it, this is the pair to type on a slot you brought up by
hand:

**(on the lab computer)**

```bash
"$MM/delay_scan.sh" A configs/initLD-Full-3b_muxA_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

Every other type has the same pair per slot in its own section. Never carry a
config onto another type or slot: the trigger set is per slot.

`delay_scan.sh` restarts the puller, scans and prints the gate. It prints a
header line, `scanning, 20 to 40 s` with the path of its log,
`Mux<SLOT>/delay_scan.log`, and then the gate. The long form shows the
client's log as it goes:

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

In the long form the client's log ends healthy with `status after start cmd :
running`. One `returned status (from initialize) = b'error'` followed by
`initialized`, or one `configure` answering `error`, is the client retrying;
whether it mattered is in `daq-server`'s log.

**The gate must PASS before a pedestal.** A failure is a retry, not a result:
re-run bring-up, which restarts `daq-server`, then scan again. A missed claim
or a link dropped at init happens about once a session and the retry works.
On an HD Top the first gate read `link4=0` on DAQ and `link5=0` on trigger,
and the same bring-up run again gave full marks.

Trigger 0 across the board with DAQ fine means this slot does not hold the
trigger claim. Restart `daq-server` and scan this slot first, per 1.1.

**`no summary.json -- the scan did not produce output`** or **`STALE: newest
summary is ... written N s before this scan started`** means `daq-server`
delivered nothing. The gate refuses to report an older scan, and
`delay_scan.sh` prints the last lines of its own log and of `~/daq-server.log`
on the Kria under the verdict:

**(expected output of a failure, not a command)**

```
no summary.json -- the scan did not produce output
  last lines of the scan's log, .../MuxA/delay_scan.log:
    INFO : ... (daqController) : returned status (from configure) = error
  last lines of ~/daq-server.log on the Kria:
    ERROR - Device ID , "TOP_A", does not exist in connection map
    impossible to process configure when state is Error
```

`Device ID , "TOP_<SLOT>", does not exist in connection map` is the stock
`connections.xml`: B4 skipped, or a firmware install put it back. `Permission
denied` on a uio device is B7. Either way the server is in state `Error` until
it restarts, which the next bring-up does. A scan that times out after 180 s
with nothing in either log is `KRIA_IP` or the firewall, per 0.5 and B6.

🛑 A full-marks delay scan is **not** a health gate on its own. Idle is the
easiest pattern to sample. The real check is an actual START plus the offset
finder's header positions.

## 2.6 Pedestal

Restart the puller first; the `daq-client` from the delay scan is not
reusable.

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
PYTHONPATH=$PWD/analysis \
  python3 pedestal_run.py -d Mux<SLOT> -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/<FAMILY>_mux<SLOT>_ped.yaml
```

`-I` is **required**. Without it `daq-server` never leaves `created`.

Or N runs in a row, each on a fresh puller, scored by CRC in one table:

**(on the lab computer)**

```bash
PED_BOARD=<BOARD> "$MM/ped_run.sh" <SLOT> 5 <label> 10000
```

For an LD Full on slot A. `<label>` only names the output; `5` is the number
of runs and `10000` the events per run:

**(on the lab computer)**

```bash
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

Other types differ in `PED_BOARD`, and the partials add `PED_EXTPOWER=1`; each
type's section has the line per slot.

It runs on the slot as it stands, **no bring-up and no gate**, so 2.4 and 2.5
come first. `PED_BRINGUP=1` adds a bring-up before every run, and only then do
`PED_BOARD`, `PED_EXTPOWER=1` and `PED_MODULE=N` apply. Each run prints one
row, about 30 s apart. `RUN-FAILED (rc=124)` is the 240 s timeout; with an
empty run directory it means the client hung at initialize, per 12.3.

Keep `method: 'automatic'`. It sets **per-link** `fifo_latency`; manual
applies one shared value and can only fix a subset. The exception is a slot
with no good lane at all, where you pin `fifo_latency` and `L1A_offset_or_BX`
by hand, which is a symptom of broken links.

About 30 s per run is healthy. Minutes means the finder is retrying per link,
which says the links are marginal.

## 2.7 Hexmaps and common mode

Unpacking and analysis run automatically as long as the install's `bin` is on
`PATH`. A good run writes its own `.root` and nine PNGs; no `crash_report.log`
means it worked.

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" <run-dir> -l <label> --clip 5
python3 "$MM/cm_analysis.py" "$OUT/Mux<SLOT>/pedestal_run/run_*"
```

For the LD Full slot A runs of 2.6, a shell glob covers the set:

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" "$OUT"/MuxA/pedestal_run/run_* -l ldfull --clip 5
python3 "$MM/cm_analysis.py" "$OUT/MuxA/pedestal_run/run_*"
```

🔑 **Neither takes a board type.** `hexmap_robust.py` reads geometry and
channel map from characters 5 and 6 of the serial, and forcing `-t` is how you
get a partial plotted on the full geometry. These two lines are the only ones
in sections 2 to 10 that do not change with the board.

Read the printed `module:` and mapping lines every time. The repository ships
dated maps and an explicit `_BAD.csv`, and the wrong one silently relocates
almost every channel.

Report **both** `adc_stdd` and `adc_iqr/1.349`, and trust the robust one.
`adc_stdd` is inflated by packet corruption, and `adc_mean` is not yet
reproducible run to run.

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
| `in_inv_cmd_rx` | **1**, on v3D boards too; the shipped configs carry it |
| `EdgeSel_T1` | per slot, in the shipped configs: A 0, B 1, C 0 |
| draw at 1.72 V | ~1.2 A enabled and idle, 1.9 to 2.0 A with three chips configured |

Measured 2026-09-02, three LD Fulls, 10 runs each through `run_slot.sh` with
`SKIP_PROBE=1`: 30 of 30 runs at CRC 1.000 on all six halves, `badBX` 0.000,
finder header positions 23 everywhere. Bring-up took one try on A, two on B
and C.

⚠️ **The power flag.** The `0x27` `EN_Mx` write powers the module and
`--external-power` skips it. With `bench_up.sh` the same choice is spelled
`--power-board`, per 1.3.

⚠️ **`in_inv_cmd_rx` stays 1 on an LD Full, whatever character 7 says.** 0 on
the revision rule of 11.1 gave 0 of 12 trigger with healthy DAQ on all three
slots. Read the applied value from the run's `initial_full_config.yaml`, and
never edit a config while a scan is in flight.

🔑 **`EdgeSel_T1` is per slot.** Slot B at edge 0 produced a zero-byte run.
The shipped configs carry the right edge; check `header positions` in
`daq-server.log` first, every link at 23 is right.

One command per slot. It begins with its own bring-up, so **use it from a slot
you have not brought up yet**; on a verified slot from 1.3, type only the last
two lines of 3.1, per 2.4:

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Full-3b LD-Full 3 ldfull 5
```

2.3 walks through what it prints; that walkthrough is this type on slot A.

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

# 4. LD Five (L5)

| | |
|---|---|
| `--board` | `LD-Five` |
| ROCs | 3, at `0x48 0x58 0x68` |
| power distribution board | none, so `--external-power` |
| DAQ links | 5, links `0 1 4 5 9` on every slot, idcodes `0 1 36 37 72` |
| trigger links | 10 of 12 live; the shipped configs keep two per slot: A `0 4`, B `1 4`, C `1 6` |
| halves in the pedestal output | five |
| delay scan gate | 5/5 and 2/2 |
| run configs | `configs/initLD-Five-3b_mux{A,B,C}_ped.yaml` |
| `EdgeSel_T1` | per slot, in the shipped configs: A 1, B 1, C 0 |
| entries per 10 000-event run | 1 956 240 |

🔑 **A 2-of-3 enable with `0x58` missing is a known bad-board signature**, not
a bench problem. `enableROCs.py` exits 1 on an incomplete set; trust it.

🔑 **A stall at 64 events behind a clean gate and a perfect finder line is a
wrong `idcode`, not a link fault.** An `idcode` names the chip and half a link
carries; `77` on `link9` claimed a fourth chip on a three-chip board and
`daq-server` halted eleven events after that link stopped. The shipped
configs carry the right codes; before spending a bring-up on a stall, unpack
the kept `.raw` per 11.5 and read the chip ids.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Five-3b LD-Five 3 ldfive 5
```

## 4.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --external-power --board LD-Five"
"$MM/delay_scan.sh" A configs/initLD-Five-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" A 5 ldfive 10000
```

## 4.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --external-power --board LD-Five"
"$MM/delay_scan.sh" B configs/initLD-Five-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" B 5 ldfive 10000
```

## 4.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --external-power --board LD-Five"
"$MM/delay_scan.sh" C configs/initLD-Five-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" C 5 ldfive 10000
```

---

# 5. LD Left and LD Right (LL, LR)

| | |
|---|---|
| `--board` | `LD-Semi` |
| ROCs | 2, at `0x48 0x58` |
| power distribution board | none, so `--external-power` |
| DAQ links | 3, links `0 1 4`, idcodes `0 1 36` |
| trigger links | 6 live: `0 1 2 3 5 6` on A and B, `0 1 2 4 5 11` on C; the shipped configs keep two per slot: A `5 6`, B `0 3`, C `1 4` |
| halves in the pedestal output | three |
| delay scan gate | 3/3 and 2/2 |
| run configs | `configs/initLD-Left-3b_mux{A,B,C}_ped.yaml` |
| `EdgeSel_T1` | per slot, in the shipped configs: A 1, B 1, C 0 |
| entries per 10 000-event run | 1 173 744 |

Both geometries use the `LD-Left` config family. Three bonded halves give one
DAQ and two trigger links each, so six trigger links are live; the config
lists two, and the gate counts what the config lists. Measured 2026-09-02 on
three LD Lefts: every slot passed first time once the probe was taken out of
the bring-up, per 11.3.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Left-3b LD-Semi 2 ldleft 5
```

The `bench_up.sh` cold start of 1.3 in its partial form. Every LD partial takes
this line, so section 6 uses it unchanged. No `--power-board`:

**(on the lab computer, when driving a cold start by hand, not in a normal run)**

```bash
"$MM/bench_up.sh" A --board LD-Semi --expect 2
```

## 5.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
"$MM/delay_scan.sh" A configs/initLD-Left-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 ldleft 10000
```

## 5.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
"$MM/delay_scan.sh" B configs/initLD-Left-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 ldleft 10000
```

## 5.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
"$MM/delay_scan.sh" C configs/initLD-Left-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 ldleft 10000
```

---

# 6. LD Bottom and LD Top (LB, LT)

| | |
|---|---|
| `--board` | `LD-Semi` |
| ROCs | 2, at `0x48 0x58` |
| power distribution board | none, so `--external-power` |
| DAQ links | 3, links `0 1 4`, idcodes `0 1 36` |
| trigger links | **3** on an LD Bottom: A `1 2 6`, B `1 2 5`; C carries two, `1 5` |
| halves in the pedestal output | three |
| delay scan gate | 3/3 and 3/3 on A and B; 3/3 and 2/2 on C |
| run configs | `configs/initLD-Bottom-3b_mux{A,B,C}_ped.yaml` |
| `EdgeSel_T1` | per slot, in the shipped configs: A 1, B 1, C 0 |
| entries per 10 000-event run | 1 173 744 |

🔑 **An LD Bottom drives THREE trigger links, not six. That is the board type,
not a fault.** Measured 2026-09-02 on three LD Bottoms, ten runs each: gate
PASS, CRC 1.000 on all three halves, finder at 23 everywhere. Slot C's `link2`
gated `ngood 0` and was dropped from that slot's config.

⚠️ A pedestal does not test the link count. `randomL1A` barely exercises the
trigger path. Use a TPG run for that.

An **LD Top** has the same two ROCs and electrical setup, but its link map is
not measured. Probe one with `run_slot.sh` and no `SKIP_PROBE=1`, per 11.3,
before trusting the LD Bottom map on it.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Bottom-3b LD-Semi 2 ldbottom 5
```

## 6.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
"$MM/delay_scan.sh" A configs/initLD-Bottom-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 ldbottom 10000
```

## 6.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
"$MM/delay_scan.sh" B configs/initLD-Bottom-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 ldbottom 10000
```

## 6.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
"$MM/delay_scan.sh" C configs/initLD-Bottom-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 ldbottom 10000
```

---

# 7. HD Full (HF)

| | |
|---|---|
| `--board` | `HD-Full` |
| ROCs | **6**, at `0x08 0x18 0x28 0x48 0x58 0x68` |
| power distribution board | **fitted**, so no `--external-power` |
| DAQ links | 12 |
| trigger links | 12, so **24 e-links**, double an LD Full |
| halves in the pedestal output | twelve, not six |
| run configs | `configs/initHD-Full-trophyV3_mux{A,B,C}_ped.yaml` |
| draw, all chips running | **4.43 A at 1.72 V** |

⚠️ **Check the supply first, per 1.0.** Six chips draw more than one channel
of a 3.2 A bench supply. At the limit the rail sags to 1.35 V and all 24
e-links die.

⚠️ **A partial enable is not success.** Require `EXPECT_ROCS=6` **and** no
`FAILED` in the log.

🔑 **If some trigger links will not align, drop *those* links and keep the
rest.** Do **not** set `elinks_trg: []`: with no trigger links `daq-server`
starts and hangs forever. Eight good trigger links are ample.

**Expected on a healthy HD Full:**

| | |
|---|---|
| DAQ links | 12/12, `wmax` 42-92 |
| CRC pass | **1.000 on all 12 halves**, `badBX` 0.000 |
| entries per 10 000-event run | 4 694 976 |
| `adc_stdd` median | ~1.24 |

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initHD-Full-trophyV3 HD-Full 6 hdfull 5
```

## 7.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh A --board HD-Full"
"$MM/delay_scan.sh" A configs/initHD-Full-trophyV3_muxA_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" A 5 hdfull 10000
```

## 7.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh B --board HD-Full"
"$MM/delay_scan.sh" B configs/initHD-Full-trophyV3_muxB_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" B 5 hdfull 10000
```

## 7.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh C --board HD-Full"
"$MM/delay_scan.sh" C configs/initHD-Full-trophyV3_muxC_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" C 5 hdfull 10000
```

---

# 8. HD Top (HT)

| | |
|---|---|
| `--board` | `HD-Top` |
| ROCs | 3, at `0x18 0x58 0x28` |
| power distribution board | **none** on every HD Top run so far, so `--external-power` |
| DAQ links | 5, links `0 1 4 5 9` on every slot |
| trigger links | per slot: A `0 1 5 9`, B `0 1`, C `0` |
| halves in the pedestal output | five |
| delay scan gate | A 5/5 and 4/4, B 5/5 and 2/2, C 5/5 and 1/1 |
| run configs | `configs/initHD-Top-trophyV3_mux{A,B,C}_ped.yaml` |
| draw, all chips running | ~2.1 A at 1.72 V; 0.4 to 0.5 A per channel with the ROCs idle |

Measured 2026-09-03, three HD Tops, 3 and then 10 runs each through
`run_slot.sh` with `SKIP_PROBE=1`: 39 of 39 runs at CRC 1.000 on all five
halves, `badBX` 0.000. Two more sets by hand later that day gave the same.

⚠️ **The power flag.** Without `--external-power` the bring-up writes `EN_Mx`
on the `0x27` power board, which is not in the loop on a bench-fed module. The
write fails with `retry 5/5` and a `write_byte` traceback, or the probe reads
`0/3` on all eight attempts, while the supply sits at 0.4 to 0.5 A per
channel. Add the flag; one recover-form bring-up clears it without a power
cycle:

**(on the lab computer)**

```bash
ssh kria "pkill -f '[z]mq_server'; sleep 2; cd ~/multimodule && \
  ./mmts_bringup.sh A --recover --external-power --board HD-Top"
```

⚠️ **HD trophies swap four P/N pairs per module.** A dead set of trigger links
wants `polarity: 0` per e-link in the yaml, not a different bitstream and not
`in_inv_cmd_rx`. The shipped configs carry the measured sets, per slot; never
copy a trigger map across slots. DAQ is the same five links everywhere.

🔑 **`EdgeSel_T1` is per slot:** 1 on A and B, 0 on C, in the shipped configs.
At the wrong edge one half rails at `adc_mean` ~709 with CRC 0.000 while the
other four look perfect. Check `header positions` in `daq-server.log` first;
every link at 23 is right.

One command per slot. `--external-power` is the default, so no `POWER=`:

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initHD-Top-trophyV3 HD-Top 3 hdtop 5
```

Hand-driven, the previous slot's i2c-server must be dead before the bring-up
starts. A stale server holding the bus produced a chip that `stopped
responding mid-config` and a 2 of 3 enable. `up_verified.sh` kills it; a
hand-typed `mmts_bringup.sh` needs the `pkill` above.

## 8.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --external-power --board HD-Top"
"$MM/delay_scan.sh" A configs/initHD-Top-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" A 5 hdtop 10000
```

## 8.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --external-power --board HD-Top"
"$MM/delay_scan.sh" B configs/initHD-Top-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" B 5 hdtop 10000
```

## 8.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --external-power --board HD-Top"
"$MM/delay_scan.sh" C configs/initHD-Top-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" C 5 hdtop 10000
```

## 8.4 Expected on a healthy HD Top

Per run of 10 000 events:

| | |
|---|---|
| entries | 1 956 240 |
| CRC pass | 1.000 on all five halves, `badBX` 0.000 |
| `adc_mean` per half | 85 to 120 |
| total noise, median over halves | 1.00 to 1.04 ADC |
| after common-mode subtraction | 0.92 to 0.96 ADC |
| common mode | 15 to 18 % of the variance |
| time per run | ~30 s |

The common-mode share is a bench number, not a board number. A bare hexaboard
flat on a metal plate read 55 to 68 % on the same boards; a spacer under it
brought that to 15 to 18 %.

---

# 9. HD Bottom (HB)

| | |
|---|---|
| `--board` | `HD-Bottom` |
| ROCs | 4, at `0x18 0x58 0x28 0x68` |
| power distribution board | not yet seen; every HD partial so far had none, so start with `--external-power` and read the supply per 1.0 |
| link sets | **not yet measured.** The shipped configs list links `4` to `11` for both DAQ and trigger as a template |
| delay scan gate | not yet measured; probe first, per 11.3 |
| run configs | `configs/initHD-Bottom-trophyV3_mux{A,B,C}_ped.yaml` |

No HD Bottom has been run yet. Section 8's trophy P/N warning and power-flag
paragraph apply: `retry 5/5` at the `0x27` write means the module is
bench-fed. Run `run_slot.sh` without `SKIP_PROBE=1` on the first board so the
live links are written into the configs, then use the blocks below.

## 9.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh A --external-power --board HD-Bottom"
"$MM/delay_scan.sh" A configs/initHD-Bottom-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" A 5 hdbottom 10000
```

## 9.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh B --external-power --board HD-Bottom"
"$MM/delay_scan.sh" B configs/initHD-Bottom-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" B 5 hdbottom 10000
```

## 9.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh C --external-power --board HD-Bottom"
"$MM/delay_scan.sh" C configs/initHD-Bottom-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" C 5 hdbottom 10000
```

---

# 10. HD Semi (HL, HR)

| | |
|---|---|
| `--board` | `HD-Semi` |
| ROCs | 2, at `0x08 0x18` |
| power distribution board | not yet seen; every HD partial so far had none, so start with `--external-power` and read the supply per 1.0 |
| link sets | **not yet measured.** The shipped configs list links `0 1 4 5` for both DAQ and trigger as a template |
| delay scan gate | not yet measured; probe first, per 11.3 |
| run configs | `configs/initHD-Semi-trophyV3_mux{A,B,C}_ped.yaml` |

No HD Semi has been run yet. Section 8's trophy P/N warning and power-flag
paragraph apply. Run `run_slot.sh` without `SKIP_PROBE=1` on the first board
so the live links are written into the configs, then use the blocks below.

## 10.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board HD-Semi"
"$MM/delay_scan.sh" A configs/initHD-Semi-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" A 5 hdsemi 10000
```

## 10.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board HD-Semi"
"$MM/delay_scan.sh" B configs/initHD-Semi-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" B 5 hdsemi 10000
```

## 10.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board HD-Semi"
"$MM/delay_scan.sh" C configs/initHD-Semi-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" C 5 hdsemi 10000
```

---

# Route B: set up a Kria by hand

Steps B1 to B8 build what the Route A image contains. Take them in order on a
Kria with only the stock hexacontroller image, or one at a time on a Route A
Kria that failed the matching check in 0.9.

## B1. Base image

Flash the standard HGCAL hexacontroller image. It provides the `daq` user,
`fw-loader`, `kconn_pwr`, and the I2C device nodes. Confirm:

**(on the lab computer)**

```bash
ssh kria 'command -v fw-loader kconn_pwr; id daq'
```

## B2. hexactrl-sw under `/opt`

The Kria needs the **server** side of the same branch, built for aarch64 on
the Kria itself, which already has `gcc`, `cmake`, `boost-devel` and uHAL
under `/opt/cactus`. `-DBUILD_CLIENT` is **omitted on purpose**: OFF gives
`daq-server` and `zmq_i2c`. `BRANCH_NAME` must still be passed, since the
copied tree has no `.git`.

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

Four cores, so expect it to take much longer than the client build. `sudo
make install` is outside the passwordless rule of 0.3, so run it from a login
shell.

🔑 **Build the same commit on the Kria and the client.** The branch carries
the `fifo_latency` mask fix, rebuilding `HwInterface` when `uhal_device`
changes, skipping a trigger elink whose chip has no DAQ elink, and the offset
finder skipping unreachable links instead of refusing the slot.

Any Kria shell that runs `daq-server` or the link diagnostics needs the
environment first. Bring-up and `zmq_server` do not.

**(on the Kria)**

```bash
source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
```

## B3. Firmware

The design is `multimodule-hd-tester-trophy-v3`, an RPM under
`/opt/cms-hgcal-firmware/hgc-test-systems/`. The Kria needs internet and a
repository file.

⚠️ **The firmware is not in the repo the image ships with.** The stock
`CERN-REPO-hgcwebsw.repo` (id `hgcal-daq-sw`) is the `hexactrl-sw` software
repo and carries no firmware, so `dnf` answers `No match for argument` for
every release. Add the firmware repo yourself:

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

Then install or update, **always by the full `name-version-release`**:

**(on the Kria)**

```bash
sudo dnf update multimodule-hd-tester-trophy-v3-feature_multiplexer_board_v2-2026_09_01_16_56_41.49751f37
rpm -q multimodule-hd-tester-trophy-v3
```

`update` when an older build is installed, `install` on a Kria that has none.
Take the newest `feature_multiplexer_board_v2` release once newer ones
appear; `sudo dnf list --available multimodule-hd-tester-trophy-v3` shows
them.

⚠️ **Never type the package name bare, and never run an unqualified `dnf
update`.** The version string is the *branch* name, so every branch publishes
the same package name and rpm's compare picks the alphabetically largest,
`test_merge_everything`, a 2025 build with no equalization.

🔑 **The release must be `2026_09_01_16_56_41.49751f37` or later**, the build
carrying the DAQ RX equalization of B5. It decides whether four of the six
DAQ e-links work at all.

⚠️ `sudo dnf` is not in the passwordless rule. Run it from a login shell.

⚠️ **The RPM overwrites `uHAL_xml/connections.xml`**, the file you edit in
B4. Re-apply that edit after every firmware install, otherwise every slot
fails. The per-slot `fw_block_addresses_{A,B,C}.xml` survive.

Then load it:

**(on the lab computer)**

```bash
ssh kria 'sudo fw-loader list'
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
```

`fw-loader load` takes a name under the base directory or an absolute path,
and the directory basename must match its dtbo. A freshly booted Kria has no
bitstream, and bring-up then dies at `[pwr]` with `[Errno 2] ...
'/dev/i2c-2'`.

## B4. `connections.xml` needs `TOP_A`, `TOP_B`, `TOP_C`

**Required, and none of it is shipped.** A fresh install has one address
table, `fw_block_addresses.xml`, with the three trigger blocks named per slot,
and a `connections.xml` defining `TOP` alone. `daq-server` addresses one slot
at a time through the generic names `bram_trg` and `link_capture_trg`, so
each slot needs its own table and connection entry.

Make the three tables from the shipped one:

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

The `grep` must report 1 for each file. If it already did, skip to
`connections.xml`. The loop is safe to re-run.

Now `connections.xml`, one entry per slot alongside the stock `TOP`. This
rewrites the file and keeps a `.orig` the first time:

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

The `grep` must print 3.

⚠️ `connections.xml` belongs to the RPM, so **a firmware install puts the
stock file back**. Re-run this block after every install, per B3. The
`fw_block_addresses_{A,B,C}` files survive.

## B5. The equalized bitstream

🔑 **Check the firmware release before trusting a pedestal.** An unequalized
build leaves `IBUF_LOW_PWR` on, and four of the six DAQ e-links then fail
100 % of CRCs while looking healthy on entry counts: halves c0h0, c0h1, c1h0
and c2h1 read exactly 0.000. Equalized against unequalized: CRC pass 0.000 to
1.000 on all three slots, `badBX` 0.10 to 0.000, eye 8 taps to 64.

The equalization sets `IBUF_LOW_PWR FALSE` and `EQUALIZATION EQ_LEVEL4` on
the DAQ inputs, in `designs/multimodule-hd-tester-trophy-v3/xdc/daq_rx_eq.xdc`.
`EQ_LEVEL4` gives 100 % CRC pass on every link; `EQ_LEVEL2` leaves 1 to 4 %
error on two, and `IBUF_LOW_PWR` alone changes nothing. I/O properties only:
no logic, address map, software or routed timing changes.

Install the RPM of B3 and set `MMTS_FW=multimodule-hd-tester-trophy-v3`. The
release string `2026_09_01_16_56_41.49751f37` or later carries it; a copied
build directory carries no such stamp, which is a reason to prefer the RPM.

⚠️ **`MMTS_FW` is not sticky.** `enableROCs.py` re-points `active` on every
run, so a bring-up without it silently reverts to stock. Check after every
bring-up:

**(on the lab computer)**

```bash
ssh kria 'readlink /opt/cms-hgcal-firmware/hgc-test-systems/active; dmesg | grep "fpga0: writing" | tail -1'
```

## B6. Open the three ports

A listening socket is not enough; the packets have to arrive. A stock
AlmaLinux firewall on either machine blocks them, and the symptom is a
**hang**, not a connection error.

| port | listens on | carries |
|---|---|---|
| 5555 | the Kria | the i2c-server, ROC configuration |
| 6000 | the Kria | `daq-server`, run control |
| **8888** | **the Kria** | **the event stream**, which the puller connects out to and pulls |
| 6001 | the lab computer | control of the puller, from `delay_scan.py` on the same machine |

⚠️ **6001 is a local control socket, not the data path.** `delay_scan.py:62`
opens it as `daqController("localhost", pullerPort)`. The events go the other
way: `daq-server` binds **8888** on the Kria and `daq-client` connects out to
it. Opening 6001 on the client is harmless and worth doing, but 8888 on the
Kria is what the event stream needs.

**(on the Kria)**

```bash
sudo firewall-cmd --permanent --add-port=5555/tcp --add-port=6000/tcp --add-port=8888/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

The last line must print `5555/tcp 6000/tcp 8888/tcp`, as the Route A image
already does.

**(on the lab computer)**

```bash
sudo firewall-cmd --permanent --add-port=6001/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

🛑 **That last line must print `6001/tcp`; an empty answer is the failure.** A
stock client runs firewalld with nothing open, and everything in section 0
still passes because the client only dials *out* until the first run. Then
the bring-up is clean, the scan reaches `status after start cmd : running`,
and nothing arrives for 180 s. The gate says `no summary.json`.

Prove reachability from the client rather than trusting `ss` on the Kria:

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

**A refusal is a pass**: until a bring-up has run, nothing listens and a
refusal is the only answer either port can give. Only the timeout is a fault.

🔑 **Then test 8888**, which only listens while `daq-server` is up, so after
a bring-up. Use the `exec` form, **not** `cat`:

**(on the lab computer)**

```bash
timeout 5 bash -c "exec 3<>/dev/tcp/$KRIA_IP/8888"; echo "8888 rc=$?"
```

`rc=0` is a pass, `rc=1` a refusal, `rc=124` a block.

⛔ **Do not test a port with a live server on it with `cat < /dev/tcp/...`.**
`cat` waits for data, so against a quiet listener it burns the full timeout
and reports `rc=124`. The `cat` form is safe for 5555 and 6000 above only
because nothing is listening yet. Use `exec 3<>` whenever a server is up.

With `iptables` or `nft` rather than `firewalld`, open the same ports there.

### One puller at a time

🛑 **A Kria serves exactly one `daq-client`, and a second one anywhere on the
network silently takes half your data.** `daq-server` pushes over a ZeroMQ
PUSH socket, which **round-robins** across every connected puller. The
`START_RUN_DELAY_SCAN` header goes to one and the data to the other, so your
client stays one message out of step for the whole run.

The symptom names nothing: clean bring-up, `no summary.json`, a run directory
holding only `initial_full_config.yaml`, and `~/daq-server.log` ending in a
healthy `STOP`. It is visible only in `$MMTS_ROOT/daq-client.log`:

**(expected output of a failure, not a command)**

```
Error : serialization::archive ... not in dataTypeMap
```

Check who is connected before believing any empty run. It only shows peers
while a run is in flight, so run it during the gate:

**(on the lab computer, during a scan)**

```bash
ssh kria 'ss -tn | grep 8888'
```

Exactly **one** peer, your client. Any other address is a stray `daq-client`
to be stopped on that machine:

**(on the other machine)**

```bash
pkill -f '[d]aq-client'
```

⚠️ **Look for containers too.** Where the client stack runs in Docker,
`pgrep -af daq-client` finds nothing while the container holds the socket.
`lsof -nP -iTCP | grep 8888` names the owner, and `docker ps` finds the
container. A container left up after someone's earlier session is the
likeliest source.

If you take a bench over from another machine, stop its puller first, and
expect the same in reverse.

**(on the lab computer, the full picture in one line)**

```bash
pgrep -af '[d]aq-client'; ssh kria 'pgrep -af "[d]aq-server|[z]mq_server"; ss -tn | grep 8888'
```

One `daq-client` here, one `daq-server` and one `zmq_server` on the Kria, one
peer on 8888. Two `daq-server` processes, or an old `zmq_server` from another
slot, are 12.1.

## B7. Device permissions

Two udev rules, both needed on a stock image. The **gpiochip** rule: the Zynq
PS chips are `root:root` 0600, which makes `gpiofind` abort. The **uio** rule:
`/dev/uio*` at `root:root` 0600 stops `daq-server` opening the firmware's UIO
devices, so it logs `Permission denied`, goes to state `Error`, and rejects
every configure.

**(on the Kria)**

```bash
echo 'SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpiochip-all.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=gpio
echo 'SUBSYSTEM=="uio", KERNEL=="uio*", GROUP="daq", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-uio-daq.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=uio
```

Confirm `daq` is in the `i2c` and `gpio` groups, and log out and back in after
any `usermod`.

## B8. Copy the code to the Kria

The Kria gets `$MM/kria/` and the i2c-server. No git on the Kria.

Two transfers. Everything from `$MM/kria/` goes to `~/multimodule`, the
wrappers included; the i2c-server goes under `~/multimodule/hexactrl-sw`,
from where it is run **and not** from the copy under `/opt`. Since 2026-10-13
the wrappers live in `~/multimodule` too, with symlinks in `~` so the older
`~/up_verified.sh` form still works.

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

The wrappers are files on the Kria on purpose: a `pkill -f` pattern typed
into an ssh one-liner matches that one-liner and kills your session.

| file | what |
|---|---|
| `up_verified.sh SLOT [--external-power] [--board NAME] [--module N]` | kills any i2c-server left from the previous slot, runs `mmts_bringup.sh` up to `BRINGUP_TRIES` times (default 8) and the i2c-server up to 3, announces each try, and reports `READY` only when the ROC count matches `EXPECT_ROCS`, nothing says `FAILED`, the board identified, and ports 5555 and 6000 both listen. `KEEP_PAYLOAD=1` reloads the bitstream per try instead of cycling payload power |
| `start_i2c.sh SLOT` | restart the i2c-server on a slot, detached, and print its identify line; no firmware reload in front of it |
| `start_daq.sh` | (re)start `daq-server` after the i2c-server is up, releasing the trigger claim |
| `set_pwr_en.py SLOT on\|off ...` | drive one slot's payload rail without a bring-up |
| `sgl_ladder.py [N] [--label TEXT]` | per-slot I2C write statistics (fake-ACK check, switch writes, Sgl selects), the first test after a power button |

Re-run the `tar` commands whenever a script changes on the client. `$MM/kria/`
is the source of truth; do not edit the copies on the Kria.

---

# 11. Reference

The material behind the numbers in sections 2 to 10. Come here when a value
looks wrong, a board type is new, or the automatic analysis did not run.

## 11.1 ROC revision and `in_inv_cmd_rx`

Character 7 of the serial is the ROC revision, `C` or `D`.

🔑 **`Top.in_inv_cmd_rx` is carried by each type's shipped config, and the
shipped value is the measured one. Do not change it.** The wrong value leaves
every trigger link at `ngood=0` with DAQ fine, and hexactrl-sw reports every
revision as `Siv3b`, so nothing in software tells you which you have.

The revision rule, v3C gives 1 and v3D gives 0, holds for the LD partials and
the HD boards. **It does not hold for the LD Full**: three v3D LD Fulls gave
12/12 trigger with 1 and 0/12 with 0, on all three slots, on 2026-09-02.

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

⚠️ A ROC register reaches silicon only on the **first** initialize of an
i2c-server's life, so testing a different value needs a **fresh bring-up**,
not a rescan.

## 11.2 ROC addresses per board

`zmq_i2c/Link.py` matches the **exact** address set. A partial with one ROC
silent does not fall back to a smaller board; it fails with `Exception: ROC
addresses [...] do not match a known board`. That message also covers a bad
bring-up, so read the printed address list before concluding the type is
wrong.

| board | ROC addresses |
|---|---|
| V3 LD Full HB | `0x08 0x18 0x28` |
| V3 LD Five HB | `0x48 0x58 0x68` |
| V3 LD Semi or Half HB | `0x48 0x58` |
| V3 HD Semi-left, Semi-right | `0x08 0x18` |
| V3 HD Bottom | `0x18 0x58 0x28 0x68` |
| V3 HD Top | `0x18 0x58 0x28` |
| **V3 HD Full HB** | **`0x08 0x18 0x28 0x48 0x58 0x68`** |

The mux probe list is `[0x08, 0x18, 0x28, 0x48, 0x58, 0x68]`, so discovery
covers all V3 partials but not `0x00/0x20/0x40/0x60`, so ROCv2 LD and NSH
boards would not be found.

## 11.3 Measured link sets and the probe

The DAQ set follows the board type. **The trigger set depends on the slot as
well**, because the mux board's crosspoints reach the trigger pairs in a
per-slot order, so never copy a trigger map across slots. Each slot's shipped
`_ped.yaml` carries its measured set, and on the partials it keeps only a
subset of the live links; the gate counts what the config lists.

| board type | DAQ, every slot | trigger live, A | B | C | in the shipped config |
|---|---|---|---|---|---|
| LD Full | `0 1 4 5 8 9` | all 12 | all 12 | all 12 | all 12 |
| LD Five | `0 1 4 5 9` | 10 of 12 | | | A `0 4`, B `1 4`, C `1 6` |
| LD Left, Right | `0 1 4` | `0 1 2 3 5 6` | `0 1 2 3 5 6` | `0 1 2 4 5 11` | A `5 6`, B `0 3`, C `1 4` |
| LD Bottom | `0 1 4` | `1 2 6` | `1 2 5` | `1 5` | the same |
| HD Full | all 12 | all 12 | all 12 | all 12 | all 12 |
| HD Top | `0 1 4 5 9` | `0 1 5 9` | `0 1` | `0` | the same |
| HD Bottom, HD Semi | not measured | | | | a template |

For a type or slot not in this table, measure the live links first. Run
`run_slot.sh` **without** `SKIP_PROBE=1`:

**(on the lab computer)**

```bash
"$MM/run_slot.sh" B initLD-Left-3b LD-Semi 2 probe 3
```

It derives a twelve-link probe from that slot's `_ped.yaml`, delay-scans with
it, writes the live set back into the config, and re-does the bring-up before
any pedestal. That last step is required: the probe arms all twelve capture
blocks and `LinkAligner` never clears `invert`, so a pedestal in the same
bring-up stalls at 64 events.

## 11.4 Trophies

Trophies are shared across geometries. LB shares with LR and with LT. A
mismatch between the trophy's type code and the module's is **not** evidence
of a wrong trophy.

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

A good LD Full run gives a `.root` of about 5 MB, `unpacker_data/hgcroc` with
2 347 488 entries, `runsummary/summary` with 234 rows, and nine PNGs. A
partial legitimately produces fewer; compute the expected row count from the
board's own chip and channel complement.

## 11.6 Slot quirks, and what a good result looks like

These follow the slot, not the module.

- **Only one slot carries trigger at a time**, the first slot `daq-server`
  scanned since it last started. Restart `daq-server` and scan the slot you
  want first. See 1.1.
- **Slot C: sub-bus 7 hangs the bus** if selected. It is no longer probed; do
  not add it back.
- **Slot C: the trigger link set differs from A and B** on the same board
  type, `0 1 2 4 5 11` rather than `0 1 2 3 5 6` on an LD Left or Right.
  Slot A's or B's config on slot C gives a FAIL that is a config error. See
  11.3.
- **Slot C: keep `L1A_offset_or_BX: 13`** with `method: 'automatic'`, measured
  on an LD Full. Do not "correct" it to 14 even though the finder writes 14;
  20 decodes nothing. Automatic beat manual 36 of 36 against 18 of 36, because
  manual 13 and 14 fix complementary halves while automatic gets all six.

Ten pedestals on a healthy LD Full slot give 60 of 60 half-ROCs below
corruption 1.0, robust σ **0.741 ADC**, a full gate on the first try, and
30 s per run. That is the yardstick for any slot.

---

# 12. Common mistakes

## 12.1 Never do these

| never | why, and what it costs |
|---|---|
| **Run the ZL30274 clock step** (`i2cset -y 0 0x70 1` plus `zl30274_configurator.py`) | It wrecks the PL I2C master. The chip sits on the Kria's PS I2C rail, so no `kconn_pwr` cycle reaches it. Recovery is a mains power cycle. Any multiplexer documentation telling you to run it is an outdated snapshot |
| **`i2cdetect -y 2`, or any `--readback`** | Reads wedge this I2C master, and even a read of a device that is present sometimes does it |
| **Hammer a non-responding ROC** | Same wedge, reached faster |
| **Re-run bring-up while `zmq_server` is running** | It reloads the bitstream, renumbers the gpiochips, and silently orphans the Multiplex hold. You get six dead DAQ links and twelve good trigger links. `up_verified.sh` kills the server first; a hand-typed `mmts_bringup.sh` needs `pkill -f '[z]mq_server'` in front of it |
| **`systemctl start zmq-server@X` or `daq-server.service`** | Those run the RPM copies, which have none of the bench fixes. Start both by hand |
| **Go straight to a pedestal** | See 1.1. A pedestal on an unaligned slot is a 240 s timeout per run and can take `daq-server` and the puller down |
| **Reuse a `daq-client` between runs** | One that saw a failed START silently produces data that decodes to nothing. Restart it per run |
| **Drop `-I`** | `daq-server` never leaves `created` and the client spins forever |

## 12.2 The traps that look like results

1. **`no ROCs` on every slot after a hardware change.** Check the physical
   pieces first: **the loopback**, then the cables you just unplugged, then
   module seating. Nothing in software reports a missing loopback. The data
   cable between the power management board and the mux board is the other
   one: unplugged, `EN_Mx` never reaches the slots.
2. **Healthy total entry counts while every lane is broken.** Entry count is
   the gate, per-half corruption is the metric; neither means anything alone.
3. **`corruption == 0` on a dead half.** A half with `adc_mean = adc_stdd =
   adc_iqr = 0` on every channel is producing well formed packets full of
   zeros. A real pedestal half sits near `adc_mean ≈ 94`.
4. **Low corruption on a low yield run.** A run that decodes 216 of 10 000
   events reports near zero corruption and looks perfect: the `.raw` is full
   size and the unpacker stopped early. Easier to fall into on a partial;
   compute the expected row count from the board's chip and channel
   complement.
5. **A stale identify line.** After the first `initialize` in a server
   process, the ROC type read frequently returns `[0, 253, 104]` instead of
   `[0, 125, 104]`. The process stays alive and 5555 stays listening, while
   every `initialize` returns `error:` and the ROCs keep stale config. Confirm
   `Identify a board with HGCROC` is the **last** identify line in the log.
   Recovery is a fresh bring-up; restarting `zmq_server` alone does not clear
   it.
6. **Config applied only on the first `initialize`.** Later runs report
   numbers for settings that were never applied. Always read the register
   back.

## 12.3 Symptom to action

| symptom | do |
|---|---|
| Everything returns `[Errno 5]`, switches do not ACK | Bring-up in the recover form. Expect to run it twice |
| `findslot.py` prints `mux GPIO write failed ([Errno 5] ...)` or `bus wedged during probe` | Not the same as `no ROCs`: the master answered, not the module. Cold start in the order of 1.2 and probe once more. If it survives that, it is the wedge of 12.4 |
| `KeyError: 'dac_hyst_toa'` | ROC type mis-detected and fell back to Siv3. Redo bring-up plus i2c-server |
| Client hangs at `ROC(s) CONFIGURED` | `daq-server` is dead or stuck in a previous unfinished run. Restart it |
| A scan sits at `Initializing i2c sockets` and never proceeds | Nothing is listening on 5555. `mmts_bringup.sh` does not start the i2c-server; run `~/start_i2c.sh SLOT`. Section 1.3 |
| Same hang, but `ss` on the Kria shows 5555 **and** 6000 listening and the identify line is good | The client cannot reach them. `echo "KRIA_IP=$KRIA_IP"` first: `192.0.2.7` is the unedited placeholder of 0.5 and routes nowhere. If the address is right, it is the firewall, per B6 |
| `status after start cmd : configured`, repeating | **Interrupt at once.** An e-link is unaligned and `start()` retries forever; the backlog can crash the puller and `daq-server`. Read `~/daq-server.log` for which link, then re-run bring-up |
| `status after start cmd : created`, repeating | You dropped `-I` |
| 6 DAQ links dead, 12 trigger fine | Multiplex hold lost. `gpiofind Multiplex_A` and `ps aux \| grep "[g]pioset"`; the chip numbers must match |
| 0 of 12 trigger, DAQ fine | The trigger claim is on another slot. Restart `daq-server` and scan this slot first |
| All 12 trigger links `ngood=0`, DAQ perfect | Wrong `in_inv_cmd_rx` for the ROC revision. v3C is 1, v3D is 0 |
| `.raw` unpacks to 0 entries | Stale puller. Restart `daq-client` |
| `unpack: command not found` in `pedestal_run0.log` | The install's `bin` was not on `PATH` in the shell that launched the run. Section 0.6a |
| `python3: can't open file '.../delay_scan.py'`, naming a directory you did not choose | `SCRIPTS` is unset, and `cd ""` is a silent no-op that left you where you were. `echo "SCRIPTS=$SCRIPTS"`, then section 0.5 |
| `register_boards.py` gives `FileNotFoundError` or `JSONDecodeError: Expecting value` on `module_ids.json` | An older copy of the scripts. The current one creates the registry itself; `git pull --ff-only` and `git submodule update --init --recursive` in `hexactrl-sw`, section 0.4 |
| `ModuleNotFoundError: No module named 'zmq'` | The venv is not active, is shadowed by conda, or never got its packages. `which python3` must be `$MMTS_ROOT/venv/bin/python3`; if it is, re-run the `pip install` of 0.6b |
| Environment variables you just set are gone again | You set them in a subshell and typed `exit`, which discarded them. Put the three exports in `~/.bashrc`, per 0.5 |
| `source .../ROCv3-alper-dev/etc/env.sh` gives `No such file or directory` on the client | Correct behavior: `env.sh` is installed only by the server build. Set `PATH` instead. Section 0.6a |
| cmake says `/hexactrl-script/analysis does not contain a CMakeLists.txt`, then `make` says `No targets specified` | The nested submodules were never fetched. `git submodule update --init --recursive` in `hexactrl-sw`. Section 0.4 |
| cmake reports `Found PythonInterp: .../miniforge3/bin/python3` | A conda environment is active. `conda deactivate`, delete the build directory, configure again. Section 0.6a |
| `make` fails on `yaml-cpp/yaml.h` or `zmq.hpp: No such file or directory` | `yaml-cpp-devel` and `cppzmq-devel` are missing. cmake never checks for them, so this only shows up in `make`. Section 0.6a |
| `$MM/puller.sh: No such file or directory`, and no `multimodule/` at all | The submodules were never fetched, or the clone predates the merge of the scripts upstream. `git pull --ff-only` then `git submodule update --init --recursive` in `hexactrl-sw`. Section 0.4 |
| `dnf` answers `No matching Packages to list` for the firmware, and `dnf repolist` shows `HCGAL-DAQ-SW` alone | The `hgc-online-sw` repo file was never written. Section B3 |
| `ZMQError: Address already in use` on 5555 | `ssh kria 'pkill -f "[z]mq_ser""ver.py"'` |
| `daq-client` cannot bind 6001 | An old one is still alive. `pkill -f '[d]aq-client'` |
| The gate says `no summary.json`, the run directory holds only `initial_full_config.yaml`, and `~/daq-server.log` ends in a healthy `STOP` | A second puller somewhere on the network is taking half the stream. `ssh kria 'ss -tn \| grep 8888'` during a scan must show exactly one peer, your client. Section B6, "One puller at a time" |
| `Error : serialization::archive ... not in dataTypeMap` in `$MMTS_ROOT/daq-client.log`, followed by pages of misparsed `link_capture_daq.link0` | The same thing: the run header went to the other puller, so this one read a data archive as the header. Not a version mismatch, and not worth rebuilding anything over |
| A port test gives `rc=124` on a port that `ss` shows listening | The test, not the port. `cat < /dev/tcp/...` waits for data and always times out against a quiet server. Use `timeout 5 bash -c "exec 3<>/dev/tcp/HOST/PORT"`. Section B6 |
| The scan reaches `status after start cmd : running` and then nothing for minutes, and the gate says `no summary.json` | The event stream is not getting back to the client. `sudo firewall-cmd --list-ports` **on the lab computer**: an empty answer means 6001 was never opened, section B6. Everything else passes without it, since the client only dials out until the first run |
| Orphaned holders after a killed server | `pkill -f 'gpioset -m signal -b'` |
| `daq-client` exits with `std::length_error` or signal 6 | It was sent the run twice by a START refusal spin. Full reset: restart `daq-server`, re-run bring-up, restart the puller |
| `elink link_capture_daq.linkN is not aligned` | A DAQ link failed to init, which happens about once a session. Re-run bring-up. `--realign` does not fix it, because the delay block is fine and the word aligner needs the `linkReset` that a full configure issues |
| `gpiofind: Permission denied` | The gpiochip udev rule is missing. Section B7 |
| `daq-server` logs `Permission denied` then `impossible to process configure when state is Error` | The uio udev rule is missing. Section B7. Every configure is rejected until `daq-server` restarts |
| `fw-loader load: error: the following arguments are required: firmware` | A `$MMTS_FW` from an older copy of these instructions expanded to nothing. Name the design outright: `multimodule-hd-tester-trophy-v3`. Section 0.5 |
| `sed: -e expression #1, char 49: extra characters after command`, and the echoed line shows `done` where you typed `!d` | Bash history expansion, not sed. Use the loop as written in B4, which contains no `!` |
| Bring-up dies at `[pwr]` with `[Errno 2] ... '/dev/i2c-2'` | Freshly booted Kria with no bitstream. `fw-loader load` first |
| Repeated `[Errno 13] Permission denied: '/dev/i2c-2'` after many reloads | The overlay reload is re-creating the node slower than udev sets the group, which takes roughly 40 reloads in a day to reach. Reboot the Kria |
| `ROC addresses [...] do not match a known board` | Read the printed address list. It is usually a bad bring-up rather than a wrong board type |
| Bring-up prints `board X needs all N of [...]; ['0x58'] never answered` | One chip is silent while its neighbours on the same I2C sub-bus answer. The bus is fine; that chip's contact, reset or local rail is not. Reseat; if the same address is missing in every slot, the board is the fault |
| `retry 5/5` at the `[pwr] power management board 0x27` line, first bring-up after a power cycle | The power board is not in the loop, so `0x27` cannot ACK. The module is fed directly: use `--external-power`. One `--recover --external-power` bring-up clears the wedge without a power cycle |
| Supply reads 0.4 to 0.5 A on a channel with nothing brought up | Normal: that slot's rail is on and its ROCs are idle. Three configured LD chips draw about 1.9 A, three HD chips about 2.2 A |
| Bring-up repeats `0/N ROCs` and the supply sits in **CV at 0.05 to 0.1 A**, well under the 0.4 A quiescent | The module was never powered. Interrupt `up_verified.sh` rather than let it spend the tries. Check the supply is on at 1.72 V and the data cable from the power distribution board to the mux board is plugged in, since without it `EN_Mx` reaches nothing. Then sweep `--module 1/2/3`, since `EN_Mx` is cabling, and keep the value that makes the meter jump to ~1.2 A; if all three read the same, check the module's flex and seating. A `0x27` that ACKs proves the data path only |
| `daq-server.log` says `Device ID , "TOP_A", does not exist in connection map` then `impossible to process configure when state is Error` | The stock `connections.xml`. Section B4, and again after every firmware install. The bring-up looks clean and the scan runs; only the gate's `no summary.json` gives it away |
| The gate prints `no summary.json -- the scan did not produce output` or `STALE: newest summary is ...` | `daq-server` rejected the scan, or nothing answered. `delay_scan.sh` prints the tails of its own log and of `~/daq-server.log` right under it; act on that line: the connection map row above, the uio rule of B7, or a timeout with empty logs, which is `KRIA_IP` or the firewall. Section 2.5 |
| `bringup try N of 8: running ...` and then a silent minute | Normal. A try is 60 to 90 s and there can be eight. `ssh kria 'tail -f ~/bu_<slot>.log'` to see inside it. Section 2.4 |
| Bring-up enables 2 of N with a different chip missing each time, or `0/N` once and then `READY bringup=2` | The lottery, not a dead ROC. Run it again, back to back: a slot that came up 0 for 5 with a fresh power cycle before each try came up 4 of 10 back to back, and another was `0/3` then `3/3` on the immediate re-run |
| Gate FAIL on a `READY` bring-up, one DAQ or trigger link reading 0 | A link dropped at init, which happens about once a session. Re-run the bring-up; the identical sequence then passes. Do not make a config that drops the link |
| A zero-byte run behind a clean gate | `EdgeSel_T1` at the wrong edge for the slot. Diff the applied `initial_full_config.yaml` in the run directory against the shipped config, whose per-slot values are in the type's table, and check `header positions` in `daq-server.log`: every link at 23 is right |
| Bring-up `3/3` but the i2c-server dies on `could not identify ROC type from readBack [0, 253, 104]` or `OSError: [Errno 5]` on a read, or the client hangs at initialize with an empty run directory and `RUN-FAILED (rc=124)` | Reads on that slot's I2C path have died while writes still work. Not the puller, so do not recreate it. Once the bus has been in use for half an hour or more no number of bring-ups recovers it: ten attempts gave seven `3/3` enables and zero servers. Power-cycle the Kria, run the bring-ups back to back, and take the runs at once with no idle gap. Or use another slot, which came up first try ten minutes before this one failed |
| `mmts_bringup.sh` on a bench-fed module dies at `[roc]` with a chip that `stopped responding mid-config`, right after a clean run on another slot | An i2c-server from the previous slot was still holding the bus. `up_verified.sh` kills it first; a hand-typed `mmts_bringup.sh` needs `pkill -f '[z]mq_server'` in front of it, per 1.3 |

## 12.4 When only the power button will do

- **Retries climb from 1/5 to 5/5 across successive runs, ROCs dropping mid
  config.** The PL I2C master is wedged. `up_verified.sh` retries 8 times per
  call, so count the retries in `~/bu_<slot>.log` rather than the outcome, and
  stop as soon as they are being exhausted. Diagnose with `mmts_bringup.sh`,
  per 1.3. `--recover` does not help once here. `sudo shutdown -h now` plus a
  power button cycle, then run the bring-ups **back to back**: on 2026-09-03 a
  slot that failed on five separate fresh boots came up 4 of 10 in a row, with
  the error count falling every attempt. Afterwards prove the bus on a
  known-good slot before spending another bring-up on the suspect one: `no
  ROCs` on a sick bus says nothing about the module. What does not come back
  this way is a slot whose reads have died while writes work, the `[0, 253,
  104]` row of 12.3.
- **It gets worse every run and `0x71` or `0x73` stops ACKing entirely.** The
  clock synthesizer. `kconn_pwr` cannot reach it. Halt and mains cycle.

Plan the session around this: rest first, then spend the good bring-ups on the
measurement you care about.

🔑 **Start a kernel recorder before chasing one of these, because the stock
image keeps no journal across a reboot.** `journalctl --list-boots` lists boot
`0` alone and answers `no persistent journal was found`, and `/var/log` is not
writable by journald on this image. The home directory survives:

**(on the Kria)**

```bash
setsid bash -c 'dmesg -w >> ~/kernel.log' < /dev/null > /dev/null 2>&1 &
pgrep -af 'dmesg -w'
```

`dmesg -w` follows the kernel ring buffer, where a hang prints. The shell
reports `Done` immediately because `setsid` exits at once; trust `pgrep`. It
does not survive a reboot, so restart it after every power cycle, and read it
with `tail -50 ~/kernel.log`.

⚠️ **The Kria boots with a wrong clock**, `2025-12-04` on this bench until
something sets it. That is a wrong date, not a time zone, so its logs cannot
be lined up against the client's until the clock is set. For that correlation
use a wall clock the client also sees, such as a timestamped `ping` on the
client side.

## 12.5 A few smaller ones

- **`pkill -f "zmq_server.py"` over ssh kills your own ssh command**, because
  the remote `bash -c` line contains that string. Use `pkill -f
  "[z]mq_server.py"`. The same applies to `daq-server` and `daq-client`.
- **Do not leave `daq-server` running after a hand driven probe.** If you call
  `daqController.start()` yourself, call `stop()`, or every later run fails at
  START.
- **The Kria logs in UTC.** So do the run directory names and
  `module_ids.json`. Convert once, where you read a wall clock.
- **Use `MMTS_L1A_LOG2PERIOD=10`.** Never worse than the default and 50 times
  gentler on the ROCs.
- **Never add an `rm -rf` of the results root to `remap_all.sh`.** The runs
  live under `Results/<serial>/`, so `rm -rf Results/320[TX]*` deletes the
  data, not just the plots.

---
