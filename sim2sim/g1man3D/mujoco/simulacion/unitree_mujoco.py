import math
import struct
import time
import threading
from threading import Thread

import cv2
import mujoco
import mujoco.viewer
import numpy as np
import zmq

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py_bridge import UnitreeSdk2Bridge, ElasticBand

# ── mujoco-lidar (https://github.com/discoverse-dev/MuJoCo-LiDAR) ──────────
from mujoco_lidar import MjLidarWrapper, scan_gen
# ───────────────────────────────────────────────────────────────────────────

import config


locker = threading.Lock()

mj_model = mujoco.MjModel.from_xml_path(config.ROBOT_SCENE)
mj_data  = mujoco.MjData(mj_model)

# === DEBUG ===
import os as _os
_abs_scene = _os.path.abspath(config.ROBOT_SCENE)
print(f"\n{'='*60}")
print(f"[DEBUG] CWD:           {_os.getcwd()}")
print(f"[DEBUG] ROBOT_SCENE:   {config.ROBOT_SCENE}")
print(f"[DEBUG] Ruta absoluta: {_abs_scene}")
print(f"[DEBUG] ¿Existe?:      {_os.path.exists(_abs_scene)}")
_lid_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_SITE, "lidar_site")
if _lid_id >= 0:
    print(f"[DEBUG] lidar_site pos en modelo: {mj_model.site_pos[_lid_id]}")
else:
    print(f"[DEBUG] lidar_site NO ENCONTRADO en el modelo")
print(f"{'='*60}\n")

ZMQ_LIDAR_MAGIC  = 0xDEAD1337
RGB_WIDTH        = 640
RGB_HEIGHT       = 480
CAMERA_NAME      = "realsense"
PELVIS_BODY_NAME = "pelvis"

# =====================================================================
# CONFIGURACIÓN DEL LIDAR 3D  (mujoco-lidar)
# =====================================================================
LIDAR_SITE_NAME  = "lidar_site"
LIDAR_PUBLISH_HZ = 10.0
LIDAR_MAX_RANGE  = 12.0
LIDAR_MIN_RANGE  = 0.15

# Patrón de escaneo: grid uniforme 360 az × 16 elev, ±15° elevación.
# → 5760 rayos/frame.  Sube LIDAR_N_ROWS a 32 para más densidad (11520 r).
LIDAR_N_COLS   = 360
LIDAR_N_ROWS   = 16
LIDAR_ELEV_MIN = math.radians(-15.0)
LIDAR_ELEV_MAX = math.radians( 15.0)

# Grupos de geometría a detectar (tus paredes están en group 3)
LIDAR_GEOMGROUP = np.array([0, 0, 0, 1, 0, 0], dtype=np.uint8)
# =====================================================================


# ── Cámara 3ª persona ────────────────────────────────────────────────────────
_thirdperson_enabled = [False]

def _key_callback(key):
    if key == 67:  # tecla C
        _thirdperson_enabled[0] = not _thirdperson_enabled[0]
        state = "ON (camara 3a persona)" if _thirdperson_enabled[0] else "OFF (camara libre)"
        print(f"\n[CAM] Tercera persona: {state}")
    if config.ENABLE_ELASTIC_BAND:
        elastic_band.MujuocoKeyCallback(key)

if config.ENABLE_ELASTIC_BAND:
    elastic_band = ElasticBand()
    if config.ROBOT in ("h1", "g1"):
        band_attached_link = mj_model.body("torso_link").id
    else:
        band_attached_link = mj_model.body("base_link").id

viewer = mujoco.viewer.launch_passive(mj_model, mj_data, key_callback=_key_callback)

mj_model.opt.timestep = config.SIMULATE_DT
num_motor_        = mj_model.nu
dim_motor_sensor_ = 3 * num_motor_

time.sleep(0.2)


