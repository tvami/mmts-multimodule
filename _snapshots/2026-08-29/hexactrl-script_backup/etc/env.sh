SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PATH_TO_HEXACTRL_SW=${SCRIPT_DIR}/../..
export PATH=${PATH_TO_HEXACTRL_SW}/bin:$PATH 

export PYTHONPATH=$SCRIPT_DIR/..:$PYTHONPATH
source ${SCRIPT_DIR}/../analysis/etc/env.sh
