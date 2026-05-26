#!/bin/bash
# ============================================================================
# run_easynav_docker.sh
# ============================================================================
# Arranca el contenedor g1-easynav:jazzy con la configuración correcta para
# que ROS 2 dentro del contenedor vea los topics publicados por el bridge
# MuJoCo que corre en el host.
#
# Claves de la configuración:
#   --network=host          → el contenedor comparte la red del host, así el
#                             discovery de DDS funciona sin puertos mapeados.
#   --ipc=host              → shared memory entre host y contenedor (DDS lo usa).
#   RMW_IMPLEMENTATION      → forzamos CycloneDDS en ambos lados para evitar
#                             incompatibilidades entre FastDDS de Humble y
#                             FastDDS de Jazzy (a veces hay líos).
#   ROS_DOMAIN_ID           → debe coincidir con el del host. Por defecto 0.
#   -v ${G1MAN_PATH}/navegacion/easynav:/g1_easynav:ro
#                           → monta tu carpeta easynav dentro del contenedor
#                             en modo lectura para que pueda leer params
#                             y launch files.
#   -v ${G1MAN_PATH}/maps:/g1_maps:ro
#                           → monta los mapas generados por el mapper.
#
# Uso:
#   ./run_easynav_docker.sh                       # bash interactivo
#   ./run_easynav_docker.sh launch                # lanza EasyNav con mapa reciente
#   ./run_easynav_docker.sh launch mapa.yaml      # lanza con un mapa específico
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EASYNAV_DIR="$(dirname "${SCRIPT_DIR}")"
NAV_DIR="$(dirname "${EASYNAV_DIR}")"
G1MAN_DIR="$(dirname "${NAV_DIR}")"

# ----------------------------------------------------------------------------
# Configuración DDS — coincidir con lo que uses en el host
# ----------------------------------------------------------------------------
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"

echo "=========================================="
echo "  g1-easynav:jazzy — arrancando contenedor"
echo "=========================================="
echo "  G1MAN_DIR:          ${G1MAN_DIR}"
echo "  ROS_DOMAIN_ID:      ${ROS_DOMAIN_ID}"
echo "  RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION}"
echo ""

# ----------------------------------------------------------------------------
# Detectar modo de uso
# ----------------------------------------------------------------------------
MODE="${1:-bash}"

if [ "${MODE}" = "launch" ]; then
    MAP_ARG="${2:-}"
    if [ -n "${MAP_ARG}" ]; then
        CMD="ros2 launch /g1_easynav/launch/g1_easynav.launch.py map:=${MAP_ARG}"
    else
        CMD="ros2 launch /g1_easynav/launch/g1_easynav.launch.py"
    fi
    echo "  Ejecutando: ${CMD}"
else
    CMD="bash"
    echo "  Abriendo shell interactiva."
    echo "  Para arrancar EasyNav manualmente:"
    echo "     ros2 launch /g1_easynav/launch/g1_easynav.launch.py"
fi
echo ""

# ----------------------------------------------------------------------------
# Lanzamiento
# ----------------------------------------------------------------------------
docker run -it --rm \
    --name g1-easynav \
    --network=host \
    --ipc=host \
    --pid=host \
    -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID}" \
    -e RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION}" \
    -v "${EASYNAV_DIR}":/g1_easynav:ro \
    -v "${G1MAN_DIR}/maps":/g1_maps:ro \
    g1-easynav:jazzy \
    ${CMD}
