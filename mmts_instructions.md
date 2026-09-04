# MMTS setup and operation, for Module Assembly Centers

Multi-Module Test System: three hexaboards in one hexacontroller, measured one
slot at a time. This document takes you from a bare AlmaLinux client and an
unflashed Kria to pedestals on all three slots.

**Conventions.** `$MMTS_ROOT` is the working directory on the client,
`$KRIA_IP` is the hexacontroller's address, `$SLOT` is `A`, `B` or `C`, and
`$MM` is the scripts directory, `$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule`.
Set them once in section 0.5.

Every code block is labeled with where it is typed: **the lab computer**, which
is the AlmaLinux client, or **the Kria**. A block labeled for the lab computer
may still act on the Kria through `ssh`; that is the normal pattern here, and
only a handful of steps have to be typed on the Kria itself.

---

## Contents

- [0. From a bare AlmaLinux client to a working bench](#0-from-a-bare-almalinux-client-to-a-working-bench)
- [1. Powering up](#1-powering-up)
- [2. Board types: choose your parameters first](#2-board-types-choose-your-parameters-first)
- [3. Running a slot: the common procedure](#3-running-a-slot-the-common-procedure)
- [4. LD Full (LF)](#4-ld-full-lf)
- [5. LD Five (L5)](#5-ld-five-l5)
- [6. LD Left and LD Right (LL, LR)](#6-ld-left-and-ld-right-ll-lr)
- [7. LD Bottom and LD Top (LB, LT)](#7-ld-bottom-and-ld-top-lb-lt)
- [8. HD Full (HF)](#8-hd-full-hf)
- [9. HD Top (HT)](#9-hd-top-ht)
- [10. HD Bottom (HB)](#10-hd-bottom-hb)
- [11. HD Semi (HL, HR)](#11-hd-semi-hl-hr)
- [12. Common mistakes](#12-common-mistakes)
- [13. Changes](#13-changes)

Sections 4 to 11 are one per hexaboard type, each with a subsection per slot.
Section 3 is the procedure they all share, so read it once and then work from
your board's section.

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
directory name is yours to choose, and `GUI_HEXMAP` in 0.5 records it.

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

Resulting layout. `Results` is the default output root; `RESULTS_DIR` in 0.5
moves it.

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

Set these once in `~/.bashrc`. Every value is either a path you chose in 0.4 or
something about your own bench. **`KRIA_IP` is the one line you must change**:
put your hexacontroller's address there, exactly as you would type it into
`ssh`, with no quotes, braces or `${...}` around it. The rest can be pasted as
they are unless you moved something.

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

Plain `export NAME=value`, nothing else: no quotes around the address, and no
`${NAME:-default}` fallback syntax, which typed at a prompt does not do what it
looks like.

Then open a new shell, or `source ~/.bashrc`, and check that all of it took:

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

🔑 **The `case` is there because the raw form of this check reads backwards.**
Nothing listens on 5555 until a bring-up starts the i2c-server, so the healthy
answer is a refusal: run bare, it prints `Connection refused` and `exit=1`, which
looks like a failure and is the result you want. What it proves is that the
packet reached the Kria and something sent an RST back, so the address is right
and nothing is silently dropping it. The failure is the opposite, a five second
silence, `rc=124`, which is a wrong `KRIA_IP` or a firewall.

| variable | what it is |
|---|---|
| `MMTS_ROOT` | the directory from 0.4, the parent of `hexactrl-sw` |
| `MM` | the bench scripts, `hexactrl-script/multimodule` |
| `SCRIPTS` | `hexactrl-script` itself, where `delay_scan.py` lives |
| `KRIA_IP`, `KRIA_USER` | **your hexacontroller**, user `daq` by default |
| `HEXACTRL` | the install prefix from 0.6a |
| `MMTS_VENV` | the virtualenv from 0.6b, or empty for system-wide |
| `MMTS_FW` | the firmware design, see 0.8e |
| `RESULTS_DIR` | the output root |
| `GUI_HEXMAP` | the `gui-hexmap` clone from 0.4 |

The scripts read these names from the environment through `$MM/lib.sh`. Two
are required, `MMTS_ROOT` and `KRIA_IP`, and a script stops on its first line
naming the missing one. The rest default to the values in the block above when
unset, so on a standard install only `KRIA_IP` carries information. Override any
of them for a single run on the command line, for example
`MMTS_FW=... "$MM/delay_scan.sh" B`.

Two of these fail in ways that do not look like a wrong variable, which is why
the check block above is worth the ten seconds:

🛑 **A wrong `KRIA_IP` hangs rather than errors.** `delay_scan.py` waits forever
at `Initializing i2c sockets` with a perfectly healthy Kria at the other end of
the room, and **`ssh kria` keeps working throughout**, because that resolves
through `~/.ssh/config` from 0.3 rather than `KRIA_IP`: every bring-up, every
log and every port check on the Kria succeeds, and only the ZeroMQ connections
fail. The scripts check that the variable is set, not that it is right; the
`/dev/tcp` line above checks that it is right.

🔑 **`SCRIPTS` unset fails silently.** `cd ""` is a no-op that returns success, so
`cd "$SCRIPTS"` does not stop: it leaves you wherever you were and runs
`delay_scan.py` there. The error names a directory you never chose, which reads
as a broken clone rather than an unset variable. Only the hand-typed commands of
sections 3 to 11 use it; the scripts derive it from their own location.

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

Confirm what landed. The `ls` must show `daq-client`, `hitproducer` and `unpack`:

**(on the lab computer)**

```bash
ls /opt/hexactrl/ROCv3-alper-dev/bin
```

Every shell that runs a client command needs that directory on `PATH`, which the
`~/.bashrc` block of 0.5 already does with `export PATH=$HEXACTRL/bin:$PATH`.

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
hand-driven commands of sections 3 to 11, not for `run_slot.sh` and its kin.

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
rebuild it if it is not the system one. With the venv active, `which python3`
must be `$MMTS_ROOT/venv/bin/python3` and the `ls` must show `python3.9` on
AlmaLinux 9. The `conda deactivate` is needed only if a `(base)` prompt is
showing, and the last two lines only if the version is wrong:

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
| `run_slot.sh` | **one slot end to end**: bring-up, gate, N pedestals, finder line, hexmaps, per-half check. This is the command a routine measurement uses |
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

Sections 3 to 11 give the underlying commands as well, so you can drive the whole
procedure by hand if you prefer.

**What you see while they work.** `run_slot.sh` prints a banner per stage and
then that stage's output as it happens. `up_verified.sh` prints one line when a
bring-up try starts and one when it ends, so a silent minute is a try in
progress; `delay_scan.sh` says it is scanning, names the log it keeps, and
prints the gate. Section 3 says what each step prints and how long it takes,
and which log to `tail -f` in a second terminal when you want the detail.

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
| `up_verified.sh SLOT [--external-power] [--board NAME] [--module N]` | kills any i2c-server left from the previous slot, runs `mmts_bringup.sh` up to 8 times and the i2c-server up to 3, announces each try, and reports `READY` only when the ROC count matches `EXPECT_ROCS`, nothing says `FAILED`, the board identified, and ports 5555 and 6000 both listen |
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
equalization. `dnf install multimodule-hd-tester-trophy-v3` gets you that, and so
does a routine `dnf update` with this repository enabled.

🔑 **The release string must be `2026_09_01_16_56_41.49751f37` or later**, the
build that carries the DAQ RX equalization of 0.8e. Earlier ones do not, and the
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
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
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

That `grep` must report 1 for each of the three files. Each generated table also
loses four lines against the shipped one, the two trigger blocks of each of the
other two slots.

**If the `grep` already reports 1 for all three, the tables are made and you can
skip to the `connections.xml` step below.** The loop is safe to re-run in any
case: it rebuilds each file from the shipped table and overwrites, so running it
twice gives the same result as running it once.

Now `connections.xml`, which needs one entry per slot alongside the stock `TOP`.
This rewrites the whole file rather than asking you to edit XML by hand, and
keeps a `.orig` of the shipped version the first time it runs:

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

That `grep` must print 3. If it already printed 3 before you ran the block, the
file is already correct and the block only rewrites it identically.

⚠️ `connections.xml` belongs to the firmware RPM, so **a firmware install or
upgrade puts the stock `TOP`-only file back**. Re-run the block above after every
install, per 0.8c. The `fw_block_addresses_{A,B,C}` files are yours and survive,
so the table loop does not need repeating.

### e. The equalized bitstream

🔑 **Check your firmware release before trusting a pedestal.** An unequalized
build leaves the DAQ inputs with `IBUF_LOW_PWR` on, and four of the six DAQ
e-links then fail 100 % of CRCs while looking healthy on entry counts: halves
c0h0, c0h1, c1h0 and c2h1 read exactly 0.000. Equalized against unequalized, CRC
pass goes 0.000 to 1.000 on all three slots, `badBX` 0.10 to 0.000, and the eye
8 taps to 64.

The equalization sets `IBUF_LOW_PWR FALSE` and `EQUALIZATION EQ_LEVEL4` on the
DAQ inputs, in `designs/multimodule-hd-tester-trophy-v3/xdc/daq_rx_eq.xdc`.
Levels are uncalibrated, and `EQ_LEVEL4` is the one that gives 100 % CRC pass on
every link; `EQ_LEVEL2` recovers them but leaves 1 to 4 % error on two, and
`IBUF_LOW_PWR` alone changes nothing. These are I/O properties only, so no logic,
address map, software or routed timing changes with them.

Install the RPM of 0.8c and set `MMTS_FW=multimodule-hd-tester-trophy-v3`. Read
the commit out of the RPM's release string to confirm what you have:
`2026_09_01_16_56_41.49751f37` or later carries the equalization. A copied build
directory carries no such stamp, which is a reason to prefer the RPM.

⚠️ **`MMTS_FW` is not sticky.** `enableROCs.py` re-points `active` on
every run, so a bring-up without it silently reverts the bench to stock. Check
after every bring-up:

**(on the lab computer)**

```bash
ssh kria 'readlink /opt/cms-hgcal-firmware/hgc-test-systems/active; dmesg | grep "fpga0: writing" | tail -1'
```

### f. Open the three ports

The client drives the bench over ZeroMQ, so a listening socket on the Kria is not
enough: the packets have to arrive. A stock AlmaLinux firewall on either machine
blocks them, and the symptom is not a connection error but a **hang**, which
reads as a broken bring-up rather than a network problem.

Three ports, and they do not all belong to the Kria:

| port | listens on | carries |
|---|---|---|
| 5555 | the Kria | the i2c-server, ROC configuration |
| 6000 | the Kria | `daq-server`, run control |
| **6001** | **the lab computer** | the event stream, pushed back by `daq-server` |

**(on the Kria)**

```bash
sudo firewall-cmd --permanent --add-port=5555/tcp --add-port=6000/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

**(on the lab computer)**

```bash
sudo firewall-cmd --permanent --add-port=6001/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

🛑 **That last line must print `6001/tcp`, and an empty answer is the failure to
look for.** A stock AlmaLinux client runs firewalld with no ports open at all, so
`--list-ports` prints a blank line and everything in section 0 still passes: the
client only ever dials *out* to the Kria until the first run. The cost lands much
later and does not look like a firewall. The bring-up is clean, the scan
initializes, configures and reaches `status after start cmd : running`, and then
nothing arrives for 180 s, because `daq-server` is pushing the event stream at a
port that is dropping it. The gate then says `no summary.json`. Seen on a new
client on 2026-09-04, three minutes per attempt.

Prove reachability from the client rather than trusting `ss` on the Kria, since
`ss` only tells you something is bound locally:

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

`PASS` here means the packet arrived and got an answer, either from a listening
server or as a refusal. **A refusal is a pass**, and until a bring-up has run
that is the only answer either port can give, since nothing is listening yet.
Only the timeout is a fault, and it is silent, which is why the `case` prints a
verdict rather than leaving you to read `Connection refused` and guess.

🔑 **Then test 6001 in the other direction, which is the one no other check in
this document covers.** Start the puller so something is listening, and dial the
client from the Kria. Substitute your client's address, which the Kria's own
login banner shows as the host you connected `from`:

**(on the lab computer)**

```bash
"$MM/puller.sh"
ssh kria "timeout 5 bash -c 'cat < /dev/tcp/<client-ip>/6001'; echo rc=\$?"
```

`rc=0` or `rc=1` is a pass. `rc=124` is the closed client firewall above, and it
is worth ten seconds here because the same fault costs 180 s per scan later and
presents as a hung run rather than as a network problem. If your
site uses `iptables` or `nft` rather than `firewalld`, open the same three ports
with those instead.

### g. Device permissions

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

All of it is typed on the lab computer. The first four lines check the Kria over
`ssh`; the rest check the client stack, which exists only on the lab computer.

**(on the lab computer, checking the Kria)**

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria 'ls -l /dev/i2c-2 /dev/uio0; gpiofind Multiplex_A'
ssh kria 'grep -c "id=\"TOP_[ABC]\"" /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml'
ssh kria 'cd ~/multimodule && python3 findslot.py'
```

The `grep` must print `3`. Anything else means 0.8d is not done, or a firmware
install has put the stock file back, and the failure it causes comes much later
and looks like something else: the bring-up is clean, the scan runs, and the gate
says `no summary.json` because `daq-server` logged `Device ID , "TOP_A", does
not exist in connection map` and rejected every configure. Ten seconds here
against an hour there.

**(on the lab computer, checking the lab computer)**

```bash
source "$MMTS_VENV/bin/activate"
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

### What to do when `findslot.py` fails instead

🛑 **`mux GPIO write failed ([Errno 5] Input/output error)` or `bus wedged during
probe` is a different result from `no ROCs`, and it is a fault.** `no ROCs` means
the bus worked and found nothing; `[Errno 5]` means the write never completed, so
the PL I2C master, not the module, is what answered:

**(expected output of a failure, not a command)**

```
slot A: mux GPIO write failed ([Errno 5] Input/output error)
slot B (switch 0x73): no ROCs [bus wedged during probe]
slot C: mux GPIO write failed ([Errno 5] Input/output error)
```

**Do not try to fix it from here. Go on to section 1 and power the bench up in
the documented order**, then come back and run `findslot.py` once more. The usual
cause at this point is simply that nothing has powered the bench yet: a freshly
booted Kria has payload power off, `findslot.py` does not turn it on, and 1.2 is
the step that does. If the probe still fails after a clean cold start, 12.3 and
12.4 cover the wedge and its recovery.

Two things not to do meanwhile, because both make the fault worse rather than
diagnosing it: re-running `findslot.py` over and over, and reaching for
`i2cdetect -y 2` to see whether the bus is alive. Reads wedge this master, so
that check causes the very fault it is looking for.

---

# 1. Powering up

🔑 **Read your board's row in 2.7 before you run anything here.** Every bring-up
command in this section takes three values that come from the board type, not
from the bench: `--board`, the ROC count in `EXPECT_ROCS`, and whether the module
has a power distribution board, which decides `--external-power`. Getting them
from the wrong row is not a harmless mistake. `--external-power` on a board that
has a power distribution board skips the `0x27` `EN_Mx` write that powers the
module, so the module stays dead and every probe reads `no ROCs`.

The short version of that table, which is all this section needs. The `--board`
names are the ones `enableROCs.py` accepts, and `any` probes every V3 address and
enables whatever answers, which is what to use on a board type you have not run
before:

| board | `--board` | `EXPECT_ROCS` | power distribution board |
|---|---|---|---|
| LD Full | `LD-Full` | 3 | fitted |
| HD Full | `HD-Full` | 6 | fitted |
| LD Five | `LD-Five` | 3 | none |
| LD Left, Right, Bottom, Top | `LD-Semi` | 2 | none |
| HD Top, Bottom, Semi | `HD-Top`, `HD-Bottom`, `HD-Semi` | 3, 4, 2 | none |
| unknown | `any` | read it off the probe | check the board |

The examples below use an LD Full, the three-ROC board with a power distribution
board fitted, and give the partial form where it differs.

⚠️ **The two wrappers default the opposite way, so never copy a power flag from
one to the other.** `enableROCs.py` and `up_verified.sh` assume the power
distribution board is there and take `--external-power` to say it is not.
`bench_up.sh` assumes it is not and takes `--power-board` to say it is. An LD
Full therefore needs no power flag in the first pair and `--power-board` in the
second, and both mistakes produce the same symptom: a module that never powers up
and reads `no ROCs`.

## 1.0 Size the supply BEFORE you trust any measurement

🔑 **A module at its supply's current limit produces data that looks like broken
hardware.** On an HD Full at the limit the rail sags from 1.72 V to **1.35 V**
and **all 24 e-links die**. With headroom the same module gives 12/12 DAQ links
and CRC 1.000 on every half.

| board | measured draw at 1.72 V |
|---|---|
| any slot, rail on, ROCs idle | 0.4 to 0.5 A |
| LD Full, three chips | ~1.2 A enabled, **1.9 to 2.0 A** configured and running |
| LD partials, two chips | ~1.2 A |
| HD Top, three chips | ~2.1 to 2.2 A |
| **HD Full, six chips** | **4.43 A** |

The meter reads 0 A for a moment during every bring-up: `--recover` turns
payload power off before it turns it on again. A reading taken while the log sits
at `Turning off payload power` means nothing. Read it after `Turning on payload
power`, and again while a scan or run has the chips configured.

⚠️ **Many bench supplies are ~3.2 A per channel and cannot run an HD Full on one
channel.** On a SIGLENT SPD3303X-E, CH1 and CH2 are 0-3.2 A each and this is a
**hardware maximum, not a settable compliance**. Press **`Para`** to link them
into one 0-6.4 A channel:

* both leads go on **CH1 only**, whose terminals are labeled `Para Out`; CH2's
  terminals stay empty;
* set the voltage on CH1 and leave the current at its per-channel maximum, since
  the doubling happens in hardware and asking for 6.4 A gives
  `current setting overrange`;
* 🛑 **never wire `+CH1 / −CH2`**. That is the *series* pattern, and in `Ser`
  mode it puts **double** the set voltage on the board.

**How to tell you are clipping**, since this is the failure that wastes days: the
on-screen mode reads **`CC`** and the **output voltage is below the setpoint**.
Both halves matter, because in parallel mode the slave channel always reads `CC`
and that on its own is normal.

**What clipping imitates.** Each of these is the sagging rail, and each reads as
a hardware fault:

* the meter wandering between plausible values with nothing running;
* consecutive bring-ups finding a **different number of ROCs** (4 of 6, then 6
  of 6). ROCs enable sequentially and the rail sags as they come up, so the
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

## 1.2 Powering the bench without a bring-up

🔑 **Skip this section if your next command is a bring-up.** `mmts_bringup.sh`
and `up_verified.sh` default to `--recover`, which does exactly these two things
and a `kconn_pwr off` first, before it touches I2C, so a wrapper bring-up on a
freshly booted Kria needs nothing in front of it. This section is for the case
where you want the bench powered and are **not** about to run one.

A freshly booted Kria has no bitstream, and payload power is off. There are two
occasions to fix that by hand. One is a `findslot.py` that failed with `[Errno 5]`
at 0.9: run these, then probe once more before concluding anything about the bus.
The other is driving `enableROCs.py` yourself, which defaults the opposite way
from the wrappers, per the warning below.

**(on the lab computer)**

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria 'sudo kconn_pwr on'
```

⚠️ `enableROCs.py` has no `--no-recover` flag. Plain is the default and
does not cycle power; `--recover` opts into the `kconn_pwr off` then
`fw-loader load` then `kconn_pwr on` sequence. After a mains cycle use the
recover form, or do the two commands above by hand first. Otherwise every probe
returns `no ROCs` against an unpowered bus, with all writes still ACKing.

🔑 **The wrappers already do this for you, so do not conclude that a failed
bring-up was missing `kconn_pwr`.** `mmts_bringup.sh` sets `--recover` as its
default and takes `--no-recover` to turn it off, and `up_verified.sh` passes your
flags straight through to it. The default is therefore opposite to
`enableROCs.py`'s, and a bring-up run through either wrapper has cycled payload
power on every attempt.

## 1.3 The bring-up wrappers

There are two, and picking the wrong one is what makes a bad bench feel
mysterious. **`mmts_bringup.sh` for a first bring-up or when anything is wrong;
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
`mmts_bringup.sh`.** It runs once and puts the real error in front of you. Its
`--recover` default means it still cycles payload power, so it is a complete
bring-up and not a reduced one:

**(on the Kria)**

```bash
pkill -f '[z]mq_server'
cd ~/multimodule && ./mmts_bringup.sh A --board LD-Full
```

🛑 **Stop here and read the result before typing anything else.** Go on only when
the bring-up ended in its ROC list, `3 ROC(s) enabled [...]` for an LD Full, per
1.4. If it ended in `bring-up failed`, or in a traceback, the next step is 12.3
and 12.4, not this one.

**(on the Kria, only after the bring-up printed its ROC list)**

```bash
~/start_i2c.sh A
```

⚠️ **This block is not optional, and nothing reminds you of it.**
`mmts_bringup.sh` brings the slot up and restarts `daq-server` on 6000, but it
does **not** start the i2c-server on 5555; only `start_i2c.sh` does, and
`up_verified.sh` is what normally calls it for you. Skip it and the bring-up
looks perfectly healthy while the next scan sits at `Initializing i2c sockets`
with nothing to talk to. `ss -ltn | grep -E '5555|6000'` must show both.

`start_i2c.sh` takes about 25 s and ends by printing the identify line, which is
the second thing to read: **`Identify a board with HGCROC Siv3b`** is what you
want, and plain `Siv3` means redo the bring-up rather than continue, per 1.4.

🔑 **Running it on a failed bring-up costs you the next attempt.** It starts and
binds 5555 regardless, so `--- listening ---` and an `ss` line appear under the
traceback and read as partial success. What you actually have is a server holding
the I2C bus with nothing configured behind it, and the re-run you are about to
type is then a bring-up under a live server, which is 12.1. If you have already
done it, `pkill -f '[z]mq_server'` before re-running the bring-up.

### When the bring-up fails instead

The two wrappers say it differently, and the difference is how much has already
been spent when you read it:

| message | from | means |
|---|---|---|
| `!! bring-up failed -- re-run once.` | `mmts_bringup.sh` | one attempt failed |
| `FAILED to bring slot A up cleanly -- read ~/bu_A.log and ~/zmq_srvA.log` | `up_verified.sh` | **eight** bring-ups failed, each with up to three i2c-server starts, so roughly ten minutes and eight payload power cycles are already gone |

🔑 **`up_verified.sh` failing after a hand-run `mmts_bringup.sh` that looked fine
is not a contradiction.** It does not trust the log line: a try counts as good
only when the ROC count reaches `EXPECT_ROCS`, the string `FAILED` appears
nowhere in the log, the i2c-server logged `Board identification`, and 5555 and
6000 are both listening. Any one of those can be missing behind a bring-up that
read as healthy on your screen.

**Read its per-try lines first, because they say which half failed**, and the two
halves have different causes:

* `bringup try 3: 0/3 ROCs ...` is the bring-up, and the rest of this subsection
  applies;
* `i2c try 1: 4 errors, 5555=0 ...` is the i2c-server, which is the stale
  identify trap of 12.2 or the dead-reads case of 9.4, not the bus wedge below.

Then read the logs it names, `~/bu_A.log` for the bring-up and `~/zmq_srvA.log`
for the server. Both are truncated on each launch, so read them before running
anything else.

🔑 **Re-run the bring-up block exactly once, and decide on the retry counts
rather than the ROC count.** A partial enable with a different chip missing each
time is the lottery of 1.4 and wants another go. What does not want another go is
`[Errno 5]` on the `[mux]` writes to `0x71`, `0x73` and `0x77`: those never leave
the mux board, so the PL I2C master is what is failing, not the module. Compare
the two runs, and **if the retries reach `5/5`, or reach it earlier than they did
last time, stop**. `--recover` cannot clear that state and every further attempt
degrades it. Only then, halt the Kria with `sudo shutdown -h now`, press the
power button, wait for `ssh kria` to answer again, and **restart at the bring-up
block of this section, 1.3. Nothing else has to be redone.**
Everything a reboot could cost is on disk and survives it: the udev rules of
0.8g, `connections.xml` and the per-slot tables of 0.8d, the firewall of 0.8f,
the sudoers rule of 0.3, the firmware RPM, and the Kria-side scripts of 0.7. The
cold-start lines of 1.2 are not needed either, because `mmts_bringup.sh` defaults
to `--recover`, whose `[rec]` step does `kconn_pwr off`, `fw-loader load` and
`kconn_pwr on` before it touches I2C. Only a firmware install sends you back into
section 0, and only to 0.8d.

Run the bring-ups **back to back** rather than one per boot: a slot that failed
on five separate fresh boots came up 4 of 10 in a row, with the error count
falling on every attempt. 12.4 is the long form, and it also covers the case
where a power cycle is not enough.

⚠️ **`up_verified.sh` retries what should not be retried.** Its eight attempts
are calibrated for the bring-up lottery of 1.4, where a healthy bench needs two
to four goes and each failure is a *partial* enable. Against a real fault, an
unpowered module, a wrong `--module` bit, an open power path, they are eight
identical failures that take minutes, give the I2C master eight more chances to
wedge, and show you only `0/3 ROCs` while the actual error sits unread in
`~/bu_<slot>.log`. **A run of identical zero-ROC tries is a fault, not bad luck:
interrupt it, read that log, and go back to `mmts_bringup.sh`.** 12.4 makes the
same point in terms of counting retries rather than outcomes.

Once the slot is known good, `up_verified.sh` is the one to use, because it also
starts the i2c-server and checks the things a log line will happily lie about,
including the stale-identify trap of 12.2. This is the LD Full form; your own
board type's section, 4 to 11, carries the exact line for each of its slots:

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --board LD-Full"
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

Get it wrong and you see `no ROCs` with **next to nothing on the meter**, which is
indistinguishable from a dead module, a bad trophy or a seating fault. The
default is right on a normally cabled bench, so leave `--module` off until it
fails that way. When it does, sweep the three values one at a time, keeping
`--board` and `EXPECT_ROCS` at your own board's, and watch the meter rather than
the ROC count:

**(on the lab computer, only after a bring-up gave `no ROCs` at near-zero
current; run one line at a time and stop at the one that draws current)**

```bash
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 1"
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 2"
ssh kria "MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 ~/up_verified.sh A --board LD-Full --module 3"
```

⛔ **Do not change `--board` while sweeping.** It must match the module you
actually have, from the table at the top of this section. `--board HD-Full` on an
LD Full demands all six addresses of a six-chip board and can never succeed on a
three-chip one, so it turns a one-variable sweep into a guaranteed failure that
costs bring-ups.

🔑 **Diagnostic rule.** If the probe says `no ROCs` but the **mux-board GPIO
writes succeeded**, the master, the switch and the expander are all fine, because
those writes never leave the mux board. **Sweep `--module 1/2/3` and watch the
meter before suspecting the module.** With one module on the bench, any draw at
all must be that module, so the meter identifies the correct bit immediately. If
all three read the same near-zero current, the bit is not the problem and the
power path is: see the low-current row of 12.3.

The flag is forwarded by `bench_up.sh` and `mmts_bringup.sh` directly, by
`ped_run.sh` as `PED_MODULE`, and by `slot_measure.sh` as `SM_MODULE`.

`bench_up.sh` on the client does the cold start in the only order that works, and
needs no adaptation since it only calls `ssh`. It is a commissioning and
diagnosis tool, not part of a routine measurement, which goes through
`up_verified.sh` or `run_slot.sh`. Reach for it when you want the cold start
driven from the client rather than from a shell on the Kria. The LD Full form,
with each board type's own line in its section, 4 to 11:

**(on the lab computer, when driving a cold start by hand, not in a normal run)**

```bash
"$MM/bench_up.sh" A --board LD-Full --expect 3 --power-board
```

⚠️ **`bench_up.sh` spells the power board the other way round from
`up_verified.sh`.** Here you opt *in* with `--power-board`; there you opt *out*
with `--external-power`. Leaving `--power-board` off an LD Full is the same
mistake as adding `--external-power` to one, and gives the same dead module.

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

🛑 **Read the `[I2C] Board identification` line above it as well, and stop if it
names a board type you do not have.** `Link.py` matches the exact address set, so
when a partial enable leaves a subset that happens to be *another* board's whole
set, the server identifies that other board, prints a perfectly clean `Siv3b`
line, and binds 5555. Nothing downstream contradicts it, and you get that board
type's link map applied to yours. Seen on an LD Full whose `0x28` never came up:

**(expected output of a failure, not a command)**

```
[I2C] Board identification: V3 HD Semi-left or HD Semi-right HB
Identify a board with HGCROC Siv3b
--- listening ---
```

The subsets that collide, from the table in 2.2. An HD Full is the dangerous one,
since five different board types sit inside its address set:

| you have | missing | identifies as |
|---|---|---|
| LD Full | `0x28` | HD Semi |
| LD Five | `0x68` | LD Semi |
| HD Bottom | `0x68` | HD Top |
| HD Full | `0x48 0x58 0x68` | LD Full |
| HD Full | `0x28 0x48 0x58 0x68` | HD Semi |
| HD Full | `0x08 0x18 0x28` | LD Five |

The cure is the bring-up, not the server: re-run it and require the full ROC
list, `3 ROC(s) enabled ['0x8', '0x18', '0x28']` for an LD Full. `up_verified.sh`
catches this for you, since it rejects any try whose log contains `FAILED`; a
hand-driven `mmts_bringup.sh` plus `start_i2c.sh` does not, which is why 1.3
makes you read the ROC list before starting the server. If the same address is
missing every time, it is 12.3's silent chip: reseat, and suspect the board if it
is missing in every slot.

⏳ **Give each step time.** Both look broken partway through.

| step | takes | what it looks like mid-flight, which is not failure |
|---|---|---|
| bring-up | 60 to 90 s | log stops at `Turning on payload power`, and `daq-server` is down with 6000 not listening, because it is killed before being restarted |
| i2c-server | 15 to 30 s | `IOError in mux_setup group (attempt n/5) ... Retrying.` Retries are normal and usually succeed. 5555 is not yet bound |
| a scan or pedestal starting | tens of seconds | it sits at `Initializing i2c sockets` while the ROCs are configured over ZeroMQ. A pause here is the normal case, not a hang |

Do not conclude anything until the bring-up log ends in `next:` or
`bring-up failed`, **and** the server log contains `Identify a board with HGCROC
Siv3b` or a traceback. Both logs are truncated on each launch, so a log read too
early may be the previous attempt's. Check the mtime if in doubt.

**Fewer ROCs than expected means run it again.** Bring-up needs two to four
attempts routinely on a healthy bench. A few `transient I2C error ... retry n/5`
lines are normal.

⚠️ **That applies to a *partial* enable, which is what the lottery looks like:
some ROCs answer and one does not, and a different one each time.** Repeated
`0/N`, the same result every attempt, is not the lottery and running it again
will not help. Switch to `mmts_bringup.sh` and read the error, per 1.3.

---

# 2. Board types: choose your parameters first

Everything in sections 3 to 11 depends on four values: the `--board` name, the
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

🔑 **`Top.in_inv_cmd_rx` is carried by the shipped config of each type, and the
shipped value is the measured one. Do not change it.** The wrong value leaves
every trigger link at `ngood=0` while DAQ looks completely fine, and hexactrl-sw
reports every revision as `Siv3b`, so nothing in software tells you which one
you have.

The revision rule, v3C gives 1 and v3D gives 0, holds for the LD partials and
the HD boards. **It does not hold for the LD Full**: three v3D LD Fulls gave
12/12 trigger with 1 and 0/12 with 0, on all three slots, on 2026-09-02.
Changing the shipped 1 to 0 on the strength of the rule cost forty minutes and
two wrong diagnoses. The measured values:

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

## 2.3 Where each type's parameters live

One section per hexaboard type, sections 4 to 11, each carrying its `--board`
name, ROC count, power flag, run configs, expected gate and the commands for all
three slots. Go there once you know your type; this section is only for working
out what the type is.

| type | section | `--board` | ROCs | power distribution board |
|---|---|---|---|---|
| LD Full (LF) | 4 | `LD-Full` | 3 | fitted |
| LD Five (L5) | 5 | `LD-Five` | 3 | none |
| LD Left, LD Right (LL, LR) | 6 | `LD-Semi` | 2 | none |
| LD Bottom, LD Top (LB, LT) | 7 | `LD-Semi` | 2 | none |
| HD Full (HF) | 8 | `HD-Full` | 6 | fitted |
| HD Top (HT) | 9 | `HD-Top` | 3 | none, measured |
| HD Bottom (HB) | 10 | `HD-Bottom` | 4 | not yet seen; start with `--external-power` |
| HD Semi (HL, HR) | 11 | `HD-Semi` | 2 | not yet seen; start with `--external-power` |

On the first board of a type you have not run before, probe with `--board any`
and read the printed address list before pinning `--board` and `EXPECT_ROCS`.

`slot_measure.sh` takes the same three values from the environment instead of
flags, and **`SM_EXTPOWER` is inverted relative to `--external-power`**: 0 means
the power distribution board is fitted.

**(on the lab computer)**

```bash
SM_BOARD=LD-Full SM_EXPECT=3 SM_EXTPOWER=0
SM_BOARD=HD-Full SM_EXPECT=6 SM_EXTPOWER=0 SM_MODULE=<n>
SM_BOARD=LD-Semi SM_EXPECT=2 SM_EXTPOWER=1
```

## 2.4 Measured link sets

The DAQ set follows the board type. **The trigger set depends on the slot as
well as the board type**, because the mux board's crosspoints reach the trigger
pairs in a per-slot order, so a trigger map measured on one slot must never be
copied to another. The shipped `_ped.yaml` for each slot carries its measured
set, and on the partials it keeps only a subset of the live trigger links; the
gate counts what the config lists, not what is live.

| board type | DAQ, every slot | trigger live, A | B | C | in the shipped config |
|---|---|---|---|---|---|
| LD Full | `0 1 4 5 8 9` | all 12 | all 12 | all 12 | all 12 |
| LD Five | `0 1 4 5 9` | 10 of 12 | | | A `0 4`, B `1 4`, C `1 6` |
| LD Left, Right | `0 1 4` | `0 1 2 3 5 6` | `0 1 2 3 5 6` | `0 1 2 4 5 11` | A `5 6`, B `0 3`, C `1 4` |
| LD Bottom | `0 1 4` | `1 2 6` | `1 2 5` | `1 5` | the same |
| HD Full | all 12 | all 12 | all 12 | all 12 | all 12 |
| HD Top | `0 1 4 5 9` | `0 1 5 9` | `0 1` | `0` | the same |
| HD Bottom, HD Semi | not measured | | | | a template |

For a board type or slot not in this table, measure the live links before picking
a run config. Run `run_slot.sh` **without** `SKIP_PROBE=1`:

**(on the lab computer)**

```bash
"$MM/run_slot.sh" B initLD-Left-3b LD-Semi 2 probe 3
```

It derives a twelve-link probe from that slot's own `_ped.yaml`, delay-scans with
it, writes the live set back into the config, and then re-does the bring-up
before running any pedestal. That last step is not optional: the probe arms all
twelve capture blocks and `LinkAligner` never clears `invert`, so a pedestal in
the same bring-up stalls at 64 events.

## 2.5 Trophies

Trophies are shared across geometries. LB shares with LR, and LB shares with LT.
A mismatch between the trophy's type code and the module's type code is **not**
evidence of a wrong trophy.

## 2.6 Register the board

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

Record the boards, and re-run the first command after every swap. On a new
bench it creates the results directory and the registry itself and says so:

**(on the lab computer)**

```bash
"$MM/register_boards.py" A=320XLF4DQR00332 B=320XLF4DME01621 C=320XLF4DME01744
"$MM/module_of.py" B
```

The last line prints the serial now recorded for slot B.

A slot left out of the command is recorded as empty from then on; `--at
YYYY-mm-ddTHH:MM:SSZ` backdates a swap that happened earlier. A board with no
window falls back to the flat layout and the plotter prints `module: UNKNOWN`.
Fix the registry rather than passing `-m` on every command, so the swap history
stays in one place.

## 2.7 Summary

The types that have been run. HD Bottom and HD Semi are in sections 10 and 11
with the same rows, unmeasured.

| | LD Full (LF) | HD Full (HF) | HD Top (HT) | LD Five (L5) | LD Left, LD Right | LD Bottom (LB) |
|---|---|---|---|---|---|---|
| section | 4 | 8 | 9 | 5 | 6 | 7 |
| power distribution board | fitted | fitted | none | none | none | none |
| `--external-power` | **no** | **no** | yes | yes | yes | yes |
| `--board` | `LD-Full` | `HD-Full` | `HD-Top` | `LD-Five` | `LD-Semi` | `LD-Semi` |
| ROCs | 3, at `0x08 0x18 0x28` | 6, all six | 3, at `0x18 0x58 0x28` | 3, at `0x48 0x58 0x68` | 2, at `0x48 0x58` | 2, at `0x48 0x58` |
| DAQ links | 6 | 12 | 5 | 5 | 3 | 3 |
| trigger links in the config | 12 | 12 | A 4, B 2, C 1 | 2 | 2 | A 3, B 3, C 2 |
| delay scan gate | 18 of 18 | 24 of 24 | 9, 7, 6 | 7 of 7 | 5 of 5 | 6, 6, 5 |
| run config | `initLD-Full-3b` | `initHD-Full-trophyV3` | `initHD-Top-trophyV3` | `initLD-Five-3b` | `initLD-Left-3b` | `initLD-Bottom-3b` |

Run configs are `configs/<family>_mux{A,B,C}_ped.yaml`.

---

Sections 3 to 11 assume this preamble in every client shell:

**(on the lab computer)**

```bash
source "$MMTS_VENV/bin/activate"
SLOT=A
OUT=$RESULTS_DIR/$(python3 "$MM/module_of.py" "$SLOT")
echo "SCRIPTS=$SCRIPTS KRIA_IP=$KRIA_IP OUT=$OUT"
```

Everything else, `PATH` included, comes from the exports you put in `~/.bashrc`
at 0.5. That `echo` is worth the second it costs: all three are expanded locally
by the commands below, and an empty one does not stop anything. `cd ""` silently
leaves you where you were, `-i ""` hangs, and `-o ""` writes the run somewhere
you will not find it.

`module_of.py` prints the serial for the slot, so `$OUT` lands in the by-board
layout of 2.6. If the board is not in the registry it prints nothing, and you
should use `$RESULTS_DIR` directly.

**The short form of everything in sections 3 to 11 is one command per slot:**

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" B initLD-Left-3b LD-Semi 2 LLeft 5
```

That is bring-up, gate, a one-run trial, the remaining runs, the finder
line, hexmaps and a per-half check, each stage stopping the sequence on failure
instead of burning the next stage's timeout. `POWER=` in front of it selects the
power distribution board for an LD or HD Full. The hand-driven steps below are
what it does, for when you need to see one of them on its own.

---

# 3. Running a slot: the common procedure

Every board type follows the same four steps, and only two things change with the
type: the bring-up flags and the run config. This section is the procedure with
those two left blank; sections 4 to 11 fill them in per board type and per slot.

Read your type's section for the exact commands. Come back here for what each
step means and what to do when one of them misbehaves.

## 3.1 Bring up the slot

🔑 **Skip this step if you already have a verified slot**, that is, if 1.3 has
just given you the full ROC list and an `[I2C] Board identification` line naming
your board type. Go straight to 3.2, or equivalently to the **last two lines** of
your type's slot block in sections 4 to 11, and leave its bring-up line untyped.

⚠️ **In that case do not reach for the one-command `run_slot.sh` form either.**
It always starts with its own `up_verified.sh`, because what it promises is a
verified slot, and it has no flag to skip that. On a bench where the bring-up is
going first time that costs a minute; on the bus of 12.4, where you spent several
attempts and a power cycle earning the state you are standing in, it throws that
state away and re-rolls the lottery. Hand-drive the remaining steps instead, and
keep `run_slot.sh` for a bench that brings up on the first or second try.

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=<N> \
  ~/up_verified.sh <SLOT> --board <BOARD>"
```

`up_verified.sh` first kills any i2c-server left over from the previous slot. A
bring-up under a live server reloads the bitstream out from under it and orphans
its Multiplex hold, per 12.1, and on the HD Tops it produced a chip that
`stopped responding mid-config`. Only when you call `mmts_bringup.sh` by hand,
per 1.3, is that kill yours to do.

Add `--external-power` for a board with no power distribution board fitted. Add
`--module N` if `EN_Mx` does not match the slot index, per 1.3.

**What it prints.** One line when a try starts, one when it ends, then `READY`:

**(expected output, not a command)**

```
bringup try 1 of 8: running (60 to 90 s) ...
bringup try 1: 0/3 ROCs
bringup try 2 of 8: running (60 to 90 s) ...
  i2c-server start 1 of 3: running (about 25 s) ...
READY  bringup=2 i2c=1  [I2C] Board identification: V3 LD Full HB
```

A silent minute after a `running` line is that try in progress, and there can
be eight, so ten minutes is possible. `READY` means the ROC count matched
`EXPECT_ROCS`, nothing said `FAILED`, the board identified, and 5555 and 6000
both listen. The identification must name your board type. To see inside a try:

**(on the lab computer, in a second terminal)**

```bash
ssh kria 'tail -f ~/bu_<SLOT>.log'
```

The meter tells the same story: 0 A while the log sits at `Turning off payload
power`, the slot's idle draw once `Turning on payload power` has passed, per
1.0, and the configured draw while a scan or run is in flight.

If it prints `FAILED to bring slot <SLOT> up cleanly`, read `~/bu_<SLOT>.log`
before running it again. A partial enable with a different chip missing each
time is the lottery: run it again, back to back, per 1.4. Eight identical `0/N`
tries are a fault, per 1.3, and the meter says which one: 0.05 to 0.1 A in CV
past `Turning on payload power` is an unpowered module, not a bad bus.

## 3.2 Delay scan and the gate

Always before a pedestal, never after.

**(on the lab computer)**

```bash
"$MM/delay_scan.sh" <SLOT> configs/<FAMILY>_mux<SLOT>_ped.yaml
```

`<FAMILY>` is your board type's config family, from the last row of the table in
2.7. Filled in for an LD Full on slot A, the type every worked example up to here
has used, and with the pedestal of 3.3 after it, this is the pair to type on a
slot you already brought up by hand in 1.3:

**(on the lab computer)**

```bash
"$MM/delay_scan.sh" A configs/initLD-Full-3b_muxA_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

Every other type has the same pair, per slot, in its own section: LD Five in 5,
LD Left and Right in 6, LD Bottom and Top in 7, HD Full in 8, HD Top in 9, HD
Bottom in 10, HD Semi in 11. Do not carry an LD Full config onto another type or
onto another slot, since the trigger set is per slot as well as per type, per
2.4.

That restarts the puller, scans and prints the gate in one step. It prints its
header line, then `scanning, 20 to 40 s` with the path of the log it keeps,
`Mux<SLOT>/delay_scan.log` next to the output, and then the gate. The long form
shows you the client's log as it goes:

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

In the long form the client's own log ends healthy with `status after start
cmd : running`. One `returned status (from initialize) = b'error'` followed by
`initialized`, or a `configure` that answers `error` once, is the client
retrying; whether it mattered is written in `daq-server`'s log, not the client's.

**The gate must PASS before you run a pedestal.** A failure is a retry and not a
result: re-run bring-up, which also restarts `daq-server`, then scan again. A
missed claim or a link dropped at init happens about once a session, and the
identical sequence then works on the retry, so repeat once before concluding
anything. On an HD Top the first gate read `link4=0` on DAQ and `link5=0` on
trigger, and the same bring-up run again gave full marks.

If trigger reads 0 across the board while DAQ is fine, this slot does not hold
the trigger claim. Restart `daq-server` and scan this slot first, per 1.1.

**`no summary.json -- the scan did not produce output`**, or **`STALE: newest
summary is ... written N s before this scan started`**, means the scan ran and
`daq-server` delivered nothing. The gate refuses to report an older scan's
verdict in that case, and `delay_scan.sh` prints the last lines of its own log
and of `~/daq-server.log` on the Kria under the verdict, which is where the
reason is:

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
`connections.xml`: 0.8d was skipped, or a firmware install put the stock file
back. `Permission denied` on a uio device is 0.8g. Either way the server is in
state `Error` and rejects every configure until it restarts, which the next
bring-up does for you. A scan that times out after 180 s with nothing in either
log is a `KRIA_IP` or firewall problem, per 0.5 and 0.8f.

🛑 A full-marks delay scan is **not** a health gate on its own. Idle is the
easiest pattern to sample, and a slot can score worse on eye width while
producing far better data. The real health check is an actual START plus the
offset finder's header positions.

## 3.3 Pedestal

Restart the puller first. The `daq-client` from the delay scan is not reusable.

**(on the lab computer)**

```bash
"$MM/puller.sh"
cd "$SCRIPTS"
PYTHONPATH=$PWD/analysis \
  python3 pedestal_run.py -d Mux<SLOT> -i "$KRIA_IP" -o "$OUT" \
    -I -f configs/<FAMILY>_mux<SLOT>_ped.yaml
```

`-I` is **required**. Without it `daq-server` never leaves `created` and the
client spins forever.

Or N runs in a row, each on a fresh puller, scored by CRC in one table:

**(on the lab computer)**

```bash
PED_BOARD=<BOARD> "$MM/ped_run.sh" <SLOT> 5 <label> 10000
```

Filled in for an LD Full on slot A, the type every worked example up to here has
used. `<label>` is yours to choose and only names the output; `5` is the number
of runs and `10000` the events per run:

**(on the lab computer)**

```bash
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

Each other type differs only in `PED_BOARD`, and the partials additionally need
`PED_EXTPOWER=1`; the exact line per slot is in that type's section, 5 to 11.

It runs on the slot as it stands: **no bring-up and no gate**, so 3.1 and 3.2
come first. `PED_BRINGUP=1` adds a fresh bring-up before every run, and only
then do `PED_BOARD`, `PED_EXTPOWER=1` for a board with no power distribution
board, and `PED_MODULE=N` for a bring-up that needed `--module` come into play.
Each run prints one row, about 30 s apart; `RUN-FAILED (rc=124)` is a run that
hit the 240 s timeout, and an empty run directory with it means the client hung
at initialize, per 12.3.

Keep `method: 'automatic'`. It wins because it sets **per-link** `fifo_latency`,
not because of the offset value; manual applies one shared value to every link
and can only ever fix a subset. The exception is a slot with no good lane at all,
which the finder cannot bootstrap, and there you pin `fifo_latency` and
`L1A_offset_or_BX` by hand. That is a symptom of broken links rather than a
property of a slot.

Expect about 30 s per run on a healthy slot. Minutes means the finder's phase 2
is retrying per link, which is a signal the links are marginal.

## 3.4 Hexmaps and common mode

Unpacking and analysis run automatically as long as the installation's `bin` is
on `PATH` in this shell, which the `~/.bashrc` block of 0.5 handles. A good run
writes its own `.root` and nine PNGs unattended, and no `crash_report.log` means
it worked.

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" <run-dir> -l <label> --clip 5
python3 "$MM/cm_analysis.py" "$OUT/Mux<SLOT>/pedestal_run/run_*"
```

Filled in for the LD Full slot A runs of 3.3, the type every worked example up to
here has used. `<run-dir>` is one run directory, which the `ped_run.sh` table
names in its last column, so a shell glob covers the set:

**(on the lab computer)**

```bash
python3 "$MM/hexmap_robust.py" "$OUT"/MuxA/pedestal_run/run_* -l ldfull --clip 5
python3 "$MM/cm_analysis.py" "$OUT/MuxA/pedestal_run/run_*"
```

🔑 **Neither takes a board type, and neither should be given one.**
`hexmap_robust.py` reads the geometry and channel map from characters 5 and 6 of
the serial, so it is already right for every type, and forcing `-t` is how you
get a partial plotted on the full geometry, per 2.1. That makes these two lines
the only ones in sections 3 to 11 that do not change with the board.

Read the printed `module:` and mapping lines every time. Mapping version matters:
the repository ships dated maps and even an explicit `_BAD.csv`, and the wrong
one silently relocates almost every channel.

Report **both** `adc_stdd` and `adc_iqr/1.349`, and trust the robust one.
`adc_stdd` is inflated by packet corruption, and `adc_mean` is not yet
reproducible run to run.

## 3.5 Offline unpack, when the automatic path fails

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
2 347 488 entries, `runsummary/summary` with 234 rows, and nine PNGs. A partial
legitimately produces fewer, so compute the expected row count from the board's
own chip and channel complement rather than comparing to these.

## 3.6 Slot quirks that apply to every board type

These follow the slot, not the module, so they are stated once here rather than
repeated in every type section.

- **Only one slot carries trigger at a time**, the first slot `daq-server`
  scanned since it last started. The other two read 0 of 12 with DAQ perfect.
  Restart `daq-server` and scan the slot you want first. See 1.1.
- **Slot C: sub-bus 7 hangs the bus** if it is selected. It is no longer probed,
  so do not add it back.
- **Slot C: the trigger link set differs from A and B** on the same board type,
  0, 1, 2, 4, 5, 11 rather than 0, 1, 2, 3, 5, 6 on an LD Left or Right. Using
  slot A's or B's config on slot C gives a FAIL that is a config error and not a
  hardware fault. See 2.4.
- **Slot C: keep `L1A_offset_or_BX: 13`** with `method: 'automatic'`, measured on
  an LD Full. Do not "correct" it to 14 even though the finder writes 14, and
  note that 20 decodes nothing. Automatic beat manual 36 of 36 against 18 of 36,
  because manual 13 and manual 14 fix complementary halves while automatic gets
  all six.

## 3.7 What a good result looks like

Ten pedestals on a healthy LD Full slot give 60 of 60 half-ROCs below corruption
1.0, with robust σ of **0.741 ADC**. A healthy slot reaches its full gate on the
first try and runs at 30 s per run. Use those as the yardstick for any slot.

---

# 4. LD Full (LF)

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

Measured 2026-09-02 with three LD Fulls, one per slot, 10 runs each through
`run_slot.sh` with `SKIP_PROBE=1`: 30 of 30 runs at CRC 1.000 on all six
halves, `badBX` 0.000, finder header positions 23 on every link. Bring-up took
one try on A and two on B and C.

⚠️ **The power flag is the one to get right.** The `0x27` `EN_Mx` write is what
powers the module, and `--external-power` skips it, so adding it leaves the
module dead. With `bench_up.sh` the same choice is spelled the other way, as
`--power-board`, per 1.3.

⚠️ **`in_inv_cmd_rx` stays 1 on an LD Full, whatever character 7 of the serial
says.** Setting it to 0 on the revision rule of 2.1 gave 0 of 12 trigger links
with healthy DAQ on all three slots. Read the applied value out of the run's own
`initial_full_config.yaml`, never out of the config file, and never edit a
config while a scan is in flight: a config edit that lands mid-scan produced a
"lottery" that was nothing of the kind.

🔑 **`EdgeSel_T1` is per slot.** Slot B at edge 0 produced a zero-byte run, not a
stall. The shipped configs carry the right edge for each slot; check `header
positions` in `daq-server.log` before touching anything else, every link at 23
is right.

One command end to end, per slot. It begins with its own bring-up, so **use it
from a slot you have not brought up yet**; if you are already standing on a
verified slot from 1.3, go to 4.1 and type only its last two lines, per 3.1:

**(on the lab computer)**

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Full-3b LD-Full 3 ldfull 5
```

**What you see, and when.** The script prints a `##########` banner per stage
and then that stage's output as it happens. On a healthy slot the whole thing
reads like this:

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

The meter tells the same story. It reads 0 A while the log sits at `Turning off
payload power`, because `--recover` cycles payload power on every try; about
1.2 A once `Turning on payload power` has passed and `EN_Mx` is written; and
1.9 to 2.0 A while the gate or a run has the chips configured. A bring-up that
stays near 0 A past `Turning on payload power` ends in `0/3 ROCs`, per 4.4.

## 4.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --board LD-Full"
"$MM/delay_scan.sh" A configs/initLD-Full-3b_muxA_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" A 5 ldfull 10000
```

## 4.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --board LD-Full"
"$MM/delay_scan.sh" B configs/initLD-Full-3b_muxB_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" B 5 ldfull 10000
```

## 4.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --board LD-Full"
"$MM/delay_scan.sh" C configs/initLD-Full-3b_muxC_ped.yaml
PED_BOARD=LD-Full "$MM/ped_run.sh" C 5 ldfull 10000
```

Keep `L1A_offset_or_BX: 13` in the slot C config, per 3.6.

## 4.4 When it does not go to plan

Everything below happened on LD Fulls on 2026-09-02 and 2026-09-03, and was
recovered without a config change. The first two are what a first day on a new
bench looks like.

- **`0/3 ROCs` on all eight tries, supply in CV at 0.05 to 0.1 A** after the
  log passed `Turning on payload power`. The module was never powered: `EN_Mx`
  did not reach it. Interrupt `up_verified.sh` rather than let it spend the
  tries. Then, in this order: the supply output is on and reads 1.72 V; the data
  cable from the power distribution board to the mux board is plugged in, since
  without it `EN_Mx` reaches nothing; then sweep `--module 1/2/3` per 1.3 and
  watch the meter, because the value that makes it jump to ~1.2 A is the one to
  keep. A `0x27` that ACKs proves the data path only.
- **`0/3` once, then `READY bringup=2`.** The ordinary lottery. Nothing to do.
- **The gate reads `no summary.json` or `STALE`, and under it the Kria's log
  says `Device ID , "TOP_A", does not exist in connection map`.** `daq-server`
  rejected the scan because `connections.xml` is the stock one, section 0.8d,
  which a firmware install also puts back. `Permission denied` there instead is
  the uio rule of 0.8g. The bring-up was clean in both cases, which is what
  makes this one expensive if 0.9's `grep` was skipped.
- **0 of 12 trigger, DAQ 6/6.** The trigger claim is on another slot, per 3.6,
  or `in_inv_cmd_rx` was changed to 0. The shipped config has 1.
- **Slot B produces a zero-byte run behind a clean gate.** `EdgeSel_T1` at 0 on
  slot B. The shipped config has 1; diff the applied config in the run
  directory against the shipped one before anything else.

---

# 5. LD Five (L5)

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

🔑 **A 2-of-3 enable with `0x58` missing is a known bad-board signature**, not a
bench problem. `enableROCs.py` exits 1 on an incomplete set rather than reporting
a partial enable as success, so trust that exit code.

🔑 **A stall at 64 events behind a clean gate and a perfect finder line is a
wrong `idcode`, not a link fault.** An `idcode` names the chip and half that a
link carries, so `77` on `link9` claimed a fourth chip on a three-chip board and
`daq-server` halted eleven events after that link stopped. The shipped configs
carry the right codes; before spending a bring-up on a stall, unpack the kept
`.raw` per 3.5 and read the chip ids out of it.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Five-3b LD-Five 3 ldfive 5
```

## 5.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --external-power --board LD-Five"
"$MM/delay_scan.sh" A configs/initLD-Five-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" A 5 ldfive 10000
```

## 5.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --external-power --board LD-Five"
"$MM/delay_scan.sh" B configs/initLD-Five-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" B 5 ldfive 10000
```

## 5.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --external-power --board LD-Five"
"$MM/delay_scan.sh" C configs/initLD-Five-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Five "$MM/ped_run.sh" C 5 ldfive 10000
```

---

# 6. LD Left and LD Right (LL, LR)

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

Both geometries use the same `LD-Left` config family. Three bonded halves give
one DAQ and two trigger links each, which is why six trigger links are live; the
config lists two, and the gate counts what the config lists. Measured
2026-09-02 on three LD Lefts: every slot passed first time once the probe was
taken out of the bring-up, per 2.4.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Left-3b LD-Semi 2 ldleft 5
```

The `bench_up.sh` cold start of 1.3, in its partial form. Every LD partial takes
this same line, so LD Bottom and LD Top of section 7 use it unchanged. There is
no `--power-board`, since none of them has a power distribution board:

**(on the lab computer, when driving a cold start by hand, not in a normal run)**

```bash
"$MM/bench_up.sh" A --board LD-Semi --expect 2
```

## 6.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
"$MM/delay_scan.sh" A configs/initLD-Left-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 ldleft 10000
```

## 6.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
"$MM/delay_scan.sh" B configs/initLD-Left-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 ldleft 10000
```

## 6.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
"$MM/delay_scan.sh" C configs/initLD-Left-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 ldleft 10000
```

---

# 7. LD Bottom and LD Top (LB, LT)

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

🔑 **An LD Bottom drives THREE trigger links, not six. That is the board type and
not a fault.** Measured 2026-09-02 on three LD Bottoms, ten runs each: gate
PASS, CRC 1.000 on all three halves, finder at 23 everywhere. Slot C's `link2`
gated `ngood 0` and was dropped from that slot's config; two links are ample.

⚠️ A pedestal does not test the link count. `randomL1A` barely exercises the
trigger path and would look identical if links were being lost. Use a TPG run for
that.

An **LD Top** has the same two ROCs and the same electrical setup, but its link
map has not been measured, so it has no config family of its own. Probe one with
`run_slot.sh` and no `SKIP_PROBE=1`, per 2.4, before trusting the LD Bottom
map on it.

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Bottom-3b LD-Semi 2 ldbottom 5
```

## 7.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board LD-Semi"
"$MM/delay_scan.sh" A configs/initLD-Bottom-3b_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" A 5 ldbottom 10000
```

## 7.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board LD-Semi"
"$MM/delay_scan.sh" B configs/initLD-Bottom-3b_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" B 5 ldbottom 10000
```

## 7.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board LD-Semi"
"$MM/delay_scan.sh" C configs/initLD-Bottom-3b_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=LD-Semi "$MM/ped_run.sh" C 5 ldbottom 10000
```

---

# 8. HD Full (HF)

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

⚠️ **Check the supply first, per 1.0.** Six chips draw more than one channel of a
typical 3.2 A bench supply. At the limit the rail sags to 1.35 V, all 24 e-links
die, and the module looks catastrophically broken.

⚠️ **A partial enable is not success.** Require `EXPECT_ROCS=6` **and** no
`FAILED` in the log.

🔑 **If some trigger links will not align, drop *those* links and keep the rest.**
Do **not** set `elinks_trg: []`: with no trigger links `daq-server` starts and
then hangs forever producing nothing, which is a documented dead end. Eight good
trigger links are ample for event building.

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

## 8.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh A --board HD-Full"
"$MM/delay_scan.sh" A configs/initHD-Full-trophyV3_muxA_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" A 5 hdfull 10000
```

## 8.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh B --board HD-Full"
"$MM/delay_scan.sh" B configs/initHD-Full-trophyV3_muxB_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" B 5 hdfull 10000
```

## 8.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=6 \
  ~/up_verified.sh C --board HD-Full"
"$MM/delay_scan.sh" C configs/initHD-Full-trophyV3_muxC_ped.yaml
PED_BOARD=HD-Full "$MM/ped_run.sh" C 5 hdfull 10000
```

---

# 9. HD Top (HT)

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

Measured 2026-09-03 with three HD Tops, one per slot, 3 and then 10 runs each
through `run_slot.sh` with `SKIP_PROBE=1`: 39 of 39 runs at CRC 1.000 on all
five halves and `badBX` 0.000. Two more sets on slots A and C later that day,
run by hand with the three-line sequence of 9.1 to 9.3, gave the same.

⚠️ **The power flag.** Without `--external-power` the bring-up writes `EN_Mx` on
the `0x27` power management board, which is not in the loop on a bench-fed
module. The write fails with `retry 5/5` and a `write_byte` traceback, or the ROC
probe reads `0/3` on all eight attempts, while the supply sits at 0.4 to 0.5 A on
every channel. That is a module already powered from the bench. Add the flag; a
power cycle is not needed, one recover-form bring-up with the flag clears it:

**(on the lab computer)**

```bash
ssh kria "pkill -f '[z]mq_server'; sleep 2; cd ~/multimodule && \
  ./mmts_bringup.sh A --recover --external-power --board HD-Top"
```

⚠️ **HD trophies swap four P/N pairs per module.** If a set of trigger links is
dead, the fix is `polarity: 0` per e-link in the yaml, not a different bitstream
and not `in_inv_cmd_rx`. The shipped configs carry the measured sets, and the
trigger set differs per slot, so never copy a trigger map from one slot to
another. DAQ is the same five links everywhere.

🔑 **`EdgeSel_T1` is per slot and the shipped configs carry it:** 1 on A and B,
0 on C. At the wrong edge one half rails at `adc_mean` ~709 with CRC 0.000 while
the other four halves look perfect. Check `header positions` in `daq-server.log`
before touching anything else: every link at 23 is right.

One command per slot. `--external-power` is the script's default, so no
`POWER=` in front of it:

**(on the lab computer)**

```bash
SKIP_PROBE=1 "$MM/run_slot.sh" A initHD-Top-trophyV3 HD-Top 3 hdtop 5
```

The hand-driven form is in 9.1 to 9.3. One thing it depends on that is easy to
lose when typing the pieces yourself: the i2c-server of the previous slot must
be dead before the bring-up starts. A stale server holds the bus during the
bring-up, and on the HD Tops that produced a chip that `stopped responding
mid-config` and a 2 of 3 enable. `up_verified.sh` kills it first; a hand-typed
`mmts_bringup.sh` does not, hence the `pkill` in the recovery line above.

## 9.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh A --external-power --board HD-Top"
"$MM/delay_scan.sh" A configs/initHD-Top-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" A 5 hdtop 10000
```

## 9.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh B --external-power --board HD-Top"
"$MM/delay_scan.sh" B configs/initHD-Top-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" B 5 hdtop 10000
```

## 9.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=3 \
  ~/up_verified.sh C --external-power --board HD-Top"
"$MM/delay_scan.sh" C configs/initHD-Top-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Top "$MM/ped_run.sh" C 5 hdtop 10000
```

## 9.4 When it does not go to plan

Everything below happened on 2026-09-03 and was recovered without a config
change.

- **Gate FAIL on a READY bring-up.** Slot A's first gate read DAQ 4/5 with
  `link4=0` and trigger 3/4 with `link5=0`. The identical bring-up run again gave
  5/5 and 4/4, and every later gate on that slot passed. Re-run the bring-up. Do
  not make a config that drops the link.
- **`0/3` or `2/3` ROCs with the missing chip wandering** between `0x18` and
  `0x58`. That is the bring-up lottery, not a dead ROC. Run the bring-ups back to
  back: slot A came up 0 for 5 when each attempt followed a fresh power cycle,
  then 4 of 10 back to back; slot B was `0/3` and then `3/3` on the immediate
  re-run. `up_verified.sh` makes eight attempts for you.
- **Bring-up `3/3` but the i2c-server dies** with `could not identify ROC type
  from readBack [0, 253, 104]`, or with `OSError: [Errno 5]` on a read. The
  client then hangs at initialize, `ped_run.sh` prints `RUN-FAILED (rc=124)`,
  and the run directory is empty. Writes on that slot's I2C path still work and
  reads have died. This is not the puller, so do not recreate it. Once the bus
  has been in use for half an hour or more, no number of bring-ups recovers it:
  ten back-to-back attempts gave seven `3/3` enables and zero servers.
  Power-cycle the Kria, run the bring-ups back to back, and take the runs
  immediately, with no idle gap between the gate and the pedestals. Or take the
  data on another slot: slot C came up first try with zero I2C errors ten
  minutes before slot B failed this way.

**Expected on a healthy HD Top, per run of 10 000 events:**

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
lying flat on a metal plate read 55 to 68 % on the same three boards; a spacer
under the board brought it to the table's 15 to 18 %.

---

# 10. HD Bottom (HB)

| | |
|---|---|
| `--board` | `HD-Bottom` |
| ROCs | 4, at `0x18 0x58 0x28 0x68` |
| power distribution board | not yet seen; every HD partial so far had none, so start with `--external-power` and read the supply per 1.0 |
| link sets | **not yet measured.** The shipped configs list links `4` to `11` for both DAQ and trigger as a template |
| delay scan gate | not yet measured; probe first, per 2.4 |
| run configs | `configs/initHD-Bottom-trophyV3_mux{A,B,C}_ped.yaml` |

No HD Bottom has been run yet. The trophy P/N warning of section 9 applies, and
so does its power-flag paragraph: `retry 5/5` at the `0x27` write means the
module is bench-fed. Run `run_slot.sh` without `SKIP_PROBE=1` on the first
board so the live links are written into the configs, then use the blocks below.

## 10.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh A --external-power --board HD-Bottom"
"$MM/delay_scan.sh" A configs/initHD-Bottom-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" A 5 hdbottom 10000
```

## 10.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh B --external-power --board HD-Bottom"
"$MM/delay_scan.sh" B configs/initHD-Bottom-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" B 5 hdbottom 10000
```

## 10.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=4 \
  ~/up_verified.sh C --external-power --board HD-Bottom"
"$MM/delay_scan.sh" C configs/initHD-Bottom-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Bottom "$MM/ped_run.sh" C 5 hdbottom 10000
```

---

# 11. HD Semi (HL, HR)

| | |
|---|---|
| `--board` | `HD-Semi` |
| ROCs | 2, at `0x08 0x18` |
| power distribution board | not yet seen; every HD partial so far had none, so start with `--external-power` and read the supply per 1.0 |
| link sets | **not yet measured.** The shipped configs list links `0 1 4 5` for both DAQ and trigger as a template |
| delay scan gate | not yet measured; probe first, per 2.4 |
| run configs | `configs/initHD-Semi-trophyV3_mux{A,B,C}_ped.yaml` |

No HD Semi has been run yet. The trophy P/N warning of section 9 applies, and
so does its power-flag paragraph. Run `run_slot.sh` without `SKIP_PROBE=1`
on the first board so the live links are written into the configs, then use the
blocks below.

## 11.1 Slot A

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh A --external-power --board HD-Semi"
"$MM/delay_scan.sh" A configs/initHD-Semi-trophyV3_muxA_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" A 5 hdsemi 10000
```

## 11.2 Slot B

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh B --external-power --board HD-Semi"
"$MM/delay_scan.sh" B configs/initHD-Semi-trophyV3_muxB_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" B 5 hdsemi 10000
```

## 11.3 Slot C

**(on the lab computer)**

```bash
ssh kria "cd ~/multimodule && MMTS_FW=multimodule-hd-tester-trophy-v3 EXPECT_ROCS=2 \
  ~/up_verified.sh C --external-power --board HD-Semi"
"$MM/delay_scan.sh" C configs/initHD-Semi-trophyV3_muxC_ped.yaml
PED_EXTPOWER=1 PED_BOARD=HD-Semi "$MM/ped_run.sh" C 5 hdsemi 10000
```

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

## 12.3 Symptom to action

| symptom | do |
|---|---|
| Everything returns `[Errno 5]`, switches do not ACK | Bring-up in the recover form. Expect to run it twice |
| `findslot.py` prints `mux GPIO write failed ([Errno 5] ...)` or `bus wedged during probe` | Not the same as `no ROCs`: the master answered, not the module. Cold start in the order of 1.2 and probe once more. If it survives that, it is the wedge of 12.4 |
| `KeyError: 'dac_hyst_toa'` | ROC type mis-detected and fell back to Siv3. Redo bring-up plus i2c-server |
| Client hangs at `ROC(s) CONFIGURED` | `daq-server` is dead or stuck in a previous unfinished run. Restart it |
| A scan sits at `Initializing i2c sockets` and never proceeds | Nothing is listening on 5555. `mmts_bringup.sh` does not start the i2c-server; run `~/start_i2c.sh SLOT`. Section 1.3 |
| Same hang, but `ss` on the Kria shows 5555 **and** 6000 listening and the identify line is good | The client cannot reach them. `echo "KRIA_IP=$KRIA_IP"` first: `192.0.2.7` is the unedited placeholder of 0.5 and routes nowhere. If the address is right, it is the firewall, per 0.8f |
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
| `dnf` answers `No matching Packages to list` for the firmware, and `dnf repolist` shows `HCGAL-DAQ-SW` alone | The `hgc-online-sw` repo file was never written. Section 0.8c |
| `ZMQError: Address already in use` on 5555 | `ssh kria 'pkill -f "[z]mq_ser""ver.py"'` |
| `daq-client` cannot bind 6001 | An old one is still alive. `pkill -f '[d]aq-client'` |
| The scan reaches `status after start cmd : running` and then nothing for minutes, and the gate says `no summary.json` | The event stream is not getting back to the client. `sudo firewall-cmd --list-ports` **on the lab computer**: an empty answer means 6001 was never opened, section 0.8f. Everything else passes without it, since the client only dials out until the first run |
| Orphaned holders after a killed server | `pkill -f 'gpioset -m signal -b'` |
| `daq-client` exits with `std::length_error` or signal 6 | It was sent the run twice by a START refusal spin. Full reset: restart `daq-server`, re-run bring-up, restart the puller |
| `elink link_capture_daq.linkN is not aligned` | A DAQ link failed to init, which happens about once a session. Re-run bring-up. `--realign` does not fix it, because the delay block is fine and the word aligner needs the `linkReset` that a full configure issues |
| `gpiofind: Permission denied` | The gpiochip udev rule is missing. Section 0.8g |
| `daq-server` logs `Permission denied` then `impossible to process configure when state is Error` | The uio udev rule is missing. Section 0.8g. Every configure is rejected until `daq-server` restarts |
| `fw-loader load: error: the following arguments are required: firmware` | A `$MMTS_FW` from an older copy of these instructions expanded to nothing. Name the design outright: `multimodule-hd-tester-trophy-v3`. Section 0.5 |
| `sed: -e expression #1, char 49: extra characters after command`, and the echoed line shows `done` where you typed `!d` | Bash history expansion, not sed. Use the loop as written in 0.8d, which contains no `!` |
| Bring-up dies at `[pwr]` with `[Errno 2] ... '/dev/i2c-2'` | Freshly booted Kria with no bitstream. `fw-loader load` first |
| Repeated `[Errno 13] Permission denied: '/dev/i2c-2'` after many reloads | The overlay reload is re-creating the node slower than udev sets the group, which takes roughly 40 reloads in a day to reach. Reboot the Kria |
| `ROC addresses [...] do not match a known board` | Read the printed address list. It is usually a bad bring-up rather than a wrong board type |
| Bring-up prints `board X needs all N of [...]; ['0x58'] never answered` | One chip is silent while its neighbours on the same I2C sub-bus answer. The bus is fine; that chip's contact, reset or local rail is not. Reseat; if the same address is missing in every slot, the board is the fault |
| `retry 5/5` at the `[pwr] power management board 0x27` line, first bring-up after a power cycle | The power board is not in the loop, so `0x27` cannot ACK. The module is fed directly: use `--external-power`. One `--recover --external-power` bring-up clears the wedge without a power cycle |
| Supply reads 0.4 to 0.5 A on a channel with nothing brought up | Normal: that slot's rail is on and its ROCs are idle. Three configured LD chips draw about 1.9 A, three HD chips about 2.2 A |
| Bring-up repeats `0/N ROCs` and the supply sits in **CV at 0.05 to 0.1 A**, well under the 0.4 A quiescent | The power path is open, not the bus. Sweep `--module 1/2/3` first, since `EN_Mx` is cabling; if all three read the same, check the power-management-to-mux cable, then the module's flex and seating. A `0x27` that ACKs proves the data path only |
| `daq-server.log` says `Device ID , "TOP_A", does not exist in connection map` then `impossible to process configure when state is Error` | The stock `connections.xml`. Section 0.8d, and again after every firmware install. The bring-up looks clean and the scan runs; only the gate's `no summary.json` gives it away |
| The gate prints `no summary.json -- the scan did not produce output` or `STALE: newest summary is ...` | `daq-server` rejected the scan, or nothing answered. `delay_scan.sh` prints the tails of its own log and of `~/daq-server.log` right under it; act on that line: the connection map row above, the uio rule of 0.8g, or a timeout with empty logs, which is `KRIA_IP` or the firewall. Section 3.2 |
| `bringup try N of 8: running ...` and then a silent minute | Normal. A try is 60 to 90 s and there can be eight. `ssh kria 'tail -f ~/bu_<slot>.log'` to see inside it. Section 3.1 |
| Bring-up enables 2 of N, with a different chip missing each time | The lottery, not a dead ROC. Run it again, back to back |
| Bring-up `3/3` but the i2c-server dies on `could not identify ROC type from readBack [0, 253, 104]`, or the client hangs at initialize with an empty run directory and `RUN-FAILED (rc=124)` | Reads on that slot's I2C path have died while writes still work. Not the puller, so do not recreate it. Power-cycle the Kria, run the bring-ups back to back, take the runs at once. Section 9.4 |
| `mmts_bringup.sh` on a bench-fed module dies at `[roc]` with a chip that `stopped responding mid-config`, right after a clean run on another slot | An i2c-server from the previous slot was still holding the bus. `up_verified.sh` kills it first; a hand-typed `mmts_bringup.sh` needs `pkill -f '[z]mq_server'` in front of it, per 1.3 |

## 12.4 When only the power button will do

- **Retries climb from 1/5 to 5/5 across successive runs, ROCs dropping mid
  config.** The PL I2C master is wedged. `up_verified.sh` retries 8 times per
  call, so a handful of failed calls is 40 bring-ups; count the retries in
  `~/bu_<slot>.log` rather than the outcome, and stop as soon as they are being
  exhausted instead of succeeding on attempt 1 or 2. Diagnose with
  `mmts_bringup.sh`, which runs once and shows you the error, per 1.3. `--recover` does not help
  once it has reached this state. `sudo shutdown -h now` plus a power button
  cycle, and then run the bring-ups **back to back** rather than one per boot:
  on 2026-09-03 a slot that failed on five separate fresh boots came up 4 of 10
  in a row, with the error count falling on every attempt. Afterwards prove the
  bus on a known-good slot before spending another bring-up on the suspect one:
  `no ROCs` measured on a sick bus says nothing about the module. What does not
  come back this way is a slot whose reads have died while its writes work,
  the `[0, 253, 104]` case of 9.4.
- **It gets worse every run and `0x71` or `0x73` stops ACKing entirely.** The
  clock synthesizer. `kconn_pwr` cannot reach it. Halt and mains cycle.

Plan the session around this. Rest first, then spend the good bring-ups on the
measurement you actually care about.

## 12.5 A few smaller ones

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

# 13. Changes

Dated provenance for the numbers and rules above, kept out of the procedure
itself. Newest first.

| date | change |
|---|---|
| 2026-09-03 | Scripts changed to match, in one `hexactrl-script` MR. `site.sh` is gone: `lib.sh` reads the environment, requires `MMTS_ROOT` and `KRIA_IP` and stops naming a missing one, and defaults the rest, so no placeholder address or stale firmware name can hang a scan later. `partial_slot.sh` is `run_slot.sh`, since it runs full boards too, and it streams every stage instead of holding the output until the end. `up_verified.sh` kills the previous slot's i2c-server before the first try and announces each try, so the hand-driven blocks lost their `pkill` line again. `delay_scan.sh` keeps the scan's log, times out at 180 s, and `gate.py` refuses a summary older than the scan and prints both logs' tails when there is nothing to report. `register_boards.py` creates the registry. `module_of.py` and `hexmap_robust.py` lost their site-named results default |
| 2026-09-03 | Corrected against two full sessions: the HD Top campaign on the reference bench and the first LD Full attempt from these instructions on a new client, which reached the gate and no further. Every hand-driven bring-up now kills the previous slot's i2c-server first, which `run_slot.sh` always did and `up_verified.sh` never does. Sections 3.1 to 3.3 and 4 say what each step prints, how long its silence lasts, which log to `tail -f`, and what the meter reads at each point. The gate's missing age check is documented. `ped_run.sh` is described as what it is, N runs on the slot as it stands, rather than as a bring-up plus gate. The `in_inv_cmd_rx` revision rule is restricted to the boards it holds for, since the LD Full keeps 1. 0.9 checks `connections.xml`, whose stock `TOP`-only form is what stopped the new client at the gate. The HD Top section carries its measured gates, per-slot trigger sets, edge settings and the three failures seen that day; its configs' claim of a power distribution board was wrong |
| 2026-09-03 | Restructured around hexaboard type instead of slot. The old sections 3, 4 and 5 were Slot A, Slot B and Slot C, which meant a board type's parameters were scattered across three places and the commands for one module were interleaved with two others. Now section 3 is the procedure every type shares, sections 4 to 11 are one per type with a subsection per slot, and 12 and 13 are the old 6 and 7. Section 2's per-type subsections collapsed into a single pointer table, and the slot-level quirks that used to be repeated per slot, the trigger claim, slot C's sub-bus 7, its trigger set and its `L1A_offset_or_BX: 13`, are stated once in 3.6 |
| 2026-09-03 | The output root is now `Results/` rather than a site-named subdirectory of it. `RESULTS_DIR` in `site.sh` is the one place that sets it |
| 2026-09-03 | `site.sh` is sourced by the scripts but not by your shell, so the hand-typed commands were expanding an empty `$MMTS_FW` and `$KRIA_IP`. The firmware design is now spelled out in every command instead of going through the variable, and section 0.5 and the preamble to sections 3 to 11 source `site.sh` for the rest |
| 2026-09-03 | The MMTS scripts branch was merged into `hexactrl-script:ROCv3-alper-dev` as `ffb42a2`, and `hexactrl-sw` MR !56 bumped the submodule pointer to it, so the scripts and configs are upstream. Section 0.4 loses the `tvami` fork remote and the branch checkout: `git clone --recurse-submodules` is now the whole step, and the submodules are correctly detached at their pinned commits |
| 2026-09-03 | The client-side `source .../etc/env.sh` line was wrong throughout and is now `export PATH=.../bin:$PATH`. `CMakeLists.txt` installs `env.sh` inside `if( NOT BUILD_CLIENT )`, so it exists only on the Kria, and it holds cactus and uHAL paths the client has no use for. The 0.8b occurrences are server-side and stay |
| 2026-09-03 | First install from these instructions on a fresh AlmaLinux client, completed end to end, found four gaps now fixed in 0.4, 0.6a and 0.8c. The clone step initialized only `hexactrl-script` and left the nested `analysis` and the sibling `zmq_i2c` empty, stopping the build at `add_subdirectory(analysis)`; the first repair for that was itself wrong, since a top-level recursive update resets `hexactrl-script` off the fork branch, so the nested update is now run from inside the submodule. cmake takes its interpreter from `PATH`, so an active conda base built against Python 3.12. `yaml-cpp-devel` and `cppzmq-devel` were missing from the package list, and since cmake never checks for them the failure came minutes later in `make`. And the firmware repo file of 0.8c had never been written on the bench Kria, so `dnf` answered `No matching Packages to list` for every firmware release |
| 2026-09-03 | Bench Kria upgraded from `2026_07_20_23_20_01.45587078` to `2026_09_01_16_56_41.49751f37`. The superseded build predates the DAQ RX equalization, so any CRC or dead-DAQ-link result recorded on this bench before this date is an unequalized measurement |
| 2026-09-03 | Bench scripts moved into `hexactrl-script/multimodule/`, so there is no separate bench repository to clone and every site value lives in `site.sh`. `hexactrl-sw` is built from source on both the client and the Kria; the CI-artifact route is gone. Configs reduced to exactly one per geometry per slot, `<family>_mux<SLOT>_ped.yaml`, with the family named for the geometry: `initLD-Full-3b`, `initLD-Five-3b`, `initLD-Left-3b`, `initLD-Bottom-3b`, `initHD-Full-trophyV3`, `initHD-Top-trophyV3`, `initHD-Bottom-trophyV3`, `initHD-Semi-trophyV3`. The bring-up script is now `enableROCs.py`, and it exits 1 when a `--board` address set comes up incomplete instead of reporting a partial enable as success |
| 2026-09-01 | DAQ RX equalization merged into `feature/multiplexer_board_v2` as `49751f37` and released, so the design has no `-rxeq` suffix any more. Measured against the unequalized build: CRC pass 0.000 to 1.000 on all three slots, `badBX` 0.10 to 0.000, eye 8 taps to 64 |
| 2026-08-31 | HD Full characterized on a supply with headroom: 4.43 A at 1.72 V for six chips, 12/12 DAQ links, CRC 1.000 on all twelve halves over 25 runs. At the current limit the rail sagged to 1.35 V and all 24 e-links died, which is where the clipping section of 1.0 comes from. `in_inv_cmd_rx` measured both ways on a v3D board: 0 gives 8/12 trigger, 1 gives 0/12. `--module N` added after a wrong `EN_Mx` bit cost a reseat and a full power-down |
| 2026-08-30 | `hexactrl-sw` MR !55 and `zmq_i2c` MR !24 merged: the `fifo_latency` mask fix, rebuilding `HwInterface` when `uhal_device` changes, skipping a trigger elink whose chip has no DAQ elink, and the offset finder skipping unreachable links rather than refusing the slot |
| 2026-08-28 | Slot C settled on `L1A_offset_or_BX: 13` with `method: 'automatic'`, which beat manual 36 of 36 against 18 of 36 |
