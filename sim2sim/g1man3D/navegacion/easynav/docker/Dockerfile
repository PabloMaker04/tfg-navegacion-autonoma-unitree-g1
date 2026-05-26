# ============================================================================
# Dockerfile — EasyNavigation on ROS 2 Jazzy
# ============================================================================
# Imagen basada en la oficial de ROS 2 Jazzy. Clona EasyNav (rama jazzy) y
# sus dependencias, compila el workspace, y deja el contenedor listo para
# ejecutar el binario `system_main` con los parámetros del G1.
#
# La comunicación con el host (donde corren MuJoCo, el bridge y el mapper)
# se hace vía DDS sobre la red. Al lanzar el contenedor con --network=host
# (ver run_easynav_docker.sh), ROS 2 dentro del contenedor y ROS 2 en el
# host se ven mutuamente sin más configuración.
#
# Build:
#   docker build -t g1-easynav:jazzy -f docker/Dockerfile .
# ============================================================================

FROM ros:jazzy-ros-base

# --- Paquetes de sistema ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    build-essential \
    ros-jazzy-rviz2 \
    ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# --- Workspace ---
ENV EASYNAV_WS=/root/easynav_ws
RUN mkdir -p ${EASYNAV_WS}/src
WORKDIR ${EASYNAV_WS}/src

# --- Clonar los repos de EasyNav (rama jazzy) ---
RUN git clone -b jazzy https://github.com/EasyNavigation/EasyNavigation.git && \
    git clone -b jazzy https://github.com/EasyNavigation/NavMap.git && \
    git clone -b jazzy https://github.com/EasyNavigation/easynav_plugins.git && \
    git clone -b jazzy https://github.com/fmrico/yaets.git

# --- Resolver dependencias ---
WORKDIR ${EASYNAV_WS}
RUN apt-get update && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -y -r && \
    rm -rf /var/lib/apt/lists/*

# --- Compilar ---
# Usamos shell completa para poder sourcing ROS antes de colcon
SHELL ["/bin/bash", "-c"]
RUN source /opt/ros/jazzy/setup.bash && \
    colcon build --symlink-install

# --- Entrypoint ---
# Lo copiamos como archivo (no inline) para evitar problemas de line endings
# y de comillas con el SHELL ["/bin/bash"].
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    sed -i 's/\r$//' /entrypoint.sh

# --- Crear la carpeta donde se montará la config del G1 ---
RUN mkdir -p /g1_easynav

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
