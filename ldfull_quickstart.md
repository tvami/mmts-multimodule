# MMTS quick start: LD Full

Pedestal runs on three LD Full hexaboards, one per slot (A, B, C).

Type everything on the lab computer unless it says **on the
Kria**. Steps 1 to 3 are done once per bench. Steps 4 and 5 are the routine.

If a step fails and the table at the end does not cover it, the full manual
is `mmts_instructions.md` in the same directory.

## 1. Flash the Kria

You need a 32 GB SD card (16 GB is a few MB too small).

```bash
L=https://cernbox.cern.ch/remote.php/dav/public-files/gA7anszJiATLSSR
curl -L -o kria-mmts-20261013.img.gz $L/kria-mmts-20261013.img.gz
sha256sum kria-mmts-20261013.img.gz
```

The hash must be
`6849d162dc1a01814b01e3d08e693118b9e98725adeb0c1d76a7766914df254a`.
If it is not, download again.

If you have xrootd and read access to the folder:
`xrdcp root://eosuser.cern.ch//eos/user/t/tvami/forMACs/kria-mmts-20261013.img.gz .`

Find the card and write it. `dd` erases whatever device you name, so check the
size matches the card.

```bash
lsblk -d -o NAME,SIZE,MODEL
sudo umount /dev/sdX* 2>/dev/null
gunzip -c kria-mmts-20261013.img.gz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Put the card in the Kria. It takes its address by DHCP; that address is
`KRIA_IP` below. The user is `daq`.

To find the address, scan the network with the Kria off, then again with it
on. `ip -4 addr` shows your own address and subnet; use that subnet in place
of `10.116.24.0/23`.

```bash
sudo dnf install -y nmap
sudo nmap -sn 10.116.24.0/23 -oG - | awk '/Up/{print $2}' | sort > before.txt
# power the Kria on, wait 2 minutes
sudo nmap -sn 10.116.24.0/23 -oG - | awk '/Up/{print $2}' | sort > after.txt
comm -13 before.txt after.txt
```

The new address is the Kria. `ssh daq@<address>` should ask for the `daq`
password. If more than one new address shows up, ask your network admin to
look up the lease, and to give the Kria a fixed address while they are at it.

## 2. Set up the lab computer

Packages:

```bash
sudo dnf install -y git python3 python3-pip cmake make gcc-c++ boost-devel epel-release
sudo dnf config-manager --set-enabled crb
sudo dnf install -y root yaml-cpp-devel cppzmq-devel zeromq-devel
```

Settings. Change `KRIA_IP`; the rest can stay as is. Append to `~/.bashrc`,
then `source ~/.bashrc`:

```bash
export KRIA_IP=10.0.0.1
export MMTS_ROOT=$HOME/mmts
export MM=$MMTS_ROOT/hexactrl-sw/hexactrl-script/multimodule
export SCRIPTS=$MMTS_ROOT/hexactrl-sw/hexactrl-script
export HEXACTRL=/opt/hexactrl/ROCv3-alper-dev
export MMTS_VENV=$MMTS_ROOT/venv
export RESULTS_DIR=$MMTS_ROOT/Results
export GUI_HEXMAP=$MMTS_ROOT/gui-hexmap
export PATH=$HEXACTRL/bin:$PATH
```

Code, build and Python environment. If you use conda, run `conda deactivate`
first; the build and the venv must use the system Python 3.9.

```bash
mkdir -p "$MMTS_ROOT" && cd "$MMTS_ROOT"
git clone -b ROCv3-alper-dev --recurse-submodules \
  ssh://git@gitlab.cern.ch:7999/hgcal-daq-sw/hexactrl-sw.git hexactrl-sw
git clone -b master \
  ssh://git@gitlab.cern.ch:7999/acrobert/hgcal-module-testing-gui.git gui-hexmap

cd hexactrl-sw && mkdir -p build && cd build
cmake -DBUILD_CLIENT=ON -DBRANCH_NAME=ROCv3-alper-dev \
      -DCMAKE_INSTALL_PREFIX=/opt/hexactrl/ROCv3-alper-dev ../
make -j"$(nproc)" && sudo make install

python3 -m venv --system-site-packages "$MMTS_VENV"
source "$MMTS_VENV/bin/activate"
pip install --no-cache-dir "numpy<2" pyzmq pyyaml pandas matplotlib scipy seaborn \
    uproot uproot3 awkward awkward-pandas more_itertools \
    nested_dict nested_lookup pyinotify tables
