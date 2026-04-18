#!/bin/bash

DEVICE="/dev/video0"

if [ -r "$DEVICE" ]; then
    sudo chmod 000 "$DEVICE"
    notify-send -i camera-off "Cámara" "Cámara desactivada"
else
    sudo chmod 660 "$DEVICE"
    notify-send -i camera "Cámara" "Cámara activada"
fi