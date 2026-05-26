# EasyNavigation (EasyNav) para el G1 en MuJoCo — vía Docker

Esta carpeta contiene la integración de **EasyNavigation** como alternativa a Nav2 para la navegación autónoma del robot G1 en simulación. EasyNav es un framework de navegación del Intelligent Robotics Lab de la URJC, pensado como alternativa modular, representation-agnostic y con despliegue de binario único.

📦 Proyecto oficial: [github.com/EasyNavigation](https://github.com/EasyNavigation)
📚 Documentación: [easynavigation.github.io](https://easynavigation.github.io)

---

## ¿Por qué Docker?

EasyNav soporta oficialmente **Ubuntu 24.04 + ROS 2 Jazzy / Kilted / Rolling**. Este proyecto usa **Ubuntu 22.04 + ROS 2 Humble**. Para evitar romper el stack existente (MuJoCo, unitree_sdk2py, ONNX runtime, policy de locomoción), EasyNav corre **dentro de un contenedor Docker** basado en Jazzy, mientras todo lo demás sigue en el host.

El contenedor y el host se comunican vía **DDS sobre la red**, gracias a `--network=host` al arrancar Docker. Esto significa que los topics ROS 2 publicados en el host (`/scan`, `/odom`, `/tf`) son visibles desde dentro del contenedor sin ninguna configuración adicional, y el `/cmd_vel` que publica EasyNav dentro del contenedor es visible desde el host.

---

## Estructura de la carpeta

```
EasyNav/
├── README.md                          ← este archivo
├── cmd_vel_bridge.py                  ← puente /cmd_vel → TCP:6000 (corre en el HOST)
├── config/
│   └── easynav_params.yaml            ← parámetros del SimpleStack para el G1
├── launch/
│   └── g1_easynav.launch.py           ← lanza system_main con el yaml + mapa
├── rviz2/
│   └── g1_easynav.rviz                ← config de RViz2 para navegar con EasyNav
└── docker/
    ├── Dockerfile                     ← imagen basada en ros:jazzy-ros-base
    ├── build_easynav_docker.sh        ← construye la imagen
    └── run_easynav_docker.sh          ← arranca el contenedor con --network=host
```

**Qué corre dónde:**

| Componente | Sitio | Por qué |
|---|---|---|
| MuJoCo + policy (`run_sim_ai_g1.py`) | Host | Tiene todas las dependencias (onnxruntime, unitree_sdk2py) |
| Bridge MuJoCo → ROS 2 | Host | Lee ZMQ del simulador en `localhost:5556` |
| Mapper (opcional) | Host | Necesita `/scan` y `/odom` del host |
| **EasyNav (`system_main`)** | **Contenedor Docker** | Necesita Jazzy |
| `cmd_vel_bridge.py` | Host | Abre socket TCP a `localhost:6000` de `run_sim_ai_g1.py` |
| RViz2 | Host | El que ya usas, reutiliza `g1_navigation.rviz` o `g1_easynav.rviz` |

El truco clave es que `cmd_vel_bridge.py` suscribe `/cmd_vel` por ROS 2 DDS (da igual quién lo publique: Nav2, EasyNav dentro del contenedor, o cualquier otro nodo) y lo reenvía por TCP al puerto 6000 del host, donde `run_sim_ai_g1.py` ya escucha. Así no hay que tocar nada del simulador.

---

## Instalación (una vez)

### Requisitos previos en el host

```bash
# Docker Engine
sudo apt install docker.io
sudo usermod -aG docker $USER
# (cierra sesión y vuelve a entrar para que el grupo docker tenga efecto)

# CycloneDDS en el host (recomendado para que cuadre con el contenedor)
sudo apt install ros-humble-rmw-cyclonedds-cpp
```

Añade a tu `~/.bashrc`:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0
```

Y vuelve a abrir la terminal (o `source ~/.bashrc`).

### Construir la imagen

```bash
cd g1man/EasyNav
chmod +x docker/build_easynav_docker.sh docker/run_easynav_docker.sh
./docker/build_easynav_docker.sh
```

Esto tarda **10-15 minutos la primera vez**: descarga la imagen base de Jazzy, clona los repos de EasyNav, resuelve dependencias y compila el workspace con colcon. Las siguientes veces Docker cachea las capas y es casi instantáneo.

Si algo falla durante la compilación dentro del Dockerfile (suele ser algún repo de EasyNav que ha cambiado API respecto a cuando escribí esto), el log te dirá qué paquete ha fallado. En ese caso avísame con el error concreto y lo ajustamos.

---

## Uso diario (fase B — navegar con un mapa ya hecho)

Necesitas **5 terminales en el host** y el contenedor Docker aparte (que cuenta como una sexta "terminal" efectiva pero se arranca con un script).

### Terminal 1 — Simulador + policy

```bash
cd g1man/mujoco && python3 run_sim_ai_g1.py
```

### Terminal 2 — Bridge MuJoCo → ROS 2

```bash
source /opt/ros/humble/setup.bash
cd g1man/mujoco && python3 mujoco_ros2_lidar_bridge.py
```

### Terminal 3 — Puente cmd_vel → TCP (en el HOST)

```bash
source /opt/ros/humble/setup.bash
cd g1man/EasyNav && python3 cmd_vel_bridge.py
```

Este paso es **crítico**: sin él, EasyNav publicará `/cmd_vel` dentro del contenedor, el host lo recibirá, pero nadie lo traducirá a la tecla TCP que entiende `run_sim_ai_g1.py`, y el robot no se moverá.

### Terminal 4 — EasyNav en Docker

```bash
cd g1man/EasyNav

# Opción A — lanza directo con el mapa más reciente
./docker/run_easynav_docker.sh launch

# Opción B — lanza con un mapa específico (ruta dentro del contenedor:
# /g1_maps/ está montado desde g1man/mujoco/maps/ del host)
./docker/run_easynav_docker.sh launch /g1_maps/maze_map_20260406_200946.yaml

# Opción C — shell interactiva en el contenedor para depurar
./docker/run_easynav_docker.sh
# ... y dentro del contenedor:
ros2 launch /g1_easynav/launch/g1_easynav.launch.py
```

### Terminal 5 — RViz2 (en el host)

```bash
source /opt/ros/humble/setup.bash
cd g1man && rviz2 -d EasyNav/rviz2/g1_easynav.rviz
```

El RViz del host ve perfectamente los topics publicados por EasyNav dentro del contenedor (mismo dominio DDS, misma red, mismo middleware).

### Enviar un goal

En RViz2, botón **"2D Goal Pose"** (arriba en la barra de herramientas), clic donde quieras que vaya el robot arrastrando para fijar la orientación final. EasyNav lo publica en `/goal_pose`, el planner simple calcula la ruta, el Serest controller genera los Twist, el `cmd_vel_bridge.py` los traduce a teclas, y el robot camina.

---

## Configuración DDS — lo importante

Para que host y contenedor se vean, **tres cosas tienen que coincidir**:

1. **`RMW_IMPLEMENTATION`** — misma implementación en ambos lados. Por defecto forzamos `rmw_cyclonedds_cpp` porque es el más estable cross-versión. Si en el host usas FastDDS, cámbialo también dentro del `run_easynav_docker.sh`.

2. **`ROS_DOMAIN_ID`** — mismo número en ambos lados. Por defecto 0. Si tienes varios proyectos ROS conviviendo en la misma máquina, usa IDs distintos para evitar colisiones.

3. **`--network=host`** — que le pasamos automáticamente al `docker run`. Sin esto, el contenedor tendría su propia red aislada y el discovery DDS no vería el host.

Puedes verificar que todo funciona desde el host con:

```bash
ros2 topic list
# Deberías ver /scan, /odom, /tf, /cmd_vel (este último si EasyNav está corriendo)

ros2 topic echo /cmd_vel
# Cuando envíes un goal en RViz, deberías ver Twist mensajes fluyendo.
```

---

## Los parámetros del G1 (config/easynav_params.yaml)

El archivo configura el **SimpleStack** de EasyNav, que es el más ligero y el que mejor encaja con lo que ya tienes (mapa PGM+YAML binario generado por tu mapper casero). Los cinco bloques son:

- **`controller_node` — SerestController.** El controller de trayectoria de EasyNav. Es similar en espíritu a DWB pero más simple: sigue directamente la ruta del planner con ganancias proporcionales (`k_theta`, `k_y`). Límites de velocidad ajustados al G1: `max_linear_speed: 0.6 m/s`, `max_angular_speed: 0.8 rad/s` (los mismos que pusimos en el DWB de Nav2).

- **`localizer_node` — AMCLLocalizer.** Localización Monte Carlo con 200 partículas. Asume pose inicial en (0, 0, 0), igual que el AMCL de Nav2.

- **`maps_manager_node` — SimpleMapsManager.** Carga un mapa binario PGM+YAML. La ruta `map_path_file` se sobreescribe desde el launch file según el argumento `map:=`.

- **`planner_node` — SimplePlanner.** Planner A*-ish sobre mapa binario. `robot_radius: 0.30 m` igual que Nav2.

- **`sensors_node`.** Configura el LiDAR. El topic es `scan` (sin `/`, como espera EasyNav), que es lo que publica el bridge del host.

---

## ¿Y si quiero volver a Nav2?

Los dos stacks (Nav2 y EasyNav) son **completamente intercambiables** porque comparten todo el resto del sistema:

- Mismo bridge MuJoCo → ROS 2.
- Mismo `cmd_vel_bridge.py` (lo hicimos genérico).
- Mismos topics de entrada (`/scan`, `/odom`, `/tf`).
- Mismos mapas PGM+YAML.
- Mismo RViz (con la salvedad de que los topics de costmaps solo existen en Nav2).

Solo cambia qué arrancas en la terminal del navegador: `ros2 launch g1_nav2.launch.py` (Nav2, host) o `./docker/run_easynav_docker.sh launch` (EasyNav, contenedor).

---

## Estado actual de la integración (abril 2026)

> **TL;DR — Toda la infraestructura de EasyNav está lista, compila perfectamente, y arranca el binario `system_main` correctamente, pero hay un bug interno del framework que mata el proceso al activarse. La navegación con EasyNav no es funcional ahora mismo. Nav2 sigue siendo el navegador operativo del proyecto.**

### Lo que SÍ funciona

- **Construcción de la imagen Docker**: el `Dockerfile` clona los 4 repos de EasyNav (rama `jazzy`), resuelve dependencias con `rosdep`, y compila los **39 paquetes** del workspace con `colcon build` sin errores. Solo aparecen warnings de CMake relacionados con PCL (`CMP0144`), que son ruido inofensivo.
- **Arranque del contenedor**: el script `run_easynav_docker.sh` levanta el contenedor con `--network=host` y configuración DDS correcta. ROS 2 dentro del contenedor ve perfectamente los topics publicados en el host (`/scan`, `/odom`, `/tf`).
- **Lanzamiento de `system_main`**: el binario se ejecuta, lee el archivo de parámetros `easynav_params.yaml`, reconoce todos los plugins (`SimpleMapsManager`, `AMCLLocalizer`, `SimplePlanner`, `SerestController`, `LaserScan` sensor), y llega hasta la fase de **`Activating [easynav_system]`**.

### El problema: 

Justo después de activarse, el proceso muere con este error:

```
[easynav_system]: Activating [easynav_system]
[easynav_system]: Selected Real-Time
terminate called after throwing an instance of 'std::runtime_error'
  what():  can't compare times with different time sources
process has died [exit code -6]
```

**¿Qué significa esto?** En ROS 2 hay tres tipos de relojes: el del sistema operativo, el monotónico, y el "ROS time" (que se sincroniza con el topic `/clock` cuando hay simulación). Estos relojes no se pueden comparar entre sí — es como restar metros y kilos. Si dos partes del programa usan tipos distintos y luego intentan compararlos, ROS lanza una excepción y el proceso muere.

En el caso de EasyNav, **algún componente interno** del binario `system_main` está construyendo su propio reloj con un tipo distinto al que tiene el resto del nodo, y al activarse intenta comparar ambos. Esto pasa **incluso sin nadie publicando datos** desde el host (lo verificamos cerrando el simulador, el bridge y todos los procesos del lado Humble) y **incluso sin sensores configurados** en el YAML (lo verificamos vaciando `sensors_node.sensors: []`).

### Por qué no es problema de configuración

Hicie cuatro pruebas para descartar que fuera un fallo en el YAML:

1. **`use_sim_time: false` en todos los bloques del YAML** → crashea igual.
2. **`use_sim_time: false` forzado adicionalmente desde el launch file** → crashea igual.
3. **Lanzando EasyNav sin nada del host corriendo** → crashea igual (ningún `/scan`, ningún `/odom`, ningún `/tf` desde el bridge).
4. **Lanzando EasyNav con `sensors_node.sensors: []` vacío** → crashea igual.

Las cuatro pruebas dan exactamente el mismo error en exactamente el mismo momento (entre `Activating` y la línea siguiente). Eso confirma que el bug **no está en la configuración** ni en la mezcla de relojes con el bridge del host. Está en código C++ compilado de algún plugin del core de EasyNav, en la rama `jazzy` que clonamos.

### Por qué publicar `/clock` no resolvería el problema.

Una solución natural sería: hacer que el bridge `mujoco_ros2_lidar_bridge.py` publique también el topic `/clock` con el tiempo simulado de MuJoCo, y poner `use_sim_time: true` en el YAML de EasyNav. Así todos los nodos vivirían en el mismo tiempo (el del simulador) y no habría mezcla de relojes.

Pero esto **solo funcionaría si el bug viniera de mezclar el reloj del host con el reloj de EasyNav**. Como demostramos con la prueba 3 (cerrando todo el host y lanzando EasyNav solo), el crash ocurre de todas formas, lo que significa que el problema no es el reloj externo del bridge, sino dos relojes **internos** del propio binario `system_main`. Publicar `/clock` desde el host no cambia nada en ese escenario, y además rompería el sistema actual con Nav2 (que está configurado para reloj de sistema).

### Lo que esto significa para el proyecto

Toda la infraestructura de EasyNav queda lista en esta carpeta para el día en que el bug se arregle. Cuando eso pase, bastará con hacer `git pull` dentro del contenedor (o reconstruir la imagen Docker para que clone la versión nueva), y el sistema funcionará sin tocar ningún archivo de los que están aquí. Los params del G1, el launch file, el RViz config, el `cmd_vel_bridge.py` — todo está adaptado y listo.

Mientras tanto, **el navegador operativo del proyecto sigue siendo Nav2**, que funciona perfectamente y cubre todos los requisitos de navegación autónoma del G1 en el laberinto.

---

