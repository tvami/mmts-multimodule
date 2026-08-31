# site.sh -- the ONLY file you edit. Sourced by every script in this directory.
# Each value can also be overridden from the environment for a one-off run.

# Where the clone and the results live (the parent of multimodule/).
MMTS_ROOT="${MMTS_ROOT:-$HOME/mmts}"

# The hexacontroller.
KRIA_IP="${KRIA_IP:-192.0.2.7}"
KRIA_USER="${KRIA_USER:-daq}"

# Native hexactrl-sw install prefix on THIS machine (the client).
HEXACTRL="${HEXACTRL:-/opt/hexactrl/ROCv3-alper-dev}"

# Python virtualenv holding uproot, pandas, matplotlib and friends.
# Leave empty if you installed them system-wide.
MMTS_VENV="${MMTS_VENV:-$MMTS_ROOT/venv}"

# Firmware design the bring-up loads. The equalised variant is mandatory:
# the stock bitstream fails 100 % of CRCs on four of the six DAQ e-links.
MMTS_FW="${MMTS_FW:-multimodule-hd-tester-trophy-v3-rxeq4}"

# Output root. Keep the name unless you also change it in the analysis scripts.
RESULTS_DIR="${RESULTS_DIR:-$MMTS_ROOT/Results/alabama}"
