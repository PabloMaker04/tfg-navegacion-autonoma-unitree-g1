# g1_mapping_stack

Paquete ROS 2 Humble para mapear con el Unitree G1 usando:

- tu `PointCloud2` ya alineado (`/livox/lidar_aligned`)
- URDF o Xacro del robot
- `robot_state_publisher`
- `joint_state_publisher` opcional
- `pointcloud_to_laserscan`
- `slam_toolbox`
- grabación con `rosbag2`
- guardado del mapa final

## Lo más importante: dónde poner el URDF

Tienes tres formas válidas.

### Forma 1: usar ya el paquete tal cual
Ya viene un modelo mínimo incluido en:

- `description/urdf/g1_minimal_livox.urdf.xacro`

Con eso **puedes arrancar ya** aunque todavía no metas el URDF completo del G1. Solo tendrás que ajustar la pose del LiDAR respecto a `base_link`.

### Forma 2: meter tu URDF/Xacro dentro de este paquete
Ponlo aquí:

- `description/urdf/g1_full.urdf`
- o `description/urdf/g1_full.urdf.xacro`

Si usa mallas, mete las mallas en:

- `description/meshes/`

Y lanza así:

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/ABSOLUTA/RUTA/A/g1_full.urdf
```

### Forma 3: dejar tu paquete de descripción aparte
Esta es la mejor si ya tienes algo como `g1_description`.

No copies solo el archivo. Deja el paquete completo en tu workspace y usa la ruta absoluta del URDF o Xacro.

Ejemplo:

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/home/pablo/tu_ws/src/g1_description/urdf/g1_29dof.urdf
```

## Dependencias

```bash
sudo apt update
sudo apt install -y \
  ros-humble-xacro \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher \
  ros-humble-pointcloud-to-laserscan \
  ros-humble-slam-toolbox \
  ros-humble-nav2-map-server
```

## Compilación

```bash
cd ~/tu_ws/src
cp -r /ruta/a/g1_mapping_stack .
cd ~/tu_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select g1_mapping_stack
source install/setup.bash
```

## Flujo mínimo recomendado

### 1) En el robot
Dentro del Docker del robot:

```bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

### 2) En el portátil
Lanza tu nodo que corrige la nube y la IMU.

Necesitas tener estos topics:

- `/livox/lidar_aligned`
- `/livox/imu_aligned`

### 3) Arrancar el stack con el modelo mínimo

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  lidar_x:=0.15 lidar_y:=0.0 lidar_z:=0.85 \
  lidar_roll:=0.0 lidar_pitch:=0.0 lidar_yaw:=0.0
```

### 4) Arrancar el stack con tu URDF real

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/home/pablo/tu_ws/src/g1_description/urdf/g1_29dof.urdf
```

Si el robot no publica `/joint_states`, deja `use_joint_state_publisher:=true`.
Si el robot ya los publica, puedes desactivarlo:

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/home/pablo/tu_ws/src/g1_description/urdf/g1_29dof.urdf \
  use_joint_state_publisher:=false
```

## Qué hace el launch principal

1. carga tu URDF/Xacro
2. publica `robot_description`
3. lanza `robot_state_publisher`
4. lanza `joint_state_publisher` opcional para que el árbol TF no se quede cojo
5. convierte `/livox/lidar_aligned` a `/scan_flat`
6. usa `/scan_flat` con `slam_toolbox` para crear `/map`

## Cómo grabar un rosbag

Esto es solo para grabar la sesión mientras teleoperas.
No reemplaza el mapeado: simplemente lo guarda.

Con launch:

```bash
ros2 launch g1_mapping_stack record_mapping_bag.launch.py bag_name:=mi_sesion_01
```

Con script:

```bash
ros2 run g1_mapping_stack record_mapping_bag.sh mi_sesion_01
```

## Cómo guardar el mapa al terminar

```bash
ros2 run g1_mapping_stack save_map.sh mi_mapa_g1
```

Eso te generará normalmente:

- `mi_mapa_g1.pgm`
- `mi_mapa_g1.yaml`

## Qué comprobar si algo falla

```bash
ros2 topic echo /livox/lidar_aligned --once
ros2 topic echo /scan_flat --once
ros2 topic echo /map --once
ros2 topic echo /robot_description --once
ros2 topic echo /tf_static --once
ros2 run tf2_ros tf2_echo odom base_link
```

## Lo que este paquete sí resuelve

- usar URDF/Xacro
- publicar TF del robot con `robot_state_publisher`
- poder arrancar incluso sin URDF completo gracias al modelo mínimo
- convertir la nube en `LaserScan`
- generar mapa 2D en directo
- grabar bag y guardar mapa final

## Lo que aún tendrás que afinar después

- la huella exacta (`footprint`) para navegación fina
- un `odom -> base_link` bueno si hoy no existe
- costmaps de navegación y capa de seguridad final

