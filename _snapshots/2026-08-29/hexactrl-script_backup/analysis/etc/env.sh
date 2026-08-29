SOURCE=${BASH_ARGV[0]}
if [ "x$SOURCE" = "x" ]; then
   SOURCE=${(%):-%N} # for zsh
fi
BASEDIR="$( cd "$(dirname "$SOURCE")" >/dev/null 2>&1 ; pwd -P )"
BASEDIR=${BASEDIR%\/etc}
export PYTHONPATH=$BASEDIR:$PYTHONPATH
