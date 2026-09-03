# MMTS setup and operation, for Module Assembly Centres

Multi-Module Test System: three hexaboards in one hexacontroller, measured one
slot at a time. This document takes you from a bare AlmaLinux client and an
unflashed Kria to pedestals on all three slots.

**Conventions.** `$MMTS_ROOT` is the working directory on the client,
`$KRIA_IP` is the hexacontroller's address, `$SLOT` is `A`, `B` or `C`, and
`$MM` is the scripts directory, `$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule`.
Set them once in section 0.5.

Every code block is labelled with where it is typed: **the lab computer**, which
is the AlmaLinux client, or **the Kria**. A block labelled for the lab computer
may still act on the Kria through `ssh`; that is the normal pattern here, and
only a handful of steps have to be typed on the Kria itself.

---

## Contents

- [0. From a bare AlmaLinux client to a working bench](#0-from-a-bare-almalinux-client-to-a-working-bench)
- [1. Powering up](#1-powering-up)
- [2. Board types: choose your parameters first](#2-board-types-choose-your-parameters-first)
- [3. Slot A](#3-slot-a)
- [4. Slot B](#4-slot-b)
- [5. Slot C](#5-slot-c)
- [6. Common mistakes](#6-common-mistakes)
- [7. Changes](#7-changes)

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

The client drives everything over ssh and over ZeroMQ. It needs GitLab access
only at install time, and the Kria never needs internet access at run time.

## 0.2 Client prerequisites

**(on the lab computer)**

```bash
sudo dnf install -y git python3 python3-pip
```

You also need about 20 GB of free disk for results, and a CERN account with an
ssh key registered at `gitlab.cern.ch` so the two CERN repositories clone.

## 0.3 Passwordless access to the Kria

The wrappers make many short ssh calls per run. Two things make that painless,
and both are worth doing before anything else.

**Key based login.**

**(on the lab computer)**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_kria -C "mmts-client"
ssh-copy-id -i ~/.ssh/id_ed25519_kria.pub daq@<kria-ip>
```

**Connection multiplexing.** Add to `~/.ssh/config`. Listing the raw address in
the `Host` pattern as well as the alias matters, because the scripts call
`ssh daq@<kria-ip>` directly and would otherwise miss these settings.

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

The first connection authenticates, the next hundred reuse it and are instant.
Verify with `ssh kria true` and then `ls ~/.ssh/cm-*`.

**Passwordless `sudo` on the Kria for the two power commands.** Bring-up runs
`sudo kconn_pwr` and `sudo fw-loader` over a non-interactive ssh channel, which
has no terminal to prompt on. Without this the bring-up hangs or fails silently.

This is the one setup step done on the Kria rather than from the client, because
`sudo` needs a real terminal to prompt on the first time. Log in and stay there:

**(on the lab computer, this is what logs you into the Kria)**

```bash
ssh kria
```

Everything in the rest of this block runs on the Kria. First confirm where the
two binaries actually live, since the rule below only matches an exact path:

**(on the Kria)**

```bash
command -v fw-loader kconn_pwr
```

Then write the rule, substituting those paths if they differ. `/etc/sudoers.d/hgc-bench`
does not exist on a fresh Kria, so creating it is expected, not a repair:

**(on the Kria)**

```bash
echo "daq ALL=(root) NOPASSWD: /usr/bin/fw-loader, /usr/bin/kconn_pwr" \
  | sudo tee /etc/sudoers.d/hgc-bench
sudo chmod 440 /etc/sudoers.d/hgc-bench
sudo -n fw-loader list
```

That last line is the only check that matters, and it must print without
prompting. A password prompt means the paths in the rule are wrong or the file is
not mode 440. Log out with `exit` when it passes.

## 0.4 Clone the repositories

Two clones, both on CERN GitLab. The bench scripts, the run configs and the
Kria-side helpers all live inside `hexactrl-script`, so there is no separate
bench repository to fetch.

**Step 1, `hexactrl-sw`.** Branch `ROCv3-alper-dev`, not `ROCv3`. This is the DAQ
software, the `zmq_i2c` server you later copy to the Kria, and, through its
`hexactrl-script` submodule, the bench scripts and run configs. No fork remote
and no branch switching: everything is on the upstream branch.

**(on the lab computer)**

```bash
export MMTS_ROOT=$HOME/mmts
mkdir -p "$MMTS_ROOT" && cd "$MMTS_ROOT"
git clone -b ROCv3-alper-dev --recurse-submodules \
  ssh://git@gitlab.cern.ch:7999/hgcal-daq-sw/hexactrl-sw.git hexactrl-sw
```

⚠️ **`--recurse-submodules` is not optional.** There are three submodules across
two levels: `hexactrl-sw` has `hexactrl-script` and `zmq_i2c`, and
`hexactrl-script` has `analysis`. A plain clone leaves all three empty, and both
failures come later without either naming a submodule:

* `hexactrl-script/CMakeLists.txt` does `add_subdirectory(analysis)`, so the
  client build of 0.6a dies with `The source directory ... /hexactrl-script/analysis
  does not contain a CMakeLists.txt file` followed by
  `make: *** No targets specified and no makefile found`;
* the `zmq_i2c` tar of 0.7 copies an empty directory to the Kria.

On a clone that already exists, `git submodule update --init --recursive` from
`hexactrl-sw` does the same job.

**Step 2, `gui-hexmap`.** The repository is named `hgcal-module-testing-gui`; the
directory name is yours to choose, and `site.sh` records it as `GUI_HEXMAP`.

**(on the lab computer)**

```bash
git clone -b master \
  ssh://git@gitlab.cern.ch:7999/acrobert/hgcal-module-testing-gui.git gui-hexmap
```

If ssh to GitLab is not set up, the clones work over https instead, and prompt
for your CERN username and a personal access token: replace
`ssh://git@gitlab.cern.ch:7999/` with `https://gitlab.cern.ch/` in each URL.

Check everything landed on the right branch before moving on:

**(on the lab computer)**

```bash
git -C hexactrl-sw rev-parse --abbrev-ref HEAD
git -C gui-hexmap  rev-parse --abbrev-ref HEAD
ls hexactrl-sw/hexactrl-script/multimodule/puller.sh
ls hexactrl-sw/zmq_i2c/Link.py hexactrl-sw/hexactrl-script/analysis/CMakeLists.txt
```

The first two must print `ROCv3-alper-dev` and `master`. The last two are the
submodule check: `No such file or directory` rather than the files means the
recursive update did not run. The submodules are pinned by commit, so
`git -C hexactrl-sw/hexactrl-script rev-parse --abbrev-ref HEAD` prints a bare
`HEAD`, and detached is the correct state for a submodule, not a fault.

Resulting layout. `Results` is the default output root; it is set in
`site.sh` as `RESULTS_DIR`.

**(the resulting layout on the lab computer, not commands)**

```
$MMTS_ROOT/
├── hexactrl-sw/                  step 1, branch ROCv3-alper-dev
│   ├── hexactrl-script/          submodule: the scripts, configs and analysis
│   │   ├── analysis/             submodule: the pedestal and scan analyses
│   │   ├── configs/              the run configs, one per board type and slot
│   │   ├── multimodule/          THE BENCH SCRIPTS: this is $MM
│   │   │   └── kria/             the subset copied to the Kria in 0.7
│   │   ├── delay_scan.py
│   │   └── pedestal_run.py
│   └── zmq_i2c/                  submodule: the i2c-server, copied to the Kria
├── gui-hexmap/                   step 2, channel maps and geometries
└── Results/                      created on the first run
```

`hgc-test-systems`, the firmware, is needed only if you rebuild a bitstream and
lives on a fork branch. Clone it separately at that point rather than now.

⛔ Do not clone `gitlab.cern.ch/hgcal-daq-sw/hexmap`. It is deprecated, and its
`master` has no LD-Full-V3 channel map, so plots come out with the right outline
and the wrong channel positions. That failure looks fine, which is what makes it
dangerous. `gui-hexmap` is the only correct source.

## 0.5 Site settings

Every script takes its site values from one file, `$MM/site.sh`. Edit that and
nothing else; no script carries a hardcoded path or address.

**(on the lab computer)**

```bash
export MM=$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule
$EDITOR "$MM/site.sh"
```

| variable | set it to |
|---|---|
| `MMTS_ROOT` | the directory from 0.4 |
| `KRIA_IP`, `KRIA_USER` | your hexacontroller, user `daq` by default |
| `HEXACTRL` | the native install prefix from 0.6a |
| `MMTS_VENV` | the virtualenv from 0.6b, or empty for system-wide |
| `MMTS_FW` | the firmware design, see 0.8e |
| `RESULTS_DIR` | the output root, `$MMTS_ROOT/Results` by default |
| `GUI_HEXMAP` | the `gui-hexmap` clone from 0.4 |

Put `MMTS_ROOT` and `MM` in your shell profile as well, since this document
uses both in every command. Any value can also be overridden for one run, for
example `MMTS_FW=... "$MM/delay_scan.sh" B`.

## 0.6 Install the client stack

### a. hexactrl-sw

Build the client side of `hexactrl-sw` from the branch **`ROCv3-alper-dev`**
clone you made in 0.4, and install it under `/opt/hexactrl/ROCv3-alper-dev`.

**There is no RPM to install.** The `deploy-eos` job in
`hexactrl-sw/.gitlab-ci.yml` runs only for `$CI_COMMIT_BRANCH == "ROCv3"`, so the
public CERN repository at `hgc-online-sw.web.cern.ch` carries `ROCv3` builds and
nothing from our branch. Building from source is the supported route on both the
client and the Kria.

The client build needs **Boost, ROOT, yaml-cpp and cppzmq**: `unpack` and the
pedestal analysis read and write ROOT files, the client links against boost, and
every source in `sources/client` and `sources/common` includes
`yaml-cpp/yaml.h` or `zmq.hpp`. uHAL is not needed here, it belongs to the server
build of 0.8b.

A stock client has no toolchain, so the build starts by installing one. This is a
large download, ROOT alone runs to about a gigabyte:

**(on the lab computer)**

```bash
sudo dnf install -y cmake make gcc-c++ boost-devel
sudo dnf install -y epel-release
sudo dnf config-manager --set-enabled crb
sudo dnf install -y root yaml-cpp-devel cppzmq-devel zeromq-devel
cmake --version && root-config --version
ls /usr/include/yaml-cpp/yaml.h /usr/include/zmq.hpp
```

`root` comes from EPEL on AlmaLinux 9. If your site provides ROOT another way,
through CVMFS or a module, source that instead and skip the EPEL lines; cmake
finds it through `$ROOTSYS`.

⚠️ **Two traps in that block.** There is **no `root-devel`** package: EPEL splits
ROOT into `root-core`, `root-io` and friends, the headers ship inside
`root-core`, and the `root` metapackage pulls what you need. Asking for
`root-devel` gives `Unable to find a match`. **`crb` must be enabled first**,
because `root-io` needs `liburing-devel`, which lives in CRB and is disabled by
default; without it the install dies with `nothing provides liburing-devel` and
`root-config: command not found` afterwards. And **cmake does not check for
yaml-cpp or cppzmq at all**, so leaving them out configures cleanly and fails
minutes later in `make` with `fatal error: yaml-cpp/yaml.h: No such file or
directory` across most of `anaobjectlib`. If EPEL has no `cppzmq-devel` on your
release, the CERN software repo carries `cppzmq-devel-latest`, which is the same
header-only binding.

**(on the lab computer)**

```bash
cd "$MMTS_ROOT/hexactrl-sw" && mkdir -p build && cd build
cmake -DBUILD_CLIENT=ON -DBRANCH_NAME=ROCv3-alper-dev \
      -DCMAKE_INSTALL_PREFIX=/opt/hexactrl/ROCv3-alper-dev ../
make -j"$(nproc)" && sudo make install
```

⚠️ **Do not shorten that to a bare `cmake ..`.** All three flags earn their
place, and the failures are quiet:

* `BUILD_CLIENT` defaults to **OFF**. Without `-DBUILD_CLIENT=ON` you build the
  server side, `daq-server` and `zmq_i2c`, which needs uHAL and leaves you with
  no `daq-client` and no `unpack`, which is what the client is for.
* The install path is hardcoded to `/opt/hexactrl/${BRANCH_NAME}`, and
  `BRANCH_NAME` is read out of `git` when it is not passed. In a clone that
  works; **from a source snapshot with no `.git` it comes back empty** and
  everything installs into `/opt/hexactrl/` itself, breaking every path in this
  document.
* `make install` writes under `/opt`, so it needs `sudo`.

🔑 **Deactivate conda before configuring.** cmake resolves the interpreter with
`find_package(PythonInterp)`, which takes the first `python3` on `PATH`, so a
`(base)` prompt puts miniforge's 3.12 into the build and the install writes its
Python modules and shebangs for an interpreter that cannot import `uproot3`, per
0.6b. Read the line back out of the configure output:

**(configure output, not a command)**

```
-- Found PythonInterp: /usr/bin/python3 (found suitable version "3.9...")
```

Anything under `miniforge3` or `anaconda3` there means `conda deactivate`, then
**delete the build directory and configure again**: the interpreter is cached, so
re-running cmake in place keeps the wrong one.

Build it on the machine that will run it: this is the x86_64 AlmaLinux client,
and binaries from any other architecture or OS are useless here. The Kria gets
its own aarch64 build in 0.8b.

⛔ Installing the public `ROCv3` RPM instead is not a substitute. It lands under
`/opt/hexactrl/ROCv3/`, so every path in this document changes, and it predates
the MR !55 fixes listed in 0.8b.

Confirm what landed, then put the install's `bin` on `PATH` in your profile.
Every shell that runs a client command needs it. The `ls` must show
`daq-client`, `hitproducer` and `unpack`:

**(on the lab computer)**

```bash
ls /opt/hexactrl/ROCv3-alper-dev/bin
export PATH=/opt/hexactrl/ROCv3-alper-dev/bin:$PATH
```

🔑 That `PATH` is the fix for the most common analysis failure. The notifier
shells out to a bare `unpack`, so if the installation's `bin` is not on `PATH` in
the shell that launched `pedestal_run.py`, the run produces no `.root` and
`pedestal_run0.log` says `unpack: command not found`.

⚠️ **There is no `etc/env.sh` on the client, and you must not go looking for
one.** `CMakeLists.txt` installs it inside `if( NOT BUILD_CLIENT )`, so it is a
server-side file, and its contents are the cactus and uHAL paths of 0.8b, which
the client neither has nor needs. Sourcing it here gives
`No such file or directory`. The client build installs executables into `bin` and
nothing else: no `lib`, no `etc`.

The bench scripts already handle this for themselves. `multimodule/lib.sh`
sources `$HEXACTRL/etc/env.sh` only if the file exists and then prepends
`$HEXACTRL/bin` to `PATH` regardless, so the export above matters for the
hand-driven commands of sections 3 to 5, not for `partial_slot.sh` and its kin.

### b. Python dependencies

The RPM does not bring the Python packages `delay_scan.py` and the analyses need.
Use a virtual environment so the system Python stays untouched, and make sure it
can still see the RPM's Python modules.

**(on the lab computer)**

```bash
python3 -m venv --system-site-packages "$MMTS_ROOT/venv"
source "$MMTS_ROOT/venv/bin/activate"
pip install --no-cache-dir \
    "numpy<2" pyzmq pyyaml pandas matplotlib scipy seaborn \
    uproot uproot3 awkward awkward-pandas more_itertools \
    nested_dict nested_lookup pyinotify tables
```

`numpy<2` and `uproot3` are pinned deliberately: the pedestal analysis and
`hexmap_robust.py` both read trees through uproot3. ROOT and pylandau are not
needed here, since they only serve the MIP, injection and TDC analyses.

🔑 **Build the venv with the system `python3`, and deactivate conda first.**
`uproot3` does not work on Python 3.12: `uproot3_methods` calls
`loader.find_module()`, which was removed in that release, so the import dies
with `AttributeError: 'FileFinder' object has no attribute 'find_module'`. A
conda `base` environment on the client shadows `/usr/bin/python3`, and
`python3 -m venv` then builds a 3.12 venv without saying so. The same mistake
also defeats `--system-site-packages`, since the RPM installs its Python modules
for the system interpreter. Check the version the venv was built with, and
rebuild it if it is not the system one. The `ls` must show `python3.9` on
AlmaLinux 9, and the `conda deactivate` is needed only if a `(base)` prompt is
showing:

**(on the lab computer)**

```bash
ls "$MMTS_ROOT/venv/lib"
conda deactivate
rm -rf "$MMTS_ROOT/venv"
/usr/bin/python3 -m venv --system-site-packages "$MMTS_ROOT/venv"
```

Then re-run the `pip install` above.

### c. The scripts

`$MM` holds the bench scripts. `$MM/README.md` lists every file; these are the
ones you will type.

**(on the lab computer)**

```bash
cd "$MM"
chmod +x *.sh *.py kria/*
./puller.sh
```

The last line should print `puller up on 6001`.

| script | what |
|---|---|
| `partial_slot.sh` | **one slot end to end**: bring-up, gate, N pedestals, finder line, hexmaps, per-half check. This is the command a routine measurement uses |
| `register_boards.py` | record which serial is in which slot. Run it before the first bring-up after every board change |
| `bench_up.sh` | cold start: bitstream, payload power, ROC enable |
| `delay_scan.sh` | delay scan plus the PASS/FAIL gate |
| `ped_run.sh` | N pedestal runs scored by CRC |
| `slot_measure.sh` | bring up, gate, N pedestals, common-mode decomposition |
| `cm_analysis.py` | common-mode decomposition of a pedestal run: total, CM, residual, autocorrelation |
| `hexmap_robust.py`, `remap_all.sh` | hexmaps for one run, or for everything under the results root |
| `puller.sh`, `gate.py`, `module_of.py`, `finder_positions.sh` | the pieces the others share |

Two things they do that matter, and that you would otherwise have to remember:

- **The puller is restarted per run.** `daq-client` receives the event stream on
  port 6001 and writes the `.raw`. One that has seen a failed START silently
  produces data that decodes to nothing, so it is restarted for every scan and
  every pedestal, never reused across runs.
- **`PATH` picks up the hexactrl `bin`.** The run's notifier shells out to a bare
  `unpack`, so without this a run produces no `.root` and `pedestal_run0.log`
  says `unpack: command not found`.

Sections 3 to 5 give the underlying commands as well, so you can drive the whole
procedure by hand if you prefer.

## 0.7 Copy the code to the Kria

The Kria gets the contents of `$MM/kria/` and the i2c-server. No git on the Kria.

Three transfers, in the order below. The bring-up, mux and power helpers go to
`~/multimodule`; the three wrappers you type by hand go to the home directory
itself, for the reason given after the block; and the i2c-server goes under
`~/multimodule/hexactrl-sw`, from where it is run **and not** from the RPM copy
under `/opt`.

**(on the lab computer)**

```bash
cd "$MM/kria"
ssh kria 'mkdir -p ~/multimodule/hexactrl-sw'
tar cf - enableROCs.py mmts_bringup.sh findslot.py set_daq_delays.py \
  | ssh kria 'tar xf - -C ~/multimodule'
tar cf - up_verified.sh start_i2c.sh set_pwr_en.py | ssh kria 'tar xf - -C ~'
cd "$MMTS_ROOT/hexactrl-sw"
tar czf - --exclude=__pycache__ zmq_i2c | ssh kria 'tar xzf - -C ~/multimodule/hexactrl-sw'
ssh kria 'chmod +x ~/multimodule/*.sh ~/*.sh ~/*.py'
```

The three home directory scripts live as files on the Kria on purpose: a
`pkill -f` pattern typed into an ssh one-liner matches that one-liner's own
command line and kills your session. What they do:

| file | what |
|---|---|
| `up_verified.sh SLOT [--external-power] [--board NAME]` | runs `mmts_bringup.sh` up to 8 times and the i2c-server up to 3, and reports `READY` only when the ROC count matches `EXPECT_ROCS`, nothing says `FAILED`, and ports 5555 and 6000 both listen |
| `start_i2c.sh SLOT` | restart the i2c-server on a slot, detached, and print its identify line |
| `set_pwr_en.py SLOT on\|off ...` | drive one slot's payload rail without a bring-up |

Re-run the `tar` commands whenever you change a script on the client. The
client's `$MM/kria/` is the source of truth; do not edit the copies on the Kria.

## 0.8 One-time Kria setup

### a. Base image

Flash the standard HGCAL hexacontroller image for your Kria. It provides the
`daq` user, `fw-loader`, `kconn_pwr`, and the I2C device nodes. Confirm before
going further, and check the image against your own hexacontroller documentation
if either command is missing:

**(on the lab computer)**

```bash
ssh kria 'command -v fw-loader kconn_pwr; id daq'
```

### b. hexactrl-sw under `/opt`

The Kria needs the **server** side of the same branch, built for aarch64. It is a
different architecture, so the client build of 0.6a is useless here; build it on
the Kria itself, which has `gcc`, `cmake`, `boost-devel` and uHAL under
`/opt/cactus` already.

Copy the source over and build it there. The **`-DBUILD_CLIENT` flag is omitted
on purpose**: OFF is the default and gives `daq-server` and `zmq_i2c`, which is
what the Kria runs. `BRANCH_NAME` must still be passed, since the copied tree has
no `.git` for cmake to read it from, and without it everything installs into
`/opt/hexactrl/` itself.

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

The Kria is a four-core aarch64 board, so expect this to take considerably longer
than the client build. `sudo make install` writes under `/opt`, which is outside
the passwordless rule of 0.3, so run it from a login shell.

🔑 **Build the same commit on the Kria and on the client.** The branch carries
fixes this procedure depends on: the `fifo_latency` mask fix, rebuilding
`HwInterface` when `uhal_device` changes, skipping a trigger elink whose chip has
no DAQ elink, and the offset finder skipping unreachable links instead of
refusing the slot.

Any Kria shell that runs `daq-server` or the link diagnostics needs the
environment first. Bring-up and `zmq_server` do not.

**(on the Kria)**

```bash
source /opt/hexactrl/ROCv3-alper-dev/etc/env.sh
```

### c. Firmware

The design is `multimodule-hd-tester-trophy-v3`, installed from the CERN
repository as an RPM under `/opt/cms-hgcal-firmware/hgc-test-systems/`. The Kria
needs internet access and a repository file for it.

⚠️ **The firmware is not in the repo the image ships with.** A stock Kria has
`/etc/yum.repos.d/CERN-REPO-hgcwebsw.repo`, repo id `hgcal-daq-sw`, whose
`baseurl` ends in `hgcal-daq-sw/almalinux/9/aarch64/`. That is the `hexactrl-sw`
software repo and it carries no firmware, so `dnf` answers `No match for
argument` for every firmware release even though the RPM has been published for
days. The firmware repo is `hgc-online-sw/repository/`, and you add it yourself.
Write the file once:

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

Then install or update the firmware, **always by its full `name-version-release`**:

**(on the Kria)**

```bash
sudo dnf update multimodule-hd-tester-trophy-v3-feature_multiplexer_board_v2-2026_09_01_16_56_41.49751f37
rpm -q multimodule-hd-tester-trophy-v3
```

`update` is right when an older build is already installed, which is the usual
case; `install` does the same job on a Kria that has none. Take the newest
`feature_multiplexer_board_v2` release rather than this exact one once newer ones
appear; `sudo dnf list --available multimodule-hd-tester-trophy-v3` shows what is
on offer.

⚠️ **Never type the package name bare, and never run an unqualified `dnf
update`.** The package version string is the *branch* name, so every branch that
ever built publishes the same package name, and rpm's version compare picks the
alphabetically largest one, `test_merge_everything`, a 2025 build with no
equalisation. `dnf install multimodule-hd-tester-trophy-v3` gets you that, and so
does a routine `dnf update` with this repository enabled.

🔑 **The release string must be `2026_09_01_16_56_41.49751f37` or later**, the
build that carries the DAQ RX equalisation of 0.8e. Earlier ones do not, and the
difference decides whether four of the six DAQ e-links work at all.

⚠️ `sudo dnf` is not in the passwordless rule of 0.3, which covers `fw-loader`
and `kconn_pwr` only. Run it from a login shell on the Kria, not through a
one-shot `ssh` that has no terminal to prompt on.

⚠️ **The RPM overwrites `uHAL_xml/connections.xml`**, which is the file you edit
by hand in 0.8d. Re-apply that edit after every firmware install or upgrade,
otherwise the next bring-up addresses `TOP` only and every slot fails. The
per-slot `fw_block_addresses_{A,B,C}.xml` are not RPM files and survive.

Then load it:

**(on the lab computer)**

```bash
ssh kria 'sudo fw-loader list'
ssh kria "sudo fw-loader load $MMTS_FW"
```

`fw-loader load` takes a name under the base directory or an absolute path, and
the directory basename must match its own dtbo. A freshly booted Kria has no
bitstream at all, and bring-up then dies at `[pwr]` with
`[Errno 2] ... '/dev/i2c-2'`.

### d. `connections.xml` needs `TOP_A`, `TOP_B`, `TOP_C`

**This is required and none of it is shipped.** A fresh install carries one
address table, `fw_block_addresses.xml`, whose three trigger blocks are named per
slot, and a `connections.xml` defining `TOP` alone. `daq-server` addresses one
slot at a time through the generic names `bram_trg` and `link_capture_trg`, so
each slot needs its own table with its own blocks renamed to those, and its own
connection entry. Without them nothing can address a slot.

Make the three tables from the shipped one. This keeps each slot's addresses and
module files and only renames the ids:

**(the first line is typed on the lab computer, everything after it on the Kria)**

```bash
ssh kria
cd /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml
for S in A B C; do
  sed -E "/id=\"(bram_trg|link_capture_trg)_[ABC]\"/{ /_${S}\"/!d }" fw_block_addresses.xml \
    | sed -E "s/id=\"(bram_trg|link_capture_trg)_${S}\"/id=\"\1\"/" \
    | sudo tee fw_block_addresses_${S}.xml > /dev/null
done
grep -c 'id="bram_trg"' fw_block_addresses_[ABC].xml
```

That `grep` must report 1 for each of the three files.

Then keep a `.orig` backup of `connections.xml` and add one block per slot:

**(a file on the Kria, `uHAL_xml/connections.xml`)**

```xml
<connection id="TOP_B"
    uri="uioaxi-1.0:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/fw_block_addresses_B.xml"
    address_table="file:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/fw_block_addresses_B.xml"/>
```

⚠️ `connections.xml` belongs to the firmware RPM, so **a firmware install or
upgrade puts the stock `TOP`-only file back**. The `fw_block_addresses_{A,B,C}`
files are yours and survive. Re-check both after every install, per 0.8c.

### e. The equalised bitstream

🔑 **Check your firmware release before trusting a pedestal.** An unequalised
build leaves the DAQ inputs with `IBUF_LOW_PWR` on, and four of the six DAQ
e-links then fail 100 % of CRCs while looking healthy on entry counts: halves
c0h0, c0h1, c1h0 and c2h1 read exactly 0.000. Equalised against unequalised, CRC
pass goes 0.000 to 1.000 on all three slots, `badBX` 0.10 to 0.000, and the eye
8 taps to 64.

The equalisation sets `IBUF_LOW_PWR FALSE` and `EQUALIZATION EQ_LEVEL4` on the
DAQ inputs, in `designs/multimodule-hd-tester-trophy-v3/xdc/daq_rx_eq.xdc`.
Levels are uncalibrated, and `EQ_LEVEL4` is the one that gives 100 % CRC pass on
every link; `EQ_LEVEL2` recovers them but leaves 1 to 4 % error on two, and
`IBUF_LOW_PWR` alone changes nothing. These are I/O properties only, so no logic,
address map, software or routed timing changes with them.

Install the RPM of 0.8c and set `MMTS_FW=multimodule-hd-tester-trophy-v3`. Read
the commit out of the RPM's release string to confirm what you have:
`2026_09_01_16_56_41.49751f37` or later carries the equalisation. A copied build
directory carries no such stamp, which is a reason to prefer the RPM.

⚠️ **`MMTS_FW` is not sticky.** `enableROCs.py` re-points `active` on
every run, so a bring-up without it silently reverts the bench to stock. Check
after every bring-up:

**(on the lab computer)**

```bash
ssh kria 'readlink /opt/cms-hgcal-firmware/hgc-test-systems/active; dmesg | grep "fpga0: writing" | tail -1'
```

### f. Device permissions

Two udev rules. Both were needed on a stock image, and both fail in ways that
waste a session.

The **gpiochip** rule comes first: the Zynq PS chips are `root:root` 0600, which
makes `gpiofind` abort. The **uio** rule is second: `/dev/uio*` at `root:root`
0600 stops `daq-server` opening the firmware's UIO devices, so it logs
`Permission denied`, goes to state `Error`, and rejects every configure, leaving
scans with a header-only `.root` and no plots.

**(on the Kria)**

```bash
echo 'SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpiochip-all.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=gpio
echo 'SUBSYSTEM=="uio", KERNEL=="uio*", GROUP="daq", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-uio-daq.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=uio
```

Confirm the `daq` user is in the `i2c` and `gpio` groups, and log out and back in
after any `usermod`.

## 0.9 Check the installation

All of it is typed on the lab computer. The first three lines check the Kria over
`ssh`; the rest check the client stack, which exists only on the lab computer.

**(on the lab computer, checking the Kria)**

```bash
ssh kria "sudo fw-loader load $MMTS_FW"
ssh kria 'ls -l /dev/i2c-2 /dev/uio0; gpiofind Multiplex_A'
ssh kria 'cd ~/multimodule && python3 findslot.py'
```

**(on the lab computer, checking the lab computer)**

```bash
export PATH=/opt/hexactrl/ROCv3-alper-dev/bin:$PATH
source "$MMTS_ROOT/venv/bin/activate"
command -v daq-client unpack
python3 -c "import uproot, uproot3, numpy, zmq; print(uproot.__version__)"
"$MM/puller.sh"
```

⚠️ **Do not run the second block on the Kria.** The Kria has no `daq-client`, no
venv, and no uproot or ROOT, and it is not supposed to: it runs `daq-server`, the
i2c-server and the firmware only, per 0.1. On the Kria those lines fail with
`no daq-client at /opt/hexactrl/ROCv3-alper-dev/bin` and an import error, which
is the wrong machine and not a broken install. `hostname; uname -m` settles which
one you are on: `x86_64` is the lab computer, `aarch64` is the Kria.

`findslot.py` probes all three slots for ROCs without a bring-up. It is harmless
and it is the cheapest diagnostic on the bench.

🔑 **`no ROCs` on all three slots is the expected result here, and it is not a
fault.** At this point nothing has powered a module yet. `findslot.py`
writes the mux board's own `S*_PWR_EN` itself, but it does not run
`kconn_pwr on`, and it never touches `EN_Mx` on the power distribution board at
`0x27`, which is written only by the bring-up. It also probes the LD-Full
addresses `0x08 0x18 0x28` on sub-bus `S1_I2C` alone, so a partial at
`0x48 0x58` or an HD Full's second sub-bus reads `no ROCs` even when powered.

What the line does prove is the part that matters at this stage: the PL I2C
master is alive, all three switches ACKed at `0x71`, `0x73` and `0x77`, and the
mux GPIO writes went through, since a failure there prints `mux GPIO write
failed` instead. Run a bring-up (section 1) before reading anything into a ROC
count, and expect **0 A on the meter** until you do.

---

# 1. Powering up

## 1.0 Size the supply BEFORE you trust any measurement

🔑 **A module at its supply's current limit produces data that looks like broken
hardware.** On an HD Full at the limit the rail sags from 1.72 V to **1.35 V**
and **all 24 e-links die**. With headroom the same module gives 12/12 DAQ links
and CRC 1.000 on every half.

| board | measured draw, all chips running |
|---|---|
| LD Full, LD partials | ~1.2 A at 1.72 V |
| **HD Full, six chips** | **4.43 A at 1.72 V** |

⚠️ **Many bench supplies are ~3.2 A per channel and cannot run an HD Full on one
channel.** On a SIGLENT SPD3303X-E, CH1 and CH2 are 0-3.2 A each and this is a
**hardware maximum, not a settable compliance**. Press **`Para`** to link them
into one 0-6.4 A channel:

* both leads go on **CH1 only**, whose terminals are labelled `Para Out`; CH2's
  terminals stay empty;
* set the voltage on CH1 and leave the current at its per-channel maximum, since
  the doubling happens in hardware and asking for 6.4 A gives
  `current setting overrange`;
* 🛑 **never wire `+CH1 / −CH2`** — that is the *series* pattern, and in `Ser`
  mode it puts **double** the set voltage on the board.

**How to tell you are clipping**, since this is the failure that wastes days:

* the on-screen mode reads **`CC`**, and the **output voltage is below the
  setpoint**. That is the reliable test.
* ⚠️ Do **not** trust the terminal LED colour. On the SPD3303X-E the panel prints
  `C.V.` in green and `C.C.` in red, which is the opposite of the wording in the
  generic manual. In parallel mode the slave channel always reads CC; that is
  normal.

**What clipping imitates.** Each of these is the sagging rail, and each reads as
a hardware fault:

* the meter wandering between plausible values with nothing running;
* consecutive bring-ups finding a **different number of ROCs** (4 of 6, then 6
  of 6) — ROCs enable sequentially and the rail sags as they come up, so the
  *last* one fails, a different chip each time;
* a module that works, then stops working after ~30 minutes of cycling.

🔑 Silencing chips to reduce the draw **cannot rescue bring-up**:
`Link.find_board_for_rocs` requires an exact address-set match, so every ROC must
enable before any config can quiet them. The current spike is unavoidable by
design, which is why the supply has to be sized for it.

## 1.1 The order, always

**(the order of operations, not commands)**

```
bring-up  →  i2c-server  →  daq-server  →  puller  →  DELAY SCAN  →  pedestal
```

🔑 **Always take a delay scan before a pedestal. Never go straight to pedestals.**
The delay scan takes seconds, prints a per-link verdict, and is harmless when it
fails. A pedestal run on a slot whose links are not aligned is the expensive way
to learn the same thing: `daq-server` refuses to START, and the client's retry
loop hammers the server thousands of times and can take both it and the puller
down, costing a full reset.

🔑 **Exactly one slot carries trigger at a time: the first slot `daq-server`
scanned since it last started.** The other two read 0 of 12 on trigger while DAQ
looks perfect on all three. A slot reading 0/12 is almost always this and not a
fault. To move the trigger to another slot, restart `daq-server` and scan that
slot first. No mains cycle and no reordering of the bring-up are needed.

`mmts_bringup.sh` restarts `daq-server` for you, so a slot change releases the
claim automatically. Use `--keep-daq-server` to override.

**After any failed or interrupted run, redo the last two steps**: restart
`daq-server` and restart the puller. Both hold state from the dead run, and
skipping this is the easiest way to spend an hour debugging leftovers.

## 1.2 Cold start after a mains cycle

A freshly booted Kria has no bitstream, and payload power is off.

**(on the lab computer)**

```bash
ssh kria "sudo fw-loader load $MMTS_FW"
ssh kria 'sudo kconn_pwr on'
```

⚠️ `enableROCs.py` has no `--no-recover` flag. Plain is the default and
does not cycle power; `--recover` opts into the `kconn_pwr off` then
`fw-loader load` then `kconn_pwr on` sequence. After a mains cycle use the
recover form, or do the two commands above by hand first. Otherwise every probe
returns `no ROCs` against an unpowered bus, with all writes still ACKing.

## 1.3 The bring-up wrappers

`up_verified.sh` runs on the Kria and is the one to use. It retries both
lotteries, bring-up and i2c discovery, and verifies the result rather than
trusting a log line:

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=$MMTS_FW EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
```

⚠️ `EXPECT_ROCS` defaults to 3. Set it to your board's ROC count. With the
default, a partial enable such as `4 ROC(s) enabled ... 1 FAILED ['0x28']` on a
six-ROC board is reported as `READY`, and the pedestal run then times out four
times over with nothing to show for it.

### 🔑 `--module N`: `EN_Mx` is cabling, not the slot index

With a power distribution board fitted, the bring-up drives `EN_Mx` to switch the
module on. The default is the slot's own index (`A`→1, `B`→2, `C`→3), and that is
**an assumption about which output the module's power lead is plugged into**, not
a property of the hardware.

Get it wrong and you see `no ROCs` with **0 A on the meter**, which is
indistinguishable from a dead module, a bad trophy or a seating fault:

**(on the lab computer)**

```bash
ssh kria "MMTS_FW=$MMTS_FW EXPECT_ROCS=6 ~/up_verified.sh A --module 3 --board HD-Full"
```

🔑 **Diagnostic rule.** If the probe says `no ROCs` but the **mux-board GPIO
writes succeeded**, the master, the switch and the expander are all fine, because
those writes never leave the mux board. **Sweep `--module 1/2/3` and watch the
meter before suspecting the module.** With one module on the bench, any draw at
all must be that module, so the meter identifies the correct bit immediately.

The flag is forwarded by `bench_up.sh` and `mmts_bringup.sh` directly, by
`ped_run.sh` as `PED_MODULE`, and by `slot_measure.sh` as `SM_MODULE`.

`bench_up.sh` on the client does the cold start in the only order that works, and
needs no adaptation since it only calls `ssh`. The first line below is the form
for a partial, the second for an LD Full:

**(on the lab computer)**

```bash
"$MM/bench_up.sh" A --board LD-Semi --expect 2
"$MM/bench_up.sh" A --board LD-Full --expect 3 --power-board
```

## 1.4 What good looks like, and when to just re-run

A good bring-up prints the ROC list, readbacks of `0x0`, and `daq-server ... ok`
on port 6000:

**(expected output, not a command)**

```
3 ROC(s) enabled ['0x8', '0x18', '0x28']
```

A good i2c-server prints **`Identify a board with HGCROC Siv3b`**. If it prints
plain `Siv3`, interrupt it and redo bring-up plus i2c-server, otherwise the next
configure dies with `KeyError: 'dac_hyst_toa'`.

⏳ **Give each step time.** Both look broken partway through.

| step | takes | what it looks like mid-flight, which is not failure |
|---|---|---|
| bring-up | 60 to 90 s | log stops at `Turning on payload power`, and `daq-server` is down with 6000 not listening, because it is killed before being restarted |
| i2c-server | 15 to 30 s | `IOError in mux_setup group (attempt n/5) ... Retrying.` Retries are normal and usually succeed. 5555 is not yet bound |

Do not conclude anything until the bring-up log ends in `next:` or
`bring-up failed`, **and** the server log contains `Identify a board with HGCROC
Siv3b` or a traceback. Both logs are truncated on each launch, so a log read too
early may be the previous attempt's. Check the mtime if in doubt.

**Fewer ROCs than expected means run it again.** Bring-up needs two to four
attempts routinely on a healthy bench. A few `transient I2C error ... retry n/5`
lines are normal.

---

# 2. Board types: choose your parameters first

Everything in sections 3 to 5 depends on four values: the `--board` name, the
expected ROC count, whether the module has a power distribution board, and which
run config to use. Fix them here before touching a slot.

## 2.1 Read the serial

The serial encodes what you need. Characters 5 and 6 are the geometry, character
7 is the ROC revision.

**(example serials, not commands)**

```
320X LR 4 D QE 00020    ->  LD Right, ROC v3D
320X LF 4 C QH 00443    ->  LD Full,  ROC v3C
320X LL 4 D QE 00016    ->  LD Left,  ROC v3D
320X HF 4 D PM 02021    ->  HD Full,  ROC v3D
```

🔑 **Set `Top.in_inv_cmd_rx` from the revision: v3C gives 1, v3D gives 0.** The
wrong value leaves all twelve trigger links at `ngood=0` while DAQ looks
completely fine. hexactrl-sw reports both revisions as `Siv3b`, so nothing in
software will tell you which one you have.

Measured both ways on the HD Full above, each with its own bring-up:

| `in_inv_cmd_rx` | DAQ | trigger |
|---|---|---|
| **0** (correct for v3D) | 12/12 | 8/12 |
| 1 | 12/12 | **0/12** |

⚠️ **The rule is per ROC revision, not per board family.** A v3b HD Full needs
`1` and a v3D HD Full needs `0`. Read character 7 and do not inherit the value
from another board of the same geometry.

⚠️ A ROC register only reaches silicon on the **first** initialize of an
i2c-server's life, so testing a different `in_inv_cmd_rx` needs a **fresh
bring-up**, not just a rescan. A comparison made without one is meaningless.

Board type codes follow the GUI repository: `LF LR LL L5 LT LB` and
`HF HB HL HT HR`. They are not the old `LD` and `HD` names. `hexmap_robust.py`
derives its geometry and channel map from characters 5 and 6, so do not pass
`-t`: forcing `-t LF` on an `LR` plots a partial on the full geometry, which
looks fine and is wrong.

## 2.2 ROC addresses per board

`zmq_i2c/Link.py` matches the **exact** address set. A partial with one ROC not
responding does not fall back to a smaller board; it fails outright with
`Exception: ROC addresses [...] do not match a known board`. That same message
also covers a bad bring-up, so read the printed address list before concluding
the board type is wrong.

| board | ROC addresses |
|---|---|
| V3 LD Full HB | `0x08 0x18 0x28` |
| V3 LD Five HB | `0x48 0x58 0x68` |
| V3 LD Semi or Half HB | `0x48 0x58` |
| V3 HD Semi-left, Semi-right | `0x08 0x18` |
| V3 HD Bottom | `0x18 0x58 0x28 0x68` |
| V3 HD Top | `0x18 0x58 0x28` |
| **V3 HD Full HB** | **`0x08 0x18 0x28 0x48 0x58 0x68`** |

The mux probe list is `[0x08, 0x18, 0x28, 0x48, 0x58, 0x68]`, so discovery covers
all V3 partials. It does not cover `0x00/0x20/0x40/0x60`, so ROCv2 LD and NSH
boards would not be found on the mux path.

## 2.3 LD Full (LF)

Power distribution board **fitted**. Three ROCs. Six DAQ links and twelve trigger
links. The environment for `slot_measure.sh`:

**(on the lab computer)**

```bash
SM_BOARD=LD-Full SM_EXPECT=3 SM_EXTPOWER=0
```

⚠️ **`SM_EXTPOWER=0` is required with the power board in.** The `0x27` `EN_Mx`
write is what powers the module, and `--external-power` skips it, so the default
would leave the module dead. `bench_up.sh` takes `--power-board` for the same
reason.

Run configs: `configs/initLD-Full-3b_mux{A,B,C}_ped.yaml`.

## 2.3b HD Full (HF)

Power distribution board **fitted**. **Six** ROCs, **twelve** DAQ links and
twelve trigger links — **24 e-links**, double an LD Full. Twelve halves in the
pedestal output, not six. The first line is the environment for
`slot_measure.sh`, the second a bring-up:

**(on the lab computer)**

```bash
SM_BOARD=HD-Full SM_EXPECT=6 SM_EXTPOWER=0 SM_MODULE=<n>
"$MM/bench_up.sh" A --board HD-Full --expect 6 --power-board --module <n>
```

⚠️ **Check the supply first — see 1.0.** Six chips draw **4.43 A at 1.72 V**,
which is more than one channel of a typical 3.2 A bench supply. Everything else
about an HD Full is unremarkable *provided* the rail holds; at the limit all 24
e-links die and the module looks catastrophically broken.

⚠️ **A partial enable is not success.** Require `EXPECT_ROCS=6` **and** no
`FAILED` in the log.

Run configs: `configs/initHD-Full-trophyV3_mux{A,B,C}_ped.yaml`.

🔑 **If some trigger links will not align, drop *those* links and keep the rest.**
Do **not** set `elinks_trg: []` — with no trigger links `daq-server` starts and
then hangs forever producing nothing, which is a documented dead end. Eight good
trigger links are ample for event building.

**Expected on a healthy HD Full:**

| | |
|---|---|
| DAQ links | 12/12, `wmax` 42-92 |
| CRC pass | **1.000 on all 12 halves**, `badBX` 0.000 |
| entries per 10 000-event run | 4 694 976 |
| `adc_stdd` median | ~1.24 |

## 2.4 LD Left (LL) and LD Right (LR)

**No power distribution board.** These are fed from the bench supply directly, so
every bring-up takes `--external-power`. Two ROCs at `0x48 0x58`. Three DAQ links
and six trigger links. This is also what `slot_measure.sh` assumes when you set
nothing:

**(on the lab computer)**

```bash
SM_BOARD=LD-Semi SM_EXPECT=2 SM_EXTPOWER=1
```

Without `--external-power`, bring-up drives a `0x27` power board that is not
there. Probe with `--board any` first on the first board of a type and read the
printed address list before pinning `--board` and `EXPECT_ROCS`.

Run configs: `configs/initLD-Left-3b_mux{A,B,C}_ped.yaml`.

## 2.5 LD Bottom (LB)

Same electrical setup as 2.4: no power board, `--external-power`, two ROCs.

🔑 **An LD Bottom drives THREE trigger links, not six. That is the board type and
not a fault.** Pedestals come out clean on the three: gate PASS, CRC 1.000, 0 of
108 channels over clip.

⚠️ A pedestal does not test the link count. `randomL1A` barely exercises the
trigger path and would look identical if links were being lost. Use a TPG run to
test that.

Run configs: `configs/initLD-Bottom-3b_mux{A,B,C}_ped.yaml`.

An **LD Top** has the same two ROCs and the same electrical setup, but its link
map has not been measured, so it has no file of its own yet. Probe one with
`partial_slot.sh` and no `SKIP_PROBE=1`, per 2.6, before trusting the LD Bottom
map on it.

## 2.6 Measured link sets

DAQ is links 0, 1 and 4 for every partial. **The trigger set depends on the slot
as well as the board type.**

| board type | slot A | slot B | slot C |
|---|---|---|---|
| Right, Left | 0,1,2,3,5,6 | 0,1,2,3,5,6 | 0,1,2,4,5,11 |
| **Bottom** | **1, 2, 6** | **1, 2, 5** | not measured |

For a board type or slot not in this table, measure the live links before picking
a run config. Run `partial_slot.sh` **without** `SKIP_PROBE=1`:

**(on the lab computer)**

```bash
"$MM/partial_slot.sh" B initLD-Left-3b LD-Semi 2 probe 3
```

It derives a twelve-link probe from that slot's own `_ped.yaml`, delay-scans with
it, writes the live set back into the config, and then re-does the bring-up
before running any pedestal. That last step is not optional: the probe arms all
twelve capture blocks and `LinkAligner` never clears `invert`, so a pedestal in
the same bring-up stalls at 64 events.

## 2.7 Trophies

Trophies are shared across geometries. LB shares with LR, and LB shares with LT.
A mismatch between the trophy's type code and the module's type code is **not**
evidence of a wrong trophy.

## 2.8 Register the board

The output layout is grouped by board, so one module's whole history sits
together whichever slot it was in:

**(the output layout on the lab computer, not a command)**

```
Results/<serial>/Mux<slot>/{delay_scan,pedestal_run}/<UTC timestamp>/
```

The serial comes from `Results/module_ids.json`, a list of
`{slot, from, to, module}` windows in UTC. `register_boards.py` maintains it:
run it the moment the boards are in and **before** the first bring-up, since the
scripts name their output directories from it and a stale entry files a whole
campaign under the previous module's serial.

**(on the lab computer)**

```bash
"$MM/register_boards.py" A=320XLF4DQR00332 B=320XLF4DME01621 C=320XLF4DME01744
"$MM/module_of.py" B
```

The second line prints the serial now recorded for slot B.

A slot left out of the command is recorded as empty from then on; `--at
YYYY-mm-ddTHH:MM:SSZ` backdates a swap that happened earlier. A board with no
window falls back to the flat layout and the plotter prints `module: UNKNOWN`.
Fix the registry rather than passing `-m` on every command, so the swap history
stays in one place.

## 2.9 Summary

| | LD Full (LF) | LD Left, LD Right | LD Bottom (LB) |
|---|---|---|---|
| power distribution board | fitted | none | none |
| `--external-power` | **no** | yes | yes |
| `--board` | `LD-Full` | `LD-Semi` | `LD-Semi` |
| ROCs | 3, at `0x08 0x18 0x28` | 2, at `0x48 0x58` | 2, at `0x48 0x58` |
| DAQ links | 6 | 3 | 3 |
| trigger links | 12 | 6 | **3** |
| delay scan gate | 18 of 18 | 9 of 9 | 6 of 6 |
| run config | `initLD-Full-3b_mux*_ped.yaml` | `initLD-Left-3b_mux*_ped.yaml` | `initLD-Bottom-3b_mux*_ped.yaml` |

---

Sections 3 to 5 assume this preamble in every client shell:

**(on the lab computer)**

```bash
export PATH=/opt/hexactrl/ROCv3-alper-dev/bin:$PATH
source "$MMTS_ROOT/venv/bin/activate"
MM=$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule
SCRIPTS=$MMTS_ROOT/hexactrl-sw/hexactrl-script
OUT=$MMTS_ROOT/Results/$(python3 "$MM/module_of.py" "$SLOT")
```

`module_of.py` prints the serial for the slot, so `$OUT` lands in the by-board
layout of 2.8. If the board is not in the registry it prints nothing, and you
should use `$MMTS_ROOT/Results` directly.

**The short form of everything in sections 3 to 5 is one command per slot:**

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/partial_slot.sh" B initLD-Left-3b LD-Semi 2 LLeft 5
```

That is bring-up, gate, a one-run trial, the remaining runs, the finder
line, hexmaps and a per-half check, each stage stopping the sequence on failure
instead of burning the next stage's timeout. `POWER=` in front of it selects the
power distribution board for an LD or HD Full. The hand-driven steps below are
what it does, for when you need to see one of them on its own.

---

# 3. Slot A

⚠️ **Slot A is diagnosed but not fixed.** Its chip 1 latches a different BCR,
landing 252 to 1949 words away from chips 0 and 2 in the orbit, and the offset is
redrawn at every bring-up. Slots B and C sit flat at 23 to 25 every time.
Commissioning a new module type on slot A means debugging two unknowns at once,
so **prove a new board type on slot B first**.

## 3.1 Bring up slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=$MMTS_FW EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
```

For an LD Full drop `--external-power`, and use `EXPECT_ROCS=3 --board LD-Full`.

Wait for `READY`. If it prints `FAILED to bring slot A up cleanly`, run it again
before investigating anything.

## 3.2 Delay scan on slot A

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
python3 delay_scan.py -d MuxA -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/initLD-Left-3b_muxA_ped.yaml
python3 "$MM/gate.py" "$OUT/MuxA"
```

**(expected output, not a command)**

```
Results/<serial>/MuxA/delay_scan/<timestamp>
  daq: 3/3  link0=57 link1=61 link4=58
  trg: 6/6  link0=44 link1=51 link2=49 link3=47 link5=52 link6=45
GATE: PASS -- safe to run pedestals
```

Or `"$MM/delay_scan.sh" A configs/initLD-Left-3b_muxA_ped.yaml`, which does the
puller restart, the scan and the gate in one step.

**The gate must PASS before you run a pedestal.** A failure is a retry and not a
result: re-run bring-up, which also restarts `daq-server`, then scan again. A
missed claim or a link dropped at init happens about once a session, and the
identical sequence then works on the retry, so repeat once before concluding
anything.

If trigger reads 0 across the board while DAQ is fine, slot A does not hold the
trigger claim. Restart `daq-server` and scan A first, per section 1.1.

🛑 A delay scan reading 18 of 18 is **not** a health gate on its own. Idle is the
easiest pattern to sample, and a slot can score worse on eye width while
producing far better data. The real health check is an actual START plus the
offset finder's header positions.

## 3.3 Pedestal on slot A

Restart the puller first. The `daq-client` from the delay scan is not reusable.

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
PYTHONPATH=$PWD/analysis \
  python3 pedestal_run.py -d MuxA -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/initLD-Left-3b_muxA_ped.yaml
```

`-I` is **required**. Without it `daq-server` never leaves `created` and the
client spins forever.

Or, with the bring-up, the gate, N runs and the CRC table:

**(on the lab computer)**

```bash
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 LLeft 10000
```

**Slot A specific:** the offset finder cannot bootstrap a slot with no good lane,
so slot A is still the one case that may need `method: 'manual'` with a pinned
`fifo_latency` and `L1A_offset_or_BX`. Set that in the config yourself.
Everywhere else, leave the method on `'automatic'`.

Expect about 30 s per run on a healthy slot. Minutes means the finder's phase 2
is retrying per link, which is a signal the links are marginal.

## 3.4 Hexmaps and common mode for slot A

Unpacking and analysis run automatically as long as the installation's `bin` is
on `PATH` in this shell, which the preamble's `export PATH` handles. A good run
writes its own `.root` and nine PNGs unattended, and no `crash_report.log` means
it worked.

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" <run-dir> -l LLeft --clip 5
python3 "$MM/cm_analysis.py" "$OUT/MuxA/pedestal_run/run_*"
```

Read the printed `module:` and mapping lines every time. Mapping version matters:
the repository ships dated maps and even an explicit `_BAD.csv`, and the wrong
one silently relocates almost every channel.

Report **both** `adc_stdd` and `adc_iqr/1.349`, and trust the robust one.
`adc_stdd` is inflated by packet corruption, and `adc_mean` is not yet
reproducible run to run.

If the automatic path ever fails, unpack and analyse offline:

**(on the lab computer)**

```bash
D=$OUT/MuxA/pedestal_run/run_<timestamp>
unpack -i $D/pedestal_run0.raw -o $D/pedestal_run0.root -M $D/pedestal_run0.yaml
cd "$SCRIPTS" && python3 -c "
import sys; sys.path.insert(0,'analysis')
import level0.pedestal_run_analysis as A
a = A.pedestal_run_analyzer(odir='$D'); a.add('$D/pedestal_run0.root')
a.mergeData(); a.makePlots()"
```

A good run gives a `.root` of about 5 MB, `unpacker_data/hgcroc` with 2 347 488
entries, `runsummary/summary` with 234 rows, and nine PNGs. Those numbers are for
an LD Full; a partial legitimately produces fewer.

## 3.5 Slot A caveats

- `daq.link9` runs `nbad` around 100 out of 512. That is a persistent slot A
  signature, not a new fault.
- Chip 1's BCR offset is redrawn at every bring-up, so a slot A result that
  disagrees with slot B is more likely to be the slot than the module.

---

# 4. Slot B

**Slot B is the healthiest slot and is the reference.** It reaches 18 of 18 with
all twelve trigger links on the first try, runs at 30 s per run, and gives full
yield. Prove any new board type here first.

## 4.1 Bring up slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=$MMTS_FW EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
```

## 4.2 Delay scan on slot B

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
python3 delay_scan.py -d MuxB -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/initLD-Left-3b_muxB_ped.yaml
python3 "$MM/gate.py" "$OUT/MuxB"
```

Or `"$MM/delay_scan.sh" B configs/initLD-Left-3b_muxB_ped.yaml`.

Same gate rule as 3.2: PASS before a pedestal, and a FAIL is a retry.

## 4.3 Pedestal on slot B

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
PYTHONPATH=$PWD/analysis \
  python3 pedestal_run.py -d MuxB -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/initLD-Left-3b_muxB_ped.yaml
```

Or, with the bring-up, the gate, N runs and the CRC table:

**(on the lab computer)**

```bash
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 LLeft 10000
```

Keep `method: 'automatic'`. It wins because it sets **per-link** `fifo_latency`,
not because of the offset value. Manual applies one shared value to every link
and can only ever fix a subset.

## 4.4 Hexmaps and common mode for slot B

Identical to 3.4 with `MuxA` replaced by `MuxB`.

## 4.5 What good looks like on slot B

Ten pedestals give 60 of 60 half-ROCs below corruption 1.0, with robust σ of
**0.741 ADC**. Use that as your yardstick for a healthy LD Full half.

---

# 5. Slot C

## 5.1 Bring up slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=$MMTS_FW EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
```

⚠️ Sub-bus 7 hangs the bus if it is selected on slot C. It is no longer probed,
so do not add it back.

## 5.2 Delay scan on slot C

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
python3 delay_scan.py -d MuxC -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/initLD-Left-3b_muxC_ped.yaml
python3 "$MM/gate.py" "$OUT/MuxC"
```

Or `"$MM/delay_scan.sh" C configs/initLD-Left-3b_muxC_ped.yaml`.

Note from 2.6 that slot C's trigger set differs from A and B on the same board
type: 0, 1, 2, 4, 5, 11 rather than 0, 1, 2, 3, 5, 6. Using slot A's or B's
config on slot C produces a FAIL that is a config error and not a hardware fault.

## 5.3 Pedestal on slot C

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
PYTHONPATH=$PWD/analysis \
  python3 pedestal_run.py -d MuxC -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/initLD-Left-3b_muxC_ped.yaml
```

Or, with the bring-up, the gate, N runs and the CRC table:

**(on the lab computer)**

```bash
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 LLeft 10000
```

**Slot C specific, settled by measurement:** keep `L1A_offset_or_BX: 13` with
`method: 'automatic'`. Do not "correct" it to 14 even though the finder writes
14, and note that **20 decodes nothing**. Automatic beats manual 36 of 36 against
18 of 36 here, because manual 13 and manual 14 fix complementary halves while
automatic gets all six.

## 5.4 Hexmaps and common mode for slot C

Identical to 3.4 with `MuxA` replaced by `MuxC`.

## 5.5 Slot C notes

Slot C matches slot B on quality: robust σ **0.741 ADC**, 60 of 60 half-ROCs
below corruption 1.0 over ten pedestals.

---

# 6. Common mistakes

## 6.1 Never do these

| never | why, and what it costs |
|---|---|
| **Run the ZL30274 clock step** (`i2cset -y 0 0x70 1` plus `zl30274_configurator.py`) | It wrecks the PL I2C master. The chip sits on the Kria's PS I2C rail, so no `kconn_pwr` cycle reaches it. Recovery is a mains power cycle. Any multiplexer documentation telling you to run it is an outdated snapshot |
| **`i2cdetect -y 2`, or any `--readback`** | Reads wedge this I2C master, and even a read of a device that is present sometimes does it |
| **Hammer a non-responding ROC** | Same wedge, reached faster |
| **Re-run bring-up while `zmq_server` is running** | It reloads the bitstream, renumbers the gpiochips, and silently orphans the Multiplex hold. You get six dead DAQ links and twelve good trigger links |
| **`systemctl start zmq-server@X` or `daq-server.service`** | Those run the RPM copies, which have none of the bench fixes. Start both by hand |
| **Go straight to a pedestal** | See 1.1. A pedestal on an unaligned slot is a 240 s timeout per run and can take `daq-server` and the puller down |
| **Reuse a `daq-client` between runs** | One that saw a failed START silently produces data that decodes to nothing. Restart it per run |
| **Drop `-I`** | `daq-server` never leaves `created` and the client spins forever |

## 6.2 The traps that look like results

Each of these reads as a result and is not one.

1. **`no ROCs` on every slot after a hardware change.** Check the physical
   pieces before spending a single bring-up: **the loopback first**, then the
   cables you just unplugged, then module seating. The loopback is the easiest
   thing to forget and nothing in software reports it. The data cable between the
   power management board and the mux board is the other one: leave it unplugged
   after a swap and `EN_Mx` never reaches the slots.
2. **Healthy total entry counts while every lane is broken.** Entry count is the
   gate, per-half corruption is the metric, and neither means anything alone.
3. **`corruption == 0` on a dead half.** A half reporting corruption 0 with
   `adc_mean = adc_stdd = adc_iqr = 0` on every channel is producing well formed
   packets full of zeros. A real pedestal half sits near `adc_mean ≈ 94`.
4. **Low corruption on a low yield run.** A run that decodes 216 of 10 000 events
   reports near zero corruption on all six halves and looks perfect: the `.raw`
   is full size and the unpacker stopped early. This trap is easier to fall into
   on a partial, which legitimately produces fewer rows, so compute the expected
   row count from the board's actual chip and channel complement.
5. **A stale identify line.** After the first `initialize` in a server process,
   the ROC type read frequently returns `[0, 253, 104]` instead of
   `[0, 125, 104]`. The process stays alive and 5555 stays listening, so `pgrep`
   and `ss` look healthy while every `initialize` returns `error:` and the ROCs
   keep stale config. Confirm `Identify a board with HGCROC` is the **last**
   identify line in the log. Recovery is a fresh bring-up; restarting
   `zmq_server` alone does not clear it.
6. **Config applied only on the first `initialize`.** Later runs report numbers
   for settings that were never applied. Always read the register back.

## 6.3 Symptom to action

| symptom | do |
|---|---|
| Everything returns `[Errno 5]`, switches do not ACK | Bring-up in the recover form. Expect to run it twice |
| `KeyError: 'dac_hyst_toa'` | ROC type mis-detected and fell back to Siv3. Redo bring-up plus i2c-server |
| Client hangs at `ROC(s) CONFIGURED` | `daq-server` is dead or stuck in a previous unfinished run. Restart it |
| `status after start cmd : configured`, repeating | **Interrupt at once.** An e-link is unaligned and `start()` retries forever; the backlog can crash the puller and `daq-server`. Read `~/daq-server.log` for which link, then re-run bring-up |
| `status after start cmd : created`, repeating | You dropped `-I` |
| 6 DAQ links dead, 12 trigger fine | Multiplex hold lost. `gpiofind Multiplex_A` and `ps aux \| grep "[g]pioset"`; the chip numbers must match |
| 0 of 12 trigger, DAQ fine | The trigger claim is on another slot. Restart `daq-server` and scan this slot first |
| All 12 trigger links `ngood=0`, DAQ perfect | Wrong `in_inv_cmd_rx` for the ROC revision. v3C is 1, v3D is 0 |
| `.raw` unpacks to 0 entries | Stale puller. Restart `daq-client` |
| `unpack: command not found` in `pedestal_run0.log` | The install's `bin` was not on `PATH` in the shell that launched the run. Section 0.6a |
| `source .../ROCv3-alper-dev/etc/env.sh` gives `No such file or directory` on the client | Correct behaviour: `env.sh` is installed only by the server build. Set `PATH` instead. Section 0.6a |
| cmake says `/hexactrl-script/analysis does not contain a CMakeLists.txt`, then `make` says `No targets specified` | The nested submodules were never fetched. `git submodule update --init --recursive` in `hexactrl-sw`. Section 0.4 |
| cmake reports `Found PythonInterp: .../miniforge3/bin/python3` | A conda environment is active. `conda deactivate`, delete the build directory, configure again. Section 0.6a |
| `make` fails on `yaml-cpp/yaml.h` or `zmq.hpp: No such file or directory` | `yaml-cpp-devel` and `cppzmq-devel` are missing. cmake never checks for them, so this only shows up in `make`. Section 0.6a |
| `$MM/puller.sh: No such file or directory`, and no `multimodule/` at all | The submodules were never fetched, or the clone predates the merge of the scripts upstream. `git pull --ff-only` then `git submodule update --init --recursive` in `hexactrl-sw`. Section 0.4 |
| `dnf` answers `No matching Packages to list` for the firmware, and `dnf repolist` shows `HCGAL-DAQ-SW` alone | The `hgc-online-sw` repo file was never written. Section 0.8c |
| `ZMQError: Address already in use` on 5555 | `ssh kria 'pkill -f "[z]mq_ser""ver.py"'` |
| `daq-client` cannot bind 6001 | An old one is still alive. `pkill -f '[d]aq-client'` |
| Orphaned holders after a killed server | `pkill -f 'gpioset -m signal -b'` |
| `daq-client` exits with `std::length_error` or signal 6 | It was sent the run twice by a START refusal spin. Full reset: restart `daq-server`, re-run bring-up, restart the puller |
| `elink link_capture_daq.linkN is not aligned` | A DAQ link failed to init, which happens about once a session. Re-run bring-up. `--realign` does not fix it, because the delay block is fine and the word aligner needs the `linkReset` that a full configure issues |
| `gpiofind: Permission denied` | The gpiochip udev rule is missing. Section 0.8f |
| `daq-server` logs `Permission denied` then `impossible to process configure when state is Error` | The uio udev rule is missing. Section 0.8f. Every configure is rejected until `daq-server` restarts |
| Bring-up dies at `[pwr]` with `[Errno 2] ... '/dev/i2c-2'` | Freshly booted Kria with no bitstream. `fw-loader load` first |
| Repeated `[Errno 13] Permission denied: '/dev/i2c-2'` after many reloads | The overlay reload is re-creating the node slower than udev sets the group, which takes roughly 40 reloads in a day to reach. Reboot the Kria |
| `ROC addresses [...] do not match a known board` | Read the printed address list. It is usually a bad bring-up rather than a wrong board type |
| Bring-up prints `board X needs all N of [...]; ['0x58'] never answered` | One chip is silent while its neighbours on the same I2C sub-bus answer. The bus is fine; that chip's contact, reset or local rail is not. Reseat; if the same address is missing in every slot, the board is the fault |
| `retry 5/5` at the `[pwr] power management board 0x27` line, first bring-up after a power cycle | The power board is not in the loop, so `0x27` cannot ACK. The module is fed directly: use `--external-power`. One `--recover --external-power` bring-up clears the wedge without a power cycle |
| Supply reads 0.4 to 0.5 A on a channel with nothing brought up | Normal: that slot's rail is on and its ROCs are idle. Three configured LD chips draw about 1.9 A, three HD chips about 2.2 A |

## 6.4 When only the power button will do

- **Retries climb from 1/5 to 5/5 across successive runs, ROCs dropping mid
  config.** The PL I2C master is wedged. `up_verified.sh` retries 8 times per
  call, so a handful of failed calls is 40 bring-ups; count the retries in
  `~/bu_<slot>.log` rather than the outcome, and stop as soon as they are being
  exhausted instead of succeeding on attempt 1 or 2. `--recover` does not help
  once it has reached this state. Either `sudo shutdown -h now` plus a power
  button cycle, or rest the bench. Afterwards prove the bus on a known-good slot
  before spending another bring-up on the suspect one: `no ROCs` measured on a
  sick bus says nothing about the module.
- **It gets worse every run and `0x71` or `0x73` stops ACKing entirely.** The
  clock synthesizer. `kconn_pwr` cannot reach it. Halt and mains cycle.

Plan the session around this. Rest first, then spend the good bring-ups on the
measurement you actually care about.

## 6.5 A few smaller ones

- **`pkill -f "zmq_server.py"` over ssh kills your own ssh command**, because the
  remote `bash -c` line contains that string. Use `pkill -f "[z]mq_server.py"`,
  and keep the literal string out of the rest of the command. The same applies to
  `daq-server` and to `daq-client` on the client.
- **Do not leave `daq-server` running after a hand driven probe.** If you call
  `daqController.start()` yourself, call `stop()`. Otherwise every later run
  fails at START.
- **The Kria logs in UTC.** So do the run directory names and `module_ids.json`.
  Convert once, at the point you read a wall clock.
- **Use `MMTS_L1A_LOG2PERIOD=10`.** Never worse than the default and 50 times
  gentler on the ROCs.
- **Never add an `rm -rf` of the results root to `remap_all.sh`.** The runs
  themselves live under `Results/<serial>/`, so a line like
  `rm -rf Results/320[TX]*` deletes the data, not just the plots.

---

# 7. Changes

Dated provenance for the numbers and rules above, kept out of the procedure
itself. Newest first.

| date | change |
|---|---|
| 2026-09-03 | The output root is now `Results/` rather than a site-named subdirectory of it. `RESULTS_DIR` in `site.sh` is the one place that sets it |
| 2026-09-03 | The MMTS scripts branch was merged into `hexactrl-script:ROCv3-alper-dev` as `ffb42a2`, and `hexactrl-sw` MR !56 bumped the submodule pointer to it, so the scripts and configs are upstream. Section 0.4 loses the `tvami` fork remote and the branch checkout: `git clone --recurse-submodules` is now the whole step, and the submodules are correctly detached at their pinned commits |
| 2026-09-03 | The client-side `source .../etc/env.sh` line was wrong throughout and is now `export PATH=.../bin:$PATH`. `CMakeLists.txt` installs `env.sh` inside `if( NOT BUILD_CLIENT )`, so it exists only on the Kria, and it holds cactus and uHAL paths the client has no use for. The 0.8b occurrences are server-side and stay |
| 2026-09-03 | First install from these instructions on a fresh AlmaLinux client, completed end to end, found four gaps now fixed in 0.4, 0.6a and 0.8c. The clone step initialised only `hexactrl-script` and left the nested `analysis` and the sibling `zmq_i2c` empty, stopping the build at `add_subdirectory(analysis)`; the first repair for that was itself wrong, since a top-level recursive update resets `hexactrl-script` off the fork branch, so the nested update is now run from inside the submodule. cmake takes its interpreter from `PATH`, so an active conda base built against Python 3.12. `yaml-cpp-devel` and `cppzmq-devel` were missing from the package list, and since cmake never checks for them the failure came minutes later in `make`. And the firmware repo file of 0.8c had never been written on the bench Kria, so `dnf` answered `No matching Packages to list` for every firmware release |
| 2026-09-03 | Bench Kria upgraded from `2026_07_20_23_20_01.45587078` to `2026_09_01_16_56_41.49751f37`. The superseded build predates the DAQ RX equalisation, so any CRC or dead-DAQ-link result recorded on this bench before this date is an unequalised measurement |
| 2026-09-03 | Bench scripts moved into `hexactrl-script/multimodule/`, so there is no separate bench repository to clone and every site value lives in `site.sh`. `hexactrl-sw` is built from source on both the client and the Kria; the CI-artifact route is gone. Configs reduced to exactly one per geometry per slot, `<family>_mux<SLOT>_ped.yaml`, with the family named for the geometry: `initLD-Full-3b`, `initLD-Five-3b`, `initLD-Left-3b`, `initLD-Bottom-3b`, `initHD-Full-trophyV3`, `initHD-Top-trophyV3`, `initHD-Bottom-trophyV3`, `initHD-Semi-trophyV3`. The bring-up script is now `enableROCs.py`, and it exits 1 when a `--board` address set comes up incomplete instead of reporting a partial enable as success |
| 2026-09-01 | DAQ RX equalisation merged into `feature/multiplexer_board_v2` as `49751f37` and released, so the design has no `-rxeq` suffix any more. Measured against the unequalised build: CRC pass 0.000 to 1.000 on all three slots, `badBX` 0.10 to 0.000, eye 8 taps to 64 |
| 2026-08-31 | HD Full characterised on a supply with headroom: 4.43 A at 1.72 V for six chips, 12/12 DAQ links, CRC 1.000 on all twelve halves over 25 runs. At the current limit the rail sagged to 1.35 V and all 24 e-links died, which is where the clipping section of 1.0 comes from. `in_inv_cmd_rx` measured both ways on a v3D board: 0 gives 8/12 trigger, 1 gives 0/12. `--module N` added after a wrong `EN_Mx` bit cost a reseat and a full power-down |
| 2026-08-30 | `hexactrl-sw` MR !55 and `zmq_i2c` MR !24 merged: the `fifo_latency` mask fix, rebuilding `HwInterface` when `uhal_device` changes, skipping a trigger elink whose chip has no DAQ elink, and the offset finder skipping unreachable links rather than refusing the slot |
| 2026-08-28 | Slot C settled on `L1A_offset_or_BX: 13` with `method: 'automatic'`, which beat manual 36 of 36 against 18 of 36 |
