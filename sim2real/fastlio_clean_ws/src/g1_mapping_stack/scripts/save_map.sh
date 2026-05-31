#!/usr/bin/env bash
set -e
MAP_NAME=${1:-g1_map}
ros2 run nav2_map_server map_saver_cli -f "$MAP_NAME"
