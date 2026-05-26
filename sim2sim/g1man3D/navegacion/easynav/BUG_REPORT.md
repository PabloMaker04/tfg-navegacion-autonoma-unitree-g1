# [BUG] `system_main` crashes on activation with "can't compare times with different time sources"

## Description

When launching `easynav_system/system_main` with a Simple Stack parameter file (AMCL localizer + Simple maps manager + Simple planner + Serest controller + LaserScan sensor), the process dies immediately after the `Activating [easynav_system]` log line with a `std::runtime_error`:

```
[easynav_system]: Activating [easynav_system]
[easynav_system]: Selected Real-Time
[easynav_system]: Failed to set Real Time. Running with normal priority.
terminate called after throwing an instance of 'std::runtime_error'
  what():  can't compare times with different time sources
process has died [exit code -6]
```

The crash happens before any actual navigation work begins.

## Environment

- **OS**: Ubuntu 24.04 inside a Docker container based on `ros:jazzy-ros-base`
- **ROS 2 distro**: Jazzy
- **EasyNav branches**: all on `jazzy` (`EasyNavigation`, `NavMap`, `easynav_plugins`, `yaets`)
- **RMW**: `rmw_cyclonedds_cpp`
- **Build**: `colcon build --symlink-install` completes successfully (39 packages, only PCL `CMP0144` warnings)
- **Host**: Ubuntu 22.04 + ROS 2 Humble (host runs the simulator and a TF/sensor bridge, not relevant to the bug — see "Reproduction without host" below)

## Reproduction

Minimal `easynav_params.yaml`:

```yaml
controller_node:
  ros__parameters:
    use_sim_time: false
    controller_types: [serest]
    serest:
      rt_freq: 30.0
      plugin: easynav_serest_controller/SerestController
      max_linear_speed: 0.6
      max_angular_speed: 0.8
      goal_pos_tol: 0.25
      goal_yaw_tol_deg: 15.0

localizer_node:
  ros__parameters:
    use_sim_time: false
    localizer_types: [simple]
    simple:
      rt_freq: 50.0
      freq: 5.0
      reseed_freq: 1.0
      plugin: easynav_simple_localizer/AMCLLocalizer
      num_particles: 200
      noise_translation: 0.05
      noise_rotation: 0.1
      noise_translation_to_rotation: 0.1
      initial_pose:
        x: 0.0
        y: 0.0
        yaw: 0.0
        std_dev_xy: 0.1
        std_dev_yaw: 0.01

maps_manager_node:
  ros__parameters:
    use_sim_time: false
    map_types: [simple]
    simple:
      freq: 10.0
      plugin: easynav_simple_maps_manager/SimpleMapsManager
      map_path_file: /absolute/path/to/some/map.yaml

planner_node:
  ros__parameters:
    use_sim_time: false
    planner_types: [simple]
    simple:
      freq: 0.5
      plugin: easynav_simple_planner/SimplePlanner
      robot_radius: 0.30

sensors_node:
  ros__parameters:
    use_sim_time: false
    forget_time: 0.5
    sensors: [laser1]
    perception_default_frame: odom
    laser1:
      topic: scan
      type: sensor_msgs/msg/LaserScan
      group: points

system_node:
  ros__parameters:
    use_sim_time: false
    position_tolerance: 0.3
    angle_tolerance: 0.15
```

Launched with:
```bash
ros2 run easynav_system system_main --ros-args --params-file easynav_params.yaml
```

The crash happens reliably every time, on every run, in the same place.

## Reproduction without external publishers

To rule out a clock mismatch with topics published from outside the container, the test was repeated with **no other ROS 2 process running anywhere on the network**:
- No simulator
- No bridge
- No `/clock`, `/scan`, `/odom`, `/tf` publishers

The crash still happens, identically. This rules out external time-source contamination.

## Reproduction with empty sensors list

Setting `sensors_node.sensors: []` (no sensors at all) also reproduces the crash identically. So the issue is not in the LaserScan sensor handler.

## What I tried

- `use_sim_time: false` in every block of the YAML — no change.
- Forcing `use_sim_time: false` additionally as a global parameter from the launch file — no change.
- Empty sensors list — no change.
- Closing all host-side publishers — no change.

The crash is at activation, before any message has been processed, with no sensors configured, and with nothing on the ROS 2 network. This strongly suggests an internal clock mismatch inside `system_main` itself or one of its plugins (perhaps a `tf2_ros::Buffer` constructed with a different `Clock` than the parent node, or a hardcoded `rclcpp::Clock(RCL_ROS_TIME)` instead of `node->get_clock()`).

## Expected behavior

`system_main` should activate cleanly and start spinning, waiting for sensor data and goals.

## Additional context

Happy to provide more logs, run with additional debug flags, or test patches. Thanks for the great work on EasyNav!
