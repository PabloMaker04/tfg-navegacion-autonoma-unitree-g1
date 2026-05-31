#!/usr/bin/env bash
set -e
packages=(
  pointcloud_to_laserscan
  slam_toolbox
  nav2_map_server
  robot_state_publisher
  joint_state_publisher
)

missing=0
for pkg in "${packages[@]}"; do
  if ! ros2 pkg prefix "$pkg" >/dev/null 2>&1; then
    echo "FALTA: $pkg"
    missing=1
  else
    echo "OK:    $pkg"
  fi
done

if [ $missing -ne 0 ]; then
  echo ""
  echo "Faltan dependencias. Ejecuta:"
  echo "  ./scripts/install_runtime_deps.sh humble"
  exit 1
fi

echo ""
echo "Todo parece instalado."
