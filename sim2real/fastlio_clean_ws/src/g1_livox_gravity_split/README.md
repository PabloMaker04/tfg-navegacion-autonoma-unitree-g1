# g1_livox_gravity_split

Two-node ROS 2 Humble package for Livox MID360 / Unitree G1 workflows:

1. `gravity_quaternion_estimator`
   - listens to `/livox/imu`
   - averages the first `N` IMU acceleration samples
   - computes a single quaternion that aligns the measured gravity vector to a target axis
   - publishes that quaternion latched on `/gravity_alignment/quaternion`

2. `livox_gravity_applicator`
   - listens to `/gravity_alignment/quaternion`
   - rotates each Livox `CustomMsg` cloud on `/livox/lidar`
   - optionally rotates the IMU too
   - republishes corrected data on `/livox/lidar_aligned` and `/livox/imu_aligned`

This design avoids recomputing gravity alignment for every point cloud.

## Build

```bash
cd ~/your_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select g1_livox_gravity_split
source install/setup.bash
```

## Run

```bash
ros2 launch g1_livox_gravity_split gravity_split.launch.py
```

## Suggested FAST-LIO2 topics

```yaml
lid_topic: /livox/lidar_aligned
imu_topic: /livox/imu_aligned
```


## Heading correction

The applicator node can apply an extra fixed rotation after gravity alignment using `post_roll_deg`, `post_pitch_deg`, and `post_yaw_deg`. For a robot that still appears to face backwards after gravity alignment, set `post_yaw_deg: 180.0`.
