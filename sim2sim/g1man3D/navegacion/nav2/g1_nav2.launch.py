#!/usr/bin/env python3
"""
g1_nav2.launch.py
=================
Lanza Nav2 (AMCL + costmaps + planner + controller + behaviors) con el mapa
previamente guardado por el mapper.

Uso:
    ros2 launch g1_nav2.launch.py map:=/ruta/absoluta/al/maze_map_TIMESTAMP.yaml

    # O dejando el por defecto (último mapa de mujoco/maps/):
    ros2 launch g1_nav2.launch.py
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # ----- Rutas por defecto -----
    this_dir = os.path.dirname(os.path.abspath(__file__))
    default_params = os.path.join(this_dir, 'nav2_params.yaml')

    # Por defecto, usar el mapa más reciente en maps/
    maps_dir = os.path.join(this_dir, '..', '..', 'maps')
    default_map = ''
    if os.path.isdir(maps_dir):
        yamls = sorted(
            [f for f in os.listdir(maps_dir) if f.endswith('.yaml')],
            reverse=True)
        if yamls:
            default_map = os.path.join(maps_dir, yamls[0])

    # ----- Argumentos -----
    map_arg = DeclareLaunchArgument(
        'map',
        default_value=default_map,
        description='Ruta absoluta al .yaml del mapa a cargar')

    params_arg = DeclareLaunchArgument(
        'params_file',
        default_value=default_params,
        description='Ruta al nav2_params.yaml')

    autostart_arg = DeclareLaunchArgument(
        'autostart',
        default_value='true',
        description='Activar lifecycle nodes automáticamente')

    map_yaml = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    autostart = LaunchConfiguration('autostart')

    # Lifecycle nodes que gestiona el lifecycle_manager
    lifecycle_nodes = [
        'map_server',
        'amcl',
        'controller_server',
        'planner_server',
        'behavior_server',
        'bt_navigator',
        'waypoint_follower',
        'velocity_smoother',
    ]

    # ----- Nodos -----
    nodes = GroupAction([

        SetParameter(name='use_sim_time', value=False),

        # --- Map Server ---
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[
                {'yaml_filename': map_yaml},
                {'topic_name': 'map'},
                {'frame_id': 'map'},
            ]),

        # --- AMCL (localización) ---
        Node(
            package='nav2_amcl',
            executable='amcl',
            name='amcl',
            output='screen',
            parameters=[params_file]),

        # --- Planner global ---
        Node(
            package='nav2_planner',
            executable='planner_server',
            name='planner_server',
            output='screen',
            parameters=[params_file]),

        # --- Controller (DWB) ---
        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            output='screen',
            parameters=[params_file],
            remappings=[('cmd_vel', 'cmd_vel_nav')]),  # Pasa por velocity_smoother

        # --- Velocity Smoother (suaviza cmd_vel_nav → cmd_vel) ---
        Node(
            package='nav2_velocity_smoother',
            executable='velocity_smoother',
            name='velocity_smoother',
            output='screen',
            parameters=[params_file],
            remappings=[
                ('cmd_vel', 'cmd_vel_nav'),
                ('cmd_vel_smoothed', 'cmd_vel'),
            ]),

        # --- Behavior server (recoveries: spin, backup, wait) ---
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            name='behavior_server',
            output='screen',
            parameters=[params_file]),

        # --- BT Navigator ---
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            name='bt_navigator',
            output='screen',
            parameters=[params_file]),

        # --- Waypoint follower ---
        Node(
            package='nav2_waypoint_follower',
            executable='waypoint_follower',
            name='waypoint_follower',
            output='screen',
            parameters=[params_file]),

        # --- Lifecycle Manager (activa todos los lifecycle nodes) ---
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_navigation',
            output='screen',
            parameters=[
                {'autostart': autostart},
                {'node_names': lifecycle_nodes},
                {'bond_timeout': 0.0},
            ]),
    ])

    return LaunchDescription([
        map_arg,
        params_arg,
        autostart_arg,
        nodes,
    ])