# =====================================================================
# Utilidades de pose (sin cambios)
# =====================================================================
def _mat9_to_quat_wxyz(mat9):
    mat9 = np.asarray(mat9, dtype=np.float64).reshape(-1)
    quat = np.zeros(4, dtype=np.float64)
    mujoco.mju_mat2Quat(quat, mat9)
    return quat

def _pose_from_body(body_name):
    body_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if body_id < 0:
        raise RuntimeError(f"No existe el body '{body_name}'")
    return np.concatenate([
        np.asarray(mj_data.xpos[body_id], dtype=np.float64),
        _mat9_to_quat_wxyz(mj_data.xmat[body_id]),
    ])

def _pose_from_site(site_name):
    site_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_SITE, site_name)
    if site_id < 0:
        raise RuntimeError(f"No existe el site '{site_name}'")
    return np.concatenate([
        np.asarray(mj_data.site_xpos[site_id], dtype=np.float64),
        _mat9_to_quat_wxyz(mj_data.site_xmat[site_id]),
    ])


# =====================================================================
# Inicialización del LiDAR 3D usando mujoco-lidar
# =====================================================================

# Pre-calcular el patrón de rayos una vez (no cambia entre frames)
_theta_rays, _phi_rays = scan_gen.generate_grid_scan_pattern(
    num_ray_cols = LIDAR_N_COLS,
    num_ray_rows = LIDAR_N_ROWS,
    phi_range    = (LIDAR_ELEV_MIN, LIDAR_ELEV_MAX),
)

_pelvis_body_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_BODY, PELVIS_BODY_NAME)

# Crear el wrapper de mujoco-lidar con backend CPU
# (instalar taichi para usar backend GPU: pip install mujoco-lidar[taichi])
_lidar = MjLidarWrapper(
    mj_model,
    site_name   = LIDAR_SITE_NAME,
    backend     = "cpu",
    cutoff_dist = LIDAR_MAX_RANGE,
    args        = {
        "bodyexclude": _pelvis_body_id,   # evita auto-detección del robot
        "geomgroup":   LIDAR_GEOMGROUP,   # solo detecta paredes (group 3)
    },
)

_lidar_site_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_SITE, LIDAR_SITE_NAME)
if _lidar_site_id < 0:
    raise RuntimeError(f"Site '{LIDAR_SITE_NAME}' no encontrado en el modelo XML.")

n_rays = len(_theta_rays)
print(f"\n[LIDAR 3D] mujoco-lidar / backend CPU")
print(f"[LIDAR 3D] Patron: {LIDAR_N_COLS} az x {LIDAR_N_ROWS} elev = {n_rays} rayos/frame")
print(f"[LIDAR 3D] Elevacion: {math.degrees(LIDAR_ELEV_MIN):.0f}° a {math.degrees(LIDAR_ELEV_MAX):.0f}°")
print(f"[LIDAR 3D] Rango: {LIDAR_MIN_RANGE}–{LIDAR_MAX_RANGE} m @ {LIDAR_PUBLISH_HZ} Hz\n")


# =====================================================================
# Raycast 3D — usando la API de mujoco-lidar
# =====================================================================
def _raycast_3d(model, data):
    """
    Traza los rayos del LiDAR 3D usando mujoco-lidar.

    Flujo:
      1. _lidar.trace_rays()   → dispara los rayos, devuelve distancias (N,)
      2. _lidar.get_hit_points() → devuelve puntos XYZ en frame lidar_link (N,3)
      3. Filtramos por rango mínimo (hit_points de puntos inválidos = cutoff)

    Retorna (pts_local, lidar_pose, pelvis_pose).
    """
    # 1. Trazar rayos (actualiza internamente la pose del sensor desde mj_data)
    distances = _lidar.trace_rays(data, _theta_rays, _phi_rays)

    # 2. Obtener puntos XYZ en frame local del lidar_site
    #    get_hit_points() devuelve (N, 3) float32
    all_pts = _lidar.get_hit_points()

    # 3. Filtrar: descartar rayos que no impactaron (distancia == cutoff_dist)
    #    y los que están por debajo del rango mínimo
    valid = (distances >= LIDAR_MIN_RANGE) & (distances < LIDAR_MAX_RANGE)
    pts   = all_pts[valid].astype(np.float32)

    lidar_pose  = _pose_from_site(LIDAR_SITE_NAME)
    pelvis_pose = _pose_from_body(PELVIS_BODY_NAME)

    return pts, lidar_pose, pelvis_pose


