#!/usr/bin/env bash
set -e
ROS_DISTRO_ARG=${1:-${ROS_DISTRO:-humble}}

sudo apt update
sudo apt install -y \
  ros-${ROS_DISTRO_ARG}-pointcloud-to-laserscan \
  ros-${ROS_DISTRO_ARG}-slam-toolbox \
  ros-${ROS_DISTRO_ARG}-nav2-map-server \
  ros-${ROS_DISTRO_ARG}-xacro \
  ros-${ROS_DISTRO_ARG}-robot-state-publisher \
  ros-${ROS_DISTRO_ARG}-joint-state-publisher \
  ros-${ROS_DISTRO_ARG}-tf2-ros

echo ""
echo "Dependencias instaladas para ROS ${ROS_DISTRO_ARG}."
echo "Ahora recompila tu workspace:"
echo "  cd ~/fastlio_clean_ws"
echo "  source /opt/ros/${ROS_DISTRO_ARG}/setup.bash"
echo "  colcon build --symlink-install --packages-select g1_mapping_stack"
echo "  source install/setup.bash"
