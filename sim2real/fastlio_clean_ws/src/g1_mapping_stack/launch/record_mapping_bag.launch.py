from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bag_name = LaunchConfiguration('bag_name')

    return LaunchDescription([
        DeclareLaunchArgument('bag_name', default_value='g1_mapping_session'),
        ExecuteProcess(
            cmd=[
                'ros2', 'bag', 'record',
                '-o', bag_name,
                '/livox/lidar',
                '/livox/imu',
                '/livox/lidar_aligned',
                '/livox/imu_aligned',
                '/scan_flat',
                '/map',
                '/tf',
                '/tf_static',
            ],
            output='screen'
        )
    ])