chmod +x "$MM"/*.sh "$MM"/*.py
```

Without GitLab ssh, use `https://gitlab.cern.ch/` in place of
`ssh://git@gitlab.cern.ch:7999/`.

ssh key for the Kria:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_kria
ssh-copy-id -i ~/.ssh/id_ed25519_kria.pub daq@$KRIA_IP
```

Add this to `~/.ssh/config`, with your address in both places:

```
Host kria 10.0.0.1
    HostName        10.0.0.1
    User            daq
    IdentityFile    ~/.ssh/id_ed25519_kria
    ControlMaster   auto
    ControlPath     ~/.ssh/cm-%r@%h:%p
    ControlPersist  10m
```

Open the puller's port on the lab computer's firewall:

```bash
sudo firewall-cmd --permanent --add-port=6001/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

The last line must include `6001/tcp`.

## 3. Check

The Kria settings. The image already has them:

```bash
ssh kria 'sudo -n true && echo "sudo OK"; id; sudo firewall-cmd --list-ports; ls /etc/udev/rules.d/99-*'
```

You should see `sudo OK`, `daq` in groups `gpio` and `i2c`, the ports
`5555/tcp 6000/tcp 8888/tcp`, and two rules files, `99-gpiochip-all.rules`
and `99-uio-daq.rules`. If anything is missing, `ssh kria` and run this
**on the Kria**:

```bash
echo "daq ALL=(root) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/hgc-bench
sudo chmod 440 /etc/sudoers.d/hgc-bench
sudo usermod -aG gpio,i2c daq
sudo firewall-cmd --permanent --add-port=5555/tcp --add-port=6000/tcp --add-port=8888/tcp
sudo firewall-cmd --reload
echo 'SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-gpiochip-all.rules
echo 'SUBSYSTEM=="uio", KERNEL=="uio*", GROUP="daq", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-uio-daq.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Then log out of the Kria and back in, so the new groups apply.

The bench:

```bash
ssh kria "sudo fw-loader load multimodule-hd-tester-trophy-v3"
ssh kria "cd ~/multimodule && python3 findslot.py"
command -v daq-client unpack
```

`findslot.py` should print `no ROCs` for all three slots. That is correct:
nothing has powered the modules yet. `Errno 5` instead means power the bench
up (step 5 does that) and run it again once.

## 4. Register the boards

Before the first run, and again after every board swap. Use the serials of the
boards actually in each slot:

```bash
"$MM/register_boards.py" A=320XLF4DQR00332 B=320XLF4DME01621 C=320XLF4DME01744
```

## 5. Run each slot

One slot at a time. Each command powers the slot, aligns the links, takes 5
pedestal runs and makes the hexmaps. About 5 minutes per slot.

```bash
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" A initLD-Full-3b LD-Full 3 ldfull 5
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" B initLD-Full-3b LD-Full 3 ldfull 5
POWER= SKIP_PROBE=1 "$MM/run_slot.sh" C initLD-Full-3b LD-Full 3 ldfull 5
```

Keep `POWER=` exactly as written. It turns on the module's power board; without
it the module stays off.

A good run shows `READY`, then `GATE: PASS`, then one row per pedestal with
`1.000` in all six CRC columns, and ends in `DONE`. A failed bring-up try
followed by a good one is normal.

Each LD Full draws up to 2 A while running.

Results are in `$RESULTS_DIR/<serial>/Mux<slot>/pedestal_run/`, one directory
per run, with the hexmap PNGs inside.

## If it fails

| you see | do |
|---|---|
| `slot A has no module in the registry` | step 4 |
| `0/3 ROCs` on every try, meter near 0 A | the module is not powered. Check the power lead and that `POWER=` is there |
| a different number of ROCs on each try | normal; it retries up to 8 times. If it still fails, run the command again |
| `GATE: FAIL` | run the same command again |
| stuck at `Initializing i2c sockets` | `KRIA_IP` is wrong, or the Kria firewall blocks it (step 3) |
| `no summary.json` after a scan that ran | port 6001 closed on the lab computer, or 8888 on the Kria (steps 2 and 3) |
| `Errno 5` on every try, or retries reaching `5/5` | power-cycle the Kria: `ssh kria sudo shutdown -h now`, wait 20 s, press its power button, then run the slot again |

Do not run `i2cdetect` on the Kria. It can lock up the I2C bus.
