#!/usr/bin/env bash
set -e
BAG_NAME=${1:-g1_mapping_session}

ros2 bag record -o "$BAG_NAME" \
  /livox/lidar \
  /livox/imu \
  /livox/lidar_aligned \
  /livox/imu_aligned \
  /scan_flat \
  /map \
  /tf \
  /tf_static