# =====================================================================
# Protocolo ZMQ — idéntico al original, el bridge no cambia
# =====================================================================
def _pack_lidar_message(pelvis_pose, lidar_pose, pts):
    pts         = np.ascontiguousarray(pts,         dtype=np.float32)
    pelvis_pose = np.ascontiguousarray(pelvis_pose, dtype=np.float64)
    lidar_pose  = np.ascontiguousarray(lidar_pose,  dtype=np.float64)
    return b"".join([
        struct.pack("=II", ZMQ_LIDAR_MAGIC, int(len(pts))),
        pelvis_pose.tobytes(),
        lidar_pose.tobytes(),
        struct.pack("=d", time.time()),
        pts.tobytes(),
    ])


# =====================================================================
# Threads (sin cambios salvo LidarThread)
# =====================================================================
def ResetServerThread():
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 6005))
    sock.settimeout(0.5)
    print("[INFO] Servidor de Teletransporte activo en puerto 6005")
    while viewer.is_running():
        try:
            data, _ = sock.recvfrom(1024)
            if data == b"reset":
                print("\n[INFO] Teletransportando G1...")
                with locker:
                    mj_data.qpos[2]   = 0.793
                    mj_data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
                    mj_data.qpos[7:]  = 0.0
                    mj_data.qvel[:]   = 0.0
                    mujoco.mj_forward(mj_model, mj_data)
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[ERROR] Teletransporte: {e}")


def SimulationThread():
    global mj_data, mj_model
    ChannelFactoryInitialize(config.DOMAIN_ID, config.INTERFACE)
    unitree = UnitreeSdk2Bridge(mj_model, mj_data)
    if config.USE_JOYSTICK:
        unitree.SetupJoystick(device_id=0, js_type=config.JOYSTICK_TYPE)
    if config.PRINT_SCENE_INFORMATION:
        unitree.PrintSceneInformation()
    while viewer.is_running():
        step_start = time.perf_counter()
        locker.acquire()
        if config.ENABLE_ELASTIC_BAND and elastic_band.enable:
            mj_data.xfrc_applied[band_attached_link, :3] = elastic_band.Advance(
                mj_data.qpos[:3], mj_data.qvel[:3])
        mujoco.mj_step(mj_model, mj_data)
        locker.release()
        remaining = mj_model.opt.timestep - (time.perf_counter() - step_start)
        if remaining > 0:
            time.sleep(remaining)


def PhysicsViewerThread():
    CAM_DISTANCE  = 3.5
    CAM_ELEVATION = -20.0
    CAM_HEIGHT    = 0.3
    CAM_SMOOTHING = 0.08
    pelvis_id     = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_BODY, PELVIS_BODY_NAME)
    smooth_az     = [None]
    while viewer.is_running():
        locker.acquire()
        try:
            if _thirdperson_enabled[0]:
                px, py, pz    = mj_data.xpos[pelvis_id]
                xmat          = mj_data.xmat[pelvis_id].reshape(3, 3)
                robot_yaw_rad = np.arctan2(xmat[1, 0], xmat[0, 0])
                target_az     = np.degrees(
                    np.arctan2(-np.cos(robot_yaw_rad), np.sin(robot_yaw_rad))) + 90.0
                if smooth_az[0] is None:
                    smooth_az[0] = target_az
                diff         = (target_az - smooth_az[0] + 180.0) % 360.0 - 180.0
                smooth_az[0] = (smooth_az[0] + diff * CAM_SMOOTHING) % 360.0
                viewer.cam.lookat[0] = px
                viewer.cam.lookat[1] = py
                viewer.cam.lookat[2] = pz + CAM_HEIGHT
                viewer.cam.distance  = CAM_DISTANCE
                viewer.cam.elevation = CAM_ELEVATION
                viewer.cam.azimuth   = smooth_az[0]
            else:
                smooth_az[0] = None
        except Exception:
            pass
        viewer.sync()
        locker.release()
        time.sleep(config.VIEWER_DT)


