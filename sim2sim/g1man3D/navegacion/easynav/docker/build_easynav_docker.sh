#!/bin/bash
# ============================================================================
# build_easynav_docker.sh
# ============================================================================
# Construye la imagen Docker de EasyNav + Jazzy.
# Esto tarda unos 10-15 minutos la primera vez (clona repos + compila colcon).
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EASYNAV_DIR="$(dirname "${SCRIPT_DIR}")"

echo "=========================================="
echo "  Building g1-easynav:jazzy"
echo "=========================================="
echo "Contexto: ${EASYNAV_DIR}"
echo ""

cd "${EASYNAV_DIR}"
docker build -t g1-easynav:jazzy -f docker/Dockerfile .

echo ""
echo "=========================================="
echo "  Imagen construida: g1-easynav:jazzy"
echo "=========================================="
echo ""
echo "Siguiente paso: arrancar el contenedor con"
echo "   ./docker/run_easynav_docker.sh [ruta_mapa.yaml]"
