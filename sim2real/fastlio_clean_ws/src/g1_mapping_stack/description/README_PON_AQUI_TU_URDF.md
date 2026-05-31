# Dónde poner tu URDF o Xacro

Tienes dos opciones:

## Opción A: rápida
Usa el archivo mínimo ya incluido:

- `description/urdf/g1_minimal_livox.urdf.xacro`

Solo tendrás que ajustar en el launch la posición del LiDAR respecto a `base_link` con los argumentos:
- `lidar_x`
- `lidar_y`
- `lidar_z`
- `lidar_roll`
- `lidar_pitch`
- `lidar_yaw`

## Opción B: bien hecha con el G1 real
Pon aquí tu modelo real:

- `description/urdf/g1_full.urdf`
- o `description/urdf/g1_full.urdf.xacro`

Si tu URDF/Xacro necesita mallas (`.dae`, `.stl`, `.obj`), ponlas dentro de:

- `description/meshes/`

## Mejor opción si ya tienes un paquete de descripción
Si ya tienes un paquete externo como `g1_description`, NO copies solo el archivo suelto.
Lo mejor es dejar ese paquete en tu workspace y lanzar este stack apuntando al archivo absoluto del URDF/Xacro.

Ejemplo:

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/home/pablo/tu_ws/src/g1_description/urdf/g1_29dof.urdf
```

Si el modelo es Xacro:

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/home/pablo/tu_ws/src/g1_description/urdf/g1_29dof.urdf.xacro
```
