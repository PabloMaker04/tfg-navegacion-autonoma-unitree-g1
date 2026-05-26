#!/usr/bin/env python3
"""
g1_easynav.launch.py
====================
Launch file para EasyNavigation aplicado al robot G1 en simulación MuJoCo.

Arranca el binario único de EasyNav (system_main) con el archivo de
parámetros del SimpleStack, y opcionalmente sobreescribe la ruta al mapa.

Este launch está diseñado para ejecutarse DENTRO del contenedor Docker
g1-easynav:jazzy, donde las rutas están montadas como:
    /g1_easynav/  → carpeta EasyNav del host (montada read-only)
    /g1_maps/     → carpeta mujoco/maps/ del host (montada read-only)

Uso (desde el host):
    # Shell interactiva en el contenedor:
    ./docker/run_easynav_docker.sh

    # Lanzamiento directo (mapa más reciente):
    ./docker/run_easynav_docker.sh launch

    # Lanzamiento con mapa específico (ruta dentro del contenedor):
    ./docker/run_easynav_docker.sh launch /g1_maps/maze_map_20260406_200946.yaml

REQUISITOS PREVIOS (todos en el host, NO en el contenedor):
    1. run_sim_ai_g1.py corriendo (MuJoCo + policy)
    2. mujoco_ros2_lidar_bridge.py corriendo (publica /scan, /odom, /tf)
    3. cmd_vel_bridge.py corriendo (traduce /cmd_vel → TCP:6000)

El contenedor Docker arranca con --network=host, así que ROS 2 dentro del
contenedor ve los topics del host y publica /cmd_vel en la misma red ROS 2.
"""

import os
import glob
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


# Ruta donde se monta la carpeta de mapas dentro del contenedor
MAPS_DIR_IN_CONTAINER = "/g1_maps"


# ---------------------------------------------------------------------------
def _get_default_map():
    """
    Busca el mapa PGM más reciente en /g1_maps/ (volumen montado desde
    el host). Devuelve la ruta absoluta al .yaml, o cadena vacía si no hay.
    """
    if not os.path.isdir(MAPS_DIR_IN_CONTAINER):
        return ""

    yamls = sorted(glob.glob(os.path.join(MAPS_DIR_IN_CONTAINER, "*.yaml")))
    if not yamls:
        return ""
    return yamls[-1]  # el más reciente (orden alfabético = orden temporal)


# ---------------------------------------------------------------------------
def _launch_setup(context, *args, **kwargs):
    """
    Carga el archivo de parámetros y sobreescribe el map_path_file si se
    pasó un argumento `map:=...` desde la línea de comandos.
    """
    # El launch file vive en /g1_easynav/launch/ dentro del contenedor
    params_file = "/g1_easynav/config/easynav_params.yaml"

    if not os.path.isfile(params_file):
        raise RuntimeError(
            f"No encuentro el archivo de parámetros: {params_file}\n"
            f"¿Estás ejecutando este launch dentro del contenedor Docker?")

    map_arg = LaunchConfiguration("map").perform(context)

    # Si el usuario no pasó un mapa explícito, intentamos el más reciente
    if not map_arg:
        map_arg = _get_default_map()

    if not map_arg:
        print("[g1_easynav.launch.py] WARNING: no se encontró ningún mapa en "
              f"{MAPS_DIR_IN_CONTAINER}/ y no se pasó argumento map:=. "
              "El SimpleMapsManager fallará al arrancar.")
    else:
        if not os.path.isabs(map_arg):
            raise RuntimeError(
                f"El argumento map:= debe ser una ruta ABSOLUTA. "
                f"Recibido: {map_arg}")
        if not os.path.isfile(map_arg):
            raise RuntimeError(f"El mapa no existe: {map_arg}")
        print(f"[g1_easynav.launch.py] Usando mapa: {map_arg}")

    # Parámetros: archivo + override del map_path_file + use_sim_time global
    # use_sim_time: false porque el bridge del host publica con system clock,
    # no con /clock simulado. Si los nodos internos de EasyNav cogen sim time
    # por defecto, hay un crash "can't compare times with different time sources"
    # al comparar stamps del /scan con su reloj interno.
    parameters = [
        params_file,
        {"use_sim_time": False},
    ]
    if map_arg:
        parameters.append({
            "maps_manager_node.simple.map_path_file": map_arg,
        })

    easynav_node = Node(
        package="easynav_system",
        executable="system_main",
        name="easynav_system",
        output="screen",
        parameters=parameters,
        emulate_tty=True,
    )

    return [easynav_node]


# ---------------------------------------------------------------------------
def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            "map",
            default_value="",
            description="Ruta absoluta al archivo .yaml del mapa "
                        "(dentro del contenedor, típicamente /g1_maps/*.yaml). "
                        "Si está vacío, coge el más reciente de /g1_maps/."),
        OpaqueFunction(function=_launch_setup),
    ])
