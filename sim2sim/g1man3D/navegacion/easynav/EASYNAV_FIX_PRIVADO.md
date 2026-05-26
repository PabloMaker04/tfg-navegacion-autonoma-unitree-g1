# EasyNav — Diagnóstico y fix del bug "can't compare times with different time sources"

> ⚠️  Esta guía es de uso privado. No subir a GitHub ni compartir.

---

## El problema exacto

El crash ocurre durante `Activating [easynav_system]`.
El mensaje es: `std::runtime_error: can't compare times with different time sources`

En ROS 2 / rclcpp, los timestamps tienen un "time source" (RCL_ROS_TIME o RCL_SYSTEM_TIME).
Si mezclas un `rclcpp::Time` de un reloj de sistema con uno de un reloj ROS, la comparación
lanza esa excepción. Esto suele pasar cuando:

1. Un `tf2_ros::Buffer` se construye con un `rclcpp::Clock` distinto al del nodo padre.
2. Un componente interno usa `rclcpp::Clock(RCL_ROS_TIME)` en lugar de `node->get_clock()`.
3. Un timer usa `node->get_clock()` pero el dato que procesa tiene timestamp de `rclcpp::Clock(RCL_SYSTEM_TIME)`.

---

## Dónde mirar en el código de EasyNav

El crash pasa en `easynav_system/src/system_main.cpp` o en uno de los nodos que activa.
La activación llama a `on_activate()` en cada nodo del stack. El orden típico es:
sensors_node → localizer_node → maps_manager_node → planner_node → controller_node

Como el crash pasa **incluso con sensors vacíos**, el problema está en la inicialización
del buffer de TF2 o de un timer en `localizer_node` o `controller_node`.

### Paso 1: localizar el stack trace completo

Ejecuta con `-d gdb`:

```bash
# Dentro del contenedor
ros2 run --prefix 'gdb -ex run --args' easynav_system system_main \
    --ros-args --params-file /g1_easynav/config/easynav_params.yaml
```

Cuando pete, en el prompt de gdb:
```
(gdb) bt
```

Copia el backtrace completo. Busca la línea que menciona `tf2_ros::Buffer` o
`rclcpp::Time::operator<` o similar.

### Paso 2: el sospechoso principal — tf2_ros::Buffer

Busca en el código fuente de EasyNav los `tf2_ros::Buffer` construidos así:

```bash
# Dentro del contenedor, con el source de EasyNav en /workspace/src
grep -rn "tf2_ros::Buffer" /workspace/src/
```

Un `Buffer` **correcto** se construye pasando el reloj del nodo:
```cpp
// CORRECTO
tf_buffer_ = std::make_shared<tf2_ros::Buffer>(this->get_clock());
```

Un `Buffer` **incorrecto** se construye sin reloj o con un reloj nuevo:
```cpp
// INCORRECTO — crea un reloj RCL_ROS_TIME independiente
tf_buffer_ = std::make_shared<tf2_ros::Buffer>(std::make_shared<rclcpp::Clock>());
// TAMBIÉN INCORRECTO
tf_buffer_ = std::make_shared<tf2_ros::Buffer>();
```

Si encuentras alguna de las formas incorrectas, cámbiala a `this->get_clock()`.

### Paso 3: timers y comparaciones de tiempo internas

Busca construcciones de `rclcpp::Clock` que no pasen por el nodo:

```bash
grep -rn "rclcpp::Clock(" /workspace/src/EasyNavigation/
grep -rn "rclcpp::Clock(" /workspace/src/easynav_plugins/
```

Cualquier `rclcpp::Clock(RCL_ROS_TIME)` o `rclcpp::Clock()` suelto (sin `use_sim_time`)
puede ser el culpable. Cámbialo por `node->get_clock()` o `this->get_clock()`.

### Paso 4: el SerestController y sus timers RT

El crash menciona "Selected Real-Time" justo antes de morir. El SerestController
configura un timer de tiempo real. Busca en `easynav_plugins`:

```bash
find /workspace/src -name "*.cpp" | xargs grep -l "SerestController\|serest"
```

Dentro de ese archivo, busca donde se crea el timer RT y qué reloj usa para
los timestamps. Si usa `rclcpp::Clock(RCL_SYSTEM_TIME)` y el nodo padre
corre con `use_sim_time: false` (que usa `RCL_SYSTEM_TIME`), en teoría deberían
ser compatibles. PERO si en algún punto se compara ese timestamp con uno
obtenido de `node->get_clock()` que internamente devuelve `RCL_ROS_TIME`
(porque `use_sim_time` fue `true` en algún momento del ciclo de vida), peta.

### Paso 5: el fix más probable

En el contenedor, con el workspace montado en `/workspace`:

```bash
# Buscar todos los Buffer construidos incorrectamente
grep -rn "tf2_ros::Buffer" /workspace/src/ | grep -v "get_clock()"
```

Para cada ocurrencia encontrada, editar el .cpp correspondiente:

```cpp
// Antes (ejemplo):
tf_buffer_ = std::make_shared<tf2_ros::Buffer>(
    std::make_shared<rclcpp::Clock>(RCL_ROS_TIME));

// Después:
tf_buffer_ = std::make_shared<tf2_ros::Buffer>(this->get_clock());
```

Después recompilar solo los paquetes afectados:

```bash
cd /workspace
colcon build --packages-select easynav_system easynav_plugins \
    --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
source install/setup.bash
ros2 run easynav_system system_main \
    --ros-args --params-file /g1_easynav/config/easynav_params.yaml
```

---

## Fix alternativo sin tocar C++ (workaround)

Si no quieres recompilar, prueba forzar `use_sim_time: true` en TODOS los nodos
del YAML y publicar un `/clock` fake desde el host:

```bash
# En el host (Humble):
ros2 topic pub /clock rosgraph_msgs/msg/Clock \
    "{clock: {sec: 0, nanosec: 0}}" --rate 100 &
```

Esto fuerza a todos los relojes a usar `RCL_ROS_TIME` con el mismo origen,
eliminando la mezcla. No es la solución correcta pero puede servir para
verificar que el resto del stack funciona mientras encuentras el fix real.

---

## Resumen de archivos a auditar

| Archivo (buscar en /workspace/src) | Qué buscar |
|---|---|
| `EasyNavigation/src/*/node.cpp` | `tf2_ros::Buffer(` sin `get_clock()` |
| `easynav_plugins/serest_controller/*.cpp` | `rclcpp::Clock(` suelto, timers RT |
| `easynav_plugins/amcl_localizer/*.cpp` | `tf2_ros::Buffer(`, comparaciones de Time |
| `easynav_plugins/simple_maps_manager/*.cpp` | `rclcpp::Clock(`, timestamps de mapa |
