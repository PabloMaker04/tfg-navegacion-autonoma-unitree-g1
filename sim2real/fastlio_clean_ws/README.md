# FAST-LIO2 + Gravity Split + Mapping con Unitree G1

> **Stack completo para hacer SLAM 3D en tiempo real con el Unitree G1 EDU y el LiDAR Livox MID360, usando FAST-LIO2, corrección automática de gravedad y SLAM Toolbox.**

---

## Índice

1. [Arquitectura del sistema](#1-arquitectura-del-sistema)
2. [Requisitos previos](#2-requisitos-previos)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [Configuración de red](#4-configuración-de-red)
5. [Compilación](#5-compilación)
6. [Pasos de arranque completo](#6-pasos-de-arranque-completo)
7. [Qué hace cada paquete](#7-qué-hace-cada-paquete)
8. [Parámetros importantes](#8-parámetros-importantes)
9. [Guardar el mapa](#9-guardar-el-mapa)
10. [Diagnóstico y troubleshooting](#10-diagnóstico-y-troubleshooting)
11. [Preguntas frecuentes](#11-preguntas-frecuentes)

---

## 1. Arquitectura del sistema

El flujo de datos es el siguiente:

```
[Unitree G1]
  └─ LiDAR Livox MID360  ──►  /livox/lidar   (CustomMsg)
  └─ IMU interna         ──►  /livox/imu      (Imu)
           │
           ▼
[g1_livox_gravity_split]
  ├─ gravity_quaternion_estimator   ──►  /gravity_alignment/quaternion
  └─ livox_gravity_applicator       ──►  /livox/lidar_aligned  (CustomMsg)
                                         /livox/imu_aligned    (Imu)
           │
           ▼
[fast_lio]  (FAST-LIO2)
  └─ fastlio_mapping                ──►  /cloud_registered  (PointCloud2)
                                         /Odometry          (nav_msgs/Odometry)
           │
           ▼
[g1_mapping_stack]
  ├─ robot_state_publisher          ──►  /tf (árbol TF del robot)
  ├─ pointcloud_to_laserscan        ──►  /scan_flat (LaserScan 2D)
  └─ slam_toolbox                   ──►  /map (OccupancyGrid)
```

**Resumen**: el MID360 publica nube de puntos e IMU → el nodo de gravedad la endereza automáticamente (compensa que el robot no está perfectamente vertical) → FAST-LIO2 hace odometría 3D con el filtro de Kalman iterativo → el stack de mapping lo convierte en un mapa 2D navegable.

---

## 2. Requisitos previos

### Sistema operativo y ROS

| Componente | Versión requerida |
|---|---|
| Ubuntu | 22.04 LTS |
| ROS 2 | Humble Hawksbill |
| CMake | ≥ 3.14 |
| GCC | ≥ 9 |

### Dependencias ROS 2

Instala todo de una vez:

```bash
sudo apt update && sudo apt install -y \
  ros-humble-xacro \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher \
  ros-humble-pointcloud-to-laserscan \
  ros-humble-slam-toolbox \
  ros-humble-nav2-map-server \
  ros-humble-pcl-ros \
  ros-humble-pcl-conversions \
  libpcl-dev \
  libeigen3-dev \
  libgflags-dev
```

### Hardware necesario

- **Robot**: Unitree G1 EDU (con NX Dev Board interna)
- **LiDAR**: Livox MID360 (ya integrado en el G1 EDU)
- **PC externo**: conectado al G1 por Ethernet, Ubuntu 22.04 + ROS 2 Humble

---

## 3. Estructura del repositorio

```
src/
├── livox_ros_driver2/          # Driver oficial de Livox para ROS 2
│   ├── config/
│   │   └── MID360_config.json  # ⚠️ AQUÍ SE CONFIGURA LA IP DEL LIDAR
│   └── launch_ROS2/
│       └── msg_MID360_launch.py
│
├── g1_livox_gravity_split/     # Corrección automática de gravedad
│   ├── config/
│   │   └── params.yaml         # Parámetros de calibración y topics
│   └── launch/
│       └── gravity_split.launch.py
│
├── fast_lio/                   # FAST-LIO2: odometría LiDAR-IMU
│   ├── config/
│   │   └── mid360.yaml         # ⚠️ CONFIG PRINCIPAL DE FAST-LIO2
│   └── launch/
│       └── mapping.launch.py
│
└── g1_mapping_stack/           # SLAM 2D + URDF + guardado de mapa
    ├── config/
    │   ├── slam_toolbox_online.yaml
    │   └── pc2_to_scan.yaml
    ├── description/urdf/
    │   └── g1_minimal_livox.urdf.xacro  # URDF mínimo listo para usar
    └── launch/
        └── online_mapping_with_urdf.launch.py
```

---

## 4. Configuración de red

### IPs del sistema Unitree G1

El G1 usa la subred `192.168.123.0/24` internamente. Cuando te conectas por Ethernet al robot:

| Dispositivo | IP |
|---|---|
| Tu PC (interfaz Ethernet hacia el robot) | `192.168.123.100` |
| NX Dev Board (computador interno del G1) | `192.168.123.164` |
| LiDAR Livox MID360 | `192.168.123.120` |

> **Nota**: El MID360 que viene integrado en el G1 usa `192.168.123.120`, no la IP de fábrica `192.168.1.12`. Ajusta el fichero de config del driver en consecuencia (ver sección siguiente).

### Configurar la IP de tu PC

Tu interfaz Ethernet hacia el robot debe tener la IP `192.168.123.100`:

```bash
# Comprueba el nombre de tu interfaz (p.ej. enp2s0, eth0...)
ip link show

# Asigna la IP estática (cambia enp2s0 por tu interfaz real)
sudo ip addr add 192.168.123.100/24 dev enp2s0
sudo ip link set enp2s0 up

# Comprueba que el robot responde
ping 192.168.123.164   # NX Dev Board
ping 192.168.123.120   # MID360
```

Para hacerlo persistente, crea una conexión en NetworkManager con IP estática `192.168.123.100/24`.

### Adaptar MID360_config.json

El driver de Livox necesita saber qué IP tiene el LiDAR y cuál es la IP de tu PC (host). Edita `src/livox_ros_driver2/config/MID360_config.json`:

```json
{
  "MID360": {
    "host_net_info": {
      "cmd_data_ip":   "192.168.123.100",   // ← IP de TU PC
      "push_msg_ip":   "192.168.123.100",
      "point_data_ip": "192.168.123.100",
      "imu_data_ip":   "192.168.123.100"
    }
  },
  "lidar_configs": [
    {
      "ip": "192.168.123.120"               // ← IP del MID360 en el G1
    }
  ]
}
```

> ⚠️ **Importante**: si no cambias estas IPs, el driver arrancará pero no recibirás ningún dato.

### Variables de entorno ROS 2

Si el robot y el PC están en la misma red y quieres que compartan el dominio DDS:

```bash
export ROS_DOMAIN_ID=0          # 0 por defecto, cámbialo si hay más robots
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

---

## 5. Compilación

Crea o usa tu workspace de ROS 2 y compila los cuatro paquetes:

```bash
# Crea el workspace si no existe
mkdir -p ~/g1_ws/src
cd ~/g1_ws/src

# Copia (o clona) los paquetes aquí
cp -r /ruta/al/repo/src/* ~/g1_ws/src/

# Fuente de ROS 2
source /opt/ros/humble/setup.bash

# Compila
cd ~/g1_ws
colcon build --symlink-install \
  --packages-select livox_ros_driver2 g1_livox_gravity_split fast_lio g1_mapping_stack

# Si la compilación es lenta o se queda sin RAM, limita el paralelismo:
# colcon build --symlink-install --parallel-workers 2

# Carga el workspace compilado
source ~/g1_ws/install/setup.bash
```

> 💡 **Tip**: añade `source ~/g1_ws/install/setup.bash` al final de tu `~/.bashrc` para no tener que hacerlo en cada terminal.

---

## 6. Pasos de arranque completo

Necesitarás **tres terminales** en tu PC. Cada una hace una cosa. Síguelas en orden.

---

### Terminal 1 — Driver del LiDAR (livox_ros_driver2)

Este nodo se comunica directamente con el MID360 y publica la nube de puntos y la IMU.

```bash
source /opt/ros/humble/setup.bash
source ~/g1_ws/install/setup.bash

ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

**Qué esperar**: verás líneas como `[INFO] Livox Lidar Detected` y en unos segundos empezarán a llegar datos. Comprueba que hay datos con:

```bash
# En otra subshell o terminal nueva:
ros2 topic hz /livox/lidar   # debería estar alrededor de 10 Hz
ros2 topic hz /livox/imu     # debería estar alrededor de 200 Hz
```

Si no hay datos, revisa la sección de [troubleshooting](#10-diagnóstico-y-troubleshooting).

---

### Terminal 2 — Corrección de gravedad + FAST-LIO2

Este paso tiene **dos sub-pasos**: primero arrancas la corrección de gravedad y luego FAST-LIO2. Puedes hacerlos en la misma terminal o en dos.

#### 2a. Corrección de gravedad (g1_livox_gravity_split)

```bash
source /opt/ros/humble/setup.bash
source ~/g1_ws/install/setup.bash

ros2 launch g1_livox_gravity_split gravity_split.launch.py
```

Este nodo **tarda unos segundos en calibrarse**: muestrea los primeros 200 datos de IMU (≈ 1 segundo) para estimar la dirección de la gravedad y calcular la corrección. Durante ese tiempo no publicará nada en `/livox/lidar_aligned`.

Comprueba que ha calibrado:

```bash
ros2 topic echo /gravity_alignment/status --once
# Debería mostrar algo como: status: "ready"
```

Una vez calibrado, comprueba que llegan nubes corregidas:

```bash
ros2 topic hz /livox/lidar_aligned
```

#### 2b. FAST-LIO2 (fast_lio)

```bash
# En la misma terminal o en otra nueva (con los sources cargados)
ros2 launch fast_lio mapping.launch.py config_file:=mid360.yaml rviz:=false
```

> Usamos `rviz:=false` aquí porque el RViz lo levantará el stack de mapping. Si quieres verlo por separado, quita ese argumento.

FAST-LIO2 empezará a publicar odometría 3D en `/Odometry` y la nube registrada en `/cloud_registered`. Verás en la consola líneas con el residuo del filtro de Kalman — son normales.

---

### Terminal 3 — Stack de mapping (g1_mapping_stack)

Este paquete convierte todo lo anterior en un mapa 2D navegable.

#### Opción A: con el URDF mínimo incluido (más rápido para empezar)

```bash
source /opt/ros/humble/setup.bash
source ~/g1_ws/install/setup.bash

ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  lidar_x:=0.15 lidar_y:=0.0 lidar_z:=0.85 \
  lidar_roll:=0.0 lidar_pitch:=0.0 lidar_yaw:=0.0
```

Los valores de `lidar_x/y/z` son la posición del MID360 relativa al `pelvis` del robot en metros. Ajústalos a la montura real de tu unidad.

#### Opción B: con el URDF completo del G1

```bash
ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py \
  urdf_file:=/ruta/absoluta/a/g1_29dof.urdf \
  use_joint_state_publisher:=false
```

> Usa `use_joint_state_publisher:=true` si el robot no publica `/joint_states` por su cuenta (p.ej. si no está corriendo el controlador de articulaciones).

**Se abrirá RViz2** con la configuración de mapping. Deberías ver:

- La nube de puntos del LiDAR
- El robot en el frame `pelvis`
- El mapa 2D creciendo conforme mueves el robot

---

### Resumen de los comandos por terminal

```
Terminal 1:  ros2 launch livox_ros_driver2 msg_MID360_launch.py
Terminal 2a: ros2 launch g1_livox_gravity_split gravity_split.launch.py
Terminal 2b: ros2 launch fast_lio mapping.launch.py config_file:=mid360.yaml rviz:=false
Terminal 3:  ros2 launch g1_mapping_stack online_mapping_with_urdf.launch.py [args]
```

---

## 7. Qué hace cada paquete

### `livox_ros_driver2`

Driver oficial de Livox adaptado para ROS 2. Se comunica con el MID360 vía UDP y publica:

- `/livox/lidar` — nube de puntos en formato `livox_ros_driver2/msg/CustomMsg` (no es `PointCloud2` estándar, tiene timestamps por punto)
- `/livox/imu` — datos de la IMU integrada a ~200 Hz

### `g1_livox_gravity_split`

Paquete propio que resuelve un problema concreto del G1: el robot no camina exactamente vertical y el LiDAR queda inclinado respecto al suelo. Si se lo pasas directamente a FAST-LIO2 o a SLAM Toolbox sin corregir, el mapa queda torcido.

Funciona en dos nodos:

1. **`gravity_quaternion_estimator`**: escucha los primeros N muestras de IMU, promedia el vector de aceleración gravitacional y calcula un cuaternión de corrección. Lo publica en `/gravity_alignment/quaternion`.

2. **`livox_gravity_applicator`**: aplica ese cuaternión a cada nube de puntos y a la IMU, y republica en `/livox/lidar_aligned` y `/livox/imu_aligned`. El parámetro `post_yaw_deg: 180.0` en `params.yaml` compensa que el MID360 en el G1 EDU mira hacia atrás por defecto.

### `fast_lio`

Implementación de [FAST-LIO2](https://github.com/hku-mars/FAST_LIO) — un algoritmo de odometría LiDAR-IMU basado en un filtro de Kalman iterado (iEKF) con una estructura de datos `ikd-Tree` para la búsqueda eficiente de vecinos más cercanos.

Consume `/livox/lidar_aligned` y `/livox/imu_aligned` y produce:
- `/Odometry` — pose 6DOF del robot
- `/cloud_registered` — nube de puntos acumulada en el frame del mapa

El config relevante es `config/mid360.yaml`. Los parámetros más importantes:
- `lid_topic` y `imu_topic`: deben apuntar a los topics alineados
- `extrinsic_T` y `extrinsic_R`: transformación LiDAR→IMU (ya configurada para el G1)

### `g1_mapping_stack`

Stack de mapeo que orquesta todo lo demás:

1. Carga el URDF y publica el árbol TF del robot con `robot_state_publisher`
2. Convierte la nube 3D a `LaserScan` 2D con `pointcloud_to_laserscan` (solo toma puntos entre 5 cm y 120 cm de altura)
3. Alimenta ese LaserScan a `slam_toolbox` en modo online asíncrono
4. `slam_toolbox` produce el mapa `/map` y mantiene el TF `map → odom`

---

## 8. Parámetros importantes

### `g1_livox_gravity_split/config/params.yaml`

```yaml
gravity_quaternion_estimator:
  calibration_sample_count: 200    # Nº de muestras de IMU para calibrar (≈1 seg)
  target_axis: "+z"                # Alinea gravedad con el eje Z hacia arriba

livox_gravity_applicator:
  pass_through_until_ready: false  # Si true, pasa la nube sin corregir hasta calibrar
  post_yaw_deg: 180.0              # Rota 180° en yaw (el MID360 del G1 mira hacia atrás)
  post_roll_deg: 0.0
  post_pitch_deg: 0.0
```

> Si el mapa sale girado 180°, revisa este `post_yaw_deg`. Si el robot aparece bocabajo en RViz, el `target_axis` es incorrecto para tu montura.

### `fast_lio/config/mid360.yaml`

```yaml
common:
  lid_topic:  "/livox/lidar_aligned"   # ← topics con corrección de gravedad
  imu_topic:  "/livox/imu_aligned"

preprocess:
  lidar_type: 1       # 1 = Livox (no cambiar para el MID360)
  scan_line: 4        # Líneas de scan del MID360
  blind: 0.5          # Distancia mínima en metros (ignora puntos muy cercanos)

mapping:
  extrinsic_T: [-0.011, -0.02329, 0.04412]   # Offset IMU→LiDAR en metros
  extrinsic_R: [1,0,0, 0,1,0, 0,0,1]         # Rotación IMU→LiDAR (identidad = alineados)
  extrinsic_est_en: true    # Estima la extrínseca online si no la conoces exactamente

pcd_save:
  pcd_save_en: true     # Guarda la nube en PCD al terminar
  interval: -1          # -1 = todo en un solo archivo
```

### `g1_mapping_stack/config/pc2_to_scan.yaml`

```yaml
min_height: 0.05    # Ignora puntos por debajo de 5 cm (suelo)
max_height: 1.20    # Ignora puntos por encima de 120 cm (techo, cabeza del robot)
range_min: 0.25     # Distancia mínima de validez (25 cm)
range_max: 25.0     # Distancia máxima (25 m)
```

> Ajusta `min_height` y `max_height` según la altura a la que hayas montado el LiDAR y lo que quieras que aparezca en el mapa.

### `g1_mapping_stack/config/slam_toolbox_online.yaml`

```yaml
base_frame: pelvis     # Frame base del robot en el URDF del G1
odom_frame: odom
map_frame: map
resolution: 0.05       # 5 cm por celda del mapa
do_loop_closing: true  # Cierre de bucles activo
```

> Si usas un URDF diferente donde el frame base no se llama `pelvis`, cámbialo aquí o pásalo como argumento al launch: `base_frame:=base_link`.

---

## 9. Guardar el mapa

Cuando hayas terminado de explorar y el mapa tenga buena pinta en RViz:

```bash
# Guarda el mapa (genera .pgm + .yaml)
ros2 run g1_mapping_stack save_map.sh mi_mapa_g1
```

Esto llama a `nav2_map_server` por debajo y genera dos ficheros en el directorio actual:
- `mi_mapa_g1.pgm` — imagen en escala de grises del mapa
- `mi_mapa_g1.yaml` — metadatos (resolución, origen, umbral de ocupación)

### Guardar también la nube PCD de FAST-LIO2

FAST-LIO2 guarda automáticamente la nube 3D completa al cerrar el nodo (si `pcd_save_en: true`). Aparece en `src/fast_lio/PCD/` con nombre basado en el timestamp.

### Grabar un rosbag de la sesión

Si quieres repetir el procesado offline más tarde:

```bash
ros2 launch g1_mapping_stack record_mapping_bag.launch.py bag_name:=sesion_01
```

Graba los topics: `/livox/lidar`, `/livox/imu`, `/livox/lidar_aligned`, `/livox/imu_aligned`, `/Odometry`, `/cloud_registered`, `/scan_flat`, `/map`, `/tf`, `/tf_static`.

---

## 10. Diagnóstico y troubleshooting

### El driver del LiDAR arranca pero no llegan datos

```bash
# Comprueba que el MID360 responde
ping 192.168.123.120

# Comprueba que tu interfaz tiene la IP correcta
ip addr show enp2s0

# Mira si el driver recibe ACK del LiDAR en los logs
ros2 launch livox_ros_driver2 msg_MID360_launch.py  # lee los primeros mensajes
```

Causa más común: la `host_net_info.cmd_data_ip` en `MID360_config.json` no coincide con la IP de tu PC.

### `gravity_quaternion_estimator` no publica el cuaternión

```bash
ros2 topic echo /livox/imu --once   # ¿llega IMU del driver?
ros2 topic echo /gravity_alignment/status
```

Si no llega IMU: el driver no está corriendo o hay problema de red. Si llega pero el status nunca pone "ready": puede que `calibration_sample_count` sea muy alto o que los datos de IMU lleguen con QoS incompatible (el nodo usa `best_effort`; asegúrate de que el driver también).

### FAST-LIO2 diverge o produce odometría errática

- Comprueba que `lid_topic` e `imu_topic` apuntan a los topics alineados (`/livox/lidar_aligned`, `/livox/imu_aligned`), no a los crudos.
- Revisa los valores de `extrinsic_T` y `extrinsic_R`. Si no conoces la extrínseca exacta, deja `extrinsic_est_en: true`.
- Si el robot se mueve muy rápido, aumenta `filter_size_surf` ligeramente (p.ej. `0.3` en vez de `0.5`).

### El mapa de SLAM Toolbox aparece vacío o no crece

```bash
ros2 topic hz /scan_flat     # ¿llega LaserScan al SLAM?
ros2 topic echo /scan_flat --once  # ¿tiene ranges válidos (no todos inf)?
ros2 run tf2_ros tf2_echo map odom  # ¿existe el TF map→odom?
```

Causa más común: el TF `odom → base_link` (o `odom → pelvis`) no existe. SLAM Toolbox necesita este TF para posicionar el robot en el mapa. FAST-LIO2 publica `/Odometry` pero no el TF directamente — si lo necesitas, añade un nodo `odom_to_tf` o configura FAST-LIO2 para que lo publique.

### RViz no muestra el robot (TF errors)

```bash
ros2 topic echo /robot_description --once   # ¿está el URDF publicado?
ros2 run tf2_tools view_frames              # genera frames.pdf con el árbol TF completo
```

Si el árbol TF tiene ramas desconectadas, probablemente `joint_state_publisher` no está corriendo. Añade `use_joint_state_publisher:=true` al launch.

### Verificación rápida de que todo el pipeline está vivo

```bash
ros2 topic list | grep -E "livox|gravity|cloud|scan|map|Odom"
```

Deberías ver al menos:
```
/livox/lidar
/livox/imu
/livox/lidar_aligned
/livox/imu_aligned
/gravity_alignment/quaternion
/Odometry
/cloud_registered
/scan_flat
/map
```

---

## 11. Preguntas frecuentes

**¿Por qué hay un nodo de "gravity split" en vez de poner directamente la extrínseca en FAST-LIO2?**

La extrínseca en FAST-LIO2 es fija. El G1 es un robot bípedo que varía ligeramente su inclinación según la marcha, el terreno y el estado de los controladores. El nodo de gravedad estima la corrección en tiempo real al arrancar, adaptándose a la postura real del momento.

**¿Puedo usar el stack sin el G1 físico, en simulación?**

Sí. Si tienes ROS 2 publicando `/livox/lidar` y `/livox/imu` con los tipos correctos (desde un simulador o un rosbag), puedes saltar el driver de Livox y arrancar directamente desde el paso 2a. Para usar datos de un bag: `ros2 bag play mi_bag --clock` y añade `use_sim_time:=true` a todos los launches.

**¿El MID360 del G1 usa el mismo protocolo que el MID360 standalone?**

Sí, es el mismo hardware y el mismo driver. La única diferencia es que en el G1 EDU la IP del LiDAR es `192.168.123.120` (dentro de la subred del robot) en vez de la IP de fábrica `192.168.1.12`.

**¿Puedo usar otro LiDAR en vez del MID360?**

FAST-LIO2 soporta Velodyne, Ouster y cualquier `PointCloud2` genérico. Cambia `lidar_type` en `mid360.yaml` (2=Velodyne, 3=Ouster, 4=genérico) y usa el config correspondiente. El nodo de gravity split solo funciona con el `CustomMsg` de Livox; para otros LiDARs habría que adaptarlo.

**¿Cómo ajusto la huella del robot para Nav2?**

Eso ya no es responsabilidad de este stack: este stack termina generando un mapa. Para navegación autónoma, carga el mapa con `nav2_map_server` y configura Nav2 con la huella (`footprint`) de tu G1 — tipicamente un polígono rectangular de unos 0.4 × 0.3 m.

---

## Licencias

- `fast_lio`: GPL-2.0 (ver `src/fast_lio/LICENSE`)
- `livox_ros_driver2`: Apache 2.0 (ver `src/livox_ros_driver2/LICENSE.txt`)
- `g1_livox_gravity_split`, `g1_mapping_stack`: ver licencias individuales de cada paquete

---

*Documentación generada para el TFG de navegación autónoma del Unitree G1 — ROS 2 Humble.*
