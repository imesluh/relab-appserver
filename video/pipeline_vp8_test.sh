#!/bin/sh
# get IP adress from Server
SCRIPTPATH=$(realpath "$0")
SCRIPTDIR="${SCRIPTPATH%/*}"
. "$SCRIPTDIR/../GET_IP_CONFIG.sh"


gst-launch-1.0 videotestsrc ! tee name=t t. ! queue !  videoconvert ! videoscale ! videorate ! video/x-raw,width=352,height=288,framerate=30/1 ! vp8enc end-usage=cbr cpu-used=-10 threads=16 target-bitrate=500000 max-quantizer=55 min-quantizer=40 keyframe-max-dist=60 buffer-size=20 deadline=1 ! "video/x-vp8,level=0" ! rtpvp8pay pt=100 mtu=1200 ! udpsink host=$SERVER_IP port=5007 t. ! queue ! videoconvert ! videoscale ! videorate ! video/x-raw,width=640,height=480,framerate=30/1 ! vp8enc end-usage=cbr cpu-used=-10 threads=16 target-bitrate=2000000 max-quantizer=50 min-quantizer=20 keyframe-max-dist=60 buffer-size=20 deadline=1 ! "video/x-vp8,level=0" ! rtpvp8pay pt=100 mtu=1200 ! udpsink host=$SERVER_IP port=5006
