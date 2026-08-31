#!/usr/bin/env bash
# puller.sh -- restart daq-client. Once per RUN, not once per session.
. "$(cd "$(dirname "$0")" && pwd)/lib.sh"
puller_restart && echo "puller up on 6001"