def RGBServerThread():
    context    = zmq.Context()
    socket_rgb = context.socket(zmq.PUB)
    socket_rgb.bind("tcp://*:5555")
    renderer_rgb = mujoco.Renderer(mj_model, height=RGB_HEIGHT, width=RGB_WIDTH)
    _scene_opt   = mujoco.MjvOption()
    _scene_opt.geomgroup[:] = 1
    print("[INFO] Servidor RGB en puerto 5555")
    while viewer.is_running():
        try:
            with locker:
                renderer_rgb.update_scene(mj_data, camera=CAMERA_NAME,
                                          scene_option=_scene_opt)
                pixels_rgb = renderer_rgb.render()
            bgr_frame     = cv2.cvtColor(pixels_rgb, cv2.COLOR_RGB2BGR)
            _, rgb_buffer = cv2.imencode('.jpg', bgr_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            socket_rgb.send(rgb_buffer.tobytes())
        except Exception as e:
            print(f"[WARN] RGB thread: {e}")
        time.sleep(1.0 / 30.0)


def LidarThread():
    """
    LiDAR 3D usando mujoco-lidar (https://github.com/discoverse-dev/MuJoCo-LiDAR).
    Backend CPU: 360 x 16 = 5760 rayos/frame a 10 Hz.
    El protocolo ZMQ de salida es idéntico al LiDAR 2D original:
    el bridge ROS 2 recibe la nube y genera /scan y /lidar/points sin cambios.
    """
    context      = zmq.Context()
    socket_lidar = context.socket(zmq.PUB)
    socket_lidar.bind("tcp://*:5556")
    publish_period = 1.0 / LIDAR_PUBLISH_HZ

    print(f"[INFO] LiDAR 3D (mujoco-lidar) activo en puerto 5556")
    print(f"       {n_rays} rayos/frame @ {LIDAR_PUBLISH_HZ} Hz")

    while viewer.is_running():
        t0 = time.perf_counter()
        try:
            with locker:
                pts, lidar_pose, pelvis_pose = _raycast_3d(mj_model, mj_data)
            payload = _pack_lidar_message(pelvis_pose, lidar_pose, pts)
            socket_lidar.send(payload)

            elapsed = time.perf_counter() - t0
            if elapsed > publish_period * 0.8:
                print(f"[WARN] LiDAR lento: {elapsed*1000:.1f} ms "
                      f"(budget {publish_period*1000:.0f} ms) — "
                      f"reduce LIDAR_N_ROWS si persiste")
        except Exception as e:
            print(f"[WARN] LiDAR thread: {e}")

        sleep_time = publish_period - (time.perf_counter() - t0)
        if sleep_time > 0:
            time.sleep(sleep_time)


if __name__ == "__main__":
    viewer_thread = Thread(target=PhysicsViewerThread)
    sim_thread    = Thread(target=SimulationThread)
    rgb_thread    = Thread(target=RGBServerThread);  rgb_thread.daemon  = True
    lidar_thread  = Thread(target=LidarThread);       lidar_thread.daemon = True
    reset_thread  = Thread(target=ResetServerThread); reset_thread.daemon = True

    viewer_thread.start()
    sim_thread.start()
    rgb_thread.start()
    lidar_thread.start()
    reset_thread.start()

    print("\n[INFO] Todos los hilos arrancados.")
    print("[INFO] Pulsa '3' en el visor para ver/ocultar muros (group 3)")
    print("[INFO] Pulsa C para activar/desactivar camara 3a persona")
