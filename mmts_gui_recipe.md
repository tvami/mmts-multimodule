# Multimodule pedestal GUI on klong (port 5002)

The Kria dropdown comes from `krias:` under `MMTS_bench:` in klong's config. Right now it holds
`kria11.physics.ucsb.edu` and `128.111.19.219` (kria6). Add a line there for another Kria, or just
type the address into the lane on the page.

## Find the Krias on the network

```bash
nmap -sn -n 128.111.19.0/24                   # pings the subnet, so klong learns every MAC
ip neigh | grep -i 00:0a:35                   # Kria boards: MAC starting 00:0a:35
ssh daq@128.111.19.219 hostname               # its name; it comes from the SD card, not the board
```
Known: 128.111.19.219 kria6, .224 kria11, .216 kria3, .214 kria1 (the upstairs one).
A freshly powered Kria takes a few minutes to show up.

## Check a Kria's firmware

```bash
K=kria11.physics.ucsb.edu                     # the Kria to check
ssh daq@$K 'rpm -qa | grep trophy-v3'
# Right: multimodule-hd-tester-trophy-v3-feature_multiplexer_board_v2-2026_09_01_16_56_41.49751f37
ssh daq@$K 'grep -c "id=\"TOP_[ABC]\"" /opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml'
# Right: 3. Anything else: a firmware install put the stock connections.xml back,
# and every slot later fails with "no summary.json". Fix:
# https://github.com/tvami/mmts-multimodule/blob/main/mmts_instructions.md#b4-connectionsxml-needs-top_a-top_b-top_c
```

## Start the GUI

```bash
# ===== 1. Start it =====
cd /data/hep/mmts/MultiModuleTeststandUI
source .venv/bin/activate
source ./init_bash_vars.sh
export MMTS_PORT=5002
nohup python3 app.py >> logs/gui_5002.log 2>&1 &
sleep 5
ss -ltnp | grep ':5002 '            # one LISTEN line, python3
tail -n 5 logs/gui_5002.log         # "Running on http://...:5002"

# ===== 2. Open it in the browser =====
firefox http://localhost:5002 &
```

## Run pedestals in the page

On the main page pick **Pedestal Run, up to 8 Krias, HV optional**.

1. **Top of the form**: inspector, module status, **pedestals per slot** (5), **bring-up tries** (12),
   **label** (`ped`). Leave the probe box as it is (ticked = skip the 12+12 probe, use the shipped link map).
2. **One card per Kria** (K1 .. K8, each with its own daq-client port 6101 .. 6108):
   - Kria address: pick from the list or type it.
   - Module ID in A, B, C. Empty = that slot is skipped.
   - power board `auto`. Change it only if Configure shows the wrong answer.
3. **Initialize**: read-only checks (bench stack, Kria answers on 22, the lane's port is free,
   no other puller already on this Kria). Nothing is powered and no puller is started. A red line here stops the lane: read it before going on.
4. **Configure**: prints, per slot, the board type, the number of ROCs and the power board decision.
   Check that line for every slot. A module with a power board, run with `none`, reads `no ROCs`.
5. **Run**: slots A, B, C one after the other: bring-up (up to the tries), gate, one pedestal,
   then the rest. The lane's puller (daq-client on its port) is started here, by the bench scripts. LEDs: gray queued, yellow bring-up, green running/done, red failed.
6. **Check** (bottom): pick `K1_run1` (and so on) and press Check for the hexmaps.

Several Krias: fill several cards, then **Initialize all**, **Configure all**, **Run all**.
One card per Kria, never two cards on the same Kria.

The exit code per slot is in the lane log as `########## A: EXIT n`:
0 pedestals ran, 1 bring-up failed, 2 probe gave no summary, 3 registry or map refused,
4 gate failed, 5 first pedestal stalled.

## Stop

```bash
# In the page:
#   Stop   = stops that lane's run (bring-up, pedestals) and nothing else
#   Clear  = Stop + payload power off on that Kria + its puller ended; the card starts over

# If the page is gone, from a terminal (K1 and its Kria as an example).
# Always give MMTS_LANE: without it the stop matches the production stand's processes too.
cd /data/hep/mmts/MultiModuleTeststandUI
source .venv/bin/activate && source ./init_bash_vars.sh
MMTS_LANE=K1 MMTS_KRIA_IP=kria11.physics.ucsb.edu make -f makefile_task5 stop useHV=0

# Stop the GUI itself:
ss -ltnp | grep ':5002 '            # users:(("python3",pid=NNNN,..),("python3",pid=MMMM,..))
kill NNNN MMMM
```

## If something is wrong

```bash
# The page does not load:
ss -ltnp | grep ':5002 '                       # nothing = GUI not running, go to step 1
tail -n 30 /data/hep/mmts/MultiModuleTeststandUI/logs/gui_5002.log

# Initialize says the Kria does not answer:
ssh daq@kria11.physics.ucsb.edu hostname      # a freshly powered Kria takes a few minutes

# Every slot: "no ROCs" with retries 5/5: power board not cabled or not on.
# Read the supply first:
# https://github.com/tvami/mmts-multimodule/blob/main/mmts_instructions.md#123-symptom-to-action
```
