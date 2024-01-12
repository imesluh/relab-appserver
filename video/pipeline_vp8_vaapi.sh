#!/bin/sh
# get IP adress from Server
SCRIPTPATH=$(realpath "$0")
SCRIPTDIR="${SCRIPTPATH%/*}"
. "$SCRIPTDIR/../GET_IP_CONFIG.sh"


v4l2-ctl -d /dev/video0 -c focus_auto=0

gst-launch-1.0 -v -e v4l2src device=/dev/video0 ! tee name=t t. ! queue !  videoconvert ! videoscale ! videorate ! video/x-raw,width=352,height=288,framerate=30/1 ! vaapipostproc ! vaapivp8enc bitrate=500 ! "video/x-vp8,level=0" ! rtpvp8pay pt=100 mtu=1200 ! udpsink host=$SERVER_IP port=5007 t. ! queue ! videoconvert ! videoscale ! videorate ! video/x-raw,width=640,height=480,framerate=30/1 ! vaapipostproc ! vaapivp8enc bitrate=2000 ! "video/x-vp8,level=0" ! rtpvp8pay pt=100 mtu=1200 ! udpsink host=$SERVER_IP port=5006
