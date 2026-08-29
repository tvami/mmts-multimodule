#!/bin/bash

IP=$1
PORT=$2
NAME=$3
YAML="configs/initHD2.yaml"

python3 full_test.py -f $YAML -d $NAME -i $IP --pullerPort=$PORT
python3 delay_scan.py -f $YAML -d $NAME -i $IP --pullerPort=$PORT
