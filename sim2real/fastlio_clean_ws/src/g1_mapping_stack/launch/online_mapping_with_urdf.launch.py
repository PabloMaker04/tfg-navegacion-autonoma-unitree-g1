import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _load_robot_description(context):
    pkg_dir = get_package_share_directory('g1_mapping_stack')
    urdf_file = LaunchConfiguration('urdf_file').perform(context)
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher').perform(context).lower() == 'true'

    lidar_x = LaunchConfiguration('lidar_x').perform(context)
    lidar_y = LaunchConfiguration('lidar_y').perform(context)
    lidar_z = LaunchConfiguration('lidar_z').perform(context)
    lidar_roll = LaunchConfiguration('lidar_roll').perform(context)
    lidar_pitch = LaunchConfiguration('lidar_pitch').perform(context)
    lidar_yaw = LaunchConfiguration('lidar_yaw').perform(context)
    base_frame = LaunchConfiguration('base_frame').perform(context)
    odom_frame = LaunchConfiguration('odom_frame').perform(context)
    cloud_topic = LaunchConfiguration('cloud_topic').perform(context)
    scan_topic = LaunchConfiguration('scan_topic').perform(context)
    use_rviz = LaunchConfiguration('use_rviz').perform(context).lower() == 'true'
    rviz_config = LaunchConfiguration('rviz_config').perform(context)

    pc2_to_scan_params = os.path.join(pkg_dir, 'config', 'pc2_to_scan.yaml')
    slam_params = os.path.join(pkg_dir, 'config', 'slam_toolbox_online.yaml')

    if urdf_file.endswith('.xacro'):
        import xacro
        doc = xacro.process_file(
            urdf_file,
            mappings={
                'lidar_x': lidar_x,
                'lidar_y': lidar_y,
                'lidar_z': lidar_z,
                'lidar_roll': lidar_roll,
                'lidar_pitch': lidar_pitch,
                'lidar_yaw': lidar_yaw,
            },
        )
        robot_description = doc.toxml()
    else:
        with open(urdf_file, 'r', encoding='utf-8') as f:
            robot_description = f.read()

    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}]
    )

    nodes = [rsp]

    if use_joint_state_publisher:
        jsp = Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen'
        )
        nodes.append(jsp)

    pc2_to_scan = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pc2_to_scan',
        output='screen',
        parameters=[pc2_to_scan_params, {'target_frame': base_frame}],
        remappings=[('cloud_in', cloud_topic), ('scan', scan_topic)]
    )
    nodes.append(pc2_to_scan)

    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_params, {'base_frame': base_frame, 'odom_frame': odom_frame}],
        remappings=[('/scan', scan_topic)]
    )
    nodes.append(slam_toolbox)

    if use_rviz:
        rviz = Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config]
        )
        nodes.append(rviz)

    return nodes


def generate_launch_description():
    pkg_dir = get_package_share_directory('g1_mapping_stack')
    default_urdf = os.path.join(pkg_dir, 'description', 'urdf', 'g1_minimal_livox.urdf.xacro')
    default_rviz = os.path.join(pkg_dir, 'rviz', 'mapping.rviz')

    declared_arguments = [
        DeclareLaunchArgument('urdf_file', default_value=default_urdf,
                              description='Absolute path to URDF or Xacro file.'),
        DeclareLaunchArgument('use_joint_state_publisher', default_value='false',
                              description='Publish zeroed joint states if the real robot does not publish /joint_states.'),
        DeclareLaunchArgument('base_frame', default_value='pelvis',
                              description='Robot base frame used by slam_toolbox and pointcloud_to_laserscan.'),
        DeclareLaunchArgument('odom_frame', default_value='odom',
                              description='Odometry frame used by slam_toolbox.'),
        DeclareLaunchArgument('cloud_topic', default_value='/livox/lidar_aligned',
                              description='Aligned point cloud topic.'),
        DeclareLaunchArgument('scan_topic', default_value='/scan_flat',
                              description='Output 2D scan topic.'),
        DeclareLaunchArgument('lidar_x', default_value='0.15'),
        DeclareLaunchArgument('lidar_y', default_value='0.0'),
        DeclareLaunchArgument('lidar_z', default_value='0.85'),
        DeclareLaunchArgument('lidar_roll', default_value='0.0'),
        DeclareLaunchArgument('lidar_pitch', default_value='0.0'),
        DeclareLaunchArgument('lidar_yaw', default_value='0.0'),
        DeclareLaunchArgument('use_rviz', default_value='true',
                              description='Launch RViz2 with a basic mapping config.'),
        DeclareLaunchArgument('rviz_config', default_value=default_rviz,
                              description='RViz2 config file.'),
    ]

    return LaunchDescription(declared_arguments + [OpaqueFunction(function=_load_robot_description)])
