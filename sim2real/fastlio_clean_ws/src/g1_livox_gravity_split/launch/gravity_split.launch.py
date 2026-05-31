from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    pkg_share = get_package_share_directory('g1_livox_gravity_split')
    params = os.path.join(pkg_share, 'config', 'params.yaml')

    estimator = Node(
        package='g1_livox_gravity_split',
        executable='gravity_quaternion_estimator',
        name='gravity_quaternion_estimator',
        output='screen',
        parameters=[params],
    )

    applicator = Node(
        package='g1_livox_gravity_split',
        executable='livox_gravity_applicator',
        name='livox_gravity_applicator',
        output='screen',
        parameters=[params],
    )

    return LaunchDescription([estimator, applicator])
